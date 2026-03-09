<template>
  <div class="vt-page">
    <div class="vt-header">
      <h1 class="vt-title">任务管理</h1>
      <div class="vt-actions">
        <button class="vt-btn vt-btn-secondary" @click="goToConfig">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v6m0 6v6m5.3-10.3l-4.2 4.2m0 4.2l4.2 4.2M23 12h-6m-6 0H5m10.3 5.3l-4.2-4.2m0-4.2l4.2-4.2"/></svg>
          任务配置
        </button>
        <button class="vt-btn vt-btn-secondary" @click="loadTasks" :disabled="loading">
          <svg v-if="loading" class="vt-spinner" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          刷新
        </button>
        <el-date-picker
          v-model="targetDate"
          type="date"
          placeholder="选择日期"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          @change="loadTasks"
          style="width: 180px;"
          :clearable="false"
        />
        <button
          v-if="tasks.length > 0"
          class="vt-btn vt-btn-success"
          :class="{ 'is-loading': fetchingResults }"
          :disabled="fetchingResults"
          @click="handleFetchResults"
        >
          <svg v-if="!fetchingResults" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          <svg v-else class="vt-spinner" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          获取生成结果
        </button>
        <button
          v-if="tasks.length > 0"
          class="vt-btn vt-btn-primary"
          :class="{ 'is-loading': uploading }"
          :disabled="uploading"
          @click="handleUpload"
        >
          <svg v-if="!uploading" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          <svg v-else class="vt-spinner" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          上传任务至云端
        </button>
      </div>
    </div>

    <div v-loading="loading" class="vt-content">
      <div v-if="!loading && tasks.length === 0" class="vt-empty">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        <p>该日期下暂无任务</p>
      </div>

      <div v-else class="vt-list">
        <div v-for="(task, idx) in tasks" :key="task.id" class="vt-card">

          <!-- Card top bar: index, status, account/template, actions -->
          <div class="vt-card-topbar">
            <div class="vt-card-badge">{{ idx + 1 }}</div>
            <span class="vt-status-badge" :class="`vt-status-${task.status}`">
              {{ STATUS_LABELS[task.status] || task.status }}
            </span>
            <div class="vt-card-meta">
              <span class="vt-account-name">{{ task.account_name || '未知账号' }}</span>
              <span class="vt-sep">·</span>
              <span class="vt-template-title">{{ task.template_title || '未知模板' }}</span>
              <span class="vt-sep">·</span>
              <span class="vt-date-text">{{ task.target_date }}</span>
            </div>
            <!-- Sub-task progress -->
            <div class="vt-progress">
              <span
                v-for="n in 3"
                :key="n"
                class="vt-progress-seg"
                :class="n <= task.sub_tasks_done ? 'vt-seg-done' : 'vt-seg-empty'"
              ></span>
              <span class="vt-progress-label">{{ task.sub_tasks_done }}/3</span>
            </div>
            <!-- View detail -->
            <button class="vt-detail-btn" @click="goToDetail(task.id)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
              查看子任务
            </button>
          </div>

          <!-- Card body: cover image + prompt -->
          <div class="vt-card-body">
            <!-- Cover: first shot image -->
            <div class="vt-cover-wrap">
              <img
                v-if="firstShotUrl(task.shots)"
                :src="firstShotUrl(task.shots)"
                class="vt-cover-img"
              />
              <div v-else class="vt-cover-placeholder">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              </div>
              <div v-if="task.duration" class="vt-duration-badge">{{ task.duration }}</div>
            </div>

            <!-- Prompt -->
            <div class="vt-prompt-wrap">
              <div class="vt-prompt-label">生成 Prompt</div>
              <div class="vt-prompt-text">{{ task.prompt }}</div>
            </div>
          </div>

          <!-- Shots grid -->
          <div v-if="task.shots && task.shots.length > 0" class="vt-shots-section">
            <div class="vt-shots-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-right:5px"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              造型图 ({{ task.shots.length }} 张)
            </div>
            <div class="vt-shots-grid">
              <el-image
                v-for="(shot, i) in task.shots"
                :key="i"
                :src="shot.image_url || shot.url || shot"
                :preview-src-list="task.shots.map(s => s.image_url || s.url || s)"
                :initial-index="i"
                fit="cover"
                class="vt-shot-img"
                lazy
              />
            </div>
          </div>

        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchVideoTasks, uploadVideoTasks, fetchVideoTaskResults } from '../api/video_tasks.js'
import { isDuplicateRequestError } from '../api/http.js'

const STATUS_LABELS = {
  pending: '待处理',
  generating: '生成中',
  reviewing: '待审核',
  pending_publish: '待发布',
  published: '已发布',
  abandoned: '已废弃',
}

const router = useRouter()
const today = new Date().toISOString().slice(0, 10)
const targetDate = ref(today)
const tasks = ref([])
const loading = ref(false)
const uploading = ref(false)
const fetchingResults = ref(false)

function firstShotUrl(shots) {
  if (!shots || !shots.length) return ''
  const s = shots[0]
  return (typeof s === 'object' ? s.image_url || s.url : s) || ''
}

