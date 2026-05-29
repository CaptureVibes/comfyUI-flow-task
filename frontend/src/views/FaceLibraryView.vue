<template>
  <div class="fl-page">
    <div class="fl-header">
      <h2 class="fl-title">人脸库</h2>
      <button class="fl-btn-refresh" @click="loadTags" :disabled="loading">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round">
          <polyline points="1 4 1 10 7 10" />
          <path d="M3.51 15a9 9 0 1 0 .49-3.87" />
        </svg>
        刷新
      </button>
      <button class="fl-btn-config" @click="openConfigDialog">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
        AI配置
      </button>
      <button class="fl-btn-bulk" :disabled="bulkRunning || pendingFaceCount === 0" @click="handleBulkSelect">
        <span v-if="bulkRunning" class="btn-spin"></span>
        <span v-else>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        </span>
        一键生成人脸 ({{ pendingFaceCount }})
      </button>
    </div>

    <div v-if="loading" class="fl-loading">加载中...</div>

    <div v-else-if="tags.length === 0" class="fl-empty">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5"
        stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="8" r="4" />
        <path d="M6 21v-1a6 6 0 0 1 12 0v1" />
      </svg>
      <p>暂无标签，请先创建标签并关联视频</p>
    </div>

    <template v-else>
      <div class="fl-grid">
        <div v-for="tag in tags" :key="tag.id" class="fl-card">
          <!-- 人脸图片 -->
          <div class="fl-photo-wrap">
            <img v-if="tag.face_photo?.face_photo_url" :src="tag.face_photo.face_photo_url"
              class="fl-photo" alt="人脸照片" />
            <div v-else class="fl-photo-placeholder">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"
                stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="8" r="4" />
                <path d="M6 21v-1a6 6 0 0 1 12 0v1" />
              </svg>
            </div>
            <!-- 加载中遮罩 -->
            <div v-if="loadingTags.has(tag.id)" class="fl-loading-mask">
              <div class="fl-spinner"></div>
            </div>
          </div>

          <!-- 标签信息 -->
          <div class="fl-info">
            <div class="fl-tag-name">
              <span v-if="tag.color" class="fl-color-dot" :style="{ background: tag.color }"></span>
              {{ tag.name }}
            </div>
            <div class="fl-meta">
              <span class="fl-video-count">{{ tag.video_count }} 个视频</span>
              <span v-if="tag.face_photo" class="fl-frame-index">第 {{ tag.face_photo.frame_index }} 帧</span>
            </div>
            <div v-if="tag.face_photo" class="fl-classify">
              <template v-if="tag.face_photo.classification_status === 'success'">
                <span>{{ tag.face_photo.gender || '不确定' }}</span>
                <span>{{ tag.face_photo.ethnicity || '不确定' }}</span>
                <span>{{ tag.face_photo.age_range || '-' }}</span>
                <span>{{ beautyLabel(tag.face_photo) }}</span>
                <span :class="remixClass(tag.face_photo)">{{ remixLabel(tag.face_photo) }}</span>
                <span v-if="tag.face_photo.notes" class="fl-note">{{ tag.face_photo.notes }}</span>
              </template>
              <template v-else-if="tag.face_photo.classification_status === 'running'">
                <span class="fl-status">分类中</span>
              </template>
              <template v-else-if="tag.face_photo.classification_status === 'failed'">
                <span class="fl-status fl-status-failed">分类失败</span>
              </template>
              <template v-else>
                <span class="fl-status">待分类</span>
              </template>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="fl-actions">
            <button
              class="fl-btn-select"
              :disabled="loadingTags.has(tag.id) || tag.video_count === 0"
              @click="handleSelectFace(tag)"
            >
              <span v-if="loadingTags.has(tag.id)">AI选择中...</span>
              <span v-else-if="tag.face_photo">重新选择</span>
              <span v-else>选择人脸</span>
            </button>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > 0" class="fl-footer">
        <div class="fl-pagination-left">
          <span class="fl-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
          <select v-model="pageSize" @change="handleSizeChange(pageSize)" class="fl-size-select">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
          </select>
        </div>
        <div class="fl-pagination">
          <button class="pg-btn" :disabled="page <= 1" @click="goPage(page - 1)">← 上一页</button>
          <template v-for="p in visiblePages" :key="p">
            <span v-if="p === '...'" class="pg-ellipsis">…</span>
            <button v-else class="pg-btn pg-num" :class="{ active: p === page }" @click="goPage(p)">{{ p }}</button>
          </template>
          <button class="pg-btn" :disabled="endIdx >= total" @click="goPage(page + 1)">下一页 →</button>
          <span class="pg-jump-wrap">
            跳至
            <input
              v-model.number="jumpPage"
              class="pg-jump-input"
              type="number"
              :min="1"
              :max="totalPages"
              @keyup.enter="doJump"
            />
            页
            <button class="pg-btn pg-jump-go" @click="doJump">GO</button>
          </span>
        </div>
      </div>
    </template>

    <!-- AI配置弹窗 -->
    <el-dialog v-model="showConfigDialog" title="人脸选择 AI 配置" width="580px" align-center destroy-on-close @open="loadConfig">
      <div v-loading="loadingConfig" class="config-form">
        <div class="cf-row">
          <label class="cf-label">AI 模型</label>
          <el-input v-model="configForm.face_select_model" placeholder="gemini-3.1-pro-preview" />
          <span class="cf-hint">用于分析帧图片并选择最佳人脸的模型</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">选择提示词</label>
          <el-input
            v-model="configForm.face_select_prompt"
            type="textarea"
            :rows="6"
            placeholder="请输入人脸选择提示词，系统会自动在末尾追加 JSON 输出要求..."
          />
          <span class="cf-hint">AI 将根据此提示词从 10 张帧图片中选择最佳人脸（输出 selected: 1-10）</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">分类模型</label>
          <el-input v-model="configForm.face_classify_model" placeholder="gemini-3-pro-preview" />
          <span class="cf-hint">用于识别人脸性别、族裔、年龄、美貌和 remix 可用性</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">分类温度</label>
          <el-input-number v-model="configForm.face_classify_temperature" :min="0" :max="2" :step="0.1" />
        </div>
        <div class="cf-row">
          <label class="cf-label">分类提示词</label>
          <el-input
            v-model="configForm.face_classify_prompt"
            type="textarea"
            :rows="8"
            placeholder="留空则使用系统内置的人脸五维分类 Prompt..."
          />
          <span class="cf-hint">输出 gender / ethnicity / age / beauty / memorability 等字段</span>
        </div>
      </div>
      <template #footer>
        <button class="dlg-btn-cancel" @click="showConfigDialog = false">取消</button>
        <button class="dlg-btn-primary" :disabled="savingConfig" @click="handleSaveConfig">
          <span v-if="savingConfig" class="btn-spin"></span>
          保存配置
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchTagsWithFaces, fetchPendingFaceCount, triggerFaceSelection, bulkSelectFaces } from '../api/faceLibrary'
import { fetchPipelineSettings, updatePipelineSettings } from '../api/settings'

