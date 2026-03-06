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
          <div class="ad-hero-platforms">
            <span
              v-for="binding in (account.social_bindings || [])"
              :key="binding.platform"
              class="ad-platform-badge"
              :class="`ad-platform-${binding.platform}`"
            >{{ platformLabel(binding.platform) }}</span>
            <span v-if="!account.social_bindings?.length" class="ad-no-platform">未绑定平台</span>
          </div>
        </div>

        <div class="ad-hero-actions">
          <button class="ad-gen-btn" @click="$router.push(`/dashboard/accounts/${account.id}/generate`)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            生成视频
          </button>
          <button class="ad-edit-btn" @click="$router.push(`/dashboard/accounts/${account.id}/edit`)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            编辑账号
          </button>
        </div>
      </div>

      <!-- Info + Bindings row -->
      <div class="ad-meta-row">
        <!-- Basic info -->
        <div class="ad-info-card">
          <div class="ad-card-title">基本信息</div>
          <div class="ad-info-item">
            <span class="ad-info-label">账号名称</span>
            <span class="ad-info-value">{{ account.account_name }}</span>
          </div>
          <div v-if="account.model_appearance" class="ad-info-item">
            <span class="ad-info-label">模特描述</span>
            <span class="ad-info-value">{{ account.model_appearance }}</span>
          </div>
          <div class="ad-info-item">
            <span class="ad-info-label">创建时间</span>
            <span class="ad-info-value">{{ formatDate(account.created_at) }}</span>
          </div>
          <div class="ad-info-item">
            <span class="ad-info-label">更新时间</span>
            <span class="ad-info-value">{{ formatDate(account.updated_at) }}</span>
          </div>
        </div>

        <!-- Platform bindings -->
        <div class="ad-bindings-card">
          <div class="ad-card-title">平台绑定</div>
          <div v-if="!account.social_bindings?.length" class="ad-empty-bindings">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#c7d2fe" stroke-width="1.5"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
            <span>暂无平台绑定，<span class="ad-link" @click="$router.push(`/dashboard/accounts/${account.id}/edit`)">去添加</span></span>
          </div>
          <div v-for="binding in (account.social_bindings || [])" :key="binding.platform" class="ad-binding-block">
            <div class="ad-binding-header">
              <span class="ad-binding-platform" :class="`ad-platform-${binding.platform}`">{{ platformLabel(binding.platform) }}</span>
            </div>
            <!-- YouTube -->
            <template v-if="binding.platform === 'youtube'">
              <div class="ad-binding-field"><span>Channel ID</span><code>{{ binding.channel_id || '-' }}</code></div>
              <div class="ad-binding-field"><span>API Key</span><code>{{ maskSecret(binding.api_key) }}</code></div>
              <div class="ad-binding-field"><span>Refresh Token</span><code>{{ maskSecret(binding.refresh_token) }}</code></div>
            </template>
            <!-- TikTok -->
            <template v-if="binding.platform === 'tiktok'">
              <div class="ad-binding-field"><span>Open ID</span><code>{{ binding.open_id || '-' }}</code></div>
              <div class="ad-binding-field"><span>Access Token</span><code>{{ maskSecret(binding.access_token) }}</code></div>
              <div class="ad-binding-field"><span>Refresh Token</span><code>{{ maskSecret(binding.refresh_token) }}</code></div>
              <div v-if="binding.expires_in" class="ad-binding-field"><span>Expires In</span><code>{{ binding.expires_in }}s</code></div>
            </template>
            <!-- Instagram -->
            <template v-if="binding.platform === 'instagram'">
              <div class="ad-binding-field"><span>User ID</span><code>{{ binding.user_id || '-' }}</code></div>
              <div class="ad-binding-field"><span>Access Token</span><code>{{ maskSecret(binding.access_token) }}</code></div>
              <div class="ad-binding-field"><span>Account Type</span><code>{{ binding.account_type || '-' }}</code></div>
            </template>
          </div>
        </div>
      </div>

      <!-- Videos section -->
      <div class="ad-videos-section">
        <div class="ad-section-title">生成视频</div>

        <!-- Tab bar -->
        <div class="ad-tabs">
          <button
            v-for="tab in VIDEO_TABS"
            :key="tab.key"
            class="ad-tab"
            :class="{ active: activeTab === tab.key }"
            @click="switchTab(tab.key)"
          >
            {{ tab.label }}
            <span v-if="tabCounts[tab.key] > 0" class="ad-tab-count">{{ tabCounts[tab.key] }}</span>
          </button>
        </div>

        <!-- Video list -->
        <div v-loading="videosLoading" class="ad-video-list">
          <template v-if="videos.length">
            <div v-for="video in videos" :key="video.id" class="ad-video-item" :class="{ 'ad-video-item--reviewing': video.status === 'reviewing' }">
              <!-- Normal row header -->
              <div class="ad-video-row">
                <div class="ad-video-thumb">
                  <img v-if="video.status === 'pending_publish' || video.status === 'published'"
                    :src="selectedThumb(video)" class="ad-video-thumb-img" />
                  <img v-else-if="video.result_videos && video.result_videos[0]"
                    :src="video.result_videos[0].thumbnail_url" class="ad-video-thumb-img" />
                  <div v-else class="ad-video-thumb-placeholder">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>
                  </div>
                </div>
                <div class="ad-video-info">
                  <div class="ad-video-title">{{ video.prompt ? video.prompt.slice(0, 60) + (video.prompt.length > 60 ? '…' : '') : '(无描述)' }}</div>
                  <div class="ad-video-meta">
                    <span class="ad-video-date">{{ formatDate(video.created_at) }}</span>
                    <span v-if="video.duration" class="ad-video-duration">{{ video.duration }}</span>
                    <span
                      v-if="video.template_id"
                      class="ad-video-template-link"
                      @click="$router.push(`/dashboard/video-ai-templates/${video.template_id}/edit`)"
                    >
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                      查看模板
                    </span>
                  </div>
                </div>
                <div class="ad-video-actions">
                  <span class="ad-status-badge" :class="`ad-status-${video.status}`">
                    {{ statusLabel(video.status) }}
                  </span>
                  <!-- Publish action for pending_publish -->
                  <button
                    v-if="video.status === 'pending_publish'"
                    class="ad-action-btn"
                    @click="advanceToPublished(video)"
                  >标记已发布</button>
                </div>
              </div>

              <!-- Reviewing: pick one of 3 candidates -->
              <div v-if="video.status === 'reviewing'" class="ad-candidates">
                <div class="ad-candidates-label">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>
                  选择最佳视频，进入待发布
                </div>
                <div v-if="video.result_videos && video.result_videos.length" class="ad-candidates-grid">
                  <div
                    v-for="(candidate, idx) in video.result_videos"
                    :key="idx"
                    class="ad-candidate"
                    :class="{ 'ad-candidate--selected': selectedCandidates[video.id] === candidate.video_url }"
                    @click="selectCandidate(video.id, candidate.video_url)"
                  >
                    <div class="ad-candidate-thumb">
                      <video
                        :src="candidate.video_url"
                        class="ad-candidate-video"
                        preload="metadata"
                        controls
                        @click.stop
                      />
                      <div class="ad-candidate-check" v-if="selectedCandidates[video.id] === candidate.video_url">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                      </div>
                    </div>
                    <div class="ad-candidate-label">候选 {{ idx + 1 }}</div>
                  </div>
                </div>
                <div v-else class="ad-candidates-empty">暂无候选视频（等待生成结果回填）</div>
                <button
                  class="ad-confirm-btn"
                  :disabled="!selectedCandidates[video.id]"
                  @click="confirmSelection(video)"
                >确认选择，进入待发布</button>
              </div>
            </div>
          </template>
          <div v-else class="ad-video-empty">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#c7d2fe" stroke-width="1.2"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>
            <span>暂无{{ currentTabLabel }}的视频</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchAccount } from '../api/accounts'
