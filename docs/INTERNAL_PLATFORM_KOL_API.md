# Internal Platform KOL API

独立文档：创建站内 KOL 接口。

Base URL: `/open-api/v1`

---

## 接口

`POST /open-api/v1/internal-platform/kol`

用途：

- 基于来源平台账号创建站内 KOL
- 服务端按 `tenant + source_platform + source_user_id` 查重
- 如果 mapping 已存在，直接返回已有绑定结果
- 如果 mapping 不存在，先创建 KOL，再写入 `internal_platform_user_mappings`

---

## 认证

认证方式与现有 Open API 完全一致，仍然走 `verify_open_api_request`。

请求必须包含：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| client_id | string | 是 | Open API 客户端 ID |
| timestamp | int | 是 | Unix 时间戳（秒） |
| signature | string | 是 | HMAC-SHA256 签名 |

也支持请求头：

- `X-API-Key` / `X-Client-Id`
- `X-Signature`
- `X-Timestamp`

签名规则与 [OPEN_API.md](/Users/guyin/PycharmProjects/tiktok_upload/docs/OPEN_API.md:1) 相同。

---

## 请求参数

Request Body: `application/json`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| nickname | string | 是 | KOL 昵称 |
| source_platform | string | 是 | 来源平台：`tiktok` / `youtube` / `instagram` |
| source_user_id | string | 是 | 来源平台用户 ID / 频道 ID |
| description | string | 否 | KOL 简介 |
| avatar | string/object | 否 | 头像；支持 URL 字符串，或 `{ "url": "https://..." }` |
| tags | string[] | 否 | 标签列表 |
| client_id | string | 是 | Open API 客户端 ID |
| timestamp | int | 是 | Unix 时间戳（秒） |
| signature | string | 是 | 请求签名 |

说明：

- `tenantCode` 不对外开放，服务端使用默认配置
- `status` 不对外开放，内部固定传 `0`
- `kol_id` 不对外开放
- `user_id` 不对外传入，服务端会内部生成稳定值

### 来源平台说明

`source_platform` 用来声明 `source_user_id` 属于哪个平台，两者必须成对使用。

支持值：

| source_platform | source_user_id 应传什么 |
|------|------|
| `tiktok` | TikTok 用户 ID。优先传系统内实际使用的 `users.id`，不要传展示昵称 |
| `youtube` | YouTube 频道 ID，例如 `UC...` |
| `instagram` | Instagram 账号 ID。优先传系统内实际使用的 `account_id`，不要传展示昵称 |

补充说明：

- 不要传 `channel_name`、`nickname`、`display_name` 这类会变化的展示字段
- 这个组合既参与查重，也参与稳定 `user_id` 生成，所以必须长期稳定
- 如果同一真实账号换了 `source_user_id`，服务端会视为一个新的来源账号

如果你的业务侧拿不到平台内部 ID，而只有用户名/handle，建议先在业务侧统一映射成稳定账号主键后再调用本接口。

---

## 去重与映射逻辑

服务端行为：

1. 使用默认 `tenant_code`
2. 用 `source_platform + source_user_id` 查询 `internal_platform_user_mappings`
3. 如果已存在有效 mapping，直接返回该 mapping
4. 如果不存在：
   - 内部生成稳定 `user_id`
   - 调用下游 `fashion-kol`
   - 将结果写入 `internal_platform_user_mappings`
   - 返回保存后的 mapping

稳定 `user_id` 生成依赖：

- `tenant_code`
- `source_platform`
- `source_user_id`

所以同一来源账号重复请求，不会重复创建。

---

## 请求示例

```bash
CLIENT_ID="default_client"
CLIENT_SECRET="your_client_secret"
TIMESTAMP=$(date +%s)
SIGNATURE=$(python3 -c "
import hmac, hashlib, json
body = {
    'nickname': 'nickA',
    'source_platform': 'tiktok',
    'source_user_id': 'user_123',
    'description': 'fashion creator',
    'avatar': {'url': 'https://img.example.com/a.jpg'},
    'tags': ['ootd', 'summer'],
    'client_id': '$CLIENT_ID',
    'timestamp': $TIMESTAMP,
}
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

curl -X POST "http://localhost:8000/open-api/v1/internal-platform/kol" \
  -H "Content-Type: application/json" \
  -d "{
    \"nickname\": \"nickA\",
    \"source_platform\": \"tiktok\",
    \"source_user_id\": \"user_123\",
    \"description\": \"fashion creator\",
    \"avatar\": {\"url\": \"https://img.example.com/a.jpg\"},
    \"tags\": [\"ootd\", \"summer\"],
    \"client_id\": \"$CLIENT_ID\",
    \"timestamp\": $TIMESTAMP,
    \"signature\": \"$SIGNATURE\"
  }"
```

Python 示例：

```python
import hmac
import hashlib
import json
import time
import requests
from datetime import datetime, date

def _value_to_sign_str(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (list, dict)):
        return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(v)

def generate_signature(params, secret, timestamp):
    filtered = {k: v for k, v in params.items() if k != "signature" and v is not None and v != ""}
    param_str = "&".join(f"{k}={_value_to_sign_str(v)}" for k, v in sorted(filtered.items()))
    return hmac.new(secret.encode(), f"{param_str}&timestamp={timestamp}".encode(), hashlib.sha256).hexdigest()

BASE = "http://localhost:8000/open-api/v1"
CLIENT_ID = "default_client"
CLIENT_SECRET = "your_client_secret"

payload = {
    "nickname": "nickA",
    "source_platform": "tiktok",
    "source_user_id": "user_123",
    "description": "fashion creator",
    "avatar": {"url": "https://img.example.com/a.jpg"},
    "tags": ["ootd", "summer"],
    "client_id": CLIENT_ID,
    "timestamp": int(time.time()),
}
payload["signature"] = generate_signature(payload, CLIENT_SECRET, payload["timestamp"])

resp = requests.post(f"{BASE}/internal-platform/kol", json=payload)
print(resp.json())
```

---

## 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "acc_100",
    "user_id": "2911111111111",
    "nickname": "nickA",
    "avatar_url": "https://cdn.example.com/a.jpg",
    "description": "fashion creator",
    "tags": ["ootd", "summer"],
    "raw": {}
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 站内 KOL 账号 ID |
| user_id | string | 服务端生成并绑定的站内用户 ID |
| nickname | string | KOL 昵称 |
| avatar_url | string | 头像 URL |
| description | string | 简介 |
| tags | string[] | 标签列表 |
| raw | object | 当前从 mapping 返回时为空对象 |

---

## 错误说明

常见错误：

- `401` / `403`: Open API 认证失败
- `422`: 请求参数不合法，例如：
  - `source_platform` 不在允许范围
  - 传入未开放字段，如 `tenant_code`、`kol_id`、`status`
- `409` 或其他业务码：下游 `fashion-kol` 返回业务错误
- `500`: 服务端内部错误或下游调用失败

---

## 实现位置

- 路由：[app/routers/openapi/api.py](/Users/guyin/PycharmProjects/tiktok_upload/app/routers/openapi/api.py:221)
- 服务：[app/services/internal_platform/upload_service.py](/Users/guyin/PycharmProjects/tiktok_upload/app/services/internal_platform/upload_service.py:2058)
- 总 Open API 文档：[OPEN_API.md](/Users/guyin/PycharmProjects/tiktok_upload/docs/OPEN_API.md:521)
