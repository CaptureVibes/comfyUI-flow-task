# TikTok 博主视频补充服务 — 对接规范

> 本文档面向 **视频补充服务方**（以下简称「服务方」/「你方」）。
>
> Echo Matrix（以下简称「Echo」/「主系统」）会按本规范调用你方的 HTTP 接口
> 来发起视频采集请求；你方在完成后通过回调把结果送回 Echo。
>
> 你方需要实现的：
> - **接口 1**：`POST /supplement-requests` 接收 Echo 的采集请求
> - **接口 2**：按 Echo 给出的回调地址 `POST` 把采集结果送回
>
> 你方负责：按 TikTok 博主主页搜索视频 → 应用过滤条件 → 下载视频 → 上传到 CDN → 回调结果。

---

## 1. 总览

```
Echo                                       你方
 │                                          │
 │ ① POST {你方域名}/supplement-requests    │
 │ ─────────────────────────────────────►  │
 │                                          │  按博主搜索
 │ ◄────────────────────────────────────── │  应用过滤条件
 │   200 OK { accepted_items, ... }         │  下载视频
 │                                          │  上传到 CDN
 │                                          │
 │ ② POST {Echo 回调地址} 在请求里给出     │
 │ ◄────────────────────────────────────── │
 │   { request_id, items[].videos[] }       │
 │                                          │
 │   200 OK { accepted, duplicated, ... }   │
 │ ─────────────────────────────────────►  │
```

- 步骤 ① 是同步的「立即返回回执」，你方收到请求即排队、立即返回，不需要等真正搜索完成。
- 步骤 ② 由你方在采集完成后主动发起；允许分批（多次发同一 `request_id`，最后一次置 `final: true`）。

---

## 2. 鉴权

| 方向 | 头 | 说明 |
|---|---|---|
| Echo → 你方 | `Authorization: Bearer <共享密钥>` | 上线前双方约定 |
| 你方 → Echo（回调） | `X-API-Key: <Echo 在 outbound 请求里告诉你的密钥>` | 见下面 `callback_auth.header_value` |

> 共享密钥请提供给 Echo 团队后线下交换；不要写入文档或代码仓库。

---

## 3. 接口 1：接收采集请求

由 **Echo** 调用 **你方**：

### Endpoint
```
POST {你方域名}/supplement-requests
```

### 请求头
```
Authorization: Bearer <共享密钥>
Content-Type: application/json
```

### 请求体