import { fetchAccountGenerations, patchGenerationStatus } from '../api/video_generations'

const route = useRoute()
const router = useRouter()

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }

const VIDEO_TABS = [
  { key: 'pending',         label: '待生成' },
  { key: 'generating',      label: '生成中' },
  { key: 'reviewing',       label: '待审核' },
  { key: 'pending_publish', label: '待发布' },
  { key: 'published',       label: '已发布' },
]

const STATUS_LABELS = {
  pending:         '待生成',
  generating:      '生成中',
  reviewing:       '待审核',
  pending_publish: '待发布',
  published:       '已发布',
}

const loading = ref(false)
const videosLoading = ref(false)
const account = ref(null)
const activeTab = ref('pending')
const videos = ref([])
const allVideos = ref([])

// { [videoId]: selectedVideoUrl }
const selectedCandidates = ref({})

function platformLabel(p) { return PLATFORM_LABELS[p] || p }

function maskSecret(val) {
  if (!val) return '-'
  if (val.length <= 8) return '••••••••'
  return val.slice(0, 4) + '••••••••' + val.slice(-4)
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

function statusLabel(s) { return STATUS_LABELS[s] || s }

function selectedThumb(video) {
  if (!video.selected_video_url || !video.result_videos) return null
  const match = video.result_videos.find(v => v.video_url === video.selected_video_url)
  return match?.thumbnail_url || null
}

function selectCandidate(videoId, videoUrl) {
  selectedCandidates.value = { ...selectedCandidates.value, [videoId]: videoUrl }
}

const tabCounts = computed(() => {
  const counts = {}
  VIDEO_TABS.forEach(t => { counts[t.key] = 0 })
  allVideos.value.forEach(v => {
    if (counts[v.status] !== undefined) counts[v.status]++
  })
  return counts
})

const currentTabLabel = computed(() =>
  VIDEO_TABS.find(t => t.key === activeTab.value)?.label || ''
)

async function loadAccount() {
  loading.value = true
  try {
    account.value = await fetchAccount(route.params.id)
    await loadAllVideos()
    await loadVideos()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载失败')
    router.push('/dashboard/accounts')
  } finally {
    loading.value = false
  }
}

async function loadAllVideos() {
  allVideos.value = await fetchAccountGenerations(route.params.id)
}

let activeAbortController = null

async function loadVideos() {
  if (activeAbortController) {
    activeAbortController.abort()
  }
  const controller = new AbortController()
  activeAbortController = controller

  videosLoading.value = true
  try {
    videos.value = await fetchAccountGenerations(route.params.id, activeTab.value, {
      signal: controller.signal
    })
  } catch (err) {
    if (err?.__isCanceled || err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED' || err?.message === 'canceled') {
      return
    }
    ElMessage.error('加载视频列表失败')
  } finally {
    if (activeAbortController === controller) {
      videosLoading.value = false
      activeAbortController = null
    }
  }
}

async function switchTab(key) {
  activeTab.value = key
  await loadVideos()
}

async function confirmSelection(video) {
  const chosenUrl = selectedCandidates.value[video.id]
  if (!chosenUrl) return
  try {
    await patchGenerationStatus(video.id, {
      status: 'pending_publish',
      selected_video_url: chosenUrl,
    })
    ElMessage.success('已选择视频，进入待发布')
    delete selectedCandidates.value[video.id]
    await loadAllVideos()
    await loadVideos()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  }
}

async function advanceToPublished(video) {
  try {
    await ElMessageBox.confirm('确定将该视频标记为「已发布」吗？', '状态更新', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      customClass: 'vc-confirm-dialog',
    })
    await patchGenerationStatus(video.id, { status: 'published' })
    ElMessage.success('已标记为已发布')
    await loadAllVideos()
    await loadVideos()
  } catch (cancelOrErr) {
    if (cancelOrErr !== 'cancel') {
      ElMessage.error(cancelOrErr?.response?.data?.detail || '操作失败')
    }
  }
}