const tags = ref([])
const loading = ref(false)
const loadingTags = ref(new Set())
const bulkRunning = ref(false)

// 分页
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const jumpPage = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const startIdx = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const endIdx = computed(() => Math.min(page.value * pageSize.value, total.value))

const visiblePages = computed(() => {
  const n = totalPages.value
  const cur = page.value
  if (n <= 7) return Array.from({ length: n }, (_, i) => i + 1)
  const pages = []
  pages.push(1)
  if (cur > 3) pages.push('...')
  for (let p = Math.max(2, cur - 1); p <= Math.min(n - 1, cur + 1); p++) pages.push(p)
  if (cur < n - 2) pages.push('...')
  pages.push(n)
  return pages
})

// 一键生成人脸：全局待处理数量（不依赖当前页）
const pendingFaceCount = ref(0)

// 配置弹窗
const showConfigDialog = ref(false)
const loadingConfig = ref(false)
const savingConfig = ref(false)
const configForm = ref({
  face_select_model: 'gemini-3.1-pro-preview',
  face_select_prompt: '',
  face_classify_model: 'gemini-3-pro-preview',
  face_classify_prompt: '',
  face_classify_temperature: 0.5,
})

function beautyLabel(face) {
  const level = face.beauty_level || '普通'
  const score = Number.isFinite(face.beauty_percentile) ? face.beauty_percentile : null
  return score === null ? level : `${level} ${score}`
}

