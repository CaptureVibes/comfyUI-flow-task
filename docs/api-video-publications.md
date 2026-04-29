# Video Publications API

下游发布服务地址：`http://192.168.199.28:8080`

---

## POST /open-api/v1/upload/task

提交视频发布任务。

### 请求体

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `video_url` | string | 发布用视频 URL |
| `original_video_url` | string | 原始视频 URL（拼接 logo 前），为空时等于 `video_url` |
| `video_type` | string | `traffic` / `persona`，默认 `traffic` |
| `title` | string | 发布标题 |
| `description` | string/null | 发布描述 |
| `tags` | string[] | 标签列表 |
| `promotion_code` | string | 8 位数字带货口令 |
| `ext_products` | object[] | 外部商品列表，无商品时为空数组 |
| `channels` | object[] | 发布渠道列表 |
| `channels[].platform` | string | `tiktok` / `youtube` / `instagram` |
| `channels[].channel_id` | string | 渠道 ID |
| `external_id` | string | 关联 ID，使用 `sub_task_id` |
| `callback_url` | string/null | 发布结果回调地址 |

#### ext_products 对象字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | number | 搜索结果 ID |
| `position` | int | 搜索结果排名 |
| `title` | string | 商品标题 |
| `link` | string | 商品详情链接 |
| `source` | string | 商品来源站点 |
| `thumbnail` | string | 商品缩略图 URL |
| `image` | string | 商品主图 URL |
| `price.value` | string | 价格原始文本，如 `$80*` |
| `price.extracted_value` | number | 提取的价格数值 |
| `price.currency` | string | 货币符号 |
| `tier` | number | 商品分层（1 = Official Website） |
| `tier_label` | string | 商品分层展示文案 |
| `product_name` | string | AI 识别的单品名称 |
| `product_description` | string | AI 单品描述 |
| `product_search_query` | string | 商品搜索关键词 |
| `product_search_trace_id` | string | 搜索 trace id |

### 请求示例

```json
{
  "video_url": "https://cdn.alvinclub.com/videos/uploads/2026-04-25/final.mp4",
  "original_video_url": "https://cdn.alvinclub.com/videos/uploads/2026-04-25/final.mp4",
  "video_type": "traffic",
  "title": "Styling the Uniqlo x JW Anderson Spring Jacket ✨ Get my exact look here 👀 👇",
  "description": "Obsessed with this Uniqlo x JW Anderson spring jacket!\n\nLove this look? Search code 27383065 on Alvin's Club to shop the exact outfit.\nmango.com: $80\nCOS: $139\nUrban Outfitters: $170",
  "tags": ["uniqlo", "jwanderson", "springfashion", "gorpcore", "ootd"],
  "promotion_code": "27383065",
  "ext_products": [
    {
      "id": 1,
      "position": 4,
      "title": "Cotton jacket with corduroy collar - Women | MANGO USA",
      "link": "https://shop.mango.com/us/en/p/women/jackets/cotton-jacket-with-corduroy-collar_17085160",
      "source": "mango.com",
      "thumbnail": "https://encrypted-tbn1.gstatic.com/images?q=...",
      "image": "https://media.mango.com/is/image/punto/17085160-06-008?wid=2048",
      "price": { "value": "$80*", "extracted_value": 80.0, "currency": "$" },
      "tier": 1,
      "tier_label": "Official Website",
      "product_name": "米色立领防风夹克",
      "product_description": "一件浅米色宽松版型夹克，采用立领设计和暗门襟。",
      "product_search_query": "一件浅米色宽松版型夹克，采用立领设计和暗门襟。",
      "product_search_trace_id": "7fbff69a-19c4-4d0f-b4ef-6f8683dc68e0"
    }
  ],
  "channels": [
    { "platform": "youtube", "channel_id": "UCJTEWb_kq6Qsd2twFZJKI1A" }
  ],
  "external_id": "ede56eb4-c65e-424a-92a2-9cb32871943c",
  "callback_url": "http://192.168.199.42:8000/api/v1/open-api/callback/publication"
}
```

---

## POST /api/posts（外部发布 API）

部分渠道走外部发布 API（`channel_source == "ext_pub"`）。

### ext_pub 请求体

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `post_type` | string | 固定为 `video` |
| `title` | string | 发布标题 |
| `content` | string | 发布描述 |
| `tags` | string[] | 标签列表 |
| `promotion_code` | string | 8 位数字带货口令 |
| `ext_products` | object[] | 外部商品列表，结构同上 |
| `video_url` | string | 视频 URL |
| `business_id` | string | 关联 ID，使用 `sub_task_id` |
| `accounts` | object[] | 发布账号列表 |
| `accounts[].id` | string | 账号/渠道 ID |

### ext_pub 请求示例

```json
{
  "post_type": "video",
  "title": "Spring Outfit Ideas",
  "content": "Daily outfit inspiration\n\nLove this look? Search code 27383065 on Alvin's Club.",
  "tags": ["outfit", "fashion"],
  "promotion_code": "27383065",
  "ext_products": [],
  "video_url": "https://cdn.alvinclub.com/videos/uploads/2026-04-25/final.mp4",
  "business_id": "d3f8b885-b608-4c72-ae7c-2f50c6f4d1f6",
  "accounts": [{ "id": "pa-002" }]
}
```
