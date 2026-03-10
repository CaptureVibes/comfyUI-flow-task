<template>
  <div class="vtd-page">
    <!-- Header -->
    <div class="vtd-header">
      <button class="vtd-back-btn" @click="router.back()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
        返回任务列表
      </button>
      <div v-if="task" class="vtd-header-info">
        <span class="vtd-info-item">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" style="margin-right:4px"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          {{ accountName }}
        </span>
        <span class="vtd-sep">·</span>
        <span
          class="vtd-info-item vtd-template"
          :class="{ 'vtd-template-link': task.template_id }"
          @click="task.template_id && router.push(`/dashboard/video-ai-templates/${task.template_id}/edit`)"
        >{{ templateTitle }}</span>
        <span class="vtd-sep">·</span>
        <span class="vtd-info-item">{{ task.target_date }}</span>
        <span class="vtd-sep">·</span>
        <span class="vtd-status-badge" :class="`vtd-status-${task.status}`">
          {{ STATUS_LABELS[task.status] || task.status }}
        </span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" v-loading="true" class="vtd-loading"></div>

    <!-- Task Detail -->
    <div v-else-if="task" class="vtd-body">

      <!-- Top row: Timeline + Prompt -->
      <div class="vtd-top-row">
        <!-- Timeline -->
        <div class="vtd-timeline-card">
          <div class="vtd-section-label">任务进度</div>
          <div class="vtd-timeline">
            <div
              v-for="(step, i) in timeline"
              :key="step.key"
              class="vtd-timeline-item"
              :class="{ active: step.active, done: step.done, current: step.current }"
            >
              <div class="vtd-tl-left">
                <div class="vtd-tl-dot">
                  <svg v-if="step.done" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                  <div v-else-if="step.current" class="vtd-tl-pulse"></div>
                </div>
                <div v-if="i < timeline.length - 1" class="vtd-tl-line"></div>
              </div>
              <div class="vtd-tl-content">
                <div class="vtd-tl-title">{{ step.label }}</div>
                <div v-if="step.desc" class="vtd-tl-desc">{{ step.desc }}</div>
                <!-- AI Scores for scoring step -->
                <div v-if="step.key === 'scoring' && hasReviewingScores()" class="vtd-tl-scores">
                  <div
                    v-for="sub in reviewingSubTasks()"
                    :key="sub.id"
                    class="vtd-tl-score-item"
                    :class="{ 'vtd-tl-score-selected': sub.selected }"
                  >
                    <span class="vtd-tl-score-index">#{{ sub.sub_index }}</span>
                    <span class="vtd-tl-score-value" :class="getAiScoreClass(sub.ai_score)">
                      {{ sub.ai_score }}分
                    </span>
                    <span v-if="sub.round1_score !== null" class="vtd-tl-score-rounds">
                      R1: {{ sub.round1_score }}
                      <span v-if="sub.round2_score !== null"> | R2: {{ sub.round2_score }}</span>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Prompt (collapsible) -->
        <div class="vtd-prompt-card">
          <div class="vtd-prompt-header" @click="promptExpanded = !promptExpanded">
            <span class="vtd-section-label">生成 Prompt</span>
            <svg
              width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round"
              :style="{ transform: promptExpanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }"
            ><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <div class="vtd-prompt-text" :class="{ collapsed: !promptExpanded }">{{ task.prompt }}</div>
          <button v-if="!promptExpanded" class="vtd-prompt-expand" @click="promptExpanded = true">
            展开全部
          </button>
        </div>
      </div>

      <!-- 3 Sub-task Cards -->
      <div class="vtd-subtasks">
        <div
          v-for="sub in task.sub_tasks"
          :key="sub.id"
          class="vtd-sub-card"
          :class="{ 'vtd-sub-selected': sub.selected, 'vtd-sub-abandoned': sub.status === 'abandoned' }"
        >
          <!-- Card Header -->
          <div class="vtd-sub-header">
            <div class="vtd-sub-index">#{{ sub.sub_index }}</div>
            <span class="vtd-status-badge" :class="`vtd-status-${sub.status}`">
              {{ STATUS_LABELS[sub.status] || sub.status }}
            </span>
            <div v-if="sub.selected" class="vtd-selected-badge">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
              已选中
            </div>
            <!-- AI Score Badge -->
            <div v-if="sub.ai_score !== null && sub.ai_score !== undefined" class="vtd-ai-score" :class="getAiScoreClass(sub.ai_score)">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              {{ sub.ai_score }}分
            </div>
          </div>

          <!-- Video Player -->
          <div class="vtd-sub-video-wrap">
            <video
              v-if="sub.result_video_url"
              :src="sub.result_video_url"
              controls
              class="vtd-sub-video"
              preload="metadata"
            />
            <div v-else class="vtd-sub-video-placeholder">
              <svg v-if="sub.status === 'generating'" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              <svg v-else width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
              <span>{{ sub.status === 'generating' ? '生成中...' : '暂无视频' }}</span>
            </div>
          </div>

          <!-- AI Score Details -->
          <div v-if="hasAiScores(sub)" class="vtd-ai-details">
            <div class="vtd-ai-details-title">AI 评分详情</div>
            <div class="vtd-ai-scores">
              <div class="vtd-ai-score-item">
                <span class="vtd-ai-round">第一轮</span>
                <span class="vtd-ai-score-value" :class="getAiScoreClass(sub.round1_score)">
                  {{ sub.round1_score }}分
                </span>
              </div>
              <div v-if="sub.round2_score !== null" class="vtd-ai-score-item">
                <span class="vtd-ai-round">第二轮</span>
                <span class="vtd-ai-score-value" :class="getAiScoreClass(sub.round2_score)">
                  {{ sub.round2_score }}分
                </span>
              </div>
              <div class="vtd-ai-score-item vtd-ai-final">
                <span class="vtd-ai-round">综合得分</span>
                <span class="vtd-ai-score-value" :class="getAiScoreClass(sub.ai_score)">
                  {{ sub.ai_score }}分
                </span>
              </div>
            </div>

            <!-- Round 1 Reason -->
            <div v-if="sub.round1_reason" class="vtd-ai-reason">
              <div class="vtd-ai-reason-label">第一轮评分理由</div>
              <div class="vtd-ai-reason-text">{{ sub.round1_reason }}</div>
            </div>

            <!-- Round 2 Reason -->
            <div v-if="sub.round2_reason" class="vtd-ai-reason">
              <div class="vtd-ai-reason-label">第二轮评分理由</div>
              <div class="vtd-ai-reason-text">{{ sub.round2_reason }}</div>
            </div>
          </div>

          <!-- AI Scoring Error -->
          <div v-if="sub.scoring_error" class="vtd-scoring-error">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span class="vtd-error-text">{{ sub.scoring_error }}</span>
          </div>

          <!-- Actions -->
          <div class="vtd-sub-actions">
            <el-button
              v-if="sub.status === 'reviewing'"
              type="primary"
              size="small"
              :loading="selecting === sub.id"
              @click="handleSelect(sub)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:4px"><polyline points="20 6 9 17 4 12"/></svg>
              选择此版本
            </el-button>

            <el-button
              v-if="sub.status === 'pending_publish' && sub.selected"
              type="primary"
              size="small"
              @click="router.push(`/dashboard/accounts/${task.account_id}`)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:4px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              前往发布
            </el-button>

            <el-button
              v-if="canRollback(sub)"
              size="small"
              plain
              :loading="rollbacking === sub.id"
              @click="handleRollback(sub)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:4px"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
              撤回
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else class="vtd-error">
      <p>任务不存在或无权访问</p>
      <el-button @click="router.back()">返回</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  fetchVideoTask,
  fetchVideoTaskState,
  patchSubTaskStatus,
  rollbackSubTaskStatus,
} from '../api/video_tasks.js'

