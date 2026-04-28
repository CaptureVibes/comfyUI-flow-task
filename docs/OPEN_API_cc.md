# Open API 文档

对外开放的视频管理 API，支持多渠道（TikTok、YouTube、Instagram）视频上传和渠道查询。

**Base URL**: `/open-api/v1`

---

## 目录

- [认证方式](#认证方式)
- [签名规则](#签名规则)
- [限流说明](#限流说明)
- [API 接口](#api-接口)
  - [渠道列表](#1-获取渠道列表)
  - [查询渠道授权状态](#2-查询渠道授权状态)
  - [创建上传任务](#3-创建视频上传任务)
  - [查询上传状态](#4-查询上传任务状态)
  - [查询渠道视频指标](#5-查询上传任务渠道视频指标)
  - [健康检查](#6-健康检查)
  - [生成测试签名](#7-生成测试签名仅开发模式)
- [回调说明](#回调说明)
- [错误码](#错误码)

---

## 认证方式

所有需要签名的接口必须传递以下参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| client_id | string | 是 | 客户端ID，由管理员创建 |
| timestamp | int | 是 | 当前 Unix 时间戳（秒） |
| signature | string | 是 | 请求签名，见下方签名规则 |

**请求头**（可选）：`X-API-Key` / `X-Client-Id` 可代替 `client_id`；`X-Signature` / `X-Timestamp` 可代替对应参数。

**环境说明**：`ENV` 非 `production` 时可能放宽签名校验；生产环境须使用有效 `client_id` + `client_secret` 签名。

---

## 签名规则

1. 将所有请求参数（除 `signature` 外）按 key 字母排序
2. 将每个参数值转为**规范字符串**后拼接成 `key1=value1&key2=value2` 格式
3. 追加 `&timestamp={timestamp}`
4. 使用 `client_secret` 对上述字符串进行 **HMAC-SHA256** 签名
5. 将签名结果转为小写十六进制字符串

**参数值规范序列化**（数组、对象、日期必须按此规则）：数组/对象用紧凑 JSON（对象 key 排序），日期用 ISO8601。

**时间戳有效期**：默认 300 秒（5 分钟），超时签名将失效。

---

## 限流说明

- 每个客户端有独立的限流配置（默认 100 次/分钟）
- 使用滑动窗口算法
- 超限返回 `429 Too Many Requests`

---

## API 接口

### 1. 获取渠道列表

`GET /open-api/v1/channels`

根据平台类型获取渠道列表，返回统一格式。

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| platform | string | 是 | 平台类型：`tiktok` / `youtube` / `instagram` |
| page | int | 否 | 页码，默认 1 |
| page_size | int | 否 | 每页数量，默认 20，最大 **1000** |
| usage_types | string[] | 否 | 按用途类型筛选（与各平台 `usage_type` 一致） |
| client_id | string | 是 | 客户端ID |
| timestamp | int | 是 | 时间戳 |
| signature | string | 是 | 签名 |

当前接口固定只返回已启用渠道，不提供 `is_active` 查询参数。详见主文档 `OPEN_API.md`。

**Demo 示例**（本地计算签名）：

```bash
CLIENT_ID="default_client"
CLIENT_SECRET="your_client_secret"
TIMESTAMP=$(date +%s)
SIGNATURE=$(python3 -c "
import hmac, hashlib
params = {'client_id': '$CLIENT_ID', 'page': 1, 'page_size': 20, 'platform': 'tiktok'}
params = {k: v for k, v in params.items() if v is not None and v != ''}
param_str = '&'.join(f\"{k}={v}\" for k, v in sorted(params.items()))
print(hmac.new('$CLIENT_SECRET'.encode(), f\"{param_str}&timestamp=$TIMESTAMP\".encode(), hashlib.sha256).hexdigest())
")
curl "http://localhost:8000/open-api/v1/channels?platform=tiktok&page=1&page_size=20&client_id=$CLIENT_ID&timestamp=$TIMESTAMP&signature=$SIGNATURE"
```

```python
# Python：查询渠道列表（本地计算签名）
import hmac, hashlib, json, time, requests
from datetime import datetime, date

def _value_to_sign_str(v):
    if v is None: return ""
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, (datetime, date)): return v.isoformat()
    if isinstance(v, (list, dict)): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(v)

def generate_signature(params, secret, timestamp):
    filtered = {k: v for k, v in params.items() if k != "signature" and v is not None and v != ""}
    param_str = "&".join(f"{k}={_value_to_sign_str(v)}" for k, v in sorted(filtered.items()))
    return hmac.new(secret.encode(), f"{param_str}&timestamp={timestamp}".encode(), hashlib.sha256).hexdigest()

BASE, CLIENT_ID, CLIENT_SECRET = "http://localhost:8000/open-api/v1", "default_client", "your_client_secret"
params = {"platform": "tiktok", "page": 1, "page_size": 20, "client_id": CLIENT_ID, "timestamp": int(time.time())}
params["signature"] = generate_signature(params, CLIENT_SECRET, params["timestamp"])
print(requests.get(f"{BASE}/channels", params=params).json())
```

**响应示例**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 10,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "platform": "tiktok",
        "channel_id": "user_123",
        "channel_name": "示例用户",
        "username": "example_user",
        "description": "简介",
        "thumbnail_url": "https://...",
        "follower_count": 1000,
        "video_count": 50,
        "is_active": true,
        "extra": {},
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00"
      }
    ]
  }
}
```

---

### 2. 查询渠道授权状态

`GET /open-api/v1/channels/authorization`

查询指定用户 / 频道在**本地是否已有渠道档案**（**无需** `client_id`、`timestamp`、`signature`）。**不校验 OAuth 令牌**，仅判断库内是否存在 `users` / `yt_channels` / `ig_channels` 及是否启用。

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| platform | string | 是 | `tiktok` / `youtube` / `instagram` |
| channel_id | string | 是 | **TikTok**：`users.id` 或 **username（handle，可带 @）**。**YouTube**：频道 ID。**Instagram**：`account_id` 或 **username** |

**响应字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| authorized | boolean | 是否存在对应档案 |
| status | string | `NOT_FOUND` / `ACTIVE`（启用）/ `DISABLED`（已禁用） |

**响应示例**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "authorized": true,
    "status": "ACTIVE"
  }
}
```

**Demo 示例**：

```bash
curl "http://localhost:8000/open-api/v1/channels/authorization?platform=tiktok&channel_id=YOUR_USER_ID"
```

```python
import requests

BASE = "http://localhost:8000/open-api/v1"
r = requests.get(
    f"{BASE}/channels/authorization",
    params={"platform": "youtube", "channel_id": "UCxxxxxxxx"},
)
print(r.json())
```

更多说明见 `OPEN_API.md` 对应章节。

---

### 3. 创建视频上传任务

`POST /open-api/v1/upload/task`

创建视频上传任务，支持同时上传到多个渠道。

**Request Body**（JSON）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| video_url | string | 是 | 视频 URL，须 `http`/`https` 且扩展名为 **`.mp4` 或 `.mov`** |
| original_video_url | string | 否 | 原始视频 URL |
| video_type | string | 否 | 视频类型（最长 100 字符） |
| product_info | object[] | 否 | 商品信息列表；兼容单对象写法 |
| product_info[].product_code | string | 否 | 商品编码 |
| product_info[].sku_code | string | 否 | SKU 编码 |
| promotion_code | string | 否 | 带货口令，8 位数字字符串；由调用方生成并保证唯一 |
| ext_products | object[] | 否 | 外部商品信息列表，可为空数组；Echo Matrix 从 `video_tasks.shots[].ext_products` 聚合 |
| ext_products[].id | string/number | 否 | 外部商品 ID 或搜索结果 ID |
| ext_products[].position | int | 否 | 搜索结果排名 |
| ext_products[].title | string | 否 | 商品标题 |
| ext_products[].link | string | 否 | 商品详情链接 |
| ext_products[].source | string | 否 | 商品来源或站点 |
| ext_products[].thumbnail | string | 否 | 商品缩略图 URL |
| ext_products[].image | string | 否 | 商品主图 URL |
| ext_products[].price | any | 否 | 商品价格信息，透传搜索接口返回值 |
| ext_products[].tier | string/number | 否 | 商品分层标记，透传搜索接口返回值 |
| ext_products[].tier_label | string | 否 | 商品分层展示文案 |
| ext_products[].product_name | string | 否 | AI 单品名称 |
| ext_products[].product_description | string | 否 | AI 单品描述 |
| ext_products[].product_search_query | string | 否 | 商品搜索关键词 |
| ext_products[].product_search_trace_id | string | 否 | 商品搜索 trace id |
| title | string | 是 | 视频标题，**1–100** 字符 |
| description | string | 否 | 视频描述（最长 5000 字符） |
| tags | string[] | 否 | 标签列表 |
| comments | string[] | 否 | 预置评论文案 |
| channels | array | 是 | 至少 1 个；`platform`+`channel_id` 不可重复 |
| channels[].platform | string | 是 | `tiktok` / `youtube` / `instagram` |
| channels[].channel_id | string | 是 | 渠道 ID |
| channels[].title | string | 否 | 渠道自定义标题 |
| channels[].description | string | 否 | 渠道自定义描述 |
| channels[].tags | string[] | 否 | 渠道自定义标签 |
| channels[].privacy_level | string | 否 | `public` / `private` / `unlisted` |
| channels[].schedule_time | datetime | 否 | 定时发布时间 |
| channels[].extra_config | object | 否 | 扩展配置 |
| channels[].made_for_kids | boolean | 否 | 仅 YouTube 生效，默认 false |
| external_id | string | 否 | 外部系统 ID |
| callback_url | string | 否 | 回调 URL |
| source_task_id | string | 否 | 来源任务 ID |
| client_id | string | 是 | 客户端 ID |
| timestamp | int | 是 | 时间戳 |
| signature | string | 是 | 签名 |

**Demo 示例**（本地计算签名）：

```bash
CLIENT_ID="default_client"
CLIENT_SECRET="your_client_secret"
TIMESTAMP=$(date +%s)
SIGNATURE=$(python3 -c "
import hmac, hashlib, json
body = {'video_url': 'https://example.com/video.mp4', 'original_video_url': 'https://cdn.example.com/raw/video.mp4',
  'video_type': 'persona/traffic', 'product_info': [{'product_code': 'P001', 'sku_code': 'SKU001'}],
  'promotion_code': '12345678',
  'ext_products': [{'title': 'Black leather shoulder bag', 'link': 'https://shop.example.com/products/bag-001', 'source': 'Example Shop', 'image': 'https://cdn.example.com/products/bag-001.jpg'}],
  'title': '测试视频', 'description': '视频描述',
  'tags': ['tag1', 'tag2'], 'channels': [{'platform': 'tiktok', 'channel_id': 'user_123'}, {'platform': 'youtube', 'channel_id': 'channel_456'}],
  'external_id': 'ext_001', 'client_id': '$CLIENT_ID', 'timestamp': $TIMESTAMP}
def _v(v):
    if v is None: return ''
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, (list, dict)): return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return str(v)
f = {k: v for k, v in body.items() if v is not None and v != ''}
s = '&'.join(f\"{k}={_v(v)}\" for k, v in sorted(f.items()))
print(hmac.new('$CLIENT_SECRET'.encode(), f\"{s}&timestamp=$TIMESTAMP\".encode(), hashlib.sha256).hexdigest())
")
curl -X POST "http://localhost:8000/open-api/v1/upload/task" -H "Content-Type: application/json" -d "{
  \"video_url\": \"https://example.com/video.mp4\", \"original_video_url\": \"https://cdn.example.com/raw/video.mp4\",
  \"video_type\": \"persona/traffic\", \"product_info\": [{\"product_code\": \"P001\", \"sku_code\": \"SKU001\"}],
  \"promotion_code\": \"12345678\",
  \"ext_products\": [{\"title\": \"Black leather shoulder bag\", \"link\": \"https://shop.example.com/products/bag-001\", \"source\": \"Example Shop\", \"image\": \"https://cdn.example.com/products/bag-001.jpg\"}],
  \"title\": \"测试视频\", \"description\": \"视频描述\",
  \"tags\": [\"tag1\", \"tag2\"], \"channels\": [{\"platform\": \"tiktok\", \"channel_id\": \"user_123\"}, {\"platform\": \"youtube\", \"channel_id\": \"channel_456\"}],
  \"external_id\": \"ext_001\", \"client_id\": \"$CLIENT_ID\", \"timestamp\": $TIMESTAMP, \"signature\": \"$SIGNATURE\"
}"
```

```python
# Python：创建上传任务（本地计算签名）
import hmac, hashlib, json, time, requests
from datetime import datetime, date

def _value_to_sign_str(v):
    if v is None: return ""
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, (datetime, date)): return v.isoformat()
    if isinstance(v, (list, dict)): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(v)

def generate_signature(params, secret, timestamp):
    filtered = {k: v for k, v in params.items() if k != "signature" and v is not None and v != ""}
    param_str = "&".join(f"{k}={_value_to_sign_str(v)}" for k, v in sorted(filtered.items()))
    return hmac.new(secret.encode(), f"{param_str}&timestamp={timestamp}".encode(), hashlib.sha256).hexdigest()

BASE, CLIENT_ID, CLIENT_SECRET = "http://localhost:8000/open-api/v1", "default_client", "your_client_secret"
payload = {"video_url": "https://example.com/video.mp4", "original_video_url": "https://cdn.example.com/raw/video.mp4",
  "video_type": "persona/traffic", "product_info": [{"product_code": "P001", "sku_code": "SKU001"}],
  "promotion_code": "12345678",
  "ext_products": [{"title": "Black leather shoulder bag", "link": "https://shop.example.com/products/bag-001", "source": "Example Shop", "image": "https://cdn.example.com/products/bag-001.jpg"}],
  "title": "测试视频", "description": "视频描述",
  "tags": ["tag1", "tag2"], "channels": [{"platform": "tiktok", "channel_id": "user_123"}, {"platform": "youtube", "channel_id": "channel_456"}],
  "external_id": "ext_001", "client_id": CLIENT_ID, "timestamp": int(time.time())}
payload["signature"] = generate_signature(payload, CLIENT_SECRET, payload["timestamp"])
print(requests.post(f"{BASE}/upload/task", json=payload).json())
```

**响应示例**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "client_id": "default_client",
    "external_id": "ext_123",
    "video_url": "https://example.com/video.mp4",
    "original_video_url": "https://cdn.example.com/raw/video.mp4",
    "video_type": "persona/traffic",
    "product_info": [
      {
        "product_code": "P001",
        "sku_code": "SKU001"
      }
    ],
    "promotion_code": "12345678",
    "ext_products": [
      {
        "title": "Black leather shoulder bag",
        "link": "https://shop.example.com/products/bag-001",
        "source": "Example Shop",
        "image": "https://cdn.example.com/products/bag-001.jpg"
      }
    ],
    "title": "视频标题",
    "description": "视频描述",
    "tags": ["tag1", "tag2"],
    "comments": null,
    "source_task_id": null,
    "callback_url": null,
    "callback_retries": 0,
    "callback_success": 0,
    "error_message": null,
    "status": "pending",
    "total_channels": 2,
    "completed_channels": 0,
    "failed_channels": 0,
    "channels": [
      {
        "platform": "tiktok",
        "channel_id": "user_123",
        "channel_name": "示例用户",
        "status": "pending",
        "error_message": null,
        "platform_video_id": null,
        "platform_video_url": null,
        "upload_id": null,
        "upload_task_id": null,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "uploaded_at": null
      }
    ],
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
    "completed_at": null
  }
}
```

**任务状态**：`pending` → `processing` → `uploading` → `completed` / `partial` / `failed`（回调字段含义见 `OPEN_API.md`）

---

### 4. 查询上传任务状态

`GET /open-api/v1/upload/status`

通过 task_id 或 external_id 查询任务状态。

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | 二选一 | 任务 ID |
| external_id | string | 二选一 | 外部系统 ID |
| client_id | string | 是 | 客户端 ID |
| timestamp | int | 是 | 时间戳 |
| signature | string | 是 | 签名 |

**Demo 示例**（本地计算签名）：

```bash
CLIENT_ID="default_client"
CLIENT_SECRET="your_client_secret"
TIMESTAMP=$(date +%s)
TASK_ID="550e8400-e29b-41d4-a716-446655440000"
SIGNATURE=$(python3 -c "
import hmac, hashlib
params = {'client_id': '$CLIENT_ID', 'task_id': '$TASK_ID'}
params = {k: v for k, v in params.items() if v}
param_str = '&'.join(f\"{k}={v}\" for k, v in sorted(params.items()))
print(hmac.new('$CLIENT_SECRET'.encode(), f\"{param_str}&timestamp=$TIMESTAMP\".encode(), hashlib.sha256).hexdigest())
")
curl "http://localhost:8000/open-api/v1/upload/status?task_id=$TASK_ID&client_id=$CLIENT_ID&timestamp=$TIMESTAMP&signature=$SIGNATURE"
```

```python
# Python：查询上传任务状态（本地计算签名）
import hmac, hashlib, json, time, requests
from datetime import datetime, date

def _value_to_sign_str(v):
    if v is None: return ""
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, (datetime, date)): return v.isoformat()
    if isinstance(v, (list, dict)): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(v)

def generate_signature(params, secret, timestamp):
    filtered = {k: v for k, v in params.items() if k != "signature" and v is not None and v != ""}
    param_str = "&".join(f"{k}={_value_to_sign_str(v)}" for k, v in sorted(filtered.items()))
    return hmac.new(secret.encode(), f"{param_str}&timestamp={timestamp}".encode(), hashlib.sha256).hexdigest()

BASE, CLIENT_ID, CLIENT_SECRET = "http://localhost:8000/open-api/v1", "default_client", "your_client_secret"
params = {"task_id": "550e8400-e29b-41d4-a716-446655440000", "client_id": CLIENT_ID, "timestamp": int(time.time())}
params["signature"] = generate_signature(params, CLIENT_SECRET, params["timestamp"])
print(requests.get(f"{BASE}/upload/status", params=params).json())
```

**响应**：与创建任务返回格式相同，包含最新状态。

---

### 5. 查询上传任务渠道视频指标

`GET /open-api/v1/upload/metrics`

根据 task_id 或 external_id 查询任务各渠道的视频基本信息及数据指标。各平台返回各自的 stats 结构。

**Query 参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| task_id | string | 二选一 | 任务 ID |
| external_id | string | 二选一 | 外部系统 ID |
| client_id | string | 是 | 客户端 ID |
| timestamp | int | 是 | 时间戳 |
| signature | string | 是 | 签名 |

**Demo 示例**（本地计算签名）：

```bash
CLIENT_ID="default_client"
CLIENT_SECRET="your_client_secret"
TIMESTAMP=$(date +%s)
TASK_ID="550e8400-e29b-41d4-a716-446655440000"
SIGNATURE=$(python3 -c "
import hmac, hashlib
params = {'client_id': '$CLIENT_ID', 'task_id': '$TASK_ID'}
params = {k: v for k, v in params.items() if v}
param_str = '&'.join(f\"{k}={v}\" for k, v in sorted(params.items()))
print(hmac.new('$CLIENT_SECRET'.encode(), f\"{param_str}&timestamp=$TIMESTAMP\".encode(), hashlib.sha256).hexdigest())
")
curl "http://localhost:8000/open-api/v1/upload/metrics?task_id=$TASK_ID&client_id=$CLIENT_ID&timestamp=$TIMESTAMP&signature=$SIGNATURE"
```

```python
# Python：查询渠道视频指标（本地计算签名）
params = {"task_id": "550e8400-e29b-41d4-a716-446655440000", "client_id": CLIENT_ID, "timestamp": int(time.time())}
# 或 params = {"external_id": "ext_001", "client_id": CLIENT_ID, "timestamp": int(time.time())}
params["signature"] = generate_signature(params, CLIENT_SECRET, params["timestamp"])
print(requests.get(f"{BASE}/upload/metrics", params=params).json())
```

**响应示例**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "open_task_xxx",
    "external_id": "ext_001",
    "title": "视频标题",
    "status": "completed",
    "total_channels": 2,
    "completed_channels": 2,
    "completed_at": "2024-01-15T10:30:00",
    "channels": [
      {
        "platform": "tiktok",
        "channel_id": "user123",
        "channel_name": "账号名",
        "status": "completed",
        "platform_video_id": "7123456789",
        "platform_video_url": "https://...",
        "video_info": {
          "title": "视频标题",
          "video_id": "7123456789",
          "status": "completed",
          "uploaded_at": "2024-01-15T10:00:00"
        },
        "stats": {
          "view_count": 1000,
          "like_count": 50,
          "comment_count": 10,
          "share_count": 5,
          "download_count": 2,
          "collected_at": "2024-01-16T08:00:00"
        }
      },
      {
        "platform": "youtube",
        "video_info": { "title": "...", "video_id": "...", "duration": 120, ... },
        "stats": {
          "views": 5000,
          "engaged_views": 3000,
          "likes": 200,
          "comments": 50,
          "shares": 20,
          "average_view_duration": 45.5,
          "analytics_date": "2024-01-16T08:00:00"
        }
      },
      {
        "platform": "instagram",
        "video_info": { "caption": "...", "media_id": "...", ... },
        "stats": {
          "view_count": 500,
          "reach_count": 400,
          "impressions_count": 600,
          "like_count": 30,
          "comment_count": 5,
          "share_count": 2,
          "save_count": 10,
          "total_interactions": 47,
          "avg_watch_time": 15000,
          "stats_date": "2024-01-16T08:00:00"
        }
      }
    ]
  }
}
```

**各平台数据来源**：

| 平台 | 视频信息表 | 统计数据表 |
|------|------------|------------|
| tiktok | videos | video_stats |
| youtube | yt_videos | yt_video_analytics |
| instagram | ig_media | ig_media_stats |

**各平台 stats 字段**：

| 平台 | 主要指标 |
|------|----------|
| tiktok | view_count, like_count, comment_count, share_count, download_count |
| youtube | views, engaged_views, estimated_minutes_watched, average_view_duration, comments, likes, dislikes, shares, average_view_percentage, subscribers_gained, subscribers_lost |
| instagram | view_count, reach_count, impressions_count, like_count, comment_count, share_count, save_count, total_interactions, avg_watch_time 等 |

**说明**：stats 需由同步任务采集，未采集时返回 `null`。

---

### 6. 健康检查

`GET /open-api/v1/health`

无需签名。

**响应示例**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "status": "ok",
    "enabled": true,
    "version": "v1"
  }
}
```

---

### 7. 生成测试签名（仅开发模式）

`GET /open-api/v1/signature/generate`

仅在 `DEBUG=true` 时可用，用于生成测试签名。

**Query 参数**：`client_id`

**响应示例**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "client_id": "default_client",
    "timestamp": 1704067200,
    "signature": "abc123...",
    "client_secret_hint": "30441459...",
    "note": "仅用于开发测试"
  }
}
```

**Demo 示例**（本地计算签名，无需调用此接口）：

```python
import hmac, hashlib, json, time
from datetime import datetime, date

def _value_to_sign_str(v):
    if v is None: return ""
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, (datetime, date)): return v.isoformat()
    if isinstance(v, (list, dict)): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(v)

def generate_signature(params, secret, timestamp):
    filtered = {k: v for k, v in params.items() if k != "signature" and v is not None and v != ""}
    param_str = "&".join(f"{k}={_value_to_sign_str(v)}" for k, v in sorted(filtered.items()))
    return hmac.new(secret.encode(), f"{param_str}&timestamp={timestamp}".encode(), hashlib.sha256).hexdigest()

params = {"client_id": "default_client", "timestamp": int(time.time())}
print(generate_signature(params, "your_client_secret", params["timestamp"]))
```

---

## 回调说明

任务完成后向 `callback_url` 发送 POST JSON。完整字段与**回调签名**（使用 **`OPEN_API_SECRET_KEY`**，非 `client_secret`）见主文档 `OPEN_API.md` 的「回调说明」。

**重试**：最多 3 次。

---

## 错误码

| code | 说明 |
|------|------|
| 0 | 成功 |
| 400 | 请求参数错误 |
| 401 | 签名验证失败 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |

Open API 未启用时可能返回 HTTP **503**。完整说明见 `OPEN_API.md`。

---

## 快速开始

1. 联系管理员创建客户端，获取 `client_id` 和 `client_secret`
2. 调用 `GET /channels?platform=tiktok` 获取可用的渠道列表
3. 调用 `POST /upload/task` 创建上传任务，传入 `video_url`、`title`、`channels`（可选 `original_video_url`、`video_type`、`product_info`、`promotion_code`、`ext_products`）
4. 通过 `task_id` 调用 `GET /upload/status` 轮询状态，或配置 `callback_url` 接收回调
5. 任务完成后，调用 `GET /upload/metrics` 查询各渠道视频数据指标（播放量、点赞、评论等）