```json
{
  "request_id": "61a0b3c2-3d4e-4a52-9b8b-2f7c1a8d8e90",
  "callback_url": "https://echo-matrix.example.com/api/v1/external/supplement-callback",
  "callback_auth": {
    "header_name": "X-API-Key",
    "header_value": "ec_cb_xxx_yyy"
  },

  "mode": "exclusive",
  "platform": "tiktok",
  "target_video_count": 10,

  "filters": {
    "min_view_count": 10000,
    "published_after": "2026-01-01",
    "max_duration_seconds": 60
  },

  "items": [
    {
      "account_id": "fd3e9c4a-1234-5678-90ab-cdef12345678",
      "blogger": {
        "handle": "lilyrosent",
        "profile_url": "https://www.tiktok.com/@lilyrosent",
        "tiktok_blogger_id": "7270221987061009710"
      },
      "existing_video_urls": [
        "https://www.tiktok.com/@lilyrosent/video/7150111111111111111",
        "https://www.tiktok.com/@lilyrosent/video/7150222222222222222"
      ]
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | string (UUID) | ✅ | 唯一标识本次请求；回调时请原样回填 |
| `callback_url` | string | ✅ | 你方在采集完成后请向该地址发回调 |
| `callback_auth.header_name` | string | ✅ | 你方调回调时要带的鉴权头名（当前固定 `X-API-Key`） |
| `callback_auth.header_value` | string | ✅ | 你方调回调时要带的鉴权头值 |
| `mode` | enum | ✅ | `exclusive` / `auto`，仅作记录，不影响你方处理逻辑 |
| `platform` | enum | ✅ | 目前只 `tiktok`，预留扩展 |
| `target_video_count` | int | ✅ | **每个博主**期望返回的视频数；尽力满足 |
| `filters.min_view_count` | int \| null | 选 | 播放量下限；`null` / `0` 视为不限 |
| `filters.published_after` | date (`YYYY-MM-DD`) \| null | 选 | 仅采集**该日期及之后**发布的视频；`null` 视为不限 |
| `filters.max_duration_seconds` | int \| null | 选 | 视频时长上限（秒）；`null` / `0` 视为不限 |
| `items[]` | array | ✅ | 一次请求里的多个博主（每个对应主系统的一个账号） |
| `items[].account_id` | string (UUID) | ✅ | 主系统账号 UUID；你方不需要关心其语义，**回调时原样回填** |
| `items[].blogger.handle` | string | ✅ | TikTok handle（不含 `@`） |
| `items[].blogger.profile_url` | string | ✅ | 博主主页完整 URL |
| `items[].blogger.tiktok_blogger_id` | string | 选 | TikTok 平台的 uploader_id；如果你方内部有该博主缓存，可用此字段命中 |
| `items[].existing_video_urls` | string[] | ✅（可空数组） | 主系统已经有的视频；**你方应过滤掉这些**，避免重复采集 |

### 响应

立即同步返回，**不需要**等真正搜索完成。

```json
{
  "request_id": "61a0b3c2-...",
  "status": "accepted",
  "accepted_items": 30,
  "message": "已接收，排队执行"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `request_id` | string | 与请求一致 |
| `status` | enum | `accepted` / `rejected` |
| `accepted_items` | int | 实际接受处理的 `items[]` 数量 |
| `message` | string | 任意文案 |

### 错误响应

```json
{
  "request_id": "61a0b3c2-...",
  "status": "rejected",
  "error_code": "INVALID_BODY",
  "message": "blogger.handle 缺失"
}
```

`status=rejected` 时主系统不会重试，可以直接报错文案回到操作页面。

---

## 4. 接口 2：发送结果回调

由 **你方** 调用 **Echo**：

### Endpoint
```
POST {callback_url 取自请求里的字段}
```

### 请求头
```
{callback_auth.header_name}: {callback_auth.header_value}
Content-Type: application/json
```

例：
```
X-API-Key: ec_cb_xxx_yyy
Content-Type: application/json
```

### 请求体

```json
{
  "request_id": "61a0b3c2-...",
  "mode": "exclusive",
  "final": true,
  "items": [
    {
      "account_id": "fd3e9c4a-...",
      "status": "completed",
      "error": null,
      "videos": [
        {
          "source_url": "https://www.tiktok.com/@lilyrosent/video/7270221987061009710",
          "local_video_url": "https://cdn.alvinclub.com/videos/.../lilyrosent_20260422.mp4",

          "blogger_name": "Lily",
          "video_title": "Morning routine in Paris",
          "publish_date": "2026-04-22T12:30:00Z",
          "duration": 28,
          "view_count": 12345,
          "like_count": 1234,

          "video_desc": "...",
          "thumbnail_url": "https://...",
          "width": 1080,
          "height": 1920,
          "aspect_ratio": 0.5625,
          "comment_count": 56,
          "share_count": 7,
          "favorite_count": 89,
          "extra": {}
        }
      ]
    }
  ]
}
```

### 字段说明 — 顶层

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `request_id` | string (UUID) | ✅ | 与 outbound 请求一致；不存在返回 404 |
| `mode` | enum | ✅ | 原样回填 outbound 的 mode |
| `final` | bool | ✅ | `true` = 最后一批；`false` = 还会再发 |
| `items[]` | array | ✅ | 每个对应 outbound 中一个账号 |

### 字段说明 — `items[]` 层

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `account_id` | string (UUID) | ✅ | 与 outbound 请求里的 `account_id` 完全一致；主系统据此反查回对应的 TikTok 博主，无需再回填 handle |
| `status` | enum | ✅ | `completed` / `partial` / `failed` / `skipped` |
| `error` | string \| null | 选 | `failed` / `skipped` / `partial` 时给个原因，便于运营排查 |
| `videos[]` | array | ✅（可为空） | 采集到的视频列表 |

`status` 语义：

| 值 | 含义 |
|---|---|
| `completed` | 已达 `target_video_count`；videos 数 = target |
| `partial` | 不足 target，但有采集到一些 |
| `failed` | 完全失败（无法访问博主、网络错误等） |
| `skipped` | 主动跳过（如该博主全部视频都已在 `existing_video_urls` 中） |

### 字段说明 — `videos[]` 层

**必填**（任一缺失则该条视频被主系统拒收）

| 字段 | 类型 | 说明 |
|---|---|---|
| `source_url` | string | TikTok 视频原始页面 URL（如 `https://www.tiktok.com/@user/video/12345`）；主键级去重 |
| `local_video_url` | string | **已上传到 CDN 的 .mp4 永久链接**；主系统会直接拉这条链接 |

**推荐填**（用作前端展示和排序，缺失时主系统记 NULL）

| 字段 | 类型 | 说明 |
|---|---|---|
| `blogger_name` | string | 博主显示名（非 handle） |
| `video_title` | string | 视频标题 |
| `publish_date` | ISO 8601 datetime | 发布时间（带时区） |
| `duration` | int | 视频时长，**单位：秒** |
| `view_count` | int | 播放量 |
| `like_count` | int | 点赞数 |

**可选**（缺失对业务无影响）

| 字段 | 类型 | 说明 |
|---|---|---|
| `video_desc` | string | 视频描述 |
| `thumbnail_url` | string | 缩略图 URL |
| `width` | int | 视频宽度（像素） |
| `height` | int | 视频高度（像素） |
| `aspect_ratio` | **float** | `width / height`（**不是** `"9:16"` 这种字符串） |
| `favorite_count` | int | 收藏数 |
| `comment_count` | int | 评论数 |
| `share_count` | int | 分享数 |
| `extra` | object | 任意 JSON；可放你方内部 trace_id / job_id 等，主系统原样存档 |

### 响应

主系统收到回调后同步返回。

```json
{
  "request_id": "61a0b3c2-...",
  "accepted": 18,
  "duplicated": 2,
  "rejected": 0,
  "message": "ok"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `accepted` | int | 本次成功落库的视频数 |
| `duplicated` | int | 命中已存在的 `source_url`，主系统已跳过 |
| `rejected` | int | 必填字段缺失或字段格式不合法被拒 |
| `message` | string | 文案 |

### 错误响应

| HTTP | 场景 | 你方建议处理 |
|---|---|---|
| `401` | `X-API-Key` 与发过去的不一致 | 检查 header；不要重试 |
| `404` | `request_id` 不存在或已超时关闭 | 不要重试 |
| `422` | 字段格式错误（必填缺失、类型不对） | 修正后再发 |
| `5xx` | 主系统出错 | 建议重试，30s / 2min / 10min 三档退避；最多 3 次 |

---

## 5. 重要约束

- **`local_video_url` 必须是稳定永久链接**，至少 30 天有效。**不可使用** Apify Key-Value-Store 链接（24h 过期）。
- **`source_url` 主系统全局唯一**：同一视频在多个账号下回调，从第二次起会进入 `duplicated`，不再写库。
- **`extra` 字段建议 < 100 KB**。
- **单次回调 `items[].videos[]` 总数不超过 1000 条**；超过请用分批回调（`final: false` → ... → `final: true`）。
- **采集时效**：建议在 24 小时内完成全部回调；超过 7 天 `request_id` 会过期，回调将得到 404。
- **过滤条件由你方在采集端实现**；不要返回不满足 `filters` 的视频，主系统不会再做二次过滤。

---

## 6. 端到端示例

### 6.1 Echo 发起请求

```bash
curl -X POST https://vendor.example.com/supplement-requests \
  -H "Authorization: Bearer SHARED_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "61a0b3c2-3d4e-4a52-9b8b-2f7c1a8d8e90",
    "callback_url": "https://echo-matrix.example.com/api/v1/external/supplement-callback",
    "callback_auth": {
      "header_name": "X-API-Key",
      "header_value": "ec_cb_xxx_yyy"
    },
    "mode": "auto",
    "platform": "tiktok",
    "target_video_count": 5,
    "filters": {
      "min_view_count": 50000,
      "published_after": "2025-12-01",
      "max_duration_seconds": 90
    },
    "items": [
      {
        "account_id": "fd3e9c4a-1234-5678-90ab-cdef12345678",
        "blogger": {
          "handle": "lilyrosent",
          "profile_url": "https://www.tiktok.com/@lilyrosent"
        },
        "existing_video_urls": []
      }
    ]
  }'