onMounted(loadAccount)
</script>

<style scoped>
.ad-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
}

/* Back */
.ad-back {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #6366f1;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 24px;
  transition: color 0.15s;
}

.ad-back:hover { color: #4338ca; }

/* Hero card */
.ad-hero {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,.05);
  padding: 28px;
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 20px;
}

.ad-hero-avatar {
  flex-shrink: 0;
}

.ad-avatar-img {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid #e0e7ff;
  box-shadow: 0 2px 12px rgba(99,102,241,.15);
}

.ad-avatar-placeholder {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3px solid #e0e7ff;
}

.ad-hero-info { flex: 1; }

.ad-hero-name {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}

.ad-hero-style {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 12px;
  line-height: 1.5;
}

.ad-hero-platforms {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ad-platform-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: 20px;
  letter-spacing: .02em;
}

.ad-platform-youtube  { background: #fef2f2; color: #dc2626; }
.ad-platform-tiktok   { background: #f1f5f9; color: #0f172a; }
.ad-platform-instagram { background: #fef3c7; color: #92400e; }
.ad-no-platform { font-size: 13px; color: #94a3b8; }

.ad-hero-actions { flex-shrink: 0; display: flex; gap: 12px; }

.ad-gen-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  padding: 9px 18px;
  border-radius: 10px;
  border: none;
  background: #6366f1;
  color: #ffffff;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
}

.ad-gen-btn:hover {
  background: #4f46e5;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
}

.ad-edit-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  padding: 9px 18px;
  border-radius: 10px;
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #4338ca;
  cursor: pointer;
  transition: all 0.15s;
}

.ad-edit-btn:hover {
  background: #e0e7ff;
  border-color: #6366f1;
}

/* Meta row */
.ad-meta-row {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 20px;
  margin-bottom: 20px;
}

.ad-info-card,
.ad-bindings-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
  padding: 20px;
}

.ad-card-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f1f5f9;
}