function remixLabel(face) {
  if (face.memorability_level === '独特' || Number(face.memorability_percentile || 0) >= 78) {
    return '不进remix'
  }
  const score = Number.isFinite(face.memorability_percentile) ? face.memorability_percentile : null
  return score === null ? '可remix' : `可remix ${score}`
}

function remixClass(face) {
  return (face.memorability_level === '独特' || Number(face.memorability_percentile || 0) >= 78)
    ? 'fl-remix-blocked'
    : 'fl-remix-ok'
}

async function loadTags() {
  loading.value = true
  try {
    const res = await fetchTagsWithFaces({ page: page.value, pageSize: pageSize.value })
    tags.value = res.items
    total.value = res.total
  } catch {
    ElMessage.error('加载人脸库失败')
  } finally {
    loading.value = false
  }
}

async function loadPendingCount() {
  try {
    pendingFaceCount.value = await fetchPendingFaceCount()
  } catch {
    // 静默失败，不影响主流程
  }
}

function goPage(p) {
  const target = Math.max(1, Math.min(p, totalPages.value))
  if (target === page.value) return
  page.value = target
  jumpPage.value = target
  loadTags()
}

function handleSizeChange(val) {
  pageSize.value = val
  page.value = 1
  jumpPage.value = 1
  loadTags()
}

function doJump() {
  const p = parseInt(jumpPage.value)
  if (!isNaN(p)) goPage(p)
}

async function handleSelectFace(tag) {
  if (loadingTags.value.has(tag.id)) return
  loadingTags.value = new Set([...loadingTags.value, tag.id])
  try {
    const result = await triggerFaceSelection(tag.id)
    ElMessage.success(result?.status === 'submitted' ? '人脸选择与分类已启动' : '人脸选择成功')
    await loadTags()
    loadPendingCount()
  } catch (err) {
    const msg = err?.response?.data?.detail || '人脸选择失败，请稍后重试'
    ElMessage.error(msg)
  } finally {
    const next = new Set(loadingTags.value)
    next.delete(tag.id)
    loadingTags.value = next
  }
}

async function handleBulkSelect() {
  if (pendingFaceCount.value === 0) return
  bulkRunning.value = true
  try {
    const res = await bulkSelectFaces()
    ElMessage.success(res.message || '批量人脸选择已启动')
  } catch {
    ElMessage.error('启动批量人脸选择失败')
  } finally {
    bulkRunning.value = false
  }
}

function openConfigDialog() {
  showConfigDialog.value = true
}

async function loadConfig() {
  loadingConfig.value = true
  try {
    const data = await fetchPipelineSettings()
    configForm.value.face_select_model = data.face_select_model || 'gemini-3.1-pro-preview'
    configForm.value.face_select_prompt = data.face_select_prompt || ''
    configForm.value.face_classify_model = data.face_classify_model || 'gemini-3-pro-preview'
    configForm.value.face_classify_prompt = data.face_classify_prompt || ''
    configForm.value.face_classify_temperature = data.face_classify_temperature ?? 0.5
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loadingConfig.value = false
  }
}

async function handleSaveConfig() {
  savingConfig.value = true
  try {
    await updatePipelineSettings(configForm.value)
    ElMessage.success('配置已保存')
    showConfigDialog.value = false
  } catch {
    ElMessage.error('保存配置失败')
  } finally {
    savingConfig.value = false
  }
}

onMounted(() => {
  loadTags()
  loadPendingCount()
})
</script>

<style scoped>
.fl-page {
  padding: 24px;
  max-width: 1400px;
}

