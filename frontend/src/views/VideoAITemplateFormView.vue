<template>
  <div class="vtfd-page">
    <!-- Header -->
    <div class="vtfd-header">
      <div class="vtfd-back" @click="$router.push('/dashboard/video-ai-templates')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
        返回列表
      </div>
    </div>

    <div v-loading="loading" class="vtfd-content">
      <!-- Video Selection Prompt -->
      <div v-if="!selectedVideoSource" class="vtfd-select-prompt">
        <div class="vtfd-prompt-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>
        </div>
        <h2 class="vtfd-prompt-title">选择视频源开始创作</h2>
        <p class="vtfd-prompt-desc">从视频库中选择一个视频，AI将自动分析内容并生成造型图</p>
        <el-select
          v-model="form.video_source_id"
          placeholder="选择视频源"
          filterable
          size="large"
          style="width: 400px"
          @change="handleVideoChange"
        >
          <el-option
            v-for="vs in videoSources"
            :key="vs.id"
            :value="vs.id"
            :label="vsLabel(vs)"
          >
            <div class="vs-option">
              <span v-if="vs.platform" class="vs-option-platform">{{ platformLabel(vs.platform) }}</span>
              <span class="vs-option-title">{{ vs.video_title || '无标题' }}</span>
              <span class="vs-option-blogger">@{{ vs.blogger_name || '未知' }}</span>
            </div>
          </el-option>
        </el-select>
      </div>

      <!-- Main Content -->
      <template v-else>
        <div class="vtfd-top">
          <!-- Left: Player -->
          <div class="vtfd-player-section">
            <!-- Video Player -->
            <div class="vtfd-player-wrap">
              <video
                v-if="selectedVideoSource.local_video_url || selectedVideoSource.video_url"
                :src="selectedVideoSource.local_video_url || selectedVideoSource.video_url"
                controls
                class="vtfd-video"
              />
              <div v-else class="vtfd-noplayer">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>
                <div style="color:#94a3b8;font-size:13px;margin-top:8px">无视频地址</div>
              </div>
            </div>

            <!-- Change Video Button -->
            <el-button size="large" @click="showVideoSelector = true" style="width: 100%; margin-top: 12px;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:6px"><path d="M23 15v4a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              更换视频
            </el-button>
          </div>

          <!-- Right: Editable Info + AI Results -->
          <div class="vtfd-info-section">
            <!-- Editable Title & Description -->
            <div class="vtfd-card">
              <div class="vtfd-card-title">模板信息（可编辑）</div>

              <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
                <el-form-item label="模板标题" prop="title">
                  <el-input
                    v-model="form.title"
                    placeholder="请输入模板标题"
                    size="large"
                  />
                </el-form-item>

                <el-form-item label="模板描述">
                  <el-input
                    v-model="form.description"
                    type="textarea"
                    :rows="4"
                    placeholder="可选描述"
                    size="large"
                  />
                </el-form-item>
              </el-form>
            </div>

            <!-- Original Video Info -->
            <div class="vtfd-card">
              <div class="vtfd-card-title">原始视频信息</div>
              <div class="vtfd-info-rows">
                <div class="vtfd-info-row">
                  <span class="vtfd-info-label">博主</span>
                  <span class="vtfd-info-val">@{{ selectedVideoSource.blogger_name || '-' }}</span>
                </div>
                <div class="vtfd-info-row">
                  <span class="vtfd-info-label">平台</span>
                  <span class="vtfd-info-val">{{ platformLabel(selectedVideoSource.platform) }}</span>
                </div>
                <div v-if="selectedVideoSource.video_desc" class="vtfd-info-row">
                  <span class="vtfd-info-label">原描述</span>
                  <span class="vtfd-info-val vtfd-desc">{{ selectedVideoSource.video_desc }}</span>
                </div>
              </div>
            </div>

            <!-- AI Analysis Section -->
            <div class="vtfd-card vtfd-ai-card">
              <div class="vtfd-card-header">
                <div class="vtfd-card-title">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" style="margin-right:6px"><path d="M12 2a10 10 0 1 1 10 10H12V2z"/></svg>
                  AI 视频分析与造型图
                </div>
                <!-- Status Badge -->
                <div v-if="templateStatus" :class="['vtfd-status-badge', `vtfd-status-${templateStatus}`]">
                  {{ statusLabel(templateStatus) }}
                </div>
              </div>

              <!-- Progress/Status -->
              <div v-if="isProcessing" class="vtfd-progress">
                <el-progress :percentage="progressPercentage" :status="progressStatus" :indeterminate="isProcessing && progressPercentage === 0" />
                <p class="vtfd-progress-text">{{ progressText }}</p>
              </div>

              <!-- Empty State - Show before processing starts -->
              <div v-if="!form.prompt_description && !isProcessing && !templateStatus" class="vtfd-empty-state">
                <div class="vtfd-empty-icon">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#c7d2fe" stroke-width="1.5"><path d="M12 2a10 10 0 1 1 10 10H12V2z"/></svg>
                </div>
                <div class="vtfd-empty-title">保存后自动开始 AI 分析</div>
                <div class="vtfd-empty-desc">AI 将自动理解视频内容并提取穿搭造型图</div>
              </div>

              <!-- Error State -->
              <div v-if="templateStatus === 'fail' && errorMessage" class="vtfd-error-state">
                <div class="vtfd-error-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                </div>
                <div class="vtfd-error-title">处理失败</div>
                <div class="vtfd-error-desc">{{ errorMessage }}</div>
                <el-button size="small" type="primary" @click="handleRetry">重试</el-button>
              </div>

              <!-- AI Understanding Section -->
              <div v-if="form.prompt_description" class="vtfd-section">
                <div class="vtfd-section-header">
                  <span class="vtfd-section-tag">AI 理解</span>
                </div>
                <div class="vtfd-section-content">{{ form.prompt_description }}</div>
              </div>

              <!-- Generated Images Section -->
              <div class="vtfd-section vtfd-section-images">
                <div class="vtfd-section-header">
                  <span class="vtfd-section-tag">造型图</span>
                  <span v-if="extractedShots && extractedShots.length > 0" class="vtfd-section-count">({{ extractedShots.length }})</span>
                </div>

                <!-- Images Grid -->
                <div v-if="extractedShots && extractedShots.length > 0" class="vtfd-images-grid">
                  <div v-for="(shot, idx) in extractedShots" :key="idx" class="vtfd-shot-card">
                    <div class="vtfd-shot-img-wrap">
                      <img :src="shot.image_url" class="vtfd-shot-img" />
                    </div>
                    <div v-if="shot.description" class="vtfd-shot-desc">{{ shot.description }}</div>
                  </div>
                </div>

                <!-- Empty Images State -->
                <div v-else-if="!isProcessing && templateStatus !== 'pending' && templateStatus !== 'understanding' && templateStatus !== 'extracting'" class="vtfd-images-empty">
                  <div class="vtfd-images-empty-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                  </div>
                  <div class="vtfd-images-empty-text">暂无造型图</div>
                </div>

                <!-- Loading Images State -->
                <div v-if="isProcessing && ['downloading', 'uploading'].includes(templateStatus)" class="vtfd-images-loading">
                  <div class="vtfd-loading-card">
                    <el-skeleton :rows="1" animated />
                  </div>
                  <div class="vtfd-loading-card">
                    <el-skeleton :rows="1" animated />
                  </div>
                  <div class="vtfd-loading-card">
                    <el-skeleton :rows="1" animated />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="vtfd-actions">
          <el-button type="primary" size="large" :loading="saving" @click="handleSave">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
            {{ isEdit ? '保存修改' : '创建模板' }}
          </el-button>
          <el-button size="large" @click="$router.push('/dashboard/video-ai-templates')">取消</el-button>
        </div>
      </template>
    </div>

    <!-- Video Selector Dialog -->
    <el-dialog
      v-model="showVideoSelector"
      title="选择视频源"
      width="600px"
    >
      <el-select
        v-model="tempVideoId"
        placeholder="选择视频源"
        filterable
        size="large"
        style="width: 100%"
      >
        <el-option
          v-for="vs in videoSources"
          :key="vs.id"
          :value="vs.id"
          :label="vsLabel(vs)"
        >
          <div class="vs-option">
            <span v-if="vs.platform" class="vs-option-platform">{{ platformLabel(vs.platform) }}</span>
            <span class="vs-option-title">{{ vs.video_title || '无标题' }}</span>
            <span class="vs-option-blogger">@{{ vs.blogger_name || '未知' }}</span>
          </div>
        </el-option>
      </el-select>
      <template #footer>
        <el-button @click="showVideoSelector = false">取消</el-button>
        <el-button type="primary" @click="confirmVideoChange">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  createVideoAITemplate,
  fetchVideoAITemplate,
  fetchVideoAITemplateState,
  patchVideoAITemplate,
  startVideoAITemplate,
  resumeVideoAITemplate,
} from '../api/video_ai_templates'
import { fetchVideoSources } from '../api/video_sources'
import { isDuplicateRequestError } from '../api/http'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => Boolean(route.params.id))

