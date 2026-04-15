# AI 博主频道占用接口文档

服务地址：

```text
http://34.55.116.212:8000/api/v1
```

认证方式：

调用方需要在请求头中传入约定好的 API Key：

```http
X-API-Key: 
owner_id: 
```

服务端需要配置同一个 Key：

```env
ACCOUNT_CHANNEL_API_KEY=<api_key>
```

支持的平台：

```text
youtube, tiktok, instagram
```

## 1. 查询可用 AI 博主

按 `owner_id`、性别、平台和数量查询可用 AI 博主。

这个接口只返回候选数据，不会占用账号，不会写入数据库。

```http
POST /open-api/accounts/channel-reservations
```

请求：

```json
{
  "owner_id": "4424f85f-6e43-4ca2-a0a3-2cc75c766e0c",
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
      "hashtags": ["fashioninspo", "outfitideas"]
    }
  ],
  "requested_count": 1,
  "returned_count": 1
}
```

说明：

- 如果某个账号已经存在同平台的 `account_channel_reservations` 记录，则不会被查询出来。
- 因为查询接口不写数据库，所以在调用确认或绑定前，重复查询可能返回同一个账号。

## 2. 确认占用频道

调用方确认要占用某个 AI 博主的某个平台。

这个接口会创建或更新占用记录，状态为 `confirmed`。

```http
POST /open-api/accounts/channel-reservations/confirm
```

请求：

```json
{
  "owner_id": "4424f85f-6e43-4ca2-a0a3-2cc75c766e0c",
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
- `409`：并发情况下，该账号的平台已被其他请求占用。

## 3. 绑定频道信息

给某个 AI 博主绑定平台频道信息。

唯一定位方式是：

```text
account_id + platform
```

```http
POST /open-api/accounts/{account_id}/channel-bindings
```

请求：

```json
{
  "owner_id": "4424f85f-6e43-4ca2-a0a3-2cc75c766e0c",
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

说明：

- 如果同一个 `account_id + platform` 已经存在记录，则更新原记录。

## 测试脚本

本地测试脚本：

```bash
cd backend
uv run python scripts/test_account_channel_openapi.py
```

修改脚本顶部配置：

```python
BASE_URL = "http://34.55.116.212:8000/api/v1"
API_KEY = "..."
OWNER_ID = "..."
ACTION = "reserve"  # reserve / confirm / bind
```