function goToDetail(taskId) {
  router.push({ name: 'video-task-detail', params: { id: taskId } })
}

function goToConfig() {
  router.push({ name: 'task-config' })
}

async function loadTasks() {
  if (!targetDate.value) return
  loading.value = true
  try {
    tasks.value = await fetchVideoTasks(targetDate.value)
  } catch (e) {
    if (!isDuplicateRequestError(e)) {
      ElMessage.error('加载任务失败')
    }
  } finally {
    loading.value = false
  }
}

async function handleUpload() {
  uploading.value = true
  try {
    const res = await uploadVideoTasks(targetDate.value)
    ElMessage.success(res.message || '后台上传任务已启动')
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function handleFetchResults() {
  fetchingResults.value = true
  try {
    const res = await fetchVideoTaskResults(targetDate.value)
    ElMessage.success(res.message || '后台获取结果任务已启动')
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '获取结果失败')
  } finally {
    fetchingResults.value = false
  }
}

onMounted(() => loadTasks())
</script>

<style scoped>
.vt-page {
  padding: 28px 32px;
  min-height: 100%;
  background: #f8fafc;
}

.vt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  gap: 12px;
  flex-wrap: wrap;
}

.vt-title {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.vt-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.vt-content {
  min-height: 200px;
}

.vt-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: #94a3b8;
  gap: 12px;
}

.vt-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Card ── */
.vt-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}

/* Top bar */
.vt-card-topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
  flex-wrap: wrap;
}

.vt-card-badge {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #f1f5f9;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.vt-card-meta {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  min-width: 0;
  flex-wrap: wrap;
}

.vt-account-name {
  font-weight: 600;
  color: #1e293b;
}

.vt-template-title {
  color: #6366f1;
  font-weight: 500;
}

.vt-date-text {
  color: #94a3b8;
}

.vt-sep {
  color: #e2e8f0;
}

/* Progress segments */
.vt-progress {
  display: flex;
  align-items: center;
  gap: 3px;
  flex-shrink: 0;
}

.vt-progress-seg {
  width: 18px;
  height: 5px;
  border-radius: 3px;
}

.vt-seg-done  { background: #10b981; }
.vt-seg-empty { background: #e2e8f0; }

.vt-progress-label {
  font-size: 12px;
  color: #64748b;
  margin-left: 4px;
  font-weight: 600;
}

.vt-detail-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 13px;
  color: #6366f1;
  background: #eef2ff;
  border: none;
  cursor: pointer;
  padding: 5px 10px;
  border-radius: 6px;
  font-weight: 500;
  transition: background 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}

.vt-detail-btn:hover {
  background: #e0e7ff;
}

/* Card body */
.vt-card-body {
  display: flex;
  gap: 16px;
  padding: 16px;
}

.vt-cover-wrap {
  position: relative;
  width: 80px;
  min-width: 80px;
  aspect-ratio: 9/16;
  border-radius: 8px;
  overflow: hidden;
  background: #0f172a;
  flex-shrink: 0;
}

.vt-cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.vt-cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
}

.vt-duration-badge {
  position: absolute;
  bottom: 5px;
  right: 5px;
  background: rgba(0,0,0,0.65);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.vt-prompt-wrap {
  flex: 1;
  min-width: 0;
}

.vt-prompt-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}

.vt-prompt-text {
  font-size: 13px;
  color: #334155;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 6;
  line-clamp: 6;
  -webkit-box-orient: vertical;
}

/* Shots section */
.vt-shots-section {
  padding: 0 16px 16px;
}

.vt-shots-title {
  display: flex;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  color: #6366f1;
  margin-bottom: 8px;
}

.vt-shots-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.vt-shot-img {
  width: 64px;
  height: 64px;
  border-radius: 6px;
  object-fit: cover;
  border: 1px solid #e2e8f0;
  cursor: zoom-in;
}

/* ── Buttons ── */
.vt-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
  white-space: nowrap;
  font-family: inherit;
}

.vt-btn-secondary {
  background: #e2e8f0;
  color: #475569;
}

.vt-btn-secondary:hover:not(:disabled) {
  background: #cbd5e1;
}

.vt-btn:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.vt-btn-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
}

.vt-btn-primary:hover:not(:disabled) {
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35);
  transform: translateY(-1px);
}

.vt-btn-success {
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25);
}

.vt-btn-success:hover:not(:disabled) {
  box-shadow: 0 6px 16px rgba(16, 185, 129, 0.35);
  transform: translateY(-1px);
}

@keyframes vt-spin {
  to { transform: rotate(360deg); }
}

.vt-spinner {
  animation: vt-spin 0.8s linear infinite;
}

/* Status badges */
.vt-status-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  white-space: nowrap;
  flex-shrink: 0;
}

.vt-status-pending         { background: #f1f5f9; color: #64748b; }
.vt-status-generating      { background: #eff6ff; color: #3b82f6; }
.vt-status-reviewing       { background: #fef9c3; color: #854d0e; }
.vt-status-pending_publish { background: #fef3c7; color: #d97706; }
.vt-status-published       { background: #dcfce7; color: #15803d; }
.vt-status-abandoned       { background: #fee2e2; color: #b91c1c; }
</style>
