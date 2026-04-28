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
| `title` | string | 商品标题 |
| `link` | string | 商品页面链接 |
| `source` | string | 来源平台名称，例如 `"ZARA"`、`"H&M"` |
| `thumbnail` | string | 商品缩略图 URL |
| `image` | string | 商品原图 URL |
| `position` | integer |  |
| `tier` | integer | 正品网站可信度，1最高 |
| `price` | object | 商品价格信息（包含 value、extracted_value、currency），无价格信息时可能为空 |


### candidates 单项结构
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
        "imageUrl": "https://img.alvinclub.com/images/grid-lens-temp/1777277470610_aafd32a9.jpg",
        "q": "pants",
        "topMatch": {
            "position": 4,
            "title": "728 High Rise Wide Leg Women's Jeans - Black | Levi's® US",
            "link": "https://www.levi.com/US/en_US/clothing/women/jeans/wide-leg/728-high-rise-wide-leg-womens-jeans/p/0039B0000",
            "source": "Levi's",
            "thumbnail": "https://encrypted-tbn1.gstatic.com/images?q=tbn:ANd9GcSknueDAWwEMA_gV3Uj6HuGL6H7XKCYgDpZo7vg7mzaxVSVsjos",
            "image": "https://lscoglobal.scene7.com/is/image/lscoglobal/WB_0039B-0000_LSE_CL_FV?$qv_desktop$",
            "price": {
                "value": "$99*",
                "extracted_value": 99.0,
                "currency": "$"
            },
            "tier": 1,
            "tier_label": "Official Website",
            "id": 1
        },
        "candidates": [
            {
                "position": 4,
                "title": "728 High Rise Wide Leg Women's Jeans - Black | Levi's® US",
                "link": "https://www.levi.com/US/en_US/clothing/women/jeans/wide-leg/728-high-rise-wide-leg-womens-jeans/p/0039B0000",
                "source": "Levi's",
                "thumbnail": "https://encrypted-tbn1.gstatic.com/images?q=tbn:ANd9GcSknueDAWwEMA_gV3Uj6HuGL6H7XKCYgDpZo7vg7mzaxVSVsjos",
                "image": "https://lscoglobal.scene7.com/is/image/lscoglobal/WB_0039B-0000_LSE_CL_FV?$qv_desktop$",
                "price": {
                    "value": "$99*",
                    "extracted_value": 99.0,
                    "currency": "$"
                },
                "tier": 1,
                "tier_label": "Official Website",
                "id": 1
            },
            {
                "position": 7,
                "title": "The Icon Classic Wide-Leg Jean | Banana Republic",
                "link": "https://bananarepublic.gap.com/browse/product.do?pid=826977012",
                "source": "Gap",
                "thumbnail": "https://encrypted-tbn3.gstatic.com/images?q=tbn:ANd9GcRZlLT0OEQSdnqMRI6_7q_MuiXdwHV6qQ9y2fJh5R1CtOeV343C",
                "image": "https://bananarepublic.gap.com/webcontent/0060/104/366/cn60104366.jpg",
                "price": {
                    "value": "$130*",
                    "extracted_value": 130.0,
                    "currency": "$"
                },
                "tier": 1,
                "tier_label": "Official Website",
                "id": 2
            },
            {
                "position": 12,
                "title": "High-waisted wideleg jeans - Women | MANGO USA",
                "link": "https://shop.mango.com/us/en/p/women/jeans/plus-sizes/high-waisted-wideleg-jeans_27021196",
                "source": "mango.com",
                "thumbnail": "https://encrypted-tbn2.gstatic.com/images?q=tbn:ANd9GcQZlpKYWTL45Zw8qZu2LDmgbxTPeaB_OfSMx-UDyzcgmsWqQbUs",
                "image": "https://media.mango.com/is/image/punto/27021196-TN-021?wid=2048",
                "price": {
                    "value": "$46*",
                    "extracted_value": 46.0,
                    "currency": "$"
                },
                "tier": 1,
                "tier_label": "Official Website",
                "id": 3
            },
            {
                "position": 21,
                "title": "Girl Wide Leg Jeans Black | Mayoral ®",
                "link": "https://www.mayoral.com/us/en/girl-wide-leg-jeans-black-2506538092-1",
                "source": "Mayoral",
                "thumbnail": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTclKfpPdBJLmdH9bSZVycRveUwvgXrqX013RGvkmoBCSwbTpPy",
                "image": "https://assets.mayoral.com/images/t_default/f_auto,w_1920/v1726509483/25-06538-092-XL-5/girl-wide-leg-jeans-black-XL-5.jpg",
                "price": {
                    "value": "$50*",
                    "extracted_value": 50.0,
                    "currency": "$"
                },
                "tier": 1,
                "tier_label": "Official Website",
                "id": 4
            },
            {
                "position": 26,
                "title": "Unpicked Hem High Rise Wide Leg Jeans in Washed Black",
                "link": "https://www.loft.com/clothing/jeans/catl000015/unpicked-high-rise-wide-leg-jeans-washed-black/771709.html",
                "source": "Loft",
                "thumbnail": "https://encrypted-tbn2.gstatic.com/images?q=tbn:ANd9GcTTvurURp3kEr2wnM6SYmzRLmjyKKKYT0ghnECApe1Lr2mdTqZw",
                "image": "https://anninc.scene7.com/is/image/LO/771709_2639_D1?$fullBpdp$",
                "price": {
                    "value": "$40*",
                    "extracted_value": 40.0,
                    "currency": "$"
                },
                "tier": 1,
                "tier_label": "Official Website",
                "id": 5
            }
        ],
        "processingTime": "2139.65ms"
    },
    "traceId": "c46ee3a4-933f-430d-8942-35764c03bee4",
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
