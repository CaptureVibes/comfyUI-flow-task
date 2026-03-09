<template>
  <div class="vtfd-page" v-loading="loading">
    <!-- Header -->
    <div class="vtfd-header">
      <div class="vtfd-header-left">
        <h1 class="vtfd-title">视频生成工厂</h1>
        <div class="vtfd-subtitle">合并AI博主与AI分析，生成最终的高质量视频</div>
      </div>
      <div class="vtfd-header-actions">
        <button class="vg-btn vg-btn-cancel" @click="$router.push(`/dashboard/accounts/${accountId}`)">取消</button>
        <button
          class="vg-btn vg-btn-primary"
          :class="{ 'is-loading': batchGenerating }"
          :disabled="!batchIsReady || batchGenerating"
          @click="handleBatchGenerate"
        >
          <svg v-if="!batchGenerating" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          <svg v-else class="vg-spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          批量生成 {{ batchSelected.length > 0 ? `(${batchSelected.length})` : '' }}
        </button>
      </div>
    </div>

    <div class="vg-layout">
      <!-- Account Context Card -->
      <div class="vtfd-card">
        <div class="vtfd-section">
          <div class="vtfd-section-header">
            <span class="vtfd-section-tag">当前账号信息</span>
          </div>
          <div class="vg-info-grid">
            <div class="vg-info-item">
              <div class="vg-info-label">账号名称</div>
              <div class="vg-info-value">{{ account?.account_name || '加载中...' }}</div>
            </div>
            <div class="vg-info-item">
              <div class="vg-info-label">风格描述</div>
              <div class="vg-info-value">{{ account?.style_description || '暂无描述' }}</div>
            </div>
            <div class="vg-info-item">
              <div class="vg-info-label">模特长相描述</div>
              <div class="vg-info-value">{{ account?.model_appearance || '暂无描述' }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Template Selection Card -->
      <div class="vtfd-card">
        <div class="vtfd-section">
          <div class="vtfd-section-header">
            <span class="vtfd-section-tag">按博主批量选择模板</span>
          </div>

          <!-- Step 1: 选博主 -->
          <div class="batch-step">
            <div class="batch-step-label">① 选择博主</div>
            <el-select
              v-model="selectedBlogger"
              placeholder="请选择博主"
              class="vtfd-beautiful-input"
              style="width: 100%"
              filterable
              @change="handleBloggerChange"
            >
              <el-option
                v-for="b in bloggerList"
                :key="b"
                :label="b"
                :value="b"
              />
            </el-select>
          </div>

          <!-- Step 2: 选模板 -->
          <template v-if="selectedBlogger">
            <div class="batch-step" style="margin-top: 16px;">
              <div class="batch-step-label" style="display: flex; justify-content: space-between; align-items: center;">
                <span>② 选择视频模板</span>
                <div style="display: flex; gap: 8px; align-items: center;">
                  <button class="vg-btn vg-btn-small" @click="selectUnused">一键选未用</button>
                  <label class="vg-checkbox-wrapper">
                    <input 
                      type="checkbox" 
                      class="vg-checkbox-input"
                      :checked="isAllSelected"
                      :indeterminate="isSomeSelected"
                      @change="e => toggleSelectAll(e.target.checked)"
                    />
                    <span class="vg-checkbox-box" :class="{ 'is-indeterminate': isSomeSelected }"></span>
                    <span class="vg-checkbox-label">全选</span>
                  </label>
                  <span style="font-size: 13px; color: #64748b; margin-left: 4px;">已选 <strong style="color:#0f172a">{{ batchSelected.length }}</strong> / {{ bloggerTemplates.length }}</span>
                </div>
              </div>

              <div class="batch-tpl-list" v-loading="batchLoading">
                <div
                  v-for="item in bloggerTemplates"
                  :key="item.tpl.id"
                  class="batch-tpl-item"
                  :class="{
                    'batch-tpl-selected': batchSelected.includes(item.tpl.id),
                    'batch-tpl-used': item.tpl.is_used,
                  }"
                  @click="toggleBatchItem(item.tpl.id)"
                >
                  <label class="vg-checkbox-wrapper" @click.stop>
                    <input 
                      type="checkbox" 
                      class="vg-checkbox-input"
                      :checked="batchSelected.includes(item.tpl.id)"
                      @change="toggleBatchItem(item.tpl.id)"
                    />
                    <span class="vg-checkbox-box"></span>
                  </label>
                  <img
                    v-if="item.tpl.video_source?.thumbnail_url"
                    :src="item.tpl.video_source.thumbnail_url"
                    class="batch-tpl-thumb"
                  />
                  <div v-else class="batch-tpl-thumb batch-tpl-thumb-empty">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                  </div>
                  <div class="batch-tpl-info">
                    <div class="batch-tpl-title">{{ item.tpl.title || item.tpl.video_source?.video_title || '未命名模板' }}</div>
                    <div class="batch-tpl-meta">
                      <span class="batch-tpl-status" :class="`status-${item.tpl.process_status}`">{{ item.tpl.process_status }}</span>
                      <span v-if="item.tpl.is_used" style="font-size: 11px; color: #94a3b8; background: #f1f5f9; padding: 1px 6px; border-radius: 5px;">已使用</span>
                      <span v-if="item.tpl.video_source?.duration" style="color: #94a3b8; font-size: 11px;">
                        {{ formatDuration(item.tpl.video_source.duration) }}
                      </span>
                    </div>
                    <div v-if="item.tpl.extracted_shots?.length" style="font-size: 11px; color: #10b981;">
                      {{ item.tpl.extracted_shots.length }} 张造型图
                    </div>
                    <div v-else style="font-size: 11px; color: #f59e0b;">暂无造型图</div>
                  </div>
                </div>
                <div v-if="!batchLoading && bloggerTemplates.length === 0" class="batch-empty">
                  该博主暂无可用模板
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchAccount } from '../api/accounts'
import { fetchVideoAITemplates, fetchAllAvailableVideoAITemplates, fetchVideoAITemplate, markTemplateUsed } from '../api/video_ai_templates'
import { createVideoTask } from '../api/video_tasks'

