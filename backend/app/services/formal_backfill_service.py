"""临时需求：把现有 prod 账号按 4/1→今天的曲线重新分配「转正日期」，
用于绘制正式号增长趋势图，并最终导出 open_api_task_id 列表喂给上游 Open API。

只考虑 openapi 那侧的发布（`video_publications.open_api_task_id IS NOT NULL`），
ext_pub-only 的发布忽略。

算法概述：
1. 拉取所有 account_tier='prod' 的账号，及它们 openapi 发布的「最早一条」日期 / id。
2. 生成 4/1→今天的每日累计目标曲线 30 → N，后期斜率更大（α≈1.6）。
3. 每日基础 K_base = floor(cum[d]) - floor(cum[d-1])，加 Poisson 抖动得到 K_actual。
4. 每日按 K_actual 从「当日及之前已发过 openapi、尚未被分配」的池子里随机抽。
   池子不够则向后顺延剩余配额；最后一天若仍未触达 N，停在能达到的最大值。
5. 每个账号写一行 formal_video_backfills(account_id, promotion_date,
   trigger_publication_id=最早一条 openapi 发布的 id)。
"""
from __future__ import annotations

import logging
import math
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.formal_video_backfill import FormalVideoBackfill
from app.models.video_publication import VideoPublication
from app.models.video_task import VideoSubTask, VideoTask

logger = logging.getLogger("app.formal_backfill_service")


_INITIAL_COUNT = 30  # 起始日期当天的「已经是正式号」数
_GROWTH_ALPHA = 1.6  # 累计曲线幂指数：>1 表示前期慢、后期快


def _poisson_sample(lam: float, rng: random.Random) -> int:
    """Knuth 算法，无 numpy 依赖；适用于 lam < ~30。"""
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


@dataclass
class AccountFirstPub:
    account_id: uuid.UUID
    first_pub_date: date
    first_pub_id: uuid.UUID


async def _load_prod_accounts_with_first_pub(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID | None = None,
) -> list[AccountFirstPub]:
    """拉取（指定 owner 或全部）prod 账号 + 它们最早一条 openapi video_publication。

    `open_api_task_id IS NOT NULL` 充当「openapi 侧」的判别。
    owner_id=None 表示 admin 全量查看。
    """
    # 子查询：每个 account 最早一条 openapi 发布的 created_at
    subq = (
        select(
            VideoTask.account_id.label("account_id"),
            func.min(VideoPublication.created_at).label("first_created_at"),
        )
        .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
        .join(VideoPublication, VideoPublication.sub_task_id == VideoSubTask.id)
        .where(VideoPublication.open_api_task_id.isnot(None))
        .where(VideoTask.account_id.isnot(None))
        .group_by(VideoTask.account_id)
        .subquery()
    )

    # 主查询：account 与最早 publication 联接
    stmt = (
        select(
            Account.id.label("account_id"),
            subq.c.first_created_at.label("first_created_at"),
            VideoPublication.id.label("pub_id"),
        )
        .join(subq, subq.c.account_id == Account.id)
        .join(VideoTask, VideoTask.account_id == Account.id)
        .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
        .join(
            VideoPublication,
            and_(
                VideoPublication.sub_task_id == VideoSubTask.id,
                VideoPublication.created_at == subq.c.first_created_at,
                VideoPublication.open_api_task_id.isnot(None),
            ),
        )
        .where(Account.account_tier == "prod")
    )
    if owner_id is not None:
        stmt = stmt.where(Account.owner_id == owner_id)
    rows = (await session.execute(stmt)).all()

    seen: set[uuid.UUID] = set()
    out: list[AccountFirstPub] = []
    for r in rows:
        if r.account_id in seen:
            continue
        seen.add(r.account_id)
        out.append(
            AccountFirstPub(
                account_id=r.account_id,
                first_pub_date=r.first_created_at.date(),
                first_pub_id=r.pub_id,
            )
        )
    return out


