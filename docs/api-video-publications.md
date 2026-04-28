# Video Publications API 文档

Base URL: `http://localhost:8000/api/v1`

本文档描述 Echo Matrix 自身的视频发布接口。该接口负责创建 `video_publications` 记录，并把视频、渠道、带货口令和外部商品信息提交到下游发布服务。

## 1. 创建视频发布任务

### `POST /video-publications`

创建一个视频发布任务。调用成功后系统会：

1. 校验 `sub_task_id` 对应的视频子任务存在、已选中、状态允许发布，且已有 `result_video_url`
2. 从口令分发器获取唯一 8 位数字 `promotion_code`
3. 从父任务 `video_tasks.shots[].ext_products` 聚合外部商品信息
4. 按渠道来源提交到内部 Open API 或外部发布 API
5. 写入 `video_publications.request_payload`、`promotion_code`、`ext_products`、`channels_status`

### 请求体

`promotion_code` 和 `ext_products` 不由前端传入，发布服务会自动生成和聚合。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sub_task_id` | UUID | 是 | 要发布的视频子任务 ID |
| `video_url` | string | 是 | 发布用视频 URL，通常是子任务最终视频或拼 logo 后的视频 |
| `original_video_url` | string | 否 | 原始视频 URL；为空时使用 `video_url` |
| `video_type` | string | 否 | 视频类型；为空时默认 `traffic` |
| `title` | string | 是 | 发布标题 |
| `description` | string | 否 | 发布描述 |
| `tags` | string[] | 否 | 标签列表 |
| `channels` | object[] | 是 | 发布渠道，至少 1 个 |
| `channels[].platform` | string | 是 | `tiktok` / `youtube` / `instagram` |
| `channels[].channel_id` | string | 是 | 渠道 ID |
| `channels[].channel_name` | string | 否 | 渠道展示名，仅用于状态展示兜底 |
| `channels[].channel_source` | string | 否 | `openapi` 或 `ext_pub`；为空按 `openapi` 处理 |
| `callback_url` | string | 否 | 下游 Open API 回调地址；为空时使用后端配置 |

### 请求示例

```json
{
  "sub_task_id": "d3f8b885-b608-4c72-ae7c-2f50c6f4d1f6",
  "video_url": "https://cdn.example.com/videos/final.mp4",
  "original_video_url": "https://cdn.example.com/videos/raw.mp4",
  "video_type": "traffic",
  "title": "Spring Outfit Ideas",
  "description": "Daily outfit inspiration",
  "tags": ["outfit", "fashion"],
  "channels": [
    {
      "platform": "tiktok",
      "channel_id": "pa-002",
      "channel_name": "photo_daily",
      "channel_source": "ext_pub"
    },
    {
      "platform": "youtube",
      "channel_id": "UCxxxxxxxx",
      "channel_name": "Daily Outfit",
      "channel_source": "openapi"
    }
  ]
}
```

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 发布记录 ID |
| `sub_task_id` | UUID | 子任务 ID |
| `open_api_task_id` | string/null | 内部 Open API 返回的任务 ID；纯 `ext_pub` 发布为空 |
| `external_id` | string/null | 外部关联 ID，当前使用 `sub_task_id` |
| `status` | string | 汇总发布状态：`pending` / `processing` / `completed` / `partial` / `failed` |
| `total_channels` | int | 渠道总数 |
| `completed_channels` | int | 成功渠道数 |
| `failed_channels` | int | 失败渠道数 |
| `channels_status` | object[]/null | 渠道级发布状态 |
| `promotion_code` | string/null | 发布时生成的 8 位数字带货口令 |
| `ext_products` | object[]/null | 发布时从 `video_tasks.shots[].ext_products` 聚合的外部商品快照 |
| `error_message` | string/null | 发布失败信息 |
| `callback_received` | boolean | 是否收到 Open API 回调 |
| `created_at` | datetime/null | 创建时间 |
| `updated_at` | datetime/null | 更新时间 |
| `completed_at` | datetime/null | 完成时间 |

### 响应示例

```json
{
  "id": "a7c13eaa-e16b-4896-8d4d-4df4b4a7b807",
  "sub_task_id": "d3f8b885-b608-4c72-ae7c-2f50c6f4d1f6",
  "open_api_task_id": "550e8400-e29b-41d4-a716-446655440000",
  "external_id": "d3f8b885-b608-4c72-ae7c-2f50c6f4d1f6",
  "status": "processing",
  "total_channels": 2,
  "completed_channels": 1,
  "failed_channels": 0,
  "promotion_code": "12345678",
  "ext_products": [
    {
      "title": "Black leather shoulder bag",
      "link": "https://shop.example.com/products/bag-001",
      "source": "Example Shop",
      "image": "https://cdn.example.com/products/bag-001.jpg",
      "product_description": "black leather shoulder bag with gold hardware",
      "product_search_trace_id": "trace-001"
    }
  ],
  "channels_status": [
    {
      "platform": "tiktok",
      "channel_id": "pa-002",
      "channel_name": "photo_daily",
      "status": "completed",
      "platform_video_id": null,
      "platform_video_url": null,
      "error_message": null,
      "uploaded_at": "2026-04-28T10:00:00Z"
    },
    {
      "platform": "youtube",
      "channel_id": "UCxxxxxxxx",
      "channel_name": "Daily Outfit",
      "status": "pending",
      "platform_video_id": null,
      "platform_video_url": null,
      "error_message": null,
      "uploaded_at": null
    }
  ],
  "error_message": null,
  "callback_received": false,
  "created_at": "2026-04-28T10:00:00Z",
  "updated_at": "2026-04-28T10:00:00Z",
  "completed_at": null
}
```

## 2. 商品字段来源

`ext_products` 的来源链路：

1. AI 流程生成单品图和单品描述
2. 商品搜图接口用单品描述 + 单品图搜索商品
3. 命中 `topMatch` 后，商品图用于最终造型图生成
4. 命中商品被写入 `video_tasks.shots[].solo_products[].matched_product`
5. `ext_product_service` 从命中商品生成 `video_tasks.shots[].ext_products`
6. 发布时从 `video_tasks.shots[].ext_products` 聚合到 `video_publications.ext_products`

如果没有命中商品，`ext_products` 会是空数组，发布仍然可以继续。

当前每个 `ext_products[]` 可能包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string/number | 外部商品 ID 或搜索结果 ID |
| `position` | int | 搜索结果排名 |
| `title` | string | 商品标题 |
| `link` | string | 商品详情链接 |
| `source` | string | 商品来源或站点 |
| `thumbnail` | string | 商品缩略图 URL |
| `image` | string | 商品主图 URL |
| `price` | any | 商品价格信息 |
| `tier` | string/number | 商品分层标记 |
| `tier_label` | string | 商品分层展示文案 |
| `product_name` | string | AI 单品名称 |
| `product_description` | string | AI 单品描述 |
| `product_search_query` | string | 商品搜索关键词 |
| `product_search_trace_id` | string | 商品搜索 trace id |

## 3. 下游 payload

### 内部 Open API

`channel_source != "ext_pub"` 的渠道会提交到 `POST /open-api/v1/upload/task`：

```json
{
  "video_url": "https://cdn.example.com/videos/final.mp4",
  "original_video_url": "https://cdn.example.com/videos/raw.mp4",
  "video_type": "traffic",
  "title": "Spring Outfit Ideas",
  "description": "Daily outfit inspiration",
  "tags": ["outfit", "fashion"],
  "promotion_code": "12345678",
  "ext_products": [],
  "channels": [
    { "platform": "youtube", "channel_id": "UCxxxxxxxx" }
  ],
  "external_id": "d3f8b885-b608-4c72-ae7c-2f50c6f4d1f6"
}
```

### 外部发布 API

`channel_source == "ext_pub"` 的渠道会提交到 `POST /api/posts`：

```json
{
  "post_type": "video",
  "title": "Spring Outfit Ideas",
  "content": "Daily outfit inspiration",
  "tags": ["outfit", "fashion"],
  "promotion_code": "12345678",
  "ext_products": [],
  "video_url": "https://cdn.example.com/videos/final.mp4",
  "business_id": "d3f8b885-b608-4c72-ae7c-2f50c6f4d1f6",
  "accounts": [
    { "id": "pa-002" }
  ]
}
```

## 4. 相关接口

- `GET /video-publications/{publication_id}`：查看发布详情，包含 `request_payload` 和 `response_data`
- `GET /video-publications/subtask/{sub_task_id}`：查看子任务的发布记录
- `POST /video-publications/{publication_id}/sync`：主动同步内部 Open API 发布状态
- `GET /video-publications/stats`：数据统计页发布列表，返回 `promotion_code` 和 `ext_products`
- `GET /video-publications/stats/export`：导出数据统计 CSV