```

你方立即返回：

```json
{
  "request_id": "61a0b3c2-3d4e-4a52-9b8b-2f7c1a8d8e90",
  "status": "accepted",
  "accepted_items": 1,
  "message": "queued"
}
```

### 6.2 你方采集完成后回调

```bash
curl -X POST https://echo-matrix.example.com/api/v1/external/supplement-callback \
  -H "X-API-Key: ec_cb_xxx_yyy" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "61a0b3c2-3d4e-4a52-9b8b-2f7c1a8d8e90",
    "mode": "auto",
    "final": true,
    "items": [
      {
        "account_id": "fd3e9c4a-1234-5678-90ab-cdef12345678",
        "status": "completed",
        "videos": [
          {
            "source_url": "https://www.tiktok.com/@lilyrosent/video/7270221987061009710",
            "local_video_url": "https://cdn.alvinclub.com/videos/lilyrosent_20260422.mp4",
            "blogger_name": "Lily",
            "video_title": "Morning routine in Paris",
            "publish_date": "2026-04-22T12:30:00Z",
            "duration": 28,
            "view_count": 80000,
            "like_count": 1234
          }
        ]
      }
    ]
  }'
```

Echo 返回：

```json
{
  "request_id": "61a0b3c2-3d4e-4a52-9b8b-2f7c1a8d8e90",
  "accepted": 1,
  "duplicated": 0,
  "rejected": 0,
  "message": "ok"
}
```

### 6.3 分批回调

第一批：
```json
{ "request_id": "...", "mode": "auto", "final": false, "items": [...] }
```

第二批（最后）：
```json
{ "request_id": "...", "mode": "auto", "final": true, "items": [...] }
```

主系统在收到 `final: true` 之前，本次请求一直保持 open 状态。

---

## 7. 上线交付清单

| 方 | 内容 |
|---|---|
| 你方 | `POST /supplement-requests` 域名 + 实施完成可联调 |
| 双方 | 上行 Bearer 共享密钥（线下交换） |
| Echo | 回调 `X-API-Key` 密钥（每次 outbound 请求都会通过 `callback_auth.header_value` 传给你方）|
| Echo | 回调地址 |

> 联调阶段建议先用 `target_video_count = 1` 验证端到端链路，再逐步放量。

---

> 版本：v1.0 · 2026-05-19
> 联系人：Echo Matrix 技术对接