def _build_daily_targets(
    start_date: date,
    end_date: date,
    target_total: int,
    rng: random.Random,
) -> list[int]:
    """生成每日「新增正式号」目标，累计单调递增、后期斜率大、带 Poisson 抖动。

    返回 list[int] 长度为 days，sum 不超过 target_total。
    """
    days = (end_date - start_date).days + 1
    if days <= 0:
        return []
    if days == 1:
        return [target_total]

    # 累计目标曲线：30 → target_total，后期权重大
    delta = max(0, target_total - _INITIAL_COUNT)
    cum_targets: list[float] = []
    for i in range(days):
        progress = i / (days - 1)
        cum_targets.append(_INITIAL_COUNT + delta * (progress ** _GROWTH_ALPHA))

    base_increments: list[int] = []
    prev_floor = 0
    for i, cum in enumerate(cum_targets):
        cur_floor = int(math.floor(cum))
        inc = max(0, cur_floor - prev_floor)
        base_increments.append(inc)
        prev_floor = cur_floor

    # 应用 Poisson 抖动；保持累计单调递增
    actual = [_poisson_sample(float(b), rng) for b in base_increments]
    # day0 至少给 _INITIAL_COUNT（如果 base 第一项是 30）
    actual[0] = max(actual[0], base_increments[0])

    # 防止总和超过 target_total：截断
    total = 0
    truncated: list[int] = []
    for v in actual:
        if total + v > target_total:
            v = max(0, target_total - total)
        truncated.append(v)
        total += v
    return truncated


@dataclass
class GenerationResult:
    target_total: int
    actual_total: int
    start_date: date
    end_date: date
    daily_counts: list[dict]  # [{date, new_accounts, cumulative}]


async def generate_plan(
    session: AsyncSession,
    *,
    target_total: int,
    start_date: date,
    end_date: date,
    owner_id: uuid.UUID | None,
    seed: int | None = None,
) -> GenerationResult:
    """全量重跑：清空（owner 范围内）formal_video_backfills 后按曲线随机分配账号。

    owner_id=None 表示 admin 全量。
    """
    rng = random.Random(seed)

    # 1. 清空（按 owner 范围）
    if owner_id is None:
        await session.execute(delete(FormalVideoBackfill))
    else:
        # 仅删除属于当前 owner 的 backfill 行
        owner_account_ids_stmt = select(Account.id).where(Account.owner_id == owner_id)
        await session.execute(
            delete(FormalVideoBackfill).where(
                FormalVideoBackfill.account_id.in_(owner_account_ids_stmt)
            )
        )

    # 2. 候选池
    candidates = await _load_prod_accounts_with_first_pub(session, owner_id=owner_id)
    rng.shuffle(candidates)
    by_id = {c.account_id: c for c in candidates}
    unassigned: set[uuid.UUID] = set(by_id.keys())

    if not candidates:
        await session.commit()
        return GenerationResult(
            target_total=target_total,
            actual_total=0,
            start_date=start_date,
            end_date=end_date,
            daily_counts=[],
        )

    effective_target = min(target_total, len(candidates))

    # 3. 每日目标
    daily_target = _build_daily_targets(start_date, end_date, effective_target, rng)

    # 4. 逐日分配
    days = (end_date - start_date).days + 1
    cumulative = 0
    daily_counts: list[dict] = []
    carry = 0
    inserts: list[FormalVideoBackfill] = []

    for offset in range(days):
        d = start_date + timedelta(days=offset)
        quota = daily_target[offset] + carry
        carry = 0

        # 当日及之前已发过 openapi 的「还没被分配」账号池
        pool = [
            cid for cid in list(unassigned)
            if by_id[cid].first_pub_date <= d
        ]
        if not pool or quota <= 0:
            carry += quota
            daily_counts.append({
                "date": d.isoformat(),
                "new_accounts": 0,
                "cumulative": cumulative,
            })
            continue

        take = min(quota, len(pool))
        chosen = rng.sample(pool, take)
        for cid in chosen:
            c = by_id[cid]
            inserts.append(FormalVideoBackfill(
                account_id=c.account_id,
                promotion_date=d,
                trigger_publication_id=c.first_pub_id,
            ))
            unassigned.discard(cid)
        cumulative += take
        carry = max(0, quota - take)

        daily_counts.append({
            "date": d.isoformat(),
            "new_accounts": take,
            "cumulative": cumulative,
        })

    session.add_all(inserts)
    await session.commit()

    logger.info(
        "formal_backfill generate_plan: target=%s actual=%s start=%s end=%s candidates=%s",
        target_total, cumulative, start_date, end_date, len(candidates),
    )

    return GenerationResult(
        target_total=target_total,
        actual_total=cumulative,
        start_date=start_date,
        end_date=end_date,
        daily_counts=daily_counts,
    )


async def clear_plan(session: AsyncSession, *, owner_id: uuid.UUID | None) -> int:
    """删除 formal_video_backfills 行（owner 范围）；admin 传 None 删全部。"""
    if owner_id is None:
        result = await session.execute(delete(FormalVideoBackfill))
    else:
        owner_account_ids_stmt = select(Account.id).where(Account.owner_id == owner_id)
        result = await session.execute(
            delete(FormalVideoBackfill).where(
                FormalVideoBackfill.account_id.in_(owner_account_ids_stmt)
            )
        )
    await session.commit()
    return int(result.rowcount or 0)


