<template>
  <div class="dt-page">
    <div class="dt-header">
      <h1 class="dt-title">每日生成任务</h1>
      <div class="dt-actions">
        <!-- Date Picker for selecting the target date -->
        <el-date-picker
          v-model="targetDate"
          type="date"
          placeholder="选择生成日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="loadDailyJobs"
          style="width: 200px; margin-right: 12px;"
          :clearable="false"
        />
        <!-- Fetch Results from GCS Button -->
        <el-button
          v-if="jobs.length > 0"
          type="success"
          @click="handleFetchResults"
          :loading="fetchingResults"
          class="dt-fetch-btn"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          获取生成结果
        </el-button>
        <!-- Upload JSON to GCS Button -->
        <el-button
          v-if="jobs.length > 0"
          type="primary"
          @click="handleUpload"
          :loading="uploading"
          class="dt-upload-btn"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          上传任务至云端
        </el-button>
      </div>
    </div>

    <!-- Content Area -->
    <div v-loading="loading" class="dt-content">
      <div v-if="jobs.length === 0" class="dt-empty">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        <p>该日期下暂无生成记录</p>
      </div>
      
      <div v-else class="dt-list">
        <div v-for="(job, index) in jobs" :key="job.id" class="dt-card">
          <div class="dt-card-header-actions">
            <!-- Order Badge -->
            <div class="dt-card-badge">{{ index + 1 }}</div>
            <!-- Status Badge -->
            <span class="dt-status-badge" :class="`dt-status-${job.status}`">{{ statusLabel(job.status) }}</span>
            <!-- Rollback Button -->
            <el-button
              v-if="canRollback(job)"
              size="small"
              plain
              class="dt-rollback-btn"
              :loading="rollbacking === job.id"
              @click="handleRollback(job)"
              :title="PREV_STATUS_LABEL[job.status]"
            >
              <svg v-if="rollbacking !== job.id" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:4px"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
              {{ PREV_STATUS_LABEL[job.status] }}
            </el-button>
            <!-- Delete Button (Only for today's pending tasks) -->
            <el-button
              v-if="isToday && (job.status === 'pending' || job.status === 'generating')"
              type="danger"
              circle
              plain
              class="vc-btn-del dt-delete-btn"
              @click="handleDelete(job)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
            </el-button>
          </div>
          
          <div class="dt-card-body">
            <!-- Left: Image Preview -->
            <div class="dt-image-wrap">
              <img v-if="job.image" :src="job.image" class="dt-image" />
              <div v-else class="dt-image-placeholder">暂无截图</div>
              <div class="dt-duration-badge" v-if="job.duration">{{ formatDuration(job.duration) }}</div>
            </div>
            
            <!-- Right: Prompt Text -->
            <div class="dt-prompt-wrap">
              <div class="dt-prompt-label">最终 Prompt</div>
              <div class="dt-prompt-content markdown-body" v-html="renderMarkdown(job.prompt)"></div>
            </div>
          </div>

          <!-- Shots Grid -->
          <div v-if="job.shots && job.shots.length > 0" class="dt-shots-section">
            <div class="dt-shots-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              造型图 (Shots)
            </div>
            <div class="dt-shots-grid">
              <el-image
                v-for="(shot, idx) in job.shots"
                :key="idx"
                :src="shot.image_url || shot"
                :preview-src-list="job.shots.map(s => s.image_url || s)"
                :initial-index="idx"
                fit="cover"
                class="dt-shot-img"
                lazy
              />
            </div>
          </div>

          <!-- Result Videos (reviewing status) -->
          <div v-if="job.result_videos && job.result_videos.length > 0" class="dt-results-section">
            <div class="dt-shots-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
              生成结果视频
            </div>
            <div class="dt-results-grid">
              <div v-for="(rv, idx) in job.result_videos" :key="idx" class="dt-result-video-wrap">
                <video
                  :src="rv.video_url"
                  controls
                  class="dt-result-video"
                  preload="metadata"
                />
                <div class="dt-result-label">候选 {{ idx + 1 }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="dt-footer-actions">
           <el-button 
            type="primary" 
            size="large"
            @click="handleUpload" 
            :loading="uploading"
            class="dt-upload-large-btn"
          >
            以 JSON 格式打包今日任务并上传
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchDailyGenerations, uploadDailyGenerations, deleteDailyGeneration, fetchDailyResults, rollbackGenerationStatus } from '../api/video_generations.js'
import { renderMarkdown } from '../utils/markdown'

/** STATE **/
const loading = ref(false)
const uploading = ref(false)
const fetchingResults = ref(false)
const rollbacking = ref(null)   // job.id being rolled back
const targetDate = ref('')
const jobs = ref([])

/** COMPUTED **/
const isToday = computed(() => {
  const now = new Date()
  const yyyy = now.getFullYear()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  const todayStr = `${yyyy}-${mm}-${dd}`
  return targetDate.value === todayStr
})

const STATUS_LABELS = {
  pending:         '待生成',
  generating:      '生成中',
  reviewing:       '待审核',
  pending_publish: '待发布',
  published:       '已发布',
}

const PREV_STATUS_LABEL = {
  generating:      '回退到待生成',
  reviewing:       '回退到生成中',
  pending_publish: '回退到待审核',
  published:       '回退到待发布',
}

function statusLabel(s) { return STATUS_LABELS[s] || s }

function canRollback(job) {
  return job.status in PREV_STATUS_LABEL
}

async function handleRollback(job) {
  const label = PREV_STATUS_LABEL[job.status]
  try {
    await ElMessageBox.confirm(
      `确定将此任务「${label}」吗？`,
      '回退状态',
      { confirmButtonText: '确认回退', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  rollbacking.value = job.id
  try {
    const updated = await rollbackGenerationStatus(job.id)
    const idx = jobs.value.findIndex(j => j.id === job.id)
    if (idx >= 0) jobs.value[idx] = updated
    ElMessage.success(`已${label}`)
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '回退失败')
  } finally {
    rollbacking.value = null
  }
}

/** Computed Formatting **/
function formatDuration(secondsStr) {
  const seconds = parseFloat(secondsStr)
  if (!seconds || isNaN(seconds)) return secondsStr
  
  let s = Math.floor(seconds)
  if (s > 15) s = 15
  return `${s.toString().padStart(2, '0')}s`
}


/** DATA LOADING **/
async function loadDailyJobs() {
  if (!targetDate.value) return
  loading.value = true
  try {
    jobs.value = await fetchDailyGenerations(targetDate.value)
  } catch (error) {
    console.error('Failed to fetch daily generations:', error)
    ElMessage.error('获取生成任务失败，请重试')
    jobs.value = []
  } finally {
    loading.value = false
  }
}

/** ACTIONS **/
async function handleUpload() {
  if (!targetDate.value || jobs.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(
      `确定要将 ${targetDate.value} 日期的 ${jobs.value.length} 个任务按顺序打包上传吗？`,
      '上传任务',
      {
        confirmButtonText: '确定打包',
        cancelButtonText: '取消',
        customClass: 'vc-confirm-dialog'
      }
    )
    
    uploading.value = true
    const res = await uploadDailyGenerations(targetDate.value)
    if (res.status === 'success') {
      ElMessage.success({
        message: `任务已成功上传至 ${res.gcs_url}`,
        duration: 5000
      })
    }
  } catch (cancelOrError) {
    if (cancelOrError !== 'cancel') {
      console.error('Failed to upload jobs:', cancelOrError)
      ElMessage.error('上传打包任务失败')
    }
  } finally {
    uploading.value = false
  }
}

async function handleFetchResults() {
  if (!targetDate.value) return
  try {
    fetchingResults.value = true
    const res = await fetchDailyResults(targetDate.value)
    const msg = `获取结果完成：${res.updated} 个任务已更新为待审核，${res.skipped} 个跳过`
    if (res.errors && res.errors.length > 0) {
      ElMessage.warning({ message: msg + `，${res.errors.length} 个文件未找到`, duration: 6000 })
    } else {
      ElMessage.success({ message: msg, duration: 5000 })
    }
    await loadDailyJobs()
  } catch (e) {
    console.error('Failed to fetch results:', e)
    ElMessage.error(e?.response?.data?.detail || '获取结果失败，请重试')
  } finally {
    fetchingResults.value = false
  }
}

async function handleDelete(job) {
  try {
    await ElMessageBox.confirm(
      '确定要删除该生成任务吗？此操作不可恢复。',
      '删除任务',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'vc-btn-del',
        customClass: 'vc-confirm-dialog'
      }
    )
    
    await deleteDailyGeneration(job.id)
    ElMessage.success('任务删除成功')
    
    // Refresh the list locally
    jobs.value = jobs.value.filter(j => j.id !== job.id)
  } catch (cancelOrError) {
    if (cancelOrError !== 'cancel') {
      console.error('Failed to delete job:', cancelOrError)
      ElMessage.error('删除生成任务失败')
    }
  }
}

/** INIT **/
onMounted(() => {
  // Set default to today "YYYY-MM-DD"
  const now = new Date()
  const yyyy = now.getFullYear()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  targetDate.value = `${yyyy}-${mm}-${dd}`
  
  loadDailyJobs()
})
</script>

<style scoped>
.dt-page {
  padding: 32px 40px;
  max-width: 1200px;
  margin: 0 auto;
  min-height: calc(100vh - 60px);
}

.dt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 40px;
  padding-bottom: 24px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
}

.dt-title {
  margin: 0;
  font-size: 32px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.8px;
  background: linear-gradient(135deg, #1e293b 0%, #475569 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.dt-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

:deep(.el-date-editor.el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
  border: 1px solid #e2e8f0;
  padding: 8px 16px;
  height: 42px;
  font-weight: 500;
  color: #1e293b;
  background: white;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-date-editor.el-input__wrapper:hover),
:deep(.el-date-editor.el-input__wrapper.is-focus) {
  box-shadow: 0 4px 12px rgba(99,102,241,0.15) !important;
  border-color: #818cf8;
  transform: translateY(-1px);
}

:deep(.el-input__inner) {
  font-weight: 600;
  color: #334155;
}

.dt-fetch-btn {
  font-weight: 600;
  border-radius: 10px;
  padding: 10px 20px;
  height: auto;
  border: none;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(16,185,129,0.25);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.dt-fetch-btn:hover {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(16,185,129,0.35);
  color: white;
}

.dt-fetch-btn:active {
  transform: translateY(1px);
}

.dt-upload-btn {
  font-weight: 600;
  border-radius: 10px;
  padding: 10px 20px;
  height: auto;
  border: none;
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(99,102,241,0.25);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.dt-upload-btn:hover {
  background: linear-gradient(135deg, #4f46e5 0%, #9333ea 100%);
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(99,102,241,0.35);
  color: white;
}

.dt-upload-btn:active {
  transform: translateY(1px);
}

/* Empty State */
.dt-empty {
  text-align: center;
  padding: 100px 0;
  color: #94a3b8;
  background: #f8fafc;
  border-radius: 20px;
  border: 2px dashed #e2e8f0;
  margin-top: 20px;
}
.dt-empty p {
  margin-top: 20px;
  font-size: 16px;
  font-weight: 500;
}

/* List Area */
.dt-list {
  display: flex;
  flex-direction: column;
  gap: 32px;
  margin-bottom: 60px;
}

.dt-card {
  position: relative;
  background: #ffffff;
  border-radius: 20px;
  border: 1px solid rgba(226,232,240,0.8);
  padding: 32px;
  box-shadow: 0 4px 20px -4px rgba(0,0,0,0.04), 0 2px 4px -2px rgba(0,0,0,0.02);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.dt-card:hover {
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04);
  transform: translateY(-4px);
  border-color: #cbd5e1;
}

.dt-card-badge {
  position: absolute;
  top: -16px;
  left: -16px;
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  color: white;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 16px;
  box-shadow: 0 8px 16px -4px rgba(99,102,241,0.4);
  transform: rotate(-3deg);
  border: 4px solid #fff;
}

.dt-card:hover .dt-card-badge {
  transform: rotate(0) scale(1.05);
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.dt-rollback-btn {
  position: absolute;
  top: 24px;
  right: 68px;
  opacity: 0;
  transform: scale(0.9);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  background: white;
  border-color: #fcd34d;
  color: #b45309;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  height: auto;
  display: flex;
  align-items: center;
}

.dt-rollback-btn:hover {
  background: #fef3c7;
  border-color: #f59e0b;
  color: #92400e;
}

.dt-card:hover .dt-rollback-btn {
  opacity: 1;
  transform: scale(1);
}

.dt-delete-btn {
  position: absolute;
  top: 24px;
  right: 24px;
  opacity: 0;
  transform: scale(0.9);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  background: white;
  border-color: #fca5a5;
  color: #ef4444;
}

.dt-delete-btn:hover {
  background: #fee2e2;
  border-color: #ef4444;
  color: #dc2626;
  transform: scale(1.05);
}

.dt-card:hover .dt-delete-btn {
  opacity: 1;
  transform: scale(1);
}

.dt-card-body {
  display: flex;
  gap: 32px;
  align-items: stretch;
}

/* Image Column */
.dt-image-wrap {
  position: relative;
  flex-shrink: 0;
  width: 260px;
  border-radius: 16px;
  overflow: hidden;
  background: #f1f5f9;
  aspect-ratio: 9/16;
  border: 1px solid rgba(226,232,240,0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
}

.dt-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s ease;
}

.dt-card:hover .dt-image {
  transform: scale(1.03);
}

.dt-image-placeholder {
  color: #94a3b8;
  font-size: 14px;
  font-weight: 500;
}

.dt-duration-badge {
  position: absolute;
  bottom: 12px;
  right: 12px;
  background: rgba(15,23,42,0.75);
  color: white;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}

/* Prompt Column */
.dt-prompt-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.dt-prompt-label {
  font-size: 14px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dt-prompt-label::before {
  content: '';
  width: 8px;
  height: 8px;
  background: #818cf8;
  border-radius: 50%;
  box-shadow: 0 0 10px rgba(129,140,248,0.5);
}

.dt-prompt-content {
  background: #f8fafc;
  padding: 24px;
  border-radius: 16px;
  border: 1px solid rgba(226,232,240,0.8);
  flex: 1;
  overflow-y: auto;
  max-height: 480px;
  font-size: 15px;
  color: #334155;
  line-height: 1.6;
}

.dt-prompt-content::-webkit-scrollbar {
  width: 6px;
}
.dt-prompt-content::-webkit-scrollbar-track {
  background: transparent;
}
.dt-prompt-content::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

/* Shots Section */
.dt-shots-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid rgba(226, 232, 240, 0.6);
}

.dt-shots-title {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

.dt-shots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 16px;
}

.dt-shot-img {
  width: 100%;
  aspect-ratio: 9/16;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  border: 1px solid rgba(226,232,240,0.8);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
}

.dt-shot-img:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
  border-color: #a855f7;
}

/* Footer Actions */
.dt-footer-actions {
  display: flex;
  justify-content: center;
  margin-top: 40px;
  padding-top: 40px;
  border-top: 2px dashed #f1f5f9;
}

.dt-upload-large-btn {
  font-weight: 700;
  font-size: 16px;
  padding: 24px 64px;
  border-radius: 16px;
  border: none;
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  color: white;
  box-shadow: 0 10px 25px -5px rgba(99,102,241,0.4), 0 8px 10px -6px rgba(99,102,241,0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.dt-upload-large-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 20px 30px -5px rgba(99,102,241,0.5), 0 10px 15px -5px rgba(99,102,241,0.2);
  background: linear-gradient(135deg, #4338ca 0%, #6d28d9 100%);
}

.dt-upload-large-btn:active {
  transform: translateY(1px);
}

/* Result Videos Section */
.dt-results-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid rgba(226, 232, 240, 0.6);
}

.dt-results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.dt-result-video-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dt-result-video {
  width: 100%;
  aspect-ratio: 9/16;
  border-radius: 12px;
  background: #0f172a;
  object-fit: contain;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  border: 1px solid rgba(226,232,240,0.8);
}

.dt-result-label {
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

/* Status badge on cards */
.dt-status-badge {
  position: absolute;
  top: 24px;
  right: 24px;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
}
.dt-status-pending         { background: #f1f5f9; color: #475569; }
.dt-status-generating      { background: #fef9c3; color: #a16207; }
.dt-status-reviewing       { background: #fed7aa; color: #c2410c; }
.dt-status-pending_publish { background: #dbeafe; color: #1d4ed8; }
.dt-status-published       { background: #dcfce7; color: #166534; }
</style>
