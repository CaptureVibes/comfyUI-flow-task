<template>
  <div v-loading="loading" class="ad-page">
    <!-- Back -->
    <div class="ad-back" @click="$router.push('/dashboard/accounts')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      返回账号列表
    </div>

    <template v-if="account">
      <!-- Hero card -->
      <div class="ad-hero">
        <div class="ad-hero-avatar">
          <img v-if="account.avatar_url" :src="account.avatar_url" class="ad-avatar-img" />
          <div v-else class="ad-avatar-placeholder">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
          </div>
        </div>

        <div class="ad-hero-info">
          <div class="ad-hero-name">{{ account.account_name }}</div>
          <div v-if="account.style_description" class="ad-hero-style">{{ account.style_description }}</div>
          <div class="ad-hero-meta">
            <span class="ad-hero-stat"><strong>{{ tabCounts.published }}</strong> 已发布</span>
            <span class="ad-hero-stat"><strong>{{ tabCounts.pending_publish }}</strong> 待发布</span>
            <span v-if="tabCounts.publish_failed" class="ad-hero-stat ad-hero-stat-fail">
              <strong>{{ tabCounts.publish_failed }}</strong> 发布失败
            </span>
            <span class="ad-hero-stat ad-hero-stat-link" @click="router.push('/dashboard/daily-tasks')">
              <strong>{{ tabCounts.pending + tabCounts.generating }}</strong> 生成任务
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
            </span>
          </div>
          <div class="ad-hero-platforms">
            <span v-for="binding in (account.social_bindings || [])" :key="binding.platform"
              class="ad-platform-badge" :class="`ad-platform-${binding.platform}`">
              {{ platformLabel(binding.platform) }}
            </span>
            <span v-if="!account.social_bindings?.length" class="ad-no-platform">未绑定平台</span>
          </div>
        </div>

        <div class="ad-hero-actions">
          <button class="ad-gen-btn" @click="$router.push(`/dashboard/accounts/${account.id}/generate`)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            生成视频
          </button>
          <button class="ad-edit-btn" @click="$router.push(`/dashboard/accounts/${account.id}/edit`)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            编辑账号
          </button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="ad-tabs-bar">
        <button
          v-for="tab in TABS"
          :key="tab.key"
          class="ad-tab"
          :class="{ active: activeTab === tab.key, 'ad-tab-fail': tab.key === 'publish_failed' }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span v-if="tabCounts[tab.key]" class="ad-tab-count" :class="{ 'ad-tab-count-fail': tab.key === 'publish_failed' }">{{ tabCounts[tab.key] }}</span>
        </button>
        <button class="ad-refresh-btn" :disabled="tasksLoading" @click="loadTasks">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" :class="{ spinning: tasksLoading }"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
          刷新
        </button>
      </div>

      <!-- Video grid -->
      <div v-if="tasksLoading" class="ad-grid-loading" v-loading="true"></div>

      <div v-else-if="!filteredSubTasks.length" class="ad-grid-empty">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#c7d2fe" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
        <span>{{ emptyText }}</span>
      </div>

      <div v-else class="ad-video-grid">
        <div
          v-for="item in filteredSubTasks"
          :key="item.sub.id"
          class="ad-video-card"
          :class="{ 'ad-card-selected': item.sub.selected }"
        >
          <!-- Thumbnail / video -->
          <div class="ad-card-thumb" @click="router.push(`/dashboard/video-tasks/${item.task.id}`)">
            <video
              v-if="item.sub.result_video_url"
              :src="item.sub.result_video_url"
              class="ad-card-video"
              preload="metadata"
              muted
              loop
              @mouseenter="e => e.target.play()"
              @mouseleave="e => { e.target.pause(); e.target.currentTime = 0 }"
            />
            <div v-else class="ad-card-placeholder">
              <svg v-if="item.sub.status === 'generating'" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              <svg v-else width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
            </div>

            <!-- Status overlay -->
            <div class="ad-card-status-badge" :class="`ad-status-${item.sub.status}`">
              {{ STATUS_LABELS[item.sub.status] }}
            </div>

            <!-- Selected checkmark -->
            <div v-if="item.sub.selected" class="ad-card-check">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
          </div>

          <!-- Card content -->
          <div class="ad-card-body">
            <div class="ad-card-meta">
              <span class="ad-card-date">{{ item.task.target_date }}</span>
              <span class="ad-card-index">#{{ item.sub.sub_index }}</span>
            </div>
            <div class="ad-card-template">{{ item.task.template_title || '未知模板' }}</div>
            <div class="ad-card-prompt">{{ item.task.prompt }}</div>

            <!-- Scoring error message -->
            <div v-if="item.sub.scoring_error" class="ad-card-error">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>{{ item.sub.scoring_error }}</span>
            </div>

            <!-- Publish error message -->
            <div v-if="item.sub.publish_error" class="ad-card-error">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>发布失败: {{ item.sub.publish_error }}</span>
            </div>

            <!-- Channel status (published tab) -->
            <div v-if="activeTab === 'published' && publicationsMap[item.sub.id]?.channels_status?.length" class="ad-channel-status">
              <div
                v-for="ch in publicationsMap[item.sub.id].channels_status"
                :key="ch.upload_id || ch.channel_id"
                class="ad-ch-item"
                :class="`ad-ch-${ch.status}`"
              >
                <span class="ad-ch-platform">{{ platformLabel(ch.platform) }}</span>
                <span class="ad-ch-status-label">{{ ch.status === 'completed' ? '成功' : ch.status === 'failed' ? '失败' : ch.status }}</span>
                <a v-if="ch.platform_video_url" :href="ch.platform_video_url" target="_blank" class="ad-ch-link" @click.stop>查看</a>
                <span v-if="ch.error_message && ch.status === 'failed'" class="ad-ch-error" :title="ch.error_message">{{ ch.error_message }}</span>
              </div>
            </div>

            <!-- Action buttons -->
            <div class="ad-card-actions">
              <!-- 待发布：发布按钮 -->
              <el-button
                v-if="item.sub.status === 'pending_publish' && item.sub.selected"
                type="primary"
                size="small"
                @click="openPublishDialog(item.task, item.sub)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                发布
              </el-button>

              <!-- 发布失败：重试发布 -->
              <el-button
                v-if="item.sub.status === 'publish_failed' && item.sub.selected"
                type="primary"
                size="small"
                :loading="retrying === item.sub.id"
                @click="handleRetryPublish(item.task, item.sub)"
              >重试发布</el-button>

              <!-- 待发布：删除 -->
              <el-button
                v-if="item.sub.status === 'pending_publish'"
                type="danger"
                size="small"
                plain
                :loading="deleting === item.sub.id"
                @click="handleDeleteSubTask(item.task, item.sub)"
              >删除</el-button>

              <!-- generating：撤回 -->
              <el-button
                v-if="canRollback(item.sub)"
                size="small"
                plain
                :loading="rollbacking === item.sub.id"
                @click="handleRollback(item.task, item.sub)"
              >撤回</el-button>

              <button class="ad-card-detail-btn" @click="router.push(`/dashboard/video-tasks/${item.task.id}`)">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 发布对话框 -->
    <PublishVideoDialog
      v-model="publishDialogVisible"
      :video-url="publishVideoUrl"
      :account="account"
      :sub-task="publishSubTask"
      @success="handlePublishSuccess"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchAccount } from '../api/accounts'