const route = useRoute()
const router = useRouter()
const accountId = route.params.id

const loading = ref(false)
const batchGenerating = ref(false)
const batchLoading = ref(false)

const account = ref(null)
const templateList = ref([])
const selectedBlogger = ref('')
const bloggerTemplates = ref([])
const batchSelected = ref([])

const bloggerList = computed(() => {
  const names = new Set()
  for (const tpl of templateList.value) {
    const name = tpl.video_source?.blogger_name
    if (name) names.add(name)
  }
  return [...names].sort()
})

const isAllSelected = computed(
  () => bloggerTemplates.value.length > 0 && batchSelected.value.length === bloggerTemplates.value.length
)
const isSomeSelected = computed(
  () => batchSelected.value.length > 0 && batchSelected.value.length < bloggerTemplates.value.length
)
const batchIsReady = computed(() => batchSelected.value.length > 0 && !!account.value)

async function loadData() {
  loading.value = true
  try {
    account.value = await fetchAccount(accountId)
    // 直接一次性获取所有博主的可用模板
    const allTemplates = await fetchAllAvailableVideoAITemplates()
    templateList.value = allTemplates
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载初始数据失败')
  } finally {
    loading.value = false
  }
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  let s = Math.floor(seconds)
  if (s > 15) s = 15
  return `${s}s`
}

function buildPromptForTemplate(tpl) {
  return tpl.prompt_description || ''
}

async function handleBloggerChange(e) {
  const blogger = typeof e === 'string' ? e : e.target.value
  selectedBlogger.value = blogger
  batchSelected.value = []
  bloggerTemplates.value = []
  if (!blogger) return
  batchLoading.value = true
  try {
    const matching = templateList.value.filter(t => t.video_source?.blogger_name === blogger)
    const details = await Promise.all(matching.map(t => fetchVideoAITemplate(t.id).catch(() => t)))
    bloggerTemplates.value = details.map(tpl => ({ tpl }))
  } catch {
    ElMessage.error('加载模板失败')
  } finally {
    batchLoading.value = false
  }
}

function toggleBatchItem(tplId) {
  const idx = batchSelected.value.indexOf(tplId)
  if (idx >= 0) batchSelected.value.splice(idx, 1)
  else batchSelected.value.push(tplId)
}

function toggleSelectAll(val) {
  if (val) batchSelected.value = bloggerTemplates.value.map(item => item.tpl.id)
  else batchSelected.value = []
}

function selectUnused() {
  batchSelected.value = bloggerTemplates.value
    .filter(item => !item.tpl.is_used)
    .map(item => item.tpl.id)
}

