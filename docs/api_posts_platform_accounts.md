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
- `promotion_code` string，可选，8 位数字带货口令；Echo Matrix 发布时会生成并透传
- `ext_products` object[]，可选，外部商品信息列表；可为空数组
- `callback_url` string，可选
- `callback_status` string，可选（若传 `callback_url`，默认会补成 `pending`）
- `accounts` / `channels` array，必填，至少一个

`ext_products` 每项字段：

- `id` string/number，可选，外部商品 ID 或搜索结果 ID
- `position` int，可选，搜索结果排名
- `title` string，可选，商品标题
- `link` string，可选，商品详情链接
- `source` string，可选，商品来源或站点
- `thumbnail` string，可选，商品缩略图 URL
- `image` string，可选，商品主图 URL
- `price` any，可选，商品价格信息，透传搜索接口返回值
- `tier` string/number，可选，商品分层标记，透传搜索接口返回值
- `tier_label` string，可选，商品分层展示文案
- `product_name` string，可选，AI 单品名称
- `product_description` string，可选，AI 单品描述
- `product_search_query` string，可选，商品搜索关键词
- `product_search_trace_id` string，可选，商品搜索 trace id

Echo Matrix 会从 `video_tasks.shots[].ext_products` 聚合 `ext_products`。如果 AI 商品搜索没有命中 `topMatch`，该数组可以为空。

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
    "post_type": "video",
    "title": "带货视频发布测试",
    "content": "使用 platform + channel_id 传账号",
    "tags": ["tiktok", "outfit"],
    "video_url": "https://example.com/video.mp4",
    "promotion_code": "12345678",
    "ext_products": [
      {
        "title": "Black leather shoulder bag",
        "link": "https://shop.example.com/products/bag-001",
        "source": "Example Shop",
        "image": "https://cdn.example.com/products/bag-001.jpg",
        "product_description": "black leather shoulder bag with gold hardware"
      }
    ],
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
  "post_type": "video",
  "title": "带货视频发布测试",
  "content": "使用 platform + channel_id 传账号",
  "tags": ["tiktok", "outfit"],
  "image_urls": [],
  "video_url": "https://example.com/video.mp4",
  "promotion_code": "12345678",
  "ext_products": [
    {
      "title": "Black leather shoulder bag",
      "link": "https://shop.example.com/products/bag-001",
      "source": "Example Shop",
      "image": "https://cdn.example.com/products/bag-001.jpg",
      "product_description": "black leather shoulder bag with gold hardware"
    }
  ],
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