.ad-info-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 8px 0;
  border-bottom: 1px solid #f8fafc;
  gap: 12px;
}

.ad-info-item:last-child { border-bottom: none; }

.ad-info-label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
  flex-shrink: 0;
  width: 72px;
}

.ad-info-value {
  font-size: 13px;
  color: #334155;
  text-align: right;
  word-break: break-all;
}

/* Bindings */
.ad-empty-bindings {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}

.ad-link {
  color: #6366f1;
  cursor: pointer;
  font-weight: 600;
}

.ad-binding-block {
  border: 1px solid #e8edf5;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 12px;
  background: #fafbff;
}

.ad-binding-block:last-child { margin-bottom: 0; }

.ad-binding-header {
  margin-bottom: 10px;
}

.ad-binding-platform {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 6px;
}

.ad-binding-field {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 0;
  border-bottom: 1px solid #f1f5f9;
  gap: 12px;
}

.ad-binding-field:last-child { border-bottom: none; }

.ad-binding-field > span {
  font-size: 12px;
  color: #94a3b8;
  flex-shrink: 0;
}

.ad-binding-field code {
  font-size: 12px;
  font-family: 'Menlo', 'Consolas', monospace;
  color: #475569;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: right;
}

/* Videos section */
.ad-videos-section {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
  padding: 20px;
}

.ad-section-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 16px;
}

/* Tabs */
.ad-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 16px;
}

.ad-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
  padding: 8px 16px;
  border: none;
  background: none;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.15s;
  border-radius: 6px 6px 0 0;
}

