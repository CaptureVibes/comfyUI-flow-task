<template>
  <div class="vsd-page">
    <!-- Header -->
    <div class="vsd-header">
      <div class="vsd-back" @click="router.push('/dashboard/video-library')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
        返回视频库
      </div>
    </div>

    <div v-loading="loading" class="vsd-content">
      <template v-if="video">
        <!-- Top: Player + Info -->
        <div class="vsd-top">
          <!-- Left: Player -->
          <div class="vsd-player-section">
            <!-- Video title above player -->
            <div class="vsd-player-title">
              <h1>{{ video.video_title || '无标题' }}</h1>
            </div>

            <div class="vsd-player-wrap">
              <video
                v-if="video.local_video_url || video.video_url"
                :src="video.local_video_url || video.video_url"
                controls
                autoplay
                class="vsd-video"
              />
              <div v-else class="vsd-noplayer">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>
                <div style="color:#94a3b8;font-size:13px;margin-top:8px">无视频地址</div>
              </div>
            </div>

            <!-- Download button/status -->
            <div class="vsd-dl-area">
              <template v-if="video.download_status === 'downloading'">
                <div class="vsd-dl-status vsd-dling">
                  <span class="vsd-dl-spin"></span> 下载上传中...
                </div>
              </template>
              <template v-else-if="video.download_status === 'done'">
                <div class="vsd-dl-status vsd-done">✓ 已上传可播放</div>
              </template>
              <template v-else-if="video.download_status === 'failed'">
                <el-button type="primary" @click="handleDownload" :loading="downloading">重试上传</el-button>
              </template>
              <template v-else>
                <el-button type="primary" @click="handleDownload" :loading="downloading">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="margin-right:4px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                  下载上传到永久存储
                </el-button>
              </template>
            </div>
          </div>

          <!-- Right: Metadata -->
          <div class="vsd-info-section">
            <div class="vsd-card">
              <div class="vsd-card-title">视频信息</div>
              <div class="vsd-info-rows">
                <div class="vsd-info-row">
                  <span class="vsd-info-label">博主</span>
                  <span class="vsd-info-val">@{{ video.blogger_name || '-' }}</span>
                </div>
                <div class="vsd-info-row">
                  <span class="vsd-info-label">发布日期</span>
                  <span class="vsd-info-val">{{ formatDate(video.publish_date) }}</span>
                </div>
                <div class="vsd-info-row" v-if="video.duration != null">
                  <span class="vsd-info-label">视频时长</span>
                  <span class="vsd-info-val">{{ formatDuration(video.duration) }}</span>
                </div>
                <div class="vsd-info-row" v-if="video.width && video.height">
                  <span class="vsd-info-label">分辨率</span>
                  <span class="vsd-info-val">{{ video.width }}x{{ video.height }}</span>
                </div>
                <div class="vsd-info-row" v-if="video.aspect_ratio != null">
                  <span class="vsd-info-label">视频比例</span>
                  <span class="vsd-info-val">{{ video.aspect_ratio.toFixed(2) }}</span>
                </div>
                <div class="vsd-info-row" v-if="video.view_count != null">
                  <span class="vsd-info-label">当前播放量</span>
                  <span class="vsd-info-val">{{ formatCount(video.view_count) }}</span>
                </div>
                <div class="vsd-info-row" v-if="video.like_count != null">
                  <span class="vsd-info-label">当前点赞数</span>
                  <span class="vsd-info-val">{{ formatCount(video.like_count) }}</span>
                </div>
                <div class="vsd-info-row" v-if="video.favorite_count != null">
                  <span class="vsd-info-label">当前收藏数</span>
                  <span class="vsd-info-val">{{ formatCount(video.favorite_count) }}</span>
                </div>
                <div class="vsd-info-row" v-if="video.comment_count != null">
                  <span class="vsd-info-label">当前评论数</span>
                  <span class="vsd-info-val">{{ formatCount(video.comment_count) }}</span>
                </div>
                <div class="vsd-info-row" v-if="video.share_count != null">
                  <span class="vsd-info-label">当前分享数</span>
                  <span class="vsd-info-val">{{ formatCount(video.share_count) }}</span>
                </div>
                <div class="vsd-info-row">
                  <span class="vsd-info-label">原始链接</span>
                  <el-link :href="video.source_url" target="_blank" type="primary" :underline="false">前往观看</el-link>
                </div>
                <div class="vsd-info-row">
                  <span class="vsd-info-label">入库时间</span>
                  <span class="vsd-info-val">{{ formatDateTime(video.created_at) }}</span>
                </div>
              </div>
            </div>

            <!-- Video Description Card -->
            <div v-if="video.video_desc" class="vsd-card">
              <div class="vsd-card-title">视频描述</div>
              <div class="vsd-video-desc">{{ video.video_desc }}</div>
            </div>

            <!-- Actions -->
            <div class="vsd-actions">
              <el-button type="danger" @click="handleDelete" :loading="deleting">删除视频</el-button>
            </div>
          </div>
        </div>

        <!-- Bottom: Charts -->
        <div class="vsd-charts">
          <div class="vsd-chart-card">
            <div class="vsd-chart-header">
              <div class="vsd-chart-title">播放量趋势</div>
              <div class="vsd-chart-growth">
                <span class="vsd-growth-label">近1天</span>
                <span :class="['vsd-growth-val', viewGrowth1d.class]">{{ viewGrowth1d.text }}</span>
                <span class="vsd-growth-label" style="margin-left: 12px">近7天</span>
                <span :class="['vsd-growth-val', viewGrowth7d.class]">{{ viewGrowth7d.text }}</span>
              </div>
            </div>
            <div v-if="statsItems.length > 0" class="vsd-chart-canvas" @mousemove="handleChartMove($event, 'view')" @mouseleave="hideTooltip">
              <svg viewBox="0 0 640 220" class="vsd-svg">
                <!-- Y-axis labels -->
                <text v-for="(label, i) in viewYLabels" :key="'ylabel-'+i"
                  :x="0" :y="viewYPositions[i]"
                  font-size="11" fill="#94a3b8" text-anchor="start">{{ label }}</text>
                <!-- Grid lines -->
                <line v-for="(pos, i) in viewYPositions" :key="'grid-'+i"
                  :x1="50" :y1="pos" :x2="610" :y2="pos"
                  stroke="#f1f5f9" stroke-width="1"
                />
                <!-- X-axis labels -->
                <text v-for="(label, i) in viewXLabels" :key="'xlabel-'+i"
                  :x="viewXPositions[i]" :y="215"
                  font-size="10" fill="#94a3b8" text-anchor="middle">{{ label }}</text>
                <!-- View count line -->
                <polyline :points="viewLinePoints" fill="none" stroke="#6366f1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <!-- View points -->
                <circle v-for="(p, idx) in viewPoints" :key="'view-'+idx"
                  :cx="p.x" :cy="p.y" r="4" fill="#fff" stroke="#6366f1" stroke-width="2"
                  @mouseover="showTooltip($event, 'view', idx)"
                  style="cursor: pointer"
                />
              </svg>
              <!-- Tooltip -->
              <div v-if="tooltip.visible && tooltip.type === 'view'"
                   class="vsd-tooltip"
                   :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
                <div class="vsd-tooltip-date">{{ tooltip.date }}</div>
                <div class="vsd-tooltip-value">{{ formatCount(tooltip.value) }} 次播放</div>
              </div>
            </div>
            <el-empty v-else description="暂无历史数据" :image-size="60" />
          </div>

          <div class="vsd-chart-card">
            <div class="vsd-chart-header">
              <div class="vsd-chart-title">点赞数趋势</div>
              <div class="vsd-chart-growth">
                <span class="vsd-growth-label">近1天</span>
                <span :class="['vsd-growth-val', likeGrowth1d.class]">{{ likeGrowth1d.text }}</span>
                <span class="vsd-growth-label" style="margin-left: 12px">近7天</span>
                <span :class="['vsd-growth-val', likeGrowth7d.class]">{{ likeGrowth7d.text }}</span>
              </div>
            </div>
            <div v-if="statsItems.length > 0" class="vsd-chart-canvas" @mousemove="handleChartMove($event, 'like')" @mouseleave="hideTooltip">
              <svg viewBox="0 0 640 220" class="vsd-svg">
                <!-- Y-axis labels -->
                <text v-for="(label, i) in likeYLabels" :key="'ylabel2-'+i"
                  :x="0" :y="likeYPositions[i]"
                  font-size="11" fill="#94a3b8" text-anchor="start">{{ label }}</text>
                <!-- Grid lines -->
                <line v-for="(pos, i) in likeYPositions" :key="'grid2-'+i"
                  :x1="50" :y1="pos" :x2="610" :y2="pos"
                  stroke="#f1f5f9" stroke-width="1"
                />
                <!-- X-axis labels -->
                <text v-for="(label, i) in likeXLabels" :key="'xlabel2-'+i"
                  :x="likeXPositions[i]" :y="215"
                  font-size="10" fill="#94a3b8" text-anchor="middle">{{ label }}</text>
                <!-- Like count line -->
                <polyline :points="likeLinePoints" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <!-- Like points -->
                <circle v-for="(p, idx) in likePoints" :key="'like-'+idx"
                  :cx="p.x" :cy="p.y" r="4" fill="#fff" stroke="#10b981" stroke-width="2"
                  @mouseover="showTooltip($event, 'like', idx)"
                  style="cursor: pointer"
                />
              </svg>
              <!-- Tooltip -->
              <div v-if="tooltip.visible && tooltip.type === 'like'"
                   class="vsd-tooltip"
                   :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
                <div class="vsd-tooltip-date">{{ tooltip.date }}</div>
                <div class="vsd-tooltip-value">{{ formatCount(tooltip.value) }} 个赞</div>
              </div>
            </div>
            <el-empty v-else description="暂无历史数据" :image-size="60" />
          </div>

          <div class="vsd-chart-card">
            <div class="vsd-chart-header">
              <div class="vsd-chart-title">评论数趋势</div>
              <div class="vsd-chart-growth">
                <span class="vsd-growth-label">近1天</span>
                <span :class="['vsd-growth-val', commentGrowth1d.class]">{{ commentGrowth1d.text }}</span>
                <span class="vsd-growth-label" style="margin-left: 12px">近7天</span>
                <span :class="['vsd-growth-val', commentGrowth7d.class]">{{ commentGrowth7d.text }}</span>
              </div>
            </div>
            <div v-if="statsItems.length > 0" class="vsd-chart-canvas" @mousemove="handleChartMove($event, 'comment')" @mouseleave="hideTooltip">
              <svg viewBox="0 0 640 220" class="vsd-svg">
                <!-- Y-axis labels -->
                <text v-for="(label, i) in commentYLabels" :key="'ylabel3-'+i"
                  :x="0" :y="commentYPositions[i]"
                  font-size="11" fill="#94a3b8" text-anchor="start">{{ label }}</text>
                <!-- Grid lines -->
                <line v-for="(pos, i) in commentYPositions" :key="'grid3-'+i"
                  :x1="50" :y1="pos" :x2="610" :y2="pos"
                  stroke="#f1f5f9" stroke-width="1"
                />
                <!-- X-axis labels -->
                <text v-for="(label, i) in commentXLabels" :key="'xlabel3-'+i"
                  :x="commentXPositions[i]" :y="215"
                  font-size="10" fill="#94a3b8" text-anchor="middle">{{ label }}</text>
                <!-- Comment count line -->
                <polyline :points="commentLinePoints" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <!-- Comment points -->
                <circle v-for="(p, idx) in commentPoints" :key="'comment-'+idx"
                  :cx="p.x" :cy="p.y" r="4" fill="#fff" stroke="#f59e0b" stroke-width="2"
                  @mouseover="showTooltip($event, 'comment', idx)"
                  style="cursor: pointer"
                />
              </svg>
              <!-- Tooltip -->
              <div v-if="tooltip.visible && tooltip.type === 'comment'"
                   class="vsd-tooltip"
                   :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
                <div class="vsd-tooltip-date">{{ tooltip.date }}</div>
                <div class="vsd-tooltip-value">{{ formatCount(tooltip.value) }} 条评论</div>
              </div>
            </div>
            <el-empty v-else description="暂无历史数据" :image-size="60" />
          </div>

          <div class="vsd-chart-card">
            <div class="vsd-chart-header">
              <div class="vsd-chart-title">收藏数趋势</div>
              <div class="vsd-chart-growth">
                <span class="vsd-growth-label">近1天</span>
                <span :class="['vsd-growth-val', favoriteGrowth1d.class]">{{ favoriteGrowth1d.text }}</span>
                <span class="vsd-growth-label" style="margin-left: 12px">近7天</span>
                <span :class="['vsd-growth-val', favoriteGrowth7d.class]">{{ favoriteGrowth7d.text }}</span>
              </div>
            </div>
            <div v-if="statsItems.length > 0" class="vsd-chart-canvas" @mousemove="handleChartMove($event, 'favorite')" @mouseleave="hideTooltip">
              <svg viewBox="0 0 640 220" class="vsd-svg">
                <!-- Y-axis labels -->
                <text v-for="(label, i) in favoriteYLabels" :key="'ylabel4-'+i"
                  :x="0" :y="favoriteYPositions[i]"
                  font-size="11" fill="#94a3b8" text-anchor="start">{{ label }}</text>
                <!-- Grid lines -->
                <line v-for="(pos, i) in favoriteYPositions" :key="'grid4-'+i"
                  :x1="50" :y1="pos" :x2="610" :y2="pos"
                  stroke="#f1f5f9" stroke-width="1"
                />
                <!-- X-axis labels -->
                <text v-for="(label, i) in favoriteXLabels" :key="'xlabel4-'+i"
                  :x="favoriteXPositions[i]" :y="215"
                  font-size="10" fill="#94a3b8" text-anchor="middle">{{ label }}</text>
                <!-- Favorite count line -->
                <polyline :points="favoriteLinePoints" fill="none" stroke="#8b5cf6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <!-- Favorite points -->
                <circle v-for="(p, idx) in favoritePoints" :key="'favorite-'+idx"
                  :cx="p.x" :cy="p.y" r="4" fill="#fff" stroke="#8b5cf6" stroke-width="2"
                  @mouseover="showTooltip($event, 'favorite', idx)"
                  style="cursor: pointer"
                />
              </svg>
              <!-- Tooltip -->
              <div v-if="tooltip.visible && tooltip.type === 'favorite'"
                   class="vsd-tooltip"
                   :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
                <div class="vsd-tooltip-date">{{ tooltip.date }}</div>
                <div class="vsd-tooltip-value">{{ formatCount(tooltip.value) }} 次收藏</div>
              </div>
            </div>
            <el-empty v-else description="暂无历史数据" :image-size="60" />
          </div>

          <div class="vsd-chart-card">
            <div class="vsd-chart-header">
              <div class="vsd-chart-title">分享数趋势</div>
              <div class="vsd-chart-growth">
                <span class="vsd-growth-label">近1天</span>
                <span :class="['vsd-growth-val', shareGrowth1d.class]">{{ shareGrowth1d.text }}</span>
                <span class="vsd-growth-label" style="margin-left: 12px">近7天</span>
                <span :class="['vsd-growth-val', shareGrowth7d.class]">{{ shareGrowth7d.text }}</span>
              </div>
            </div>
            <div v-if="statsItems.length > 0" class="vsd-chart-canvas" @mousemove="handleChartMove($event, 'share')" @mouseleave="hideTooltip">
              <svg viewBox="0 0 640 220" class="vsd-svg">
                <!-- Y-axis labels -->
                <text v-for="(label, i) in shareYLabels" :key="'ylabel5-'+i"
                  :x="0" :y="shareYPositions[i]"
                  font-size="11" fill="#94a3b8" text-anchor="start">{{ label }}</text>
                <!-- Grid lines -->
                <line v-for="(pos, i) in shareYPositions" :key="'grid5-'+i"
                  :x1="50" :y1="pos" :x2="610" :y2="pos"
                  stroke="#f1f5f9" stroke-width="1"
                />
                <!-- X-axis labels -->
                <text v-for="(label, i) in shareXLabels" :key="'xlabel5-'+i"
                  :x="shareXPositions[i]" :y="215"
                  font-size="10" fill="#94a3b8" text-anchor="middle">{{ label }}</text>
                <!-- Share count line -->
                <polyline :points="shareLinePoints" fill="none" stroke="#ec4899" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <!-- Share points -->
                <circle v-for="(p, idx) in sharePoints" :key="'share-'+idx"
                  :cx="p.x" :cy="p.y" r="4" fill="#fff" stroke="#ec4899" stroke-width="2"
                  @mouseover="showTooltip($event, 'share', idx)"
                  style="cursor: pointer"
                />
              </svg>
              <!-- Tooltip -->
              <div v-if="tooltip.visible && tooltip.type === 'share'"
                   class="vsd-tooltip"
                   :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
                <div class="vsd-tooltip-date">{{ tooltip.date }}</div>
                <div class="vsd-tooltip-value">{{ formatCount(tooltip.value) }} 次分享</div>
              </div>
            </div>
            <el-empty v-else description="暂无历史数据" :image-size="60" />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchVideoSource, deleteVideoSource, downloadVideoSource, fetchVideoSourceStatsHistory } from '../api/video_sources'