const STATUS_LABELS = {
  pending: '待处理',
  generating: '生成中',
  scoring: 'AI审核中',
  pending_publish: '待发布',
  publishing: '发布中',
  publish_failed: '发布失败',
  published: '已发布',
  abandoned: '已废弃',
}

// Timeline steps in order
const TIMELINE_STEPS = [
  { key: 'pending',         label: '任务创建',   desc: '任务已建立，等待上传' },
  { key: 'generating',      label: '视频生成中', desc: '正在 AI 生成视频' },
  { key: 'scoring',         label: 'AI审核中',   desc: '正在进行 AI 智能评分' },
  { key: 'pending_publish', label: '待发布',     desc: 'AI 评分通过，请前往账号详情页发布' },
  { key: 'publishing',      label: '发布中',     desc: '视频正在上传到平台' },
  { key: 'published',       label: '已发布',     desc: '视频已成功发布' },
]

const STATUS_ORDER = ['pending', 'generating', 'scoring', 'pending_publish', 'publishing', 'published']

const route = useRoute()
const router = useRouter()
const task = ref(null)
const loading = ref(false)
const selecting = ref(null)
const rollbacking = ref(null)
const promptExpanded = ref(false)

let refreshInterval = null

const accountName = computed(() => task.value?.account_name || '未知账号')
const templateTitle = computed(() => task.value?.template_title || '未知模板')

