# AI Blogger Channel Open API

Base URL:

```text
http://34.55.116.212/api/v1
```

Authentication:

Pass the agreed API key in the request header:

```http
X-API-Key: <api_key>
```

The backend must configure the same key:

```env
ACCOUNT_CHANNEL_API_KEY=<api_key>
```

Supported platforms:

```text
youtube, tiktok, instagram
```

## 1. Search AI Bloggers

Search available AI bloggers by owner, gender, platform, and count. This endpoint only returns candidates. It does not reserve, confirm, bind, or write any database record.

```http
POST /open-api/accounts/channel-reservations
```

Request:

```json
{
  "owner_id": "4424f85f-6e43-4ca2-a0a3-2cc75c766e0c",
  "gender": "female",
  "platform": "tiktok",
  "count": 1,
  "source": "openapi"
}
```

Response:

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

Notes:

- An account is excluded if it already has a record for the requested platform in `account_channel_reservations`.
- Because search does not write data, repeated searches can return the same candidate until `confirm` or `bind` is called.

## 2. Confirm Channel Occupation

Confirm that the caller will occupy one AI blogger's platform. This endpoint creates or updates the occupation record.

```http
POST /open-api/accounts/channel-reservations/confirm
```

Request:

```json
{
  "owner_id": "4424f85f-6e43-4ca2-a0a3-2cc75c766e0c",
  "account_id": "c673e254-5eae-4b87-a1d3-b247258476b4",
  "platform": "tiktok"
}
```

Response:

```json
{
  "status": "confirmed",
  "owner_id": "4424f85f-6e43-4ca2-a0a3-2cc75c766e0c",
  "account_id": "c673e254-5eae-4b87-a1d3-b247258476b4",
  "platform": "tiktok"
}
```

Errors:

- `404`: account not found under the given owner.
- `409`: the account and platform were occupied by another concurrent request.

## 3. Bind Channel

Bind channel information to one AI blogger and platform. The unique key is `account_id + platform`.

```http
POST /open-api/accounts/{account_id}/channel-bindings
```

Request:

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

Response:

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

Notes:

- `channel_info` is not returned by this external API.
- If `confirm` was not called before `bind`, `bind` will create the record and set it to `bound`.
- If another channel already exists for the same `account_id + platform`, it is updated in place.

## Test Script

Local test script:

```bash
cd backend
uv run python scripts/test_account_channel_openapi.py
```

Edit the constants at the top of the script:

```python
BASE_URL = "http://34.55.116.212/api/v1"
API_KEY = "..."
OWNER_ID = "..."
ACTION = "reserve"  # reserve / confirm / bind
```