import { fetchAccountVideoTasks, patchSubTaskStatus, rollbackSubTaskStatus, deleteSubTask } from '../api/video_tasks'
import { fetchSubTaskPublications } from '../api/video_publications'

import PublishVideoDialog from '../components/PublishVideoDialog.vue'

const route = useRoute()
const router = useRouter()

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }

const STATUS_LABELS = {
  pending: '待处理',
  generating: '生成中',
  scoring: 'AI打分',
  pending_publish: '待发布',
  publishing: '发布中',
  publish_failed: '发布失败',
  published: '已发布',
  abandoned: '已废弃',
}

const TABS = [
  { key: 'pending_publish', label: '待发布' },
  { key: 'publishing',      label: '发布中' },
  { key: 'publish_failed',  label: '发布失败' },
  { key: 'published',       label: '已发布' },
]

const EMPTY_TEXTS = {
  pending_publish: '暂无待发布的视频',
  publishing:      '暂无发布中的视频',
  publish_failed:  '暂无发布失败的视频',
  published:       '暂无已发布的视频',
}

const loading = ref(false)
const account = ref(null)
const tasks = ref([])
const tasksLoading = ref(false)
const activeTab = ref('pending_publish')
const rollbacking = ref(null)
const retrying = ref(null)
const deleting = ref(null)