async function handleBatchGenerate() {
  if (batchGenerating.value || !batchIsReady.value) return
  batchGenerating.value = true
  const selectedItems = bloggerTemplates.value.filter(item => batchSelected.value.includes(item.tpl.id))
  let successCount = 0
  let failCount = 0
  try {
    for (const item of selectedItems) {
      const tpl = item.tpl
      try {
        const duration = formatDuration(tpl.video_source?.duration)
        const shots = (tpl.extracted_shots || []).map(({ image_base64, ...rest }) => rest)
        const finalP = buildPromptForTemplate(tpl)
        await createVideoTask({
          account_id: accountId,
          template_id: tpl.id,
          final_prompt: finalP,
          duration,
          shots,
        })
        successCount++
      } catch {
        failCount++
      }
    }
    if (successCount > 0) ElMessage.success(`成功创建 ${successCount} 个生成任务${failCount > 0 ? `，${failCount} 个失败` : ''}`)
    else ElMessage.error('所有任务创建失败')
    router.push(`/dashboard/accounts/${accountId}`)
  } finally {
    batchGenerating.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.vtfd-page {
  padding: 30px;
  max-width: 900px;
  margin: 0 auto;
  min-height: 100vh;
  animation: vtfd-fade-in 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes vtfd-fade-in {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}

.vtfd-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.vtfd-title {
  font-size: 24px;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 6px 0;
  letter-spacing: -0.02em;
}

.vtfd-subtitle {
  font-size: 14px;
  color: #64748b;
}

.vtfd-header-actions {
  display: flex;
  gap: 12px;
}

.vg-layout {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.vtfd-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 20px -10px rgba(0,0,0,0.05);
}

.vtfd-section {
  padding: 24px;
}

.vtfd-section-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.vtfd-section-tag {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
  background: #f1f5f9;
  padding: 4px 12px;
  border-radius: 8px;
  letter-spacing: 0.5px;
}

.vtfd-beautiful-input :deep(.el-input__wrapper),
.vtfd-beautiful-input :deep(.el-textarea__inner) {
  background-color: #f8fafc;
  border-radius: 10px;
  box-shadow: none !important;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.vtfd-beautiful-input :deep(.el-input__wrapper:hover),
.vtfd-beautiful-input :deep(.el-textarea__inner:hover) {
  background-color: #f1f5f9;
}

.vtfd-beautiful-input :deep(.el-input__wrapper.is-focus),
.vtfd-beautiful-input :deep(.el-textarea__inner:focus) {
  background-color: #ffffff;
  border-color: #818cf8;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}

.vg-info-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px;
  border: 1px solid #f1f5f9;
}

.vg-info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.vg-info-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.vg-info-value {
  font-size: 14px;
  color: #0f172a;
  line-height: 1.5;
}

/* ── Batch mode ── */
.batch-step-label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 10px;
}

.batch-tpl-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 560px;
  overflow-y: auto;
  padding-right: 4px;
}

.batch-tpl-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.batch-tpl-item:hover {
  border-color: #a5b4fc;
  background: #eef2ff;
}

.batch-tpl-selected {
  border-color: #6366f1 !important;
  background: #eef2ff !important;
}

.batch-tpl-used {
  opacity: 0.55;
}

.batch-tpl-used .batch-tpl-title {
  color: #94a3b8;
}

.batch-tpl-thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
  border: 1px solid #e2e8f0;
}

.batch-tpl-thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
}

.batch-tpl-info {
  flex: 1;
  min-width: 0;
}

.batch-tpl-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.batch-tpl-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.batch-tpl-status {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #64748b;
}

.batch-tpl-status.status-success {
  background: #dcfce7;
  color: #166534;
}

.batch-tpl-status.status-face_removing,
.batch-tpl-status.status-splitting,
.batch-tpl-status.status-understanding,
.batch-tpl-status.status-imagegen {
  background: #fef9c3;
  color: #a16207;
}

.batch-tpl-status.status-failed {
  background: #fee2e2;
  color: #991b1b;
}

.batch-empty {
  text-align: center;
  color: #94a3b8;
  padding: 32px 0;
  font-size: 14px;
}

/* ── Custom UI Elements ── */
.vg-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  height: 38px;
  padding: 0 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  font-family: inherit;
}

.vg-btn-small {
  height: 30px;
  padding: 0 12px;
  font-size: 13px;
  border-radius: 6px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #475569;
}

.vg-btn-small:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.vg-btn-cancel {
  background: #fff;
  border: 1px solid #e2e8f0;
  color: #475569;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.vg-btn-cancel:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #0f172a;
  transform: translateY(-1px);
}

.vg-btn-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
  color: #fff;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
}

.vg-btn-primary:hover:not(:disabled) {
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35);
  transform: translateY(-1px);
}

.vg-btn-primary:disabled {
  background: #c7d2fe;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

.is-loading {
  pointer-events: none;
  opacity: 0.8;
}

.vg-spinner {
  animation: vg-spin 1s linear infinite;
}

@keyframes vg-spin {
  100% { transform: rotate(360deg); }
}

/* Custom Checkbox */
.vg-checkbox-wrapper {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.vg-checkbox-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.vg-checkbox-box {
  width: 18px;
  height: 18px;
  border-radius: 5px;
  border: 2px solid #cbd5e1;
  background: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  position: relative;
}

.vg-checkbox-input:checked + .vg-checkbox-box {
  background: #6366f1;
  border-color: #6366f1;
}

.vg-checkbox-input:checked + .vg-checkbox-box::after {
  content: '';
  position: absolute;
  width: 4px;
  height: 8px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
  top: 2px;
}

.vg-checkbox-box.is-indeterminate {
  background: #6366f1;
  border-color: #6366f1;
}

.vg-checkbox-box.is-indeterminate::after {
  content: '';
  position: absolute;
  width: 8px;
  height: 2px;
  background: white;
  border: none;
  transform: none;
  top: 6px;
}

.vg-checkbox-label {
  margin-left: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

.vg-checkbox-wrapper:hover .vg-checkbox-box:not(.is-indeterminate) {
  border-color: #94a3b8;
}
.vg-checkbox-input:checked + .vg-checkbox-box:hover {
  border-color: #4f46e5;
  background: #4f46e5;
}
</style>