const loading = ref(false)
const saving = ref(false)
const formRef = ref(null)
const videoSources = ref([])
const showVideoSelector = ref(false)
const tempVideoId = ref(null)

// Template state
const templateStatus = ref(null) // pending, understanding, extracting, downloading, uploading, success, fail, paused
const errorMessage = ref('')
const pollTimer = ref(null)

const form = reactive({
  title: '',
  description: '',
  video_source_id: null,
  prompt_description: '',
  extracted_shots: null,
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}

const selectedVideoSource = computed(() =>
  form.video_source_id ? videoSources.value.find(v => v.id === form.video_source_id) : null
)

const extractedShots = computed(() => form.extracted_shots)

// Processing state
const isProcessing = computed(() =>
  templateStatus.value && ['pending', 'understanding', 'extracting', 'downloading', 'uploading'].includes(templateStatus.value)
)

const progressPercentage = computed(() => {
  const statusMap = {
    pending: 10,
    understanding: 30,
    extracting: 50,
    downloading: 70,
    uploading: 90,
    success: 100,
    fail: 0,
    paused: 0,
  }
  return statusMap[templateStatus.value] || 0
})

const progressStatus = computed(() => {
  if (templateStatus.value === 'fail') return 'exception'
  if (templateStatus.value === 'success') return 'success'
  return undefined
})

const progressText = computed(() => {
  const textMap = {
    pending: '等待开始处理...',
    understanding: 'AI 正在理解视频内容...',
    extracting: 'AI 正在提取穿搭造型...',
    downloading: '正在下载穿搭图片...',
    uploading: '正在上传图片到CDN...',
    success: '处理完成！',
    fail: '处理失败',
    paused: '已暂停',
  }
  return textMap[templateStatus.value] || ''
})

function statusLabel(status) {
  const labels = {
    pending: '排队中',
    understanding: '理解中',
    extracting: '提取中',
    downloading: '下载中',
    uploading: '上传中',
    success: '成功',
    fail: '失败',
    paused: '已暂停',
  }
  return labels[status] || status
}

function vsLabel(vs) {
  return `${vs.video_title || '无标题'} - @${vs.blogger_name || '未知'}`
}

function platformLabel(p) {
  const labels = { youtube: 'YouTube', tiktok: 'TikTok' }
  return labels[p] || (p || '其他')
}

function handleVideoChange() {
  // Reset state when video changes
  form.prompt_description = ''
  form.extracted_shots = null
  templateStatus.value = null
  errorMessage.value = ''

  // Auto-fill title and description from video
  if (selectedVideoSource.value) {
    if (!form.title) {
      form.title = selectedVideoSource.value.video_title || ''
    }
    if (!form.description && selectedVideoSource.value.video_desc) {
      form.description = selectedVideoSource.value.video_desc
    }
  }
}

function confirmVideoChange() {
  if (tempVideoId.value) {
    form.video_source_id = tempVideoId.value
    handleVideoChange()
  }
  showVideoSelector.value = false
  tempVideoId.value = null
}

// Poll for template state
async function pollState() {
  if (!route.params.id) return

  try {
    const state = await fetchVideoAITemplateState(route.params.id)

    // Update form with latest data
    if (state.prompt_description && state.prompt_description !== form.prompt_description) {
      form.prompt_description = state.prompt_description
    }
    if (state.extracted_shots && JSON.stringify(state.extracted_shots) !== JSON.stringify(form.extracted_shots)) {
      form.extracted_shots = state.extracted_shots
    }

    templateStatus.value = state.status
    errorMessage.value = state.error_message || ''

    // Stop polling if terminal state reached
    if (['success', 'fail', 'paused'].includes(state.status)) {
      stopPolling()
    }
  } catch (err) {
    console.error('Failed to poll state:', err)
  }
}

function startPolling() {
  stopPolling()
  pollState() // Immediate poll
  pollTimer.value = setInterval(pollState, 3000) // Poll every 3 seconds
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function handleRetry() {
  if (!route.params.id) return

  try {
    await resumeVideoAITemplate(route.params.id)
    templateStatus.value = 'pending'
    errorMessage.value = ''
    startPolling()
    ElMessage.success('已重新开始处理')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  }
}

async function loadData() {
  if (!isEdit.value) return

  loading.value = true
  try {
    const data = await fetchVideoAITemplate(route.params.id)
    Object.assign(form, {
      title: data.title,
      description: data.description,
      video_source_id: data.video_source_id,
      prompt_description: data.prompt_description,
      extracted_shots: data.extracted_shots,
    })
    templateStatus.value = data.process_status
    errorMessage.value = data.process_error || ''

    // Start polling if in progress
    if (['pending', 'understanding', 'extracting', 'downloading', 'uploading'].includes(data.process_status)) {
      startPolling()
    }
  } catch (err) {
    if (isDuplicateRequestError(err)) return
    ElMessage.error(err?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadVideos() {
  try {
    const data = await fetchVideoSources({ page: 1, page_size: 100 })
    videoSources.value = data.items || []
  } catch { /* ignore */ }
}

async function handleSave() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  saving.value = true
  try {
    let templateId
    if (isEdit.value) {
      await patchVideoAITemplate(route.params.id, form)
      templateId = route.params.id
    } else {
      const result = await createVideoAITemplate(form)
      templateId = result.id

      // Start AI processing after creation
      await startVideoAITemplate(templateId)
      ElMessage.success('创建成功，AI正在处理中...')
    }

    // Navigate to edit page to show progress
    if (!isEdit.value) {
      router.replace(`/dashboard/video-ai-templates/${templateId}`)
    } else {
      ElMessage.success('保存成功')
    }
  } catch (err) {
    if (isDuplicateRequestError(err)) return
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadVideos()
  loadData()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
/* Page layout - similar to VideoDetailView */
.vtfd-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
}

.vtfd-header {
  margin-bottom: 20px;
}

.vtfd-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
}

.vtfd-back:hover { color: #6366f1; }

.vtfd-content {
  min-height: 400px;
}

/* Selection Prompt */
.vtfd-select-prompt {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%);
  border: 2px dashed #c7d2fe;
  border-radius: 20px;
  padding: 60px 40px;
  text-align: center;
}

.vtfd-prompt-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}

.vtfd-prompt-title {
  font-size: 24px;
  font-weight: 800;
  color: #3730a3;
  margin: 0 0 12px 0;
}

.vtfd-prompt-desc {
  font-size: 15px;
  color: #6366f1;
  margin: 0 0 32px 0;
}

/* Top layout */
.vtfd-top {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 28px;
  margin-bottom: 24px;
}

@media (max-width: 1024px) {
  .vtfd-top { grid-template-columns: 1fr; }
}

/* Player section */
.vtfd-player-section {
  display: flex;
  flex-direction: column;
}

.vtfd-player-wrap {
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  aspect-ratio: 16/9;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vtfd-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.vtfd-noplayer {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

/* Info section */
.vtfd-info-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vtfd-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 12px;
  padding: 20px;
}

.vtfd-ai-card {
  border-color: #c7d2fe;
  background: linear-gradient(135deg, #fafbff 0%, #f0f9ff 100%);
}

.vtfd-card-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

.vtfd-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.vtfd-info-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vtfd-info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
}

.vtfd-info-row:last-child {
  border-bottom: none;
}

.vtfd-info-label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .04em;
}

.vtfd-info-val {
  font-size: 13px;
  color: #334155;
  font-weight: 600;
  text-align: right;
  max-width: 200px;
  word-break: break-word;
}

.vtfd-desc {
  white-space: pre-wrap;
  line-height: 1.5;
  font-weight: 400 !important;
  color: #64748b !important;
  font-size: 12px !important;
}

/* AI Section */
.vtfd-progress {
  margin: 16px 0;
}

.vtfd-progress-text {
  font-size: 13px;
  color: #64748b;
  margin-top: 8px;
}

/* Status Badge */
.vtfd-status-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.vtfd-status-pending { background: #e0f2fe; color: #0369a1; }
.vtfd-status-understanding { background: #fef3c7; color: #b45309; }
.vtfd-status-extracting { background: #e0e7ff; color: #4338ca; }
.vtfd-status-downloading { background: #fce7f3; color: #be185d; }
.vtfd-status-uploading { background: #f3e8ff; color: #7c3aed; }
.vtfd-status-success { background: #dcfce7; color: #15803d; }
.vtfd-status-fail { background: #fee2e2; color: #b91c1c; }
.vtfd-status-paused { background: #f1f5f9; color: #475569; }

/* Empty State */
.vtfd-empty-state {
  text-align: center;
  padding: 32px 20px;
  background: #fff;
  border-radius: 8px;
  border: 1px dashed #c7d2fe;
}

.vtfd-empty-icon {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}

.vtfd-empty-title {
  font-size: 14px;
  font-weight: 600;
  color: #3730a3;
  margin-bottom: 4px;
}

.vtfd-empty-desc {
  font-size: 13px;
  color: #94a3b8;
}

/* Error State */
.vtfd-error-state {
  text-align: center;
  padding: 24px;
  background: #fef2f2;
  border-radius: 8px;
  border: 1px solid #fecaca;
}

.vtfd-error-icon {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}

.vtfd-error-title {
  font-size: 14px;
  font-weight: 600;
  color: #b91c1c;
  margin-bottom: 4px;
}

.vtfd-error-desc {
  font-size: 12px;
  color: #ef4444;
  margin-bottom: 12px;
  white-space: pre-wrap;
}

/* Section Style - Matching the design */
.vtfd-section {
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.vtfd-section:last-child {
  margin-bottom: 0;
}

.vtfd-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.vtfd-section-tag {
  display: inline-block;
  font-size: 13px;
  font-weight: 600;
  color: #6366f1;
  background: #e0e7ff;
  padding: 4px 12px;
  border-radius: 6px;
}

.vtfd-section-count {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
}

.vtfd-section-content {
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
  white-space: pre-wrap;
}

/* Images Section */
.vtfd-section-images {
  background: transparent;
  padding: 0;
}

.vtfd-images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
}

/* Shot Card - Matching design */
.vtfd-shot-card {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  border: 1px solid #e8edf5;
  transition: all 0.2s ease;
}

.vtfd-shot-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  transform: translateY(-2px);
}

.vtfd-shot-img-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4;
  background: #f1f5f9;
  overflow: hidden;
}

.vtfd-shot-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.vtfd-shot-desc {
  padding: 10px 12px;
  font-size: 12px;
  color: #64748b;
  text-align: center;
  line-height: 1.4;
  background: #fff;
  border-top: 1px solid #f1f5f9;
}

/* Empty Images State */
.vtfd-images-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px dashed #e2e8f0;
}

.vtfd-images-empty-icon {
  color: #cbd5e1;
  margin-bottom: 12px;
}

.vtfd-images-empty-text {
  font-size: 13px;
  color: #94a3b8;
}

/* Loading Images State */
.vtfd-images-loading {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
}

.vtfd-loading-card {
  background: #f8fafc;
  border-radius: 12px;
  padding: 0;
  overflow: hidden;
}

.vtfd-loading-card :deep(.el-skeleton) {
  padding: 0;
}

.vtfd-loading-card :deep(.el-skeleton__item) {
  height: 180px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Actions */
.vtfd-actions {
  display: flex;
  gap: 12px;
  padding-top: 24px;
  border-top: 1px solid #e8edf5;
}

/* Video option */
.vs-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.vs-option-platform {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: #eef2ff;
  color: #6366f1;
}

.vs-option-title {
  font-weight: 500;
  color: #0f172a;
}

.vs-option-blogger {
  font-size: 12px;
  color: #94a3b8;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .vtfd-page { padding: 16px; }
  .vtfd-select-prompt { padding: 40px 20px; }
  .vtfd-prompt-title { font-size: 20px; }
}
</style>