.ad-tab:hover { color: #6366f1; background: #f5f3ff; }

.ad-tab.active {
  color: #6366f1;
  font-weight: 700;
  border-bottom-color: #6366f1;
  background: #f5f3ff;
}

.ad-tab-count {
  font-size: 11px;
  font-weight: 700;
  background: #6366f1;
  color: #fff;
  border-radius: 10px;
  padding: 1px 7px;
  min-width: 18px;
  text-align: center;
}

/* Video list */
.ad-video-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 160px;
}

.ad-video-item {
  display: flex;
  flex-direction: column;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid #f1f5f9;
  background: #fafbff;
  transition: background 0.15s;
}

.ad-video-item:hover { background: #eef2ff; border-color: #c7d2fe; }

/* Default (non-reviewing) row is a single horizontal row */
.ad-video-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ad-video-thumb {
  width: 72px;
  height: 42px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  background: #e2e8f0;
}

.ad-video-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.ad-video-thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ad-video-info { flex: 1; overflow: hidden; }

.ad-video-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.ad-video-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ad-video-platform {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 5px;
}

.ad-video-date {
  font-size: 11px;
  color: #94a3b8;
}

.ad-video-duration {
  font-size: 11px;
  color: #94a3b8;
}

.ad-video-template-link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  font-weight: 600;
  color: #6366f1;
  cursor: pointer;
  transition: color 0.15s;
}
.ad-video-template-link:hover { color: #4338ca; }

.ad-video-actions { flex-shrink: 0; display: flex; align-items: center; gap: 8px; }

.ad-status-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  white-space: nowrap;
}

.ad-status-pending         { background: #f1f5f9; color: #475569; }
.ad-status-generating      { background: #fef9c3; color: #a16207; }
.ad-status-reviewing       { background: #fed7aa; color: #c2410c; }
.ad-status-pending_publish { background: #dbeafe; color: #1d4ed8; }
.ad-status-published       { background: #dcfce7; color: #166534; }

.ad-action-btn {
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #6366f1;
  background: #eef2ff;
  color: #4338ca;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.ad-action-btn:hover { background: #e0e7ff; }

/* Candidate picker */
.ad-video-item--reviewing {
  flex-direction: column;
  align-items: stretch;
}

.ad-video-row {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
}

.ad-candidates {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.ad-candidates-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #6366f1;
  margin-bottom: 12px;
}

.ad-candidates-grid {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.ad-candidate {
  flex: 1;
  cursor: pointer;
  border-radius: 10px;
  border: 2px solid #e2e8f0;
  overflow: hidden;
  transition: all 0.15s;
}

.ad-candidate:hover {
  border-color: #a5b4fc;
  transform: translateY(-2px);
}

.ad-candidate--selected {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.2);
}

.ad-candidate-thumb {
  position: relative;
  aspect-ratio: 9/16;
  background: #f1f5f9;
  overflow: hidden;
}

.ad-candidate-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.ad-candidate-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  background: #0f172a;
}

.ad-candidate-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ad-candidate-check {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  background: #6366f1;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ad-candidate-label {
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  padding: 6px 0;
}

.ad-candidates-empty {
  font-size: 12px;
  color: #94a3b8;
  padding: 12px 0;
}

.ad-confirm-btn {
  font-size: 13px;
  font-weight: 700;
  padding: 8px 20px;
  border-radius: 8px;
  border: none;
  background: #6366f1;
  color: white;
  cursor: pointer;
  transition: all 0.15s;
}

.ad-confirm-btn:disabled {
  background: #c7d2fe;
  cursor: not-allowed;
}

.ad-confirm-btn:not(:disabled):hover {
  background: #4f46e5;
}

.ad-video-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px;
  color: #94a3b8;
  font-size: 13px;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (max-width: 900px) {
  .ad-meta-row { grid-template-columns: 1fr; }
  .ad-hero { flex-direction: column; text-align: center; }
  .ad-hero-platforms { justify-content: center; }
}
</style>