// 发布对话框
const publishDialogVisible = ref(false)
const publishVideoUrl = ref('')
const publishSubTask = ref(null)

// 已发布 tab 的渠道状态缓存（以 sub_id 为键）
const publicationsMap = ref({})

// Flatten all sub-tasks with parent task reference
const allSubTasks = computed(() => {
  const result = []
  for (const task of tasks.value) {
    for (const sub of (task.sub_tasks || [])) {
      if (sub.status !== 'abandoned') {
        result.push({ task, sub })
      }
    }
  }
  return result
})

const filteredSubTasks = computed(() => {
  if (activeTab.value === 'all') return allSubTasks.value
  return allSubTasks.value.filter(item => item.sub.status === activeTab.value)
})

const tabCounts = computed(() => {
  const counts = { pending_publish: 0, publishing: 0, publish_failed: 0, published: 0, generating: 0, pending: 0, all: 0 }
  for (const { sub } of allSubTasks.value) {
    if (counts[sub.status] !== undefined) counts[sub.status]++
    counts.all++
  }
  return counts
})

const emptyText = computed(() => EMPTY_TEXTS[activeTab.value] || '暂无内容')

function platformLabel(p) { return PLATFORM_LABELS[p] || p }

function canRollback(sub) {
  return sub.status === 'generating'
}

// 打开发布对话框
function openPublishDialog(task, sub) {
  if (!sub.result_video_url) {
    ElMessage.warning('视频尚未生成完成')
    return
  }
  if (!account.value?.social_bindings?.length) {
    ElMessage.warning('该账号尚未绑定任何发布平台，请先在编辑页面绑定平台')
    return
  }
  publishVideoUrl.value = sub.result_video_url
  publishSubTask.value = { ...sub, task }
  publishDialogVisible.value = true
}

// 发布成功处理
async function handlePublishSuccess() {
  ElMessage.success('发布任务创建成功，正在后台处理...')
  await loadTasks()
}

// 重试发布（publish_failed → pending_publish）
async function handleRetryPublish(_task, sub) {
  retrying.value = sub.id
  try {
    await patchSubTaskStatus(sub.id, { status: 'pending_publish' })
    ElMessage.success('已重置为待发布')
    activeTab.value = 'pending_publish'
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  } finally {
    retrying.value = null
  }
}

// 加载已发布视频的渠道状态
async function loadPublishedPublications() {
  const publishedSubs = allSubTasks.value.filter(({ sub }) => sub.status === 'published')
  for (const { sub } of publishedSubs) {
    if (!publicationsMap.value[sub.id]) {
      try {
        const pubs = await fetchSubTaskPublications(sub.id)
        if (pubs.length) publicationsMap.value[sub.id] = pubs[0]
      } catch {
        // ignore
      }
    }
  }
}

watch(activeTab, (tab) => {
  if (tab === 'published') {
    loadPublishedPublications()
  }
})

async function loadAccount() {
  loading.value = true
  try {
    account.value = await fetchAccount(route.params.id)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载失败')
    router.push('/dashboard/accounts')
  } finally {
    loading.value = false
  }
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    tasks.value = await fetchAccountVideoTasks(route.params.id)
    // 如果当前在已发布 tab，重新加载渠道状态
    if (activeTab.value === 'published') {
      publicationsMap.value = {}
      loadPublishedPublications()
    }
  } catch {
    ElMessage.error('加载任务失败')
  } finally {
    tasksLoading.value = false
  }
}

async function handleDeleteSubTask(_task, sub) {
  try {
    await ElMessageBox.confirm('确认删除该视频？此操作不可恢复。', '删除待发布视频', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }
  deleting.value = sub.id
  try {
    await deleteSubTask(sub.id)
    ElMessage.success('已删除')
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = null
  }
}

async function handleRollback(_task, sub) {
  rollbacking.value = sub.id
  try {
    await rollbackSubTaskStatus(sub.id)
    ElMessage.success('已撤回')
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '撤回失败')
  } finally {
    rollbacking.value = null
  }
}

onMounted(async () => {
  await loadAccount()
  await loadTasks()
})
</script>

<style scoped>
.ad-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
  background: #f8fafc;
}

