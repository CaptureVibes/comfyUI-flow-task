# Video Tasks API 文档

Base URL: `http://localhost:8000/api/v1`

## 认证说明

这两个接口**不强制要求登录**（Token 可选）：

- **有 Token**：`Authorization: Bearer <token>` → 操作与页面一致，`operator` 自动取登录用户名
- **无 Token**：`operator` 需在请求体中手动传入，否则返回 `422`

---

## 1. 查询视频任务列表

### `GET /video-tasks`

返回分页的视频任务列表，每个任务包含其子任务（含视频链接）。无需认证。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `target_date` | `string` (YYYY-MM-DD) | 否 | 按日期筛选，如 `2026-03-31` |
| `status` | `string` | 否 | 按父任务状态筛选，见状态说明 |
| `account_id` | `string` (UUID) | 否 | 按账号筛选 |
| `owner_id` | `string` (UUID) | 否 | 按所属用户筛选（外部 API 可传） |
| `tiktok_blogger_id` | `string` (UUID) | 否 | 按 TK 博主筛选 |
| `page` | `integer` | 否 | 页码，默认 `1` |
| `page_size` | `integer` | 否 | 每页数量，默认 `20`，最大 `100` |

### 请求示例

```bash
# API 调用（无 Token）
curl "http://localhost:8000/api/v1/video-tasks?target_date=2026-03-31&page=1&page_size=20"

# 页面调用（有 Token）
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/video-tasks?target_date=2026-03-31&page=1&page_size=20"
```

### 响应结构