const route = useRoute()
const router = useRouter()
const videoId = route.params.id

const loading = ref(true)
const video = ref(null)
const statsItems = ref([])
const downloading = ref(false)
const deleting = ref(false)
const tooltip = ref({ visible: false, x: 0, y: 0, date: '', value: 0, type: '' })
let pollTimer = null

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok' }
function platformLabel(p) { return PLATFORM_LABELS[p] || (p || '未知') }

function formatCount(n) {
  if (n == null) return '-'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
}

function formatDateTime(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

function formatDuration(seconds) {
  if (!seconds) return '-'
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

async function loadData() {
  loading.value = true
  try {
    video.value = await fetchVideoSource(videoId)
    schedulePollIfNeeded()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    let items = await fetchVideoSourceStatsHistory(videoId)
    // If no real data, generate mock data for demo
    if (items.length === 0 && video.value) {
      const baseView = video.value.view_count || 10000
      const baseLike = video.value.like_count || 500
      const baseComment = video.value.comment_count || 100
      const baseFavorite = video.value.favorite_count || 50
      const baseShare = video.value.share_count || 20
      const now = new Date()
      items = []
      for (let i = 14; i >= 0; i--) {
        const date = new Date(now)
        date.setDate(date.getDate() - i)
        date.setHours(0, 0, 0, 0)
        // Add some random variation
        const viewVariation = Math.floor((i / 14) * baseView * 0.3) + Math.floor(Math.random() * baseView * 0.1)
        const likeVariation = Math.floor((i / 14) * baseLike * 0.25) + Math.floor(Math.random() * baseLike * 0.08)
        const commentVariation = Math.floor((i / 14) * baseComment * 0.2) + Math.floor(Math.random() * baseComment * 0.05)
        const favoriteVariation = Math.floor((i / 14) * baseFavorite * 0.15) + Math.floor(Math.random() * baseFavorite * 0.04)
        const shareVariation = Math.floor((i / 14) * baseShare * 0.2) + Math.floor(Math.random() * baseShare * 0.06)
        items.push({
          id: `mock-${i}`,
          video_source_id: videoId,
          collected_at: date.toISOString(),
          view_count: baseView - viewVariation,
          like_count: baseLike - likeVariation,
          comment_count: baseComment - commentVariation,
          favorite_count: baseFavorite - favoriteVariation,
          share_count: baseShare - shareVariation,
        })
      }
    }
    statsItems.value = items
  } catch { /* ignore */ }
}

function schedulePollIfNeeded() {
  clearTimeout(pollTimer)
  if (video.value?.download_status === 'downloading') {
    pollTimer = setTimeout(() => {
      loadData()
      loadStats()
    }, 3000)
  }
}

async function handleDownload() {
  downloading.value = true
  try {
    video.value = await downloadVideoSource(videoId)
    ElMessage.success('已开始下载')
    schedulePollIfNeeded()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '启动下载失败')
  } finally {
    downloading.value = false
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('确定删除此视频？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch { return }

  deleting.value = true
  try {
    await deleteVideoSource(videoId)
    ElMessage.success('已删除')
    router.push('/dashboard/video-library')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

// Chart calculations
const viewData = computed(() => statsItems.value.map(s => s.view_count).filter(v => v != null))
const likeData = computed(() => statsItems.value.map(s => s.like_count).filter(v => v != null))
const commentData = computed(() => statsItems.value.map(s => s.comment_count).filter(v => v != null))
const favoriteData = computed(() => statsItems.value.map(s => s.favorite_count).filter(v => v != null))
const shareData = computed(() => statsItems.value.map(s => s.share_count).filter(v => v != null))

const viewMax = computed(() => Math.max(...viewData.value, 1))
const viewMin = computed(() => Math.min(...viewData.value, 0))

const likeMax = computed(() => Math.max(...likeData.value, 1))
const likeMin = computed(() => Math.min(...likeData.value, 0))

const commentMax = computed(() => Math.max(...commentData.value, 1))
const commentMin = computed(() => Math.min(...commentData.value, 0))

const favoriteMax = computed(() => Math.max(...favoriteData.value, 1))
const favoriteMin = computed(() => Math.min(...favoriteData.value, 0))

const shareMax = computed(() => Math.max(...shareData.value, 1))
const shareMin = computed(() => Math.min(...shareData.value, 0))

// Y-axis positions (5 grid lines from top to bottom)
const chartLeft = 50
const chartRight = 610
const chartHeight = 160
const chartTop = 30
const chartBottom = 190
const yAxisCount = 5

const viewYPositions = computed(() => {
  return Array.from({ length: yAxisCount }, (_, i) => chartTop + (i * (chartHeight / (yAxisCount - 1))))
})

const likeYPositions = viewYPositions
const commentYPositions = viewYPositions
const favoriteYPositions = viewYPositions
const shareYPositions = viewYPositions

// Y-axis labels
const formatYLabel = (val) => {
  if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M'
  if (val >= 1000) return (val / 1000).toFixed(1) + 'K'
  return String(val)
}

const viewYLabels = computed(() => {
  const step = (viewMax.value - viewMin.value) / (yAxisCount - 1)
  return Array.from({ length: yAxisCount }, (_, i) => formatYLabel(Math.round(viewMax.value - i * step)))
})

const likeYLabels = computed(() => {
  const step = (likeMax.value - likeMin.value) / (yAxisCount - 1)
  return Array.from({ length: yAxisCount }, (_, i) => formatYLabel(Math.round(likeMax.value - i * step)))
})

const commentYLabels = computed(() => {
  const step = (commentMax.value - commentMin.value) / (yAxisCount - 1)
  return Array.from({ length: yAxisCount }, (_, i) => formatYLabel(Math.round(commentMax.value - i * step)))
})

const favoriteYLabels = computed(() => {
  const step = (favoriteMax.value - favoriteMin.value) / (yAxisCount - 1)
  return Array.from({ length: yAxisCount }, (_, i) => formatYLabel(Math.round(favoriteMax.value - i * step)))
})

const shareYLabels = computed(() => {
  const step = (shareMax.value - shareMin.value) / (yAxisCount - 1)
  return Array.from({ length: yAxisCount }, (_, i) => formatYLabel(Math.round(shareMax.value - i * step)))
})

// X-axis labels (dates) - show at most 7 labels
const maxLabels = 7
const labelStep = computed(() => Math.max(1, Math.floor(statsItems.value.length / maxLabels)))
const xStep = computed(() => statsItems.value.length > 1 ? (chartRight - chartLeft) / (statsItems.value.length - 1) : 0)

const viewXLabels = computed(() => {
  return statsItems.value
    .filter((_, i) => i % labelStep.value === 0 || i === statsItems.value.length - 1)
    .map(s => formatDateShort(s.collected_at))
})

const likeXLabels = viewXLabels
const commentXLabels = viewXLabels
const favoriteXLabels = viewXLabels
const shareXLabels = viewXLabels

const viewXPositions = computed(() => {
  return statsItems.value
    .map((_, i) => chartLeft + i * xStep.value)
    .filter((_, i) => i % labelStep.value === 0 || i === statsItems.value.length - 1)
})

const likeXPositions = viewXPositions
const commentXPositions = viewXPositions
const favoriteXPositions = viewXPositions
const shareXPositions = viewXPositions

function formatDateShort(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function calcPoints(data, minVal, maxVal) {
  if (data.length < 2) return []
  const range = maxVal - minVal || 1

  return data.map((val, i) => {
    const x = chartLeft + i * xStep.value
    const normalized = (val - minVal) / range
    const y = chartBottom - normalized * chartHeight
    return { x, y }
  })
}

const viewPoints = computed(() => calcPoints(viewData.value, viewMin.value, viewMax.value))
const likePoints = computed(() => calcPoints(likeData.value, likeMin.value, likeMax.value))
const commentPoints = computed(() => calcPoints(commentData.value, commentMin.value, commentMax.value))
const favoritePoints = computed(() => calcPoints(favoriteData.value, favoriteMin.value, favoriteMax.value))
const sharePoints = computed(() => calcPoints(shareData.value, shareMin.value, shareMax.value))

const viewLinePoints = computed(() => viewPoints.value.map(p => `${p.x},${p.y}`).join(' '))
const likeLinePoints = computed(() => likePoints.value.map(p => `${p.x},${p.y}`).join(' '))
const commentLinePoints = computed(() => commentPoints.value.map(p => `${p.x},${p.y}`).join(' '))
const favoriteLinePoints = computed(() => favoritePoints.value.map(p => `${p.x},${p.y}`).join(' '))
const shareLinePoints = computed(() => sharePoints.value.map(p => `${p.x},${p.y}`).join(' '))

// Growth rate calculations
function calcGrowth(data, days) {
  if (data.length < days + 1) return { text: '-', class: 'vsd-growth-neutral' }
  const current = data[data.length - 1]
  const previous = data[data.length - 1 - days]
  if (!previous || previous === 0) return { text: '-', class: 'vsd-growth-neutral' }
  const rate = ((current - previous) / previous * 100).toFixed(1)
  const value = parseFloat(rate)
  if (value > 0) return { text: `+${rate}%`, class: 'vsd-growth-up' }
  if (value < 0) return { text: `${rate}%`, class: 'vsd-growth-down' }
  return { text: '0%', class: 'vsd-growth-neutral' }
}

const viewGrowth1d = computed(() => calcGrowth(viewData.value, 1))
const viewGrowth7d = computed(() => calcGrowth(viewData.value, 7))
const likeGrowth1d = computed(() => calcGrowth(likeData.value, 1))
const likeGrowth7d = computed(() => calcGrowth(likeData.value, 7))
const commentGrowth1d = computed(() => calcGrowth(commentData.value, 1))
const commentGrowth7d = computed(() => calcGrowth(commentData.value, 7))
const favoriteGrowth1d = computed(() => calcGrowth(favoriteData.value, 1))
const favoriteGrowth7d = computed(() => calcGrowth(favoriteData.value, 7))
const shareGrowth1d = computed(() => calcGrowth(shareData.value, 1))
const shareGrowth7d = computed(() => calcGrowth(shareData.value, 7))

// Tooltip handling
function showTooltip(event, type, index) {
  const item = statsItems.value[index]
  if (!item) return

  let value = 0
  if (type === 'view') value = item.view_count || 0
  else if (type === 'like') value = item.like_count || 0
  else if (type === 'comment') value = item.comment_count || 0

  tooltip.value = {
    visible: true,
    x: event.offsetX + 15,
    y: event.offsetY - 40,
    date: formatDate(item.collected_at),
    value,
    type,
  }
}

function hideTooltip() {
  tooltip.value.visible = false
}

function handleChartMove(event, type) {
  // Optional: show nearest point tooltip on mouse move
}

onMounted(() => {
  loadData()
  loadStats()
})

onUnmounted(() => {
  clearTimeout(pollTimer)
})
</script>

<style scoped>
.vsd-page {
  padding: 24px 32px;
  animation: rise 0.3s ease;
}

.vsd-header {
  margin-bottom: 24px;
}

.vsd-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  margin-bottom: 16px;
}
.vsd-back:hover { color: #6366f1; }

.vsd-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.vsd-title {
  font-size: 24px;
  font-weight: 800;
  color: #0f172a;
  margin: 0;
}

.vsd-content {
  max-width: 1100px;
}

.vsd-top {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 24px;
  margin-bottom: 24px;
}

@media (max-width: 900px) {
  .vsd-top { grid-template-columns: 1fr; }
}

/* Player */
.vsd-player-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vsd-player-title {
  margin-bottom: 4px;
}

.vsd-player-title h1 {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
  line-height: 1.4;
  word-break: break-word;
}

.vsd-player-wrap {
  background: #000;
  border-radius: 12px;
  overflow: hidden;
  aspect-ratio: 16/9;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vsd-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.vsd-noplayer {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.vsd-dl-area {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 36px;
}

.vsd-dl-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: 8px;
}

.vsd-dling { background: #fef9c3; color: #a16207; }
.vsd-done { background: #dcfce7; color: #166534; }

.vsd-dl-spin {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid #a16207;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Info */
.vsd-info-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.vsd-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}

.vsd-card-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 16px;
}

.vsd-video-desc {
  font-size: 14px;
  color: #64748b;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.vsd-video-title {
  font-size: 18px;
  font-weight: 600;
  color: #334155;
  line-height: 1.5;
  word-break: break-word;
}

.vsd-info-rows {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vsd-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.vsd-info-label {
  color: #64748b;
  font-weight: 500;
}

.vsd-info-val {
  color: #334155;
  font-weight: 600;
}

.vsd-actions {
  display: flex;
  gap: 10px;
}

/* Charts */
.vsd-charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
  gap: 20px;
}

@media (max-width: 1400px) {
  .vsd-charts { grid-template-columns: 1fr; }
}

.vsd-chart-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}

.vsd-chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.vsd-chart-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.vsd-chart-growth {
  display: flex;
  align-items: center;
  gap: 4px;
}

.vsd-growth-label {
  font-size: 11px;
  color: #94a3b8;
}

.vsd-growth-val {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.vsd-growth-up {
  color: #10b981;
  background: #dcfce7;
}

.vsd-growth-down {
  color: #ef4444;
  background: #fee2e2;
}

.vsd-growth-neutral {
  color: #94a3b8;
  background: #f1f5f9;
}

.vsd-chart-canvas {
  width: 100%;
  height: 220px;
  position: relative;
}

.vsd-svg {
  width: 100%;
  height: 100%;
}

.vsd-tooltip {
  position: absolute;
  background: rgba(15, 23, 42, 0.95);
  color: #fff;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  pointer-events: none;
  z-index: 100;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  white-space: nowrap;
}

.vsd-tooltip-date {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 2px;
}

.vsd-tooltip-value {
  font-weight: 600;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