const timeline = computed(() => {
  if (!task.value) return []
  const currentIdx = STATUS_ORDER.indexOf(task.value.status)
  return TIMELINE_STEPS.map((step, i) => {
    const stepIdx = STATUS_ORDER.indexOf(step.key)
    const done = stepIdx < currentIdx
    const current = stepIdx === currentIdx
    return {
      ...step,
      done,
      current,
      active: done || current,
      desc: current ? step.desc : (done ? '已完成' : step.desc),
    }
  })
})

function canRollback(sub) {
  return ['generating', 'pending_publish'].includes(sub.status)
}

function getAiScoreClass(score) {
  if (score >= 80) return 'vtd-ai-high'
  if (score >= 60) return 'vtd-ai-medium'
  return 'vtd-ai-low'
}

function hasAiScores(sub) {
  return sub.ai_score !== null && sub.ai_score !== undefined
}

function hasReviewingScores() {
  if (!task.value?.sub_tasks) return false
  return task.value.sub_tasks.some(
    sub => (sub.status === 'pending_publish' || sub.status === 'published') && sub.ai_score !== null && sub.ai_score !== undefined
  )
}

function reviewingSubTasks() {
  if (!task.value?.sub_tasks) return []
  return task.value.sub_tasks.filter(
    sub => sub.status === 'pending_publish' || sub.status === 'published'
  ).filter(sub => sub.ai_score !== null && sub.ai_score !== undefined)
}

function shouldAutoRefresh() {
  if (!task.value) return false
  // Auto-refresh if any sub-task is in 'scoring' or 'generating' status or parent task is 'scoring' or 'generating'
  return ['generating', 'scoring'].includes(task.value.status) ||
         (task.value.sub_tasks && task.value.sub_tasks.some(sub => ['generating', 'scoring'].includes(sub.status)))
}

async function loadTask(polling = false) {
  if (!polling) {
    loading.value = true
  }
  try {
    if (polling && task.value) {
      const stateData = await fetchVideoTaskState(route.params.id)
      task.value.status = stateData.status
      if (stateData.sub_tasks && task.value.sub_tasks) {
        stateData.sub_tasks.forEach(newState => {
          const sub = task.value.sub_tasks.find(s => s.id === newState.id)
          if (sub) {
            Object.assign(sub, newState)
          }
        })
      }
    } else {
      task.value = await fetchVideoTask(route.params.id)
    }
  } catch (e) {
    if (!polling) {
      task.value = null
    }
  } finally {
    if (!polling) {
      loading.value = false
    }
  }
}

function startAutoRefresh() {
  stopAutoRefresh() // Clear any existing interval
  refreshInterval = setInterval(async () => {
    if (shouldAutoRefresh()) {
      await loadTask(true)
    } else {
      stopAutoRefresh()
    }
  }, 3000) // Refresh every 3 seconds
}

function stopAutoRefresh() {
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
}

