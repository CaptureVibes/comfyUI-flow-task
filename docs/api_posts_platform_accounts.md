# API 文档（Posts / Platform Accounts）

## 基础信息

- Base URL: `http://<host>:8000`
- 认证方式: Header `X-API-Key: <your-api-key>`
- Content-Type: `application/json`

统一返回结构：

```json
{
  "code": 200,
  "message": "Success",
  "data": {}
}
```

## 枚举值

### 平台枚举

- `tiktok`
- `instagram`
- `youtube`
- `twitter`
- `facebook`

### 帖子类型 `post_type`

- `image`
- `video`

### 帖子聚合状态 `post.status`

- `pending`
- `processing`
- `completed`
- `partial`
- `failed`

### 发布状态 `publish.status`

- `pending`
- `completed`
- `failed`

兼容历史值：`published`（服务内会按 `completed` 处理）。

### 回调状态 `callback_status`（业务约定）

- `pending`
- `success`
- `failed`

---

## 1) `GET /api/posts`

查询帖子列表。

### Query 参数

- `ip_address` string，可选。按 IP 过滤可分发帖子。

### 成功返回 `data`

```json
{
  "items": [
    {
      "id": "6368297e-3d87-4125-9370-44e2ec02e69b",
      "business_id": "biz-curl-tk-001",
      "status": "pending",
      "post_type": "image",
      "title": "按平台账号创建测试",
      "content": "使用 platform + channel_id 传账号",
      "tags": ["tiktok", "photo_daily"],
      "image_urls": ["https://example.com/a.jpg"],
      "video_url": null,
      "callback_url": null,
      "callback_status": null,
      "created_at": "2026-04-14T07:43:36",
      "updated_at": "2026-04-14T07:43:36"
    }
  ],
  "total": 1
}
```

---

## 2) `POST /api/posts`

创建帖子并关联发布账号。

### 请求体字段

- `business_id` string，必填，唯一
- `post_type` string，可选，枚举：`image|video`
- `title` string，可选
- `content` string，可选
- `tags` string[]，可选
- `image_urls` string[]，可选
- `video_url` string，可选
- `callback_url` string，可选
- `callback_status` string，可选（若传 `callback_url`，默认会补成 `pending`）
- `accounts` / `channels` array，必填，至少一个

`accounts/channels` 每项支持两种格式：

1. 通过账号 ID 关联（推荐）

```json
{ "id": "pa-002" }
```

2. 通过平台 + 账号标识关联（不创建账号，仅查已有）

```json
{ "platform": "tiktok", "channel_id": "photo_daily" }
```

### 业务校验

- `business_id` 已存在：返回 `400`
- 未提供账号：返回 `400`
- 账号不存在（包含 platform+channel_id 查不到）：返回 `400`
- 未提供 `video_url` 且未提供 `image_urls`：返回 `400`

### 请求示例

```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/posts' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-secret-api-key-here' \
  -d '{
    "business_id": "biz-curl-tk-001",
    "title": "按平台账号创建测试",
    "content": "使用 platform + channel_id 传账号",
    "tags": ["tiktok", "photo_daily"],
    "image_urls": ["https://example.com/a.jpg"],
    "accounts": [
      {"platform": "tiktok", "channel_id": "photo_daily"}
    ]
  }'
```

### 成功返回

HTTP 状态码：`201`

`data` 结构与 `GET /api/posts` 的单项一致。

---

## 3) `GET /api/posts/detail`

查询帖子详情（含发布状态列表）。

### Query 参数

- `post_id` string，可选
- `business_id` string，可选

要求：`post_id` 和 `business_id` 至少传一个，否则返回 `400`。

### 成功返回 `data`

```json
{
  "id": "6368297e-3d87-4125-9370-44e2ec02e69b",
  "business_id": "biz-curl-tk-001",
  "status": "pending",
  "post_type": "image",
  "title": "按平台账号创建测试",
  "content": "使用 platform + channel_id 传账号",
  "tags": ["tiktok", "photo_daily"],
  "image_urls": ["https://example.com/a.jpg"],
  "video_url": null,
  "callback_url": null,
  "callback_status": null,
  "created_at": "2026-04-14T07:43:36",
  "updated_at": "2026-04-14T07:43:36",
  "publishes": [
    {
      "id": "e0b4c6ad-44b3-4cbf-bf51-5af05f40779c",
      "platform_account_id": "pa-002",
      "platform_type": "tiktok",
      "username": "photo_daily",
      "nickname": "每日摄影",
      "status": "pending",
      "external_post_id": null,
      "failed_reason": null,
      "published_at": null,
      "created_at": "2026-04-14T07:43:37",
      "updated_at": "2026-04-14T07:43:37"
    }
  ]
}
```

---

## 4) `GET /api/platform-accounts`

分页查询平台账号，支持平台和用户名过滤（用户名模糊匹配）。

### Query 参数

- `page` int，可选，默认 `1`，最小 `1`
- `page_size` int，可选，默认 `20`，范围 `1~200`
- `platform` string，可选，平台枚举见上
- `username` string，可选，模糊匹配（`LIKE %username%`）

兼容参数（隐藏）：`pageSize`、`platform_type`

### 请求示例

```bash
curl -sS 'http://127.0.0.1:8000/api/platform-accounts?page=1&page_size=20&platform=tiktok&username=photo' \
  -H 'X-API-Key: your-secret-api-key-here'
```

### 成功返回 `data`

```json
{
  "items": [
    {
      "id": "pa-002",
      "platform_type": "tiktok",
      "username": "photo_daily",
      "nickname": "每日摄影",
      "remark": "TikTok 官方账号",
      "created_at": "2026-04-14T06:57:20"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