/* Back */
.ad-back {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 13px; color: #6366f1; font-weight: 600;
  cursor: pointer; margin-bottom: 24px; transition: color 0.15s;
}
.ad-back:hover { color: #4338ca; }

/* Hero */
.ad-hero {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,.05);
  padding: 28px;
  display: flex; align-items: center; gap: 24px;
  margin-bottom: 16px;
}

.ad-hero-avatar { flex-shrink: 0; }

.ad-avatar-img {
  width: 80px; height: 80px; border-radius: 50%;
  object-fit: cover; border: 3px solid #e0e7ff;
  box-shadow: 0 2px 12px rgba(99,102,241,.15);
}

.ad-avatar-placeholder {
  width: 80px; height: 80px; border-radius: 50%;
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  display: flex; align-items: center; justify-content: center;
  border: 3px solid #e0e7ff;
}

.ad-hero-info { flex: 1; }

.ad-hero-name { font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em; margin-bottom: 4px; }
.ad-hero-style { font-size: 13px; color: #64748b; margin-bottom: 10px; line-height: 1.5; }

.ad-hero-meta { display: flex; gap: 20px; margin-bottom: 10px; flex-wrap: wrap; }
.ad-hero-stat { font-size: 13px; color: #64748b; }
.ad-hero-stat strong { color: #0f172a; font-weight: 700; margin-right: 3px; }
.ad-hero-stat-fail strong { color: #dc2626; }
.ad-hero-stat-link {
  cursor: pointer;
  color: #6366f1;
  display: flex;
  align-items: center;
  gap: 3px;
  transition: color 0.15s;
}
.ad-hero-stat-link:hover { color: #4f46e5; }
.ad-hero-stat-link strong { color: #6366f1; }

.ad-hero-platforms { display: flex; gap: 8px; flex-wrap: wrap; }

.ad-platform-badge {
  font-size: 12px; font-weight: 700; padding: 3px 10px;
  border-radius: 20px; letter-spacing: .02em;
}
.ad-platform-youtube  { background: #fef2f2; color: #dc2626; }
.ad-platform-tiktok   { background: #f1f5f9; color: #0f172a; }
.ad-platform-instagram { background: #fef3c7; color: #92400e; }
.ad-no-platform { font-size: 13px; color: #94a3b8; }

.ad-hero-actions { flex-shrink: 0; display: flex; gap: 10px; }

.ad-gen-btn {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 700; padding: 9px 18px;
  border-radius: 10px; border: none; background: #6366f1; color: #fff;
  cursor: pointer; transition: all 0.15s;
  box-shadow: 0 2px 8px rgba(99,102,241,0.25);
}
.ad-gen-btn:hover { background: #4f46e5; transform: translateY(-1px); }

.ad-edit-btn {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; padding: 9px 18px;
  border-radius: 10px; border: 1px solid #c7d2fe;
  background: #eef2ff; color: #4338ca; cursor: pointer; transition: all 0.15s;
}
.ad-edit-btn:hover { background: #e0e7ff; border-color: #6366f1; }

/* Tabs bar */
.ad-tabs-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 12px;
  padding: 8px 12px;
  margin-bottom: 16px;
}

.ad-tab {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 500; color: #64748b;
  padding: 7px 14px; border: none; background: none;
  cursor: pointer; border-radius: 8px;
  transition: all 0.15s; white-space: nowrap;
}
.ad-tab:hover { color: #6366f1; background: #f5f3ff; }
.ad-tab.active { color: #6366f1; font-weight: 700; background: #eef2ff; }
.ad-tab-fail:hover { color: #dc2626; background: #fef2f2; }
.ad-tab-fail.active { color: #dc2626; background: #fef2f2; }

.ad-tab-count {
  font-size: 11px; font-weight: 700;
  background: #6366f1; color: #fff;
  border-radius: 10px; padding: 1px 7px; min-width: 18px; text-align: center;
}
.ad-tab.active .ad-tab-count { background: #4f46e5; }
.ad-tab-count-fail { background: #dc2626; }
.ad-tab-fail.active .ad-tab-count { background: #dc2626; }

.ad-refresh-btn {
  margin-left: auto;
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; font-weight: 600; color: #64748b;
  background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 7px; padding: 5px 10px; cursor: pointer; transition: all 0.15s;
}
.ad-refresh-btn:hover:not(:disabled) { color: #6366f1; border-color: #c7d2fe; background: #eef2ff; }
.ad-refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.spinning { animation: spin 0.8s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* Grid */
.ad-grid-loading { height: 200px; }

.ad-grid-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 12px; padding: 60px; color: #94a3b8; font-size: 13px;
  background: #fff; border: 1px solid #e8edf5; border-radius: 12px;
}

.ad-video-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

/* Video card */
.ad-video-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
}
.ad-video-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.07); }
.ad-video-card.ad-card-selected { border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99,102,241,0.15); }

/* Thumbnail */
.ad-card-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 9/16;
  background: #0f172a;
  cursor: pointer;
  overflow: hidden;
}

.ad-card-video {
  width: 100%; height: 100%; object-fit: cover; display: block;
  transition: transform 0.3s;
}
.ad-card-thumb:hover .ad-card-video { transform: scale(1.03); }

.ad-card-placeholder {
  width: 100%; height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; color: #94a3b8; font-size: 11px;
  background: linear-gradient(135deg, #1e293b, #0f172a);
}

.ad-card-status-badge {
  position: absolute; bottom: 8px; left: 8px;
  font-size: 10px; font-weight: 700;
  padding: 3px 8px; border-radius: 6px;
  backdrop-filter: blur(6px);
}

.ad-card-check {
  position: absolute; top: 8px; right: 8px;
  width: 22px; height: 22px; border-radius: 50%;
  background: #6366f1; display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}

/* Status colors */
.ad-status-pending         { background: rgba(241,245,249,0.85); color: #64748b; }
.ad-status-generating      { background: rgba(239,246,255,0.85); color: #3b82f6; }
.ad-status-reviewing       { background: rgba(254,249,195,0.9);  color: #854d0e; }
.ad-status-pending_publish { background: rgba(254,243,199,0.9);  color: #d97706; }
.ad-status-publishing      { background: rgba(237,233,254,0.9);  color: #7c3aed; }
.ad-status-publish_failed  { background: rgba(254,226,226,0.9);  color: #b91c1c; }
.ad-status-published       { background: rgba(220,252,231,0.9);  color: #15803d; }
.ad-status-abandoned       { background: rgba(254,226,226,0.9);  color: #b91c1c; }

/* Card body */
.ad-card-body { padding: 12px; }

.ad-card-meta {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px;
}

.ad-card-date { font-size: 11px; color: #94a3b8; }
.ad-card-index { font-size: 11px; font-weight: 700; color: #6366f1; background: #eef2ff; padding: 1px 6px; border-radius: 4px; }

.ad-card-template {
  font-size: 12px; font-weight: 600; color: #6366f1;
  margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.ad-card-prompt {
  font-size: 12px; color: #475569; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; margin-bottom: 10px;
}

.ad-card-actions {
  display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
}

.ad-card-error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  margin-top: 10px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.4;
}

.ad-card-error svg {
  flex-shrink: 0;
  margin-top: 1px;
}

/* Channel status */
.ad-channel-status {
  margin-top: 8px;
  margin-bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.ad-ch-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px;
}

.ad-ch-platform {
  font-weight: 600; color: #475569; min-width: 52px;
}

.ad-ch-status-label { font-weight: 700; }
.ad-ch-completed .ad-ch-status-label { color: #15803d; }
.ad-ch-failed .ad-ch-status-label { color: #b91c1c; }

.ad-ch-link {
  color: #6366f1; text-decoration: none; font-size: 11px;
  padding: 1px 6px; background: #eef2ff; border-radius: 4px;
}
.ad-ch-link:hover { background: #e0e7ff; }

.ad-ch-error {
  color: #94a3b8; font-size: 11px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 110px;
}

.ad-card-detail-btn {
  margin-left: auto;
  display: flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 6px;
  border: 1px solid #e2e8f0; background: #f8fafc;
  color: #94a3b8; cursor: pointer; transition: all 0.15s;
  flex-shrink: 0;
}
.ad-card-detail-btn:hover { border-color: #c7d2fe; background: #eef2ff; color: #6366f1; }

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (max-width: 1100px) {
  .ad-video-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 700px) {
  .ad-hero { flex-direction: column; text-align: center; }
  .ad-hero-platforms { justify-content: center; }
  .ad-hero-meta { justify-content: center; }
  .ad-video-grid { grid-template-columns: repeat(2, 1fr); }
  .ad-page { padding: 16px; }
}
</style>
