# 内部优先以图搜图接口

## 基本信息

| 项目 | 内容 |
|------|------|
| 接口地址 | `https://api.alvinclub.com/ai-service/api/v1/style-outfits/search/image-internal` |
| 请求方式 | `POST` |
| Content-Type | `application/json` |

---

## 接口说明

传入一张已处理好的单品图片 URL，接口会对该图进行以图搜图，返回相似商品候选列表。
---

## 请求参数

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `imageUrl` | string | 是 | — | 单品图片 URL，要求图片已处理好（如已完成分割抠图），直接用于搜图 |
| `internalScoreThreshold` | float | 否 | `0.9` | 内部图搜质量阈值，范围 `0.0 ~ 1.0`。内部搜图 top1 相似度低于此值时，触发外部搜图补全候选。**传 `q` 时此参数无效** |
| `topN` | integer | 否 | `3` | 返回的候选商品数量，范围 `1 ~ 10` |
| `q` | string | 否 | — | 关键词。有值时跳过内部图搜，直接以图片 + 关键词调外部搜图。可填品类、品牌、风格描述等，例如 `"white linen shirt women"` |

### 请求示例



```json
{
  "imageUrl": "https://storage.example.com/items/shirt_001.jpg",
  "internalScoreThreshold": 0.5,
  "q": "white linen shirt women",
  "topN": 5
}
```

---

## 响应参数

### 外层结构

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `code` | integer | 状态码，`0` 表示成功 |
| `message` | string | 状态描述 |
| `success` | boolean | 是否成功 |
| `traceId` | string | 请求追踪 ID，用于排查问题 |
| `data` | object | 业务数据，见下方说明 |

### data 字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `imageUrl` | string | 请求传入的图片 URL |
| `internalScoreThreshold` | float | 本次使用的内部搜图阈值（仅不传 `q` 时返回） |
| `q` | string | 本次使用的关键词（仅传 `q` 时返回） |
| `topMatch` | object / null | 最优候选商品（即 `candidates[0]`），无结果时为 `null` |
| `candidates` | array | 候选商品列表，最多 `topN` 条，结构见下方说明 |
| `processingTime` | string | 接口处理耗时，例如 `"1234ms"` |

### candidates 单项结构

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | integer | 候选序号，从 `1` 开始，按相关度排序 |
| `position` | integer / null | 外部搜图排名；内部结果为空 |
| `title` | string | 商品标题 |
| `link` | string | 商品页面链接 |
| `source` | string | 来源平台名称；内部结果固定为空字符串 |
| `thumbnail` | string | 商品缩略图 URL |
| `image` | string | 商品原图 URL |
| `price` | object | 商品价格信息（包含 value、extracted_value、currency） |
| `tier` | integer / null | 正品网站可信度，1 最高；内部结果为空 |
| `tier_label` | string | 正品网站可信度标签；内部结果为空 |
| `product_code` | string | 内部商品 SPU code；外部结果固定为空字符串 |
| `sku_code` | string | 内部商品 SKU code；外部结果固定为空字符串 |
| `is_internal` | boolean | 是否来自内部商品库 |


### price 单项结构
| 字段名 | 类型 | 说明 |
|--------|------|------|
| `value` | string | 原始价格文本（包含货币符号），例如 "$29.99" |
| `extracted_value` | float | 提取后的数值价格，例如 29.99 |
| `currency` | string | 货币符号 |



### 响应示例

**内部优先模式成功**

```json
{
    "code": 0,
    "message": "操作成功",
    "data": {
        "imageUrl": "https://img.alvinclub.com/images/grounded-sam2/2cd26d30fb4140af/image_01/completed/item_01.png",
        "internalScoreThreshold": 0.5,
        "topMatch": {
            "position": null,
            "title": "",
            "link": "72256b9e65353ae2",
            "source": "",
            "thumbnail": "https://5thave-img-cdn-g.bybieyang.com/pf/6e73ac39-3b4b-3249-9fea-e3041912c489.jpg",
            "image": "https://5thave-img-cdn-g.bybieyang.com/pf/6e73ac39-3b4b-3249-9fea-e3041912c489.jpg",
            "price": {
                "value": "99999.00",
                "extracted_value": 99999.0,
                "currency": "USD"
            },
            "tier": null,
            "tier_label": "",
            "product_code": "SP042603297084",
            "sku_code": "SK0426031223071",
            "is_internal": true,
            "id": 1
        },
        "candidates": [
            {
                "position": null,
                "title": "",
                "link": "72256b9e65353ae2",
                "source": "",
                "thumbnail": "https://5thave-img-cdn-g.bybieyang.com/pf/6e73ac39-3b4b-3249-9fea-e3041912c489.jpg",
                "image": "https://5thave-img-cdn-g.bybieyang.com/pf/6e73ac39-3b4b-3249-9fea-e3041912c489.jpg",
                "price": {
                    "value": "99999.00",
                    "extracted_value": 99999.0,
                    "currency": "USD"
                },
                "tier": null,
                "tier_label": "",
                "product_code": "SP042603297084",
                "sku_code": "SK0426031223071",
                "is_internal": true,
                "id": 1
            },
            {
                "position": null,
                "title": "",
                "link": "703c46cb779c42de",
                "source": "",
                "thumbnail": "https://5thave-img-cdn-g.bybieyang.com/pf/b34be536-5ab8-3244-9931-8e60b4c3ad42.jpg",
                "image": "https://5thave-img-cdn-g.bybieyang.com/pf/b34be536-5ab8-3244-9931-8e60b4c3ad42.jpg",
                "price": {
                    "value": "99999.00",
                    "extracted_value": 99999.0,
                    "currency": "USD"
                },
                "tier": null,
                "tier_label": "",
                "product_code": "SP04260352691",
                "sku_code": "SK042603261330",
                "is_internal": true,
                "id": 2
            },
            {
                "position": null,
                "title": "",
                "link": "703c46cb779c42de",
                "source": "",
                "thumbnail": "https://5thave-img-cdn-g.bybieyang.com/pf/341d63b2-9848-35d2-bb28-e1c043062682.jpg",
                "image": "https://5thave-img-cdn-g.bybieyang.com/pf/341d63b2-9848-35d2-bb28-e1c043062682.jpg",
                "price": {
                    "value": "99999.00",
                    "extracted_value": 99999.0,
                    "currency": "USD"
                },
                "tier": null,
                "tier_label": "",
                "product_code": "SP04260358742",
                "sku_code": "SK042603267472",
                "is_internal": true,
                "id": 3
            }
        ],
        "processingTime": "838.79ms"
    },
    "traceId": "7f8efe6d-1bba-46e9-a81a-441002168fb8",
    "success": true
}
```

---

## 错误响应

| HTTP 状态码 | 场景 | 响应示例 |
|-------------|------|----------|
| `400` | 图片 URL 无法访问或下载失败 | `{"detail": "图片下载失败，HTTP 404"}` |
| `502` | 外部搜图服务异常 | `{"detail": "外部搜图失败: HTTP 503"}` |
| `500` | 服务器内部错误 | `{"detail": "Internal server error"}` |