```json
{
  "items": [
    {
      "id": "uuid",
      "owner_id": "uuid",
      "account_id": "uuid",
      "template_id": "uuid",
      "target_date": "2026-03-31",
      "status": "reviewing",
      "prompt": "视频提示词内容",
      "is_prompt_updated": false,
      "duration": "15s",
      "shots": null,
      "account_name": "账号名称",
      "template_title": "模板标题",
      "sub_tasks_done": 1,
      "tags": [
        { "id": "uuid", "name": "标签名" }
      ],
      "original_video": null,
      "sub_tasks": [
        {
          "id": "uuid",
          "task_id": "uuid",
          "sub_index": 1,
          "status": "reviewing",
          "result_video_url": "https://cdn.example.com/video.mp4",
          "selected": false,
          "manual_note": null,
          "operator": null,
          "has_ng": null,
          "ng_timestamps": null,
          "dimension_scores": null,
          "weighted_total_score": null,
          "queue_order": null,
          "created_at": "2026-03-31T10:00:00Z",
          "updated_at": "2026-03-31T10:05:00Z"
        }
      ],
      "created_at": "2026-03-31T10:00:00Z",
      "updated_at": "2026-03-31T10:05:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

### 响应字段说明

**任务（items[]）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 任务 ID |
| `owner_id` | UUID | 所属用户 ID |
| `target_date` | string | 任务日期 |
| `status` | string | 父任务状态（见下方状态说明） |
| `prompt` | string | 视频生成提示词 |
| `account_name` | string | 关联账号名称 |
| `template_title` | string | 关联模板标题 |
| `sub_tasks_done` | integer | 已生成视频的子任务数量 |
| `sub_tasks` | array | 子任务列表 |

**子任务（sub_tasks[]）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 子任务 ID |
| `status` | string | 子任务状态（见下方状态说明） |
| `result_video_url` | string \| null | 视频可播放/下载链接。GCS 私有桶里的视频是 **V4 签名 URL（7 天有效）**；后端会在每次返回前校验剩余有效期，剩余 < 1 天时自动续签新的 7 天 URL，调用方无需关心刷新——拿到的链接就用，过期后再次请求接口拿到的就是续签后的新链接。 |
| `operator` | string \| null | 审核人用户名 |
| `has_ng` | boolean \| null | 是否存在穿帮，`true`=有穿帮，`false`=无穿帮，`null`=未审核 |
| `ng_timestamps` | array \| null | 穿帮时间点列表，格式：`[{"second": 10, "frame": 5}]` |
| `dimension_scores` | object \| null | 多维度评分，格式：`{"audio_visual": 4, "character_realism": 3, ...}` |
| `weighted_total_score` | float \| null | 综合评分 0–100（由多维度评分计算得出） |
| `queue_order` | integer \| null | 候选池排序，仅 `queued` 状态有值 |

### 子任务状态说明

| 状态 | 含义 |
|------|------|
| `pending` | 待处理 |
| `generating` | 视频生成中 |
| `reviewing` | **待审核**（外部审核团队处理的目标状态） |
| `stashed` | 审核通过，暂存待路由 |
| `decision_rejected` | 审核未通过 |
| `queued` | 已进入发布候选池 |
| `publishing` | 发布中 |
| `published` | 已发布 |
| `publish_failed` | 发布失败 |
| `abandoned` | 已废弃（评分过低或有穿帮） |

---

## 2. 提交审核结果

### `PATCH /video-tasks/subtasks/{sub_task_id}/note`

提交对某个子任务的审核结果（穿帮信息、多维度评分、备注）。无需认证。

**重要：**
- 子任务必须处于 `reviewing` 状态，否则返回 `409`
- 提交成功后，子任务状态自动从 `reviewing` → `stashed`（暂存）
- **有 Token**：`operator` 自动取登录用户名，无需传递
- **无 Token**：`operator` 必须在请求体中传递
- 并发保护：状态校验保证同一视频不会被两人同时提交

### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `sub_task_id` | UUID | 子任务 ID |

### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `owner_id` | `string` (UUID) | 否 | 按所属用户筛选（外部 API 可传） |

### 请求体

**无 Token 调用（operator 必填）：**

```json
{
  "operator": "reviewer_zhang",
  "has_ng": false,
  "ng_timestamps": [],
  "dimension_scores": {
    "audio_visual": 4,
    "character_realism": 3,
    "performance_narrative": 4,
    "editing_transition": 3,
    "camera_composition": 4,
    "visual_environment": 4
  },
  "manual_note": "整体质量不错，人物动作自然"
}
```

**有 Token 调用（operator 可省略，自动取登录用户名）：**

```json
{
  "has_ng": false,
  "dimension_scores": {
    "audio_visual": 4,
    "character_realism": 3,
    "performance_narrative": 4,
    "editing_transition": 3,
    "camera_composition": 4,
    "visual_environment": 4
  },
  "manual_note": "整体质量不错，人物动作自然"
}
```

**请求体字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `operator` | string | 无 Token 时必填 | 审核人标识（有 Token 时忽略此字段） |
| `has_ng` | boolean \| null | 否 | 是否存在穿帮 |
| `ng_timestamps` | array \| null | 否 | 穿帮时间点，`has_ng=true` 时填写 |
| `ng_timestamps[].second` | integer | — | 穿帮时间（秒） |
| `ng_timestamps[].frame` | integer | — | 穿帮帧号 |
| `dimension_scores` | object \| null | 否 | 多维度评分，每项 1–5 分 |
| `manual_note` | string \| null | 否 | 文字备注 |

**dimension_scores 维度说明**

| 维度键 | 说明 | 权重 |
|--------|------|------|
| `audio_visual` | 声画与听觉 | 20% |
| `character_realism` | 人物与全身拟真 | 30% |
| `performance_narrative` | 表演与叙事 | 15% |
| `editing_transition` | 剪辑与转场 | 12% |
| `camera_composition` | 镜头与构图 | 12% |
| `visual_environment` | 画面与环境 | 11% |

综合评分 `weighted_total_score` = Σ (score/5 × weight × 100)，满分 100。

### 响应示例（成功）

HTTP 200

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "task_id": "uuid",
  "sub_index": 1,
  "status": "stashed",
  "result_video_url": "https://cdn.example.com/video.mp4",
  "selected": false,
  "manual_note": "整体质量不错，人物动作自然",
  "operator": "reviewer_zhang",
  "has_ng": false,
  "ng_timestamps": [],
  "dimension_scores": {
    "audio_visual": 4,
    "character_realism": 3,
    "performance_narrative": 4,
    "editing_transition": 3,
    "camera_composition": 4,
    "visual_environment": 4
  },
  "weighted_total_score": 72.0,
  "queue_order": null,
  "created_at": "2026-03-31T10:00:00Z",
  "updated_at": "2026-03-31T11:23:00Z"
}
```

### 错误响应

| HTTP 状态码 | 场景 | `detail` 示例 |
|-------------|------|---------------|
| `404` | 子任务不存在 | `"子任务不存在"` |
| `409` | 视频已被他人审核（状态不是 reviewing） | `"视频已被处理（当前状态：stashed），请刷新后重试"` |
| `422` | 无 Token 且未传 operator | `"无 token 时 operator 字段为必填"` |

---

## 典型调用流程

```bash
# 1. 获取当天 reviewing 状态的视频任务
curl "http://localhost:8000/api/v1/video-tasks?target_date=2026-03-31&page=1&page_size=20"

# 2. 从响应中找到 status=reviewing 的子任务，播放其 result_video_url
#    （GCS 视频返回 V4 签名 URL，7 天内可直接 GET；过期前 1 天后端会自动续签）

# 3. 提交审核结果（无 Token 示例）
curl -X PATCH "http://localhost:8000/api/v1/video-tasks/subtasks/{sub_task_id}/note" \
  -H "Content-Type: application/json" \
  -d '{
    "operator": "reviewer_zhang",
    "has_ng": false,
    "dimension_scores": {"audio_visual": 4, "character_realism": 3, "performance_narrative": 4, "editing_transition": 3, "camera_composition": 4, "visual_environment": 4},
    "manual_note": "质量不错"
  }'

# 若返回 409 → 视频已被他人抢先处理，重新获取列表选择下一个
```