def _video_metrics_total(metrics_snapshot: dict | None) -> tuple[int, int]:
    """从 metrics_snapshot.channels 汇总 views / likes（当前累计快照）。"""
    if not isinstance(metrics_snapshot, dict):
        return 0, 0
    channels = metrics_snapshot.get("channels") or []
    if not isinstance(channels, list):
        return 0, 0
    total_views = 0
    total_likes = 0
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        stats = ch.get("stats") or {}
        platform = str(ch.get("platform") or "").lower()
        if platform == "youtube":
            total_views += int(stats.get("views") or 0)
            total_likes += int(stats.get("likes") or 0)
        else:
            total_views += int(stats.get("view_count") or 0)
            total_likes += int(stats.get("like_count") or 0)
    return total_views, total_likes


async def get_summary(session: AsyncSession, *, owner_id: uuid.UUID | None) -> dict:
    """返回当前方案（owner 范围）的每日统计、指标曲线、LTV、周窗口和增长倍数。

    口径：每日 views / likes 直接取「当日发布的视频」当前 metrics_snapshot 累计总和。
    每日定时任务覆盖 metrics_snapshot 即可（新数据覆盖旧的就行）。

    daily_counts: [{date, new_accounts, cumulative_accounts, new_videos,
                    new_views, new_likes, ltv}]
    weekly_views: [{label, start, end, avg_daily_views, growth_multiplier}]
    growth_summary: {weekly, monthly, quarterly}

    owner_id=None 表示 admin 全量查看。
    """
    bf_stmt = (
        select(FormalVideoBackfill.account_id, FormalVideoBackfill.promotion_date)
        .join(Account, Account.id == FormalVideoBackfill.account_id)
    )
    if owner_id is not None:
        bf_stmt = bf_stmt.where(Account.owner_id == owner_id)
    backfill_rows = (await session.execute(bf_stmt)).all()
    if not backfill_rows:
        return {
            "total_accounts": 0,
            "total_videos": 0,
            "daily_counts": [],
            "weekly_views": [],
            "growth_summary": {"weekly": None, "monthly": None, "quarterly": None},
            "start_date": None,
            "end_date": None,
        }

    account_to_date: dict[uuid.UUID, date] = {r.account_id: r.promotion_date for r in backfill_rows}
    total_accounts = len(backfill_rows)

    # 拉取所有相关账号的 openapi 发布 + metrics_snapshot
    pub_rows = (await session.execute(
        select(
            VideoTask.account_id.label("account_id"),
            VideoPublication.created_at.label("created_at"),
            VideoPublication.metrics_snapshot.label("metrics_snapshot"),
        )
        .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
        .join(VideoPublication, VideoPublication.sub_task_id == VideoSubTask.id)
        .where(VideoTask.account_id.in_(list(account_to_date.keys())))
        .where(VideoPublication.open_api_task_id.isnot(None))
    )).all()

    # 过滤正式视频；按发布日聚合 views / likes / count
    new_videos_by_date: dict[date, int] = {}
    views_by_date: dict[date, int] = {}
    likes_by_date: dict[date, int] = {}
    # LTV：按发布日 cohort 收集每条视频的 views / likes，方便后续算均值
    cohort_views_sum: dict[date, int] = {}
    cohort_count: dict[date, int] = {}

    total_videos = 0
    for r in pub_rows:
        promo_date = account_to_date.get(r.account_id)
        if promo_date is None:
            continue
        pub_date = r.created_at.date() if isinstance(r.created_at, datetime) else r.created_at
        if pub_date < promo_date:
            continue
        v, l = _video_metrics_total(r.metrics_snapshot)
        new_videos_by_date[pub_date] = new_videos_by_date.get(pub_date, 0) + 1
        views_by_date[pub_date] = views_by_date.get(pub_date, 0) + v
        likes_by_date[pub_date] = likes_by_date.get(pub_date, 0) + l
        cohort_views_sum[pub_date] = cohort_views_sum.get(pub_date, 0) + v
        cohort_count[pub_date] = cohort_count.get(pub_date, 0) + 1
        total_videos += 1

    # 每日新增账号
    new_acc_by_date: dict[date, int] = {}
    for r in backfill_rows:
        new_acc_by_date[r.promotion_date] = new_acc_by_date.get(r.promotion_date, 0) + 1

    if not new_acc_by_date and not new_videos_by_date:
        return {
            "total_accounts": total_accounts,
            "total_videos": total_videos,
            "daily_counts": [],
            "weekly_views": [],
            "growth_summary": {"weekly": None, "monthly": None, "quarterly": None},
            "start_date": None,
            "end_date": None,
        }

    today = date.today()
    start_date = min(
        min(new_acc_by_date.keys()) if new_acc_by_date else today,
        min(new_videos_by_date.keys()) if new_videos_by_date else today,
    )
    end_date = max(
        max(new_acc_by_date.keys()) if new_acc_by_date else start_date,
        max(new_videos_by_date.keys()) if new_videos_by_date else start_date,
        today,
    )

    days_total = (end_date - start_date).days + 1

    # 组装 daily_counts
    daily_counts: list[dict] = []
    cum_accounts = 0
    daily_views: list[int] = []
    for i in range(days_total):
        d = start_date + timedelta(days=i)
        new_acc = new_acc_by_date.get(d, 0)
        cum_accounts += new_acc
        # LTV(D) 口径：D-7 发布的视频，当前累计 views 的均值
        cohort_date = d - timedelta(days=7)
        if cohort_count.get(cohort_date, 0) > 0:
            ltv_val: int | None = round(cohort_views_sum[cohort_date] / cohort_count[cohort_date])
        else:
            ltv_val = None
        v_today = views_by_date.get(d, 0)
        daily_views.append(v_today)
        daily_counts.append({
            "date": d.isoformat(),
            "new_accounts": new_acc,
            "cumulative_accounts": cum_accounts,
            "new_videos": new_videos_by_date.get(d, 0),
            "new_views": v_today,
            "new_likes": likes_by_date.get(d, 0),
            "ltv": ltv_val,
        })

    # 周窗口 + 增长倍数
    weekly_views: list[dict] = []
    week_growth_multipliers: list[float] = []
    prev_avg: float | None = None
    for win_start_idx in range(0, days_total, 7):
        win_end_idx = min(win_start_idx + 6, days_total - 1)
        if win_start_idx > win_end_idx:
            break
        window = daily_views[win_start_idx : win_end_idx + 1]
        avg = sum(window) / max(1, len(window))
        win_start = start_date + timedelta(days=win_start_idx)
        win_end = start_date + timedelta(days=win_end_idx)
        # 增长倍数 = 当前 / 上一个窗口
        if prev_avg is not None and prev_avg > 0:
            growth = avg / prev_avg
        else:
            growth = 1.0
        weekly_views.append({
            "label": f"{win_start.isoformat()[5:]}~{win_end.isoformat()[5:]}",
            "start": win_start.isoformat(),
            "end": win_end.isoformat(),
            "avg_daily_views": round(avg),
            "growth_multiplier": round(growth, 2),
        })
        if prev_avg is not None and prev_avg > 0:
            week_growth_multipliers.append(growth)
        prev_avg = avg

    # 周/月/季度增长倍数
    if week_growth_multipliers:
        avg_week_growth = sum(week_growth_multipliers) / len(week_growth_multipliers)
        daily_growth = avg_week_growth ** (1.0 / 7.0)
        growth_summary = {
            "weekly": round(avg_week_growth, 2),
            "monthly": round(daily_growth ** 30.5, 2),
            "quarterly": round(daily_growth ** 91.5, 2),
        }
    else:
        growth_summary = {"weekly": None, "monthly": None, "quarterly": None}

    return {
        "total_accounts": total_accounts,
        "total_videos": total_videos,
        "daily_counts": daily_counts,
        "weekly_views": weekly_views,
        "growth_summary": growth_summary,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


async def export_task_ids(
    session: AsyncSession, *, owner_id: uuid.UUID | None
) -> list[str]:
    """扁平输出（owner 范围）所有正式视频的 open_api_task_id 列表（去重）。"""
    stmt = (
        select(
            VideoPublication.open_api_task_id,
            VideoTask.account_id,
            VideoPublication.created_at,
            FormalVideoBackfill.promotion_date,
        )
        .join(VideoSubTask, VideoSubTask.task_id == VideoTask.id)
        .join(VideoPublication, VideoPublication.sub_task_id == VideoSubTask.id)
        .join(FormalVideoBackfill, FormalVideoBackfill.account_id == VideoTask.account_id)
        .join(Account, Account.id == FormalVideoBackfill.account_id)
        .where(VideoPublication.open_api_task_id.isnot(None))
    )
    if owner_id is not None:
        stmt = stmt.where(Account.owner_id == owner_id)
    rows = (await session.execute(stmt)).all()

    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        if not r.open_api_task_id:
            continue
        d = r.created_at.date() if isinstance(r.created_at, datetime) else r.created_at
        if d < r.promotion_date:
            continue
        tid = str(r.open_api_task_id)
        if tid in seen:
            continue
        seen.add(tid)
        out.append(tid)
    return out
