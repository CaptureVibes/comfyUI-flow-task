# AI 博主补充模板：行级进度与人设分类过滤说明

## 背景

AI 博主页面的「补充模板」原先只有请求级结果记录，前端无法稳定展示每个 AI 博主自己的补充进度；同时「补充人设」只按绑定博主拉取视频，不能按 14 个细分类限制入库范围。

本次改动覆盖两个需求：

1. 在 AI 博主列表中按行展示补充状态，并按 10 秒间隔轮询运行中的补充任务。
2. 在「补充人设」链路增加 14 个细分类可选过滤；不选择分类时保持原逻辑。

## 已完成工作

### 数据库

新增表 `external_supplement_request_items`，用于记录一次 vendor 补充请求下每个 AI 博主的进度。

主要字段：

- `request_id`：关联 `external_supplement_requests.request_id`
- `account_id`：AI 博主 ID
- `mode`：`auto` / `exclusive` / `shared`
- `target_video_count`：目标补充数量
- `completed_count`：已成功入库数量
- `processing_count`：已接收但仍在处理中的数量
- `failed_count` / `rejected_count` / `duplicated_count`：失败、拒绝、重复计数
- `status`：`running` / `completed` / `failed` / `skipped`
- `final_received`：vendor final callback 是否已收到
- `error_message`：失败原因

迁移文件：

- `backend/alembic/versions/g034_add_external_supplement_request_items.py`

### 后端

新增服务：

- `backend/app/models/external_supplement_request_item.py`
- `backend/app/services/supplement_status_service.py`

核心能力：

- 发起 vendor 请求时，为每个 account 创建一条行级进度记录。
- vendor callback 到达时，按 `account_id` 累计 scheduled / duplicated / rejected。
- 单条视频完成写库并进入 AI 模板 pipeline 后，增加 `completed_count`。
- 下载、上传、AI 审核、分类、写库失败时，更新对应 account 的失败原因和计数。
- 聚合更新 `external_supplement_requests.status`，保持原请求级状态可用。

新增/调整 API：

- `GET /api/v1/accounts`
  - 每个 `AccountRead` 增加 `supplement_status`
- `GET /api/v1/accounts/supplement-statuses?account_ids=...`
  - 前端轮询当前页账号的最新补充状态
- `POST /api/v1/accounts/supplement-templates`
  - `template_type=exclusive` 时支持 `filters.category_indices`
  - `category_indices` 校验范围为 `0-13`

### 自动补充链路

自动补充仍按账号已有分类聚合逻辑执行：

- 单核心：只允许 Top1 细分类入库
- 双核心：允许 Top1 + Top2 细分类入库
- 未分类、混乱、样本不足：跳过并记录失败/拒绝原因

本次主要补齐了行级进度更新，让自动补充的状态能在每个 AI 博主行内显示。

### 人设补充链路

「补充人设」新增 14 个细分类选择：

- 不选择分类：保持原逻辑，不启用分类过滤
- 选择分类：callback 视频下载/上传后先做 Gemini 分类
- 分类成功且命中所选小类：允许写入 `video_sources` 和 `video_ai_templates`
- 分类失败或未命中：记录为 rejected/failed，不写入业务视频库

分类参数存放在现有 `external_supplement_requests.filters` 中：

```json
{
  "category_indices": [0, 1, 9]
}
```

### 前端

调整文件：

- `frontend/src/api/accounts.js`
- `frontend/src/views/AccountListView.vue`

已完成内容：

- AI 博主列表行内展示补充状态：
  - `补充中`：已补充 x 个，还有 y 个需要补充
  - `补充完成`：已补充 x 个
  - `补充失败`：已补充 x 个，应该补充 y 个
- 仅当前页存在 `running` 状态时，启动 10 秒一次轮询。
- 「补充模板」弹窗中，选择「补充人设」后展示 14 个分类按钮。
- 前端仅在 `templateType === 'exclusive'` 时提交 `category_indices`。
- AI 博主列表视觉重新整理：
  - 账号身份、属性标签、补充状态、分类/库存、KOL 短链分层展示
  - 账号信息列加宽，减少信息堆叠

## 兼容性说明

- 共享补充路径不受本次改动影响。
- 自动补充原有分类筛选逻辑保持不变，只新增行级状态记录。
- 人设补充不选择分类时，不启用新过滤逻辑，保持原入库行为。
- 新增表只依赖现有 `external_supplement_requests`，不改动原表结构。

## 验证情况

已执行：

- `npm run build`

结果：

- 前端构建通过。

已知情况：

- 本地 pytest 环境缺少 `pytest` 模块，因此未保留测试代码，也未将临时测试文件纳入提交。
- 本地 SQLite mock 预览脚本和 mock 数据库已删除，不进入 PR。

## 后续计划

1. 合并 PR 后，在目标环境执行 Alembic 迁移，创建 `external_supplement_request_items`。
2. 配置好 vendor 后，用真实 `exclusive` 和 `auto` 请求各跑一轮。
3. 观察 callback 中以下状态是否符合预期：
   - running → completed
   - running → failed
   - 分类未命中 → rejected/failed 且不入库
4. 如真实数据量较大，再评估是否需要给 `account_id + updated_at` 增加组合索引。
5. 后续如果需要更精细的进度，可继续拆分为下载中、审核中、分类中、入库中等阶段。