async function handleSelect(sub) {
  await ElMessageBox.confirm(
    `确认选择子任务 #${sub.sub_index} 的视频作为发布版本？另外两个子任务将被废弃。`,
    '选择发布版本',
    { confirmButtonText: '确认选择', cancelButtonText: '取消', type: 'warning' }
  )
  selecting.value = sub.id
  try {
    await patchSubTaskStatus(sub.id, { status: 'pending_publish', selected: true })
    ElMessage.success('已选定发布版本')
    await loadTask()
    if (shouldAutoRefresh()) {
      startAutoRefresh()
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    selecting.value = null
  }
}

async function handleRollback(sub) {
  rollbacking.value = sub.id
  try {
    await rollbackSubTaskStatus(sub.id)
    ElMessage.success('已撤回')
    await loadTask()
    if (shouldAutoRefresh()) {
      startAutoRefresh()
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '撤回失败')
  } finally {
    rollbacking.value = null
  }
}

onMounted(async () => {
  await loadTask()
  if (shouldAutoRefresh()) {
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.vtd-page {
  padding: 28px 32px;
  min-height: 100%;
  background: #f8fafc;
}

.vtd-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.vtd-back-btn {
  display: flex; align-items: center; gap: 4px;
  font-size: 14px; color: #6366f1; background: none; border: none;
  cursor: pointer; padding: 6px 10px; border-radius: 6px;
  font-weight: 500; transition: background 0.15s; white-space: nowrap;
}
.vtd-back-btn:hover { background: #eef2ff; }

.vtd-header-info { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.vtd-info-item { font-size: 14px; color: #475569; display: flex; align-items: center; }

.vtd-template { color: #6366f1; font-weight: 500; }
.vtd-template-link { cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
.vtd-template-link:hover { color: #4f46e5; }

.vtd-sep { color: #cbd5e1; font-size: 14px; }

.vtd-loading { height: 300px; }

.vtd-body { display: flex; flex-direction: column; gap: 20px; }

/* Top row: timeline + prompt side by side */
.vtd-top-row {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  align-items: start;
}

/* Timeline card */
.vtd-timeline-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 18px;
}

.vtd-section-label {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 16px;
}

.vtd-timeline { display: flex; flex-direction: column; }

.vtd-timeline-item {
  display: flex;
  gap: 12px;
  position: relative;
}

.vtd-tl-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 20px;
}

.vtd-tl-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e2e8f0;
  border: 2px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  z-index: 1;
  transition: all 0.2s;
}

.vtd-timeline-item.done .vtd-tl-dot {
  background: #6366f1;
  border-color: #6366f1;
}

.vtd-timeline-item.current .vtd-tl-dot {
  background: #fff;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.2);
}

.vtd-tl-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6366f1;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.7; }
}

.vtd-tl-line {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: #e2e8f0;
  margin: 2px 0;
}

.vtd-timeline-item.done .vtd-tl-line,
.vtd-timeline-item.current .vtd-tl-line {
  background: #c7d2fe;
}

.vtd-tl-content {
  padding-bottom: 20px;
  flex: 1;
}

.vtd-timeline-item:last-child .vtd-tl-content { padding-bottom: 0; }

.vtd-tl-title {
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  line-height: 20px;
  transition: color 0.2s;
}

.vtd-timeline-item.done .vtd-tl-title { color: #475569; }
.vtd-timeline-item.current .vtd-tl-title { color: #6366f1; font-weight: 700; }

.vtd-tl-desc {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
  line-height: 1.4;
}
.vtd-timeline-item.current .vtd-tl-desc { color: #6366f1; opacity: 0.8; }

.vtd-tl-scores {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.vtd-tl-score-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 11px;
}

.vtd-tl-score-item.vtd-tl-score-selected {
  border-color: #6366f1;
  background: #eef2ff;
}

.vtd-tl-score-index {
  font-weight: 600;
  color: #64748b;
}

.vtd-tl-score-value {
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.vtd-tl-score-value.vtd-ai-high { background: #dcfce7; color: #15803d; }
.vtd-tl-score-value.vtd-ai-medium { background: #fef3c7; color: #d97706; }
.vtd-tl-score-value.vtd-ai-low { background: #fee2e2; color: #b91c1c; }

.vtd-tl-score-rounds {
  font-size: 10px;
  color: #94a3b8;
  margin-left: 2px;
}

/* Prompt card */
.vtd-prompt-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 20px;
}

.vtd-prompt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
  margin-bottom: 10px;
}
.vtd-prompt-header:hover svg { stroke: #6366f1; }

.vtd-prompt-text {
  font-size: 13px;
  color: #334155;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow: hidden;
  transition: max-height 0.3s ease;
}

.vtd-prompt-text.collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.vtd-prompt-expand {
  margin-top: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #6366f1;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}
.vtd-prompt-expand:hover { color: #4f46e5; }

/* Sub-task grid */
.vtd-subtasks {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 900px) {
  .vtd-subtasks { grid-template-columns: 1fr; }
  .vtd-top-row { grid-template-columns: 1fr; }
}

.vtd-sub-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.vtd-sub-card.vtd-sub-selected {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.12);
}

.vtd-sub-card.vtd-sub-abandoned { opacity: 0.55; }

.vtd-sub-header {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; border-bottom: 1px solid #f1f5f9;
}

.vtd-sub-index {
  font-size: 14px; font-weight: 700; color: #1e293b;
  background: #f1f5f9; border-radius: 6px; padding: 2px 8px;
}

.vtd-selected-badge {
  margin-left: auto;
  display: flex; align-items: center; gap: 3px;
  font-size: 11px; font-weight: 600; color: #6366f1;
  background: #eef2ff; padding: 2px 8px; border-radius: 20px;
}

.vtd-ai-score {
  display: flex; align-items: center; gap: 3px;
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 20px;
}

.vtd-ai-high {
  background: #dcfce7; color: #15803d;
}

.vtd-ai-medium {
  background: #fef3c7; color: #d97706;
}

.vtd-ai-low {
  background: #fee2e2; color: #b91c1c;
}

.vtd-ai-details {
  padding: 12px 16px;
  border-top: 1px solid #f1f5f9;
  background: #fafbfc;
}

.vtd-ai-details-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.vtd-ai-scores {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.vtd-ai-score-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 60px;
}

.vtd-ai-score-item.vtd-ai-final {
  margin-left: auto;
  padding-left: 12px;
  border-left: 2px solid #e2e8f0;
}

.vtd-ai-round {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}

.vtd-ai-score-value {
  font-size: 16px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 12px;
  min-width: 50px;
  text-align: center;
}

.vtd-ai-reason {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #cbd5e1;
}

.vtd-ai-reason-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.vtd-ai-reason-text {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.vtd-sub-video-wrap {
  width: 100%; aspect-ratio: 9/16; background: #0f172a;
  overflow: hidden; display: flex; align-items: center; justify-content: center;
}

.vtd-sub-video { width: 100%; height: 100%; object-fit: contain; }

.vtd-sub-video-placeholder {
  display: flex; flex-direction: column; align-items: center;
  gap: 10px; color: #64748b; font-size: 13px;
}

.vtd-sub-actions {
  padding: 12px 16px; display: flex; gap: 8px;
  flex-wrap: wrap; border-top: 1px solid #f1f5f9; min-height: 52px; align-items: center;
}

.vtd-scoring-error {
  padding: 10px 16px;
  margin: 0 16px 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.vtd-scoring-error svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.vtd-error-text {
  font-size: 13px;
  color: #b91c1c;
  line-height: 1.5;
}

.vtd-error {
  display: flex; flex-direction: column; align-items: center;
  padding: 80px 0; gap: 16px; color: #94a3b8;
}

/* Status badges */
.vtd-status-badge {
  font-size: 11px; font-weight: 600; padding: 2px 9px;
  border-radius: 20px; white-space: nowrap;
}
.vtd-status-pending         { background: #f1f5f9; color: #64748b; }
.vtd-status-generating      { background: #eff6ff; color: #3b82f6; }
.vtd-status-scoring         { background: #f0fdf4; color: #059669; }
.vtd-status-pending_publish { background: #fef3c7; color: #d97706; }
.vtd-status-publishing      { background: #ede9fe; color: #7c3aed; }
.vtd-status-publish_failed  { background: #fee2e2; color: #b91c1c; }
.vtd-status-published       { background: #dcfce7; color: #15803d; }
.vtd-status-abandoned       { background: #fee2e2; color: #b91c1c; }
</style>