.fl-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.fl-title {
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.fl-btn-refresh,
.fl-btn-config,
.fl-btn-bulk {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.fl-btn-refresh:hover:not(:disabled),
.fl-btn-config:hover:not(:disabled) { background: #f8fafc; }
.fl-btn-bulk { background: #6366f1; color: #fff; border-color: #6366f1; }
.fl-btn-bulk:hover:not(:disabled) { background: #4f46e5; border-color: #4f46e5; }
.fl-btn-refresh:disabled,
.fl-btn-config:disabled,
.fl-btn-bulk:disabled { opacity: 0.5; cursor: not-allowed; }

.fl-loading {
  color: #94a3b8;
  padding: 40px;
  text-align: center;
}

.fl-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 80px 20px;
  color: #94a3b8;
  font-size: 14px;
}

.fl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}

/* 分页 */
.fl-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20px;
  padding: 16px 0 8px;
  border-top: 1px solid #f1f5f9;
  flex-wrap: wrap;
  gap: 12px;
}

.fl-pagination-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.fl-count-text {
  font-size: 13px;
  color: #94a3b8;
}

.fl-size-select {
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  padding: 0 4px;
}
.fl-size-select:hover { color: #64748b; }

.fl-pagination {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.pg-btn {
  font-size: 13px;
  font-weight: 500;
  padding: 7px 14px;
  border-radius: 9px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
  transition: all .15s;
}
.pg-btn:hover:not(:disabled) {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}
.pg-btn:disabled { opacity: .4; cursor: not-allowed; }

.pg-num {
  min-width: 36px;
  padding: 7px 10px;
  text-align: center;
}
.pg-num.active {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border-color: transparent;
  font-weight: 700;
}

.pg-ellipsis {
  font-size: 13px;
  color: #94a3b8;
  padding: 0 4px;
  user-select: none;
}

.pg-jump-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #94a3b8;
  margin-left: 4px;
}

.pg-jump-input {
  width: 52px;
  height: 34px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  text-align: center;
  font-size: 13px;
  color: #334155;
  outline: none;
  padding: 0 6px;
}
.pg-jump-input:focus { border-color: #6366f1; }
.pg-jump-input::-webkit-inner-spin-button,
.pg-jump-input::-webkit-outer-spin-button { -webkit-appearance: none; }

.pg-jump-go { padding: 7px 12px; }

/* 卡片 */
.fl-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s;
}
.fl-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }

.fl-photo-wrap {
  position: relative;
  width: 100%;
  padding-top: 100%;
  background: #f8fafc;
}

.fl-photo {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.fl-photo-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
}

.fl-loading-mask {
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,0.75);
  display: flex;
  align-items: center;
  justify-content: center;
}

.fl-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #e2e8f0;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: fl-spin 0.8s linear infinite;
}

@keyframes fl-spin {
  to { transform: rotate(360deg); }
}

.fl-info {
  padding: 12px 12px 8px;
  flex: 1;
}

.fl-tag-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fl-color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.fl-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.fl-classify {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 8px;
}

.fl-classify span {
  max-width: 100%;
  padding: 2px 6px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 11px;
  line-height: 1.45;
}

.fl-classify .fl-remix-ok {
  background: #dcfce7;
  color: #166534;
}

.fl-classify .fl-remix-blocked,
.fl-classify .fl-status-failed {
  background: #fee2e2;
  color: #991b1b;
}

.fl-classify .fl-status {
  background: #eef2ff;
  color: #4338ca;
}

.fl-classify .fl-note {
  background: #fff7ed;
  color: #9a3412;
}

.fl-actions {
  padding: 0 12px 12px;
}

.fl-btn-select {
  width: 100%;
  padding: 7px 0;
  border: none;
  border-radius: 6px;
  background: #6366f1;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.fl-btn-select:hover:not(:disabled) { background: #4f46e5; }
.fl-btn-select:disabled { background: #c7d2fe; cursor: not-allowed; }

/* 配置弹窗样式 */
.config-form { min-height: 120px; }

.cf-row { margin-bottom: 18px; }

.cf-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 6px;
}

.cf-hint {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.dlg-btn-cancel,
.dlg-btn-primary {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  margin-left: 8px;
}

.dlg-btn-cancel { background: #f1f5f9; color: #475569; }
.dlg-btn-cancel:hover { background: #e2e8f0; }

.dlg-btn-primary {
  background: #6366f1;
  color: #fff;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.dlg-btn-primary:hover:not(:disabled) { background: #4f46e5; }
.dlg-btn-primary:disabled { background: #c7d2fe; cursor: not-allowed; }

.btn-spin {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: fl-spin 0.8s linear infinite;
}
</style>
