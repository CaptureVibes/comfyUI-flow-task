"""
Account tier evaluation scheduler
=================================
账号分级评估，规则参数从 pipeline_settings 读取（per-owner）：
  - tier_video_sample_count：最近 N 条视频
  - tier_avg_play_threshold：均播阈值
  - tier_activity_days：最近 N 天
  - tier_min_video_count：最近 N 天最少发视频数
  - tier_daily_formal_growth_min_rate / max_rate：正式号每日新增比例区间

晋级 / 降级规则（test=实验号 / dev=常规号 / prod=正式号）：
  - 同时满足：最近 N 条均播 ≥ 阈值，且过去 N 天发布数 ≥ 最少发视频数 → 应为 dev，
    否则应为 test。
  - prod 永不被自动改动。

每天北京时间 09:00 自动执行：每个 owner 各自做一次双向 test↔dev 评估，
之后再做 dev→prod 的随机扩量（按区间 random.uniform(min_rate, max_rate)）。

也可通过 API/脚本手动触发：手动只做 test↔dev，不做 prod 扩量。
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.pipeline_setting import PipelineSetting
from app.models.video_publication import VideoPublication
from app.models.video_task import VideoSubTask, VideoTask

logger = logging.getLogger("app.account_tier_scheduler")

_CRON_EXPR = "0 9 * * *"   # 北京时间每天 09:00（早于 channel_name_sync 10:00）
_POLL_INTERVAL_SECONDS = 60
_TZ = ZoneInfo("Asia/Shanghai")

_scheduler_task: asyncio.Task | None = None
_scheduler_stop_event: asyncio.Event | None = None
_last_fire_key: str | None = None
_run_lock = asyncio.Lock()


# ── Defaults ───────────────────────────────────────────────────────────────
# 用户尚未保存 pipeline_settings 时使用，跟 model 默认值保持一致

@dataclass
class TierThresholds:
    video_sample_count: int = 7
    avg_play_threshold: int = 700
    activity_days: int = 7
    min_video_count: int = 6
    daily_formal_growth_min_rate: float = 0.0
    daily_formal_growth_max_rate: float = 0.06


async def _load_thresholds(session: AsyncSession, owner_id: uuid.UUID | None) -> TierThresholds:
    """读取该 owner 的分级阈值；没有 owner 或 settings 时使用默认。"""
    if owner_id is None:
        return TierThresholds()
    row = await session.scalar(
        select(PipelineSetting).where(PipelineSetting.owner_id == owner_id)
    )
    if row is None:
        return TierThresholds()
    return TierThresholds(
        video_sample_count=int(row.tier_video_sample_count or 7),
        avg_play_threshold=int(row.tier_avg_play_threshold or 700),
        activity_days=int(row.tier_activity_days or 7),
        min_video_count=int(row.tier_min_video_count or 6),
        daily_formal_growth_min_rate=float(row.tier_daily_formal_growth_min_rate or 0.0),
        daily_formal_growth_max_rate=float(row.tier_daily_formal_growth_max_rate or 0.06),
    )


# ── 调度器生命周期 ─────────────────────────────────────────────────────────────


def start_account_tier_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_stop_event = asyncio.Event()
    _scheduler_task = asyncio.get_running_loop().create_task(
        _scheduler_loop(_scheduler_stop_event)
    )
    logger.info("【账号分级】调度器已启动，触发规则：北京时间 %s", _CRON_EXPR)


async def stop_account_tier_scheduler() -> None:
    global _scheduler_task, _scheduler_stop_event
    stop_event, worker = _scheduler_stop_event, _scheduler_task
    _scheduler_stop_event = None
    _scheduler_task = None
    if stop_event is not None:
        stop_event.set()
    if worker is None:
        return
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    logger.info("【账号分级】调度器已停止")


async def run_account_tier_evaluation() -> dict:
    """手动触发一次完整评估（test↔dev + dev→prod 扩量），跨所有 owner。"""
    async with _run_lock:
        return await _run_once_all_owners()


async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    global _last_fire_key
    now_local = datetime.now(timezone.utc).astimezone(_TZ)
    cron = croniter(_CRON_EXPR, now_local)
    prev_local: datetime = cron.get_prev(datetime)
    _last_fire_key = prev_local.strftime("%Y-%m-%d %H:%M")

    try:
        while not stop_event.is_set():
            try:
                await _check_and_maybe_fire()
            except Exception:
                logger.exception("【账号分级】调度异常")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=_POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        raise


async def _check_and_maybe_fire() -> None:
    global _last_fire_key
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(_TZ)

    cron = croniter(_CRON_EXPR, now_local)
    prev_local: datetime = cron.get_prev(datetime)
    fire_key = prev_local.strftime("%Y-%m-%d %H:%M")

    seconds_since = (now_local - prev_local).total_seconds()
    if seconds_since < 0 or seconds_since >= _POLL_INTERVAL_SECONDS * 1.5:
        return
    if fire_key == _last_fire_key:
        return

    _last_fire_key = fire_key
    logger.info("【账号分级】命中触发点 %s（北京时间），开始评估", fire_key)
    async with _run_lock:
        await _run_once_all_owners()


# ── 数据辅助 ────────────────────────────────────────────────────────────────

def _to_int(val) -> int:
    try:
        n = int(val)
        return n if n > 0 else 0
    except (TypeError, ValueError):
        return 0


def _views_from_snapshot(snapshot) -> int:
    """从 metrics_snapshot.channels 累加该发布的总播放量。"""
    if not isinstance(snapshot, dict):
        return 0
    channels = snapshot.get("channels") or []
    total = 0
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        stats = ch.get("stats") or {}
        platform = str(ch.get("platform") or "").lower()
        if platform == "youtube":
            total += _to_int(stats.get("views"))
        else:
            total += _to_int(stats.get("view_count") or stats.get("views"))
    return total


def _publication_views(pub: VideoPublication) -> int:
    """兼容旧调用：从 VideoPublication 对象取 metrics_snapshot 算视图数。"""
    return _views_from_snapshot(pub.metrics_snapshot)


# ── 公开接口（API/脚本/调度器都用） ────────────────────────────────────────────

async def compute_tier_changes(
    session: AsyncSession,
    owner_id: uuid.UUID | None,
) -> list[dict]:
    """计算该 owner 下所有 test/dev 账号的目标 tier，返回需要变更的列表。

    实现：3 次聚合查询完成全部账号判定，避免 N+1 把数据库连接锁住太久。
      Q1: 拉所有 test/dev 账号
      Q2: 用 ROW_NUMBER() 窗口函数按 account_id 取最近 N 条 publication 的 metrics_snapshot
      Q3: 按 account_id 聚合最近 K 天 publication 数

    返回项格式：
      {
        "account_id": uuid,
        "account_name": str,
        "current_tier": "test" | "dev",
        "target_tier": "test" | "dev",
        "reason": {video_count_in_sample, avg_views, recent_count, threshold},
      }
    prod 账号不参与评估。
    """
    th = await _load_thresholds(session, owner_id)

    # Q1: 候选账号
    acct_stmt = select(Account).where(Account.account_tier.in_(("test", "dev")))
    if owner_id is not None:
        acct_stmt = acct_stmt.where(Account.owner_id == owner_id)
    accounts = list((await session.execute(acct_stmt)).scalars().all())
    if not accounts:
        return []
    account_ids = [a.id for a in accounts]

    # Q2: 每个账号最近若干条 publication 的 metrics_snapshot。
    # 多取一些（×10）供后续 Python 端过滤掉 views=0/空的样本（刚发布、数据未回灌），
    # 再按时间序取真正用于均播判定的 N 条。
    rn = func.row_number().over(
        partition_by=VideoTask.account_id,
        order_by=VideoPublication.completed_at.desc(),
    ).label("rn")
    sample_subq = (
        select(
            VideoTask.account_id.label("aid"),
            VideoPublication.metrics_snapshot.label("snap"),
            VideoPublication.completed_at.label("completed_at"),
            rn,
        )
        .join(VideoSubTask, VideoSubTask.id == VideoPublication.sub_task_id)
        .join(VideoTask, VideoTask.id == VideoSubTask.task_id)
        .where(VideoTask.account_id.in_(account_ids))
        .where(VideoPublication.status.in_(["completed", "partial"]))
        .where(VideoPublication.completed_at.isnot(None))
        .subquery()
    )
    samples_by_account: dict[uuid.UUID, list[tuple]] = {}
    rows = (await session.execute(
        select(sample_subq.c.aid, sample_subq.c.snap, sample_subq.c.completed_at)
        .where(sample_subq.c.rn <= th.video_sample_count * 10)
    )).all()
    for aid, snap, completed_at in rows:
        samples_by_account.setdefault(aid, []).append((snap, completed_at))

    # Q3: 每个账号最近 K 天 publication 数
    cutoff = datetime.now(timezone.utc) - timedelta(days=th.activity_days)
    recent_counts: dict[uuid.UUID, int] = {}
    rows = (await session.execute(
        select(VideoTask.account_id, func.count(VideoPublication.id))
        .join(VideoSubTask, VideoSubTask.id == VideoPublication.sub_task_id)
        .join(VideoTask, VideoTask.id == VideoSubTask.task_id)
        .where(VideoTask.account_id.in_(account_ids))
        .where(VideoPublication.status.in_(["completed", "partial"]))
        .where(VideoPublication.completed_at >= cutoff)
        .group_by(VideoTask.account_id)
    )).all()
    for aid, cnt in rows:
        recent_counts[aid] = int(cnt or 0)

    # Python 端聚合判定
    threshold = {
        "video_sample_count": th.video_sample_count,
        "avg_play_threshold": th.avg_play_threshold,
        "activity_days": th.activity_days,
        "min_video_count": th.min_video_count,
    }
    changes: list[dict] = []
    for account in accounts:
        # 按时间序倒序排好（DB 不一定保证顺序），过滤掉 views<=0/空 的样本——刚发布
        # 的视频还没回灌数据，这些样本会拉低均播误判账号档位。
        raw_samples = samples_by_account.get(account.id, [])
        raw_samples.sort(
            key=lambda x: x[1] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        valid_snapshots: list = []
        for snap, _ in raw_samples:
            if _views_from_snapshot(snap) > 0:
                valid_snapshots.append(snap)
                if len(valid_snapshots) >= th.video_sample_count:
                    break
        sample_count = len(valid_snapshots)
        recent_count = recent_counts.get(account.id, 0)
        avg_views = 0.0
        if sample_count >= th.video_sample_count:
            avg_views = sum(_views_from_snapshot(s) for s in valid_snapshots) / th.video_sample_count
        meets = (
            sample_count >= th.video_sample_count
            and avg_views >= th.avg_play_threshold
            and recent_count >= th.min_video_count
        )
        target = "dev" if meets else "test"
        if target == account.account_tier:
            continue
        changes.append({
            "account_id": account.id,
            "account_name": account.account_name,
            "current_tier": account.account_tier,
            "target_tier": target,
            "reason": {
                "video_count_in_sample": sample_count,
                "avg_views": round(avg_views, 1),
                "recent_count": recent_count,
                "threshold": threshold,
            },
        })
    return changes


async def apply_tier_changes(
    session: AsyncSession,
    owner_id: uuid.UUID | None,
    changes: Iterable[dict],
) -> dict:
    """按提供的 changes 列表实际改写 account.account_tier。

    安全校验（任一不满足则跳过）：
      - account.owner_id 必须等于传入 owner_id（owner_id=None 时不限制，调度器/admin 用）
      - account.account_tier 必须仍等于 current_tier（避免 race）
      - target_tier 必须是 'test' 或 'dev'（绝不动 prod）
    """
    promoted = 0   # test → dev
    demoted = 0    # dev → test
    skipped = 0

    for change in changes:
        target = str(change.get("target_tier") or "")
        if target not in ("test", "dev"):
            skipped += 1
            continue
        try:
            account_id = change["account_id"]
            if not isinstance(account_id, uuid.UUID):
                account_id = uuid.UUID(str(account_id))
        except (KeyError, ValueError):
            skipped += 1
            continue
        current_tier = str(change.get("current_tier") or "")

        account = await session.get(Account, account_id)
        if account is None:
            skipped += 1
            continue
        if owner_id is not None and account.owner_id != owner_id:
            skipped += 1
            continue
        if account.account_tier == "prod":
            skipped += 1
            continue
        if current_tier and account.account_tier != current_tier:
            # 期间已被改动，跳过避免覆盖
            skipped += 1
            continue
        if account.account_tier == target:
            continue

        account.account_tier = target
        if account.account_tier == "dev" and target == "dev":
            pass  # 占位保持代码清晰
        if target == "dev":
            promoted += 1
            logger.info(
                "【账号分级】test→dev: id=%s name=%s",
                account.id, account.account_name,
            )
        else:
            demoted += 1
            logger.info(
                "【账号分级】dev→test: id=%s name=%s",
                account.id, account.account_name,
            )

    if promoted or demoted:
        await session.commit()

    return {"promoted": promoted, "demoted": demoted, "skipped": skipped}


async def evaluate_dev_to_prod(
    session: AsyncSession,
    owner_id: uuid.UUID | None,
    th: TierThresholds | None = None,
) -> int:
    """从 dev 中按 random.uniform(min_rate, max_rate) 扩量晋升 prod。"""
    if th is None:
        th = await _load_thresholds(session, owner_id)

    prod_stmt = select(func.count(Account.id)).where(Account.account_tier == "prod")
    if owner_id is not None:
        prod_stmt = prod_stmt.where(Account.owner_id == owner_id)
    prod_count = await session.scalar(prod_stmt) or 0
    if prod_count <= 0:
        logger.info("【账号分级】owner=%s 当前正式号数量为 0，跳过 dev→prod 扩量", owner_id)
        return 0

    rate = random.uniform(th.daily_formal_growth_min_rate, th.daily_formal_growth_max_rate)
    target = round(rate * prod_count)
    if target <= 0:
        logger.info(
            "【账号分级】owner=%s 今日扩量 = 0（rate=%.4f * prod=%d）",
            owner_id, rate, prod_count,
        )
        return 0

    dev_stmt = select(Account).where(Account.account_tier == "dev")
    if owner_id is not None:
        dev_stmt = dev_stmt.where(Account.owner_id == owner_id)
    dev_accounts = list((await session.execute(dev_stmt)).scalars().all())
    if not dev_accounts:
        logger.info("【账号分级】owner=%s 无可晋升的常规号", owner_id)
        return 0

    pick = min(target, len(dev_accounts))
    chosen = random.sample(dev_accounts, pick)
    for account in chosen:
        account.account_tier = "prod"
        logger.info(
            "【账号分级】dev→prod: owner=%s id=%s name=%s",
            owner_id, account.id, account.account_name,
        )
    await session.commit()
    logger.info(
        "【账号分级】owner=%s dev→prod 完成：rate=%.4f, prod=%d, picked=%d",
        owner_id, rate, prod_count, pick,
    )
    return pick


# ── 调度入口 ───────────────────────────────────────────────────────────────


async def _list_owner_ids(session: AsyncSession) -> list[uuid.UUID | None]:
    """返回所有出现过的 account.owner_id（含 None，admin 创建的账号没 owner）。"""
    rows = (await session.execute(
        select(Account.owner_id).distinct()
    )).all()
    return [row[0] for row in rows]


async def _run_once_for_owner(owner_id: uuid.UUID | None) -> dict:
    """单个 owner：双向 test↔dev + dev→prod 扩量。"""
    async with SessionLocal() as session:
        changes = await compute_tier_changes(session, owner_id)
        apply_result = await apply_tier_changes(session, owner_id, changes)
        promoted_prod = await evaluate_dev_to_prod(session, owner_id)
    return {**apply_result, "promoted_to_prod": promoted_prod}


async def _run_once_all_owners() -> dict:
    """跨所有 owner 各跑一遍，汇总返回。"""
    async with SessionLocal() as session:
        owner_ids = await _list_owner_ids(session)

    total_promoted = 0
    total_demoted = 0
    total_prod = 0
    for owner_id in owner_ids:
        try:
            res = await _run_once_for_owner(owner_id)
        except Exception:
            logger.exception("【账号分级】owner=%s 评估失败", owner_id)
            continue
        total_promoted += res.get("promoted", 0)
        total_demoted += res.get("demoted", 0)
        total_prod += res.get("promoted_to_prod", 0)

    result = {
        "owners": len(owner_ids),
        "promoted_to_dev": total_promoted,
        "demoted_to_test": total_demoted,
        "promoted_to_prod": total_prod,
    }
    logger.info("【账号分级】本轮完成：%s", result)
    return result
