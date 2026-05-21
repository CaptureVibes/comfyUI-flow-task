# AI 博主频道占用接口文档

服务地址：

```text
http://34.55.116.212:8000/api/v1
```

认证方式：

调用方需要在请求头中传入约定好的 API Key：

```http
X-API-Key: <api_key>
```

服务端需要配置同一个 Key：

```env
ACCOUNT_CHANNEL_API_KEY=<api_key>
```

支持的平台：

```text
youtube, tiktok, instagram
```

## owner_id 说明

所有接口的 `owner_id` 字段均为**可选**。

- 不传（或传 `null`）时，服务端使用 `.env` 中配置的默认值：

```env
ACCOUNT_CHANNEL_OWNER_ID=<uuid>
```

- 需要指定归属时才显式传入。

---

## 1. 查询可用 AI 博主

按 `owner_id`、性别、平台和数量查询可用 AI 博主。

这个接口只返回候选数据，不会占用账号，不会写入数据库。

```http
POST /open-api/accounts/channel-reservations
```

请求：

```json
{
  "owner_id": null,
  "gender": "female",
  "platform": "tiktok",
  "count": 1,
  "source": "openapi"
}
```

响应：

```json
{
  "items": [
    {
      "account_id": "c673e254-5eae-4b87-a1d3-b247258476b4",
      "platform": "tiktok",
      "account_name": "Sonny们的冬日七搭",
      "account_handle": "sonny_winter_7days",
      "account_signature": "账号签名",
      "hashtags": ["fashioninspo", "outfitideas"],
      "avatar_url": "https://example.com/avatar.jpg",
      "link_info": [{
          "name": "",
          "link": ""
      }]
    }
  ],
  "requested_count": 1,
  "returned_count": 1
}
```

说明：

- 如果某个账号已经存在同平台的 `account_channel_reservations` 记录，则不会被查询出来。
- 查询接口不写数据库，在调用确认或绑定前，重复查询可能返回同一个账号。

---

## 2. 确认占用频道

调用方确认要占用某个 AI 博主的某个平台。

这个接口会创建或更新占用记录，状态为 `confirmed`。**确认后，该账号的该平台不可再被他人领取，也不可通过绑定接口修改，直到调用 release 释放。**

```http
POST /open-api/accounts/channel-reservations/confirm
```

请求：

```json
{
  "owner_id": null,
  "account_id": "c673e254-5eae-4b87-a1d3-b247258476b4",
  "platform": "tiktok"
}
```

响应：

```json
{
  "status": "confirmed",
  "owner_id": "4424f85f-6e43-4ca2-a0a3-2cc75c766e0c",
  "account_id": "c673e254-5eae-4b87-a1d3-b247258476b4",
  "platform": "tiktok"
}
```

错误：

- `404`：该 `owner_id` 下不存在这个账号。
- `409`：该账号的平台已被其他请求占用。

---

## 3. 绑定频道信息

给某个 AI 博主绑定平台频道信息，状态变为 `bound`。

**前提：该账号 + 平台必须已经 confirm，或尚无记录（直接创建）。已 bound 的记录不可重复绑定，需先 release。**

```http
POST /open-api/accounts/{account_id}/channel-bindings
```

请求：

```json
{
  "owner_id": null,
  "platform": "youtube",
  "channel_source": "openapi",
  "channel_id": "UCgBJozWjiE0cqwv7UNalyog",
  "channel_name": "darrygo",
  "username": "@darrygo"
}
```

响应：

```json
{
  "account_id": "c673e254-5eae-4b87-a1d3-b247258476b4",
  "account_name": "Sonny们的冬日七搭",
  "account_handle": "sonny_winter_7days",
  "account_signature": "账号签名",
  "gender": "female",
  "account_type": "shared",
  "channel_reservations": [
    {
      "id": "b9e19849-f670-45fb-bc91-99b8083abc28",
      "account_id": "c673e254-5eae-4b87-a1d3-b247258476b4",
      "platform": "youtube",
      "status": "bound",
      "source": "openapi",
      "channel_source": "openapi",
      "channel_id": "UCgBJozWjiE0cqwv7UNalyog",
      "channel_name": "darrygo",
      "username": "@darrygo",
      "avatar_url": null,
      "reserved_at": "2026-04-15T07:13:50.401492Z",
      "confirmed_at": "2026-04-15T07:13:50.401492Z",
      "bound_at": "2026-04-15T07:13:50.401492Z",
      "created_at": "2026-04-15T07:13:50.402897Z",
      "updated_at": "2026-04-15T07:13:50.402901Z"
    }
  ]
}
```

错误：

- `404`：账号不存在。
- `409`：该平台已 `bound`，请先调用 release 释放。

---

## 4. 释放频道占用

删除某个 AI 博主的平台占用记录（`confirmed` 或 `bound` 均可释放）。

释放后该账号可重新被其他人领取并绑定。

```http
POST /open-api/accounts/channel-reservations/release
```

请求：

```json
{
  "owner_id": null,
  "account_id": "c673e254-5eae-4b87-a1d3-b247258476b4",
  "platform": "tiktok"
}
```

响应：

```json
{
  "account_id": "c673e254-5eae-4b87-a1d3-b247258476b4",
  "platform": "tiktok",
  "released": true
}
```

错误：

- `404`：账号不存在，或该平台无占用记录。

---

## 状态流转

```text
（无记录）
    ↓ reserve（查询，不写库）
    ↓ confirm
confirmed（锁定，不可再被领取）
    ↓ bind
bound（已绑定频道）
    ↓ release（confirmed 或 bound 均可）
（记录删除，可重新 reserve）
```

---

## 测试脚本

```bash
cd backend
uv run python scripts/test_account_channel_openapi.py
```

修改脚本顶部配置：

```python
BASE_URL = "http://34.55.116.212:8000/api/v1"
API_KEY = "..."        # ACCOUNT_CHANNEL_API_KEY
OWNER_ID = None        # None 则由服务端 ACCOUNT_CHANNEL_OWNER_ID 决定
ACTION = "reserve"     # reserve / confirm / bind / release
```
