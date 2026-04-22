<template>
  <div class="ps-page">
    <!-- Header -->
    <div class="ps-header">
      <h1 class="ps-title">数据统计</h1>
      <div class="ps-header-right">
        <button class="ps-btn ps-btn-sync" :disabled="syncing" @click="handleSyncMetrics">
          <svg v-if="!syncing" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:5px;vertical-align:-2px"><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:5px;vertical-align:-2px;animation:spin 1s linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          {{ syncing ? '同步中...' : '同步数据' }}
        </button>
        <button class="ps-btn ps-btn-export" :disabled="exporting" @click="handleExport">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:5px;vertical-align:-2px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          {{ exporting ? '导出中...' : '导出Excel' }}
        </button>
        <!-- Date mode -->
        <el-radio-group v-model="filters.date_mode" size="small" @change="handleDateModeChange">
          <el-radio-button label="day">某一天</el-radio-button>
          <el-radio-button label="week">最近一周</el-radio-button>
          <el-radio-button label="month">最近一个月</el-radio-button>
          <el-radio-button label="custom">自定义</el-radio-button>
        </el-radio-group>
        <el-date-picker
          v-if="filters.date_mode === 'day'"
          v-model="filters.single_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择某一天"
          size="small"
          style="width:150px"
          @change="syncDateFiltersFromMode"
        />
        <el-date-picker
          v-else-if="filters.date_mode === 'custom'"
          v-model="filters.date_range"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始"
          end-placeholder="结束"
          unlink-panels
          size="small"
          style="width:260px"
          @change="syncDateFiltersFromMode"
        />
      </div>
    </div>

    <!-- Filter bar -->
    <div class="ps-filter-bar">
      <el-select v-model="filters.platform" clearable placeholder="全部平台" size="small" style="width:120px">
        <el-option label="TikTok" value="tiktok" />
        <el-option label="YouTube" value="youtube" />
        <el-option label="Instagram" value="instagram" />
      </el-select>
      <el-select v-model="filters.account_id" clearable placeholder="全部账号" filterable size="small" style="width:180px">
        <el-option
          v-for="account in accountOptions"
          :key="account.id"
          :label="account.account_name"
          :value="account.id"
        />
      </el-select>
      <el-input
        v-model.trim="filters.keyword"
        placeholder="标题、账号、渠道名、平台链接"
        size="small"
        clearable
        style="width:260px"
        @keyup.enter="applyFilters"
      />
      <button class="ps-btn ps-btn-primary" @click="applyFilters">筛选</button>
      <button class="ps-btn ps-btn-secondary" @click="resetFilters">重置</button>
      <span class="ps-count-badge">共 {{ total }} 条</span>
    </div>

    <!-- Table -->
    <div v-loading="loading" class="ps-table-wrap">
      <div v-if="!loading && items.length === 0" class="ps-empty">暂无符合条件的数据</div>
      <table v-else class="ps-table">
        <thead>
          <tr>
            <th class="ps-th ps-th-video">视频</th>
            <th class="ps-th ps-th-title">
              <button class="ps-sort-btn" @click="toggleSort('title')">标题{{ sortMark('title') }}</button>
            </th>
            <th class="ps-th">
              <button class="ps-sort-btn" @click="toggleSort('account_name')">账号{{ sortMark('account_name') }}</button>
            </th>
            <th class="ps-th">平台</th>
            <th class="ps-th">
              <button class="ps-sort-btn" @click="toggleSort('published_at')">发布时间{{ sortMark('published_at') }}</button>
            </th>
            <th class="ps-th ps-th-num">
              <button class="ps-sort-btn" @click="toggleSort('total_views')">播放量{{ sortMark('total_views') }}</button>
            </th>
            <th class="ps-th ps-th-num">
              <button class="ps-sort-btn" @click="toggleSort('total_likes')">点赞{{ sortMark('total_likes') }}</button>
            </th>
            <th class="ps-th ps-th-num">
              <button class="ps-sort-btn" @click="toggleSort('total_comments')">评论{{ sortMark('total_comments') }}</button>
            </th>
            <th class="ps-th ps-th-num">
              <button class="ps-sort-btn" @click="toggleSort('total_shares')">分享{{ sortMark('total_shares') }}</button>
            </th>
            <th class="ps-th ps-th-num">
              <button class="ps-sort-btn" @click="toggleSort('avg_view_percentage')">平均观看比{{ sortMark('avg_view_percentage') }}</button>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id" class="ps-tr" @click="openDetail(item)">
            <td class="ps-td ps-td-video">
              <video v-if="item.video_url" :src="item.video_url" class="ps-video" controls preload="metadata" />
              <div v-else class="ps-video ps-video-empty">暂无视频</div>
            </td>
            <td class="ps-td ps-td-title">
              <div class="ps-title-main">{{ item.title || '未命名视频' }}</div>
              <div v-if="item.description" class="ps-title-sub">{{ item.description }}</div>
            </td>
            <td class="ps-td">
              <span class="ps-account-name">{{ item.account_name || '-' }}</span>
            </td>
            <td class="ps-td">
              <div class="ps-platforms">
                <a
                  v-for="channel in item.metrics_channels"
                  :key="`${item.id}-${channel.platform}-${channel.channel_id || 'na'}`"
                  :href="channel.platform_video_url || undefined"
                  :class="['ps-platform-tag', `ps-platform-${channel.platform}`]"
                  target="_blank"
                  rel="noreferrer"
                >{{ PLATFORM_LABELS[channel.platform] || channel.platform }}</a>
                <span v-if="!item.metrics_channels?.length" class="ps-dash">-</span>
              </div>
            </td>
            <td class="ps-td ps-td-date">{{ formatDateTime(item.published_at || item.created_at) }}</td>
            <td class="ps-td ps-td-num">{{ compactNumber(item.total_views) }}</td>
            <td class="ps-td ps-td-num">{{ compactNumber(item.total_likes) }}</td>
            <td class="ps-td ps-td-num">{{ compactNumber(item.total_comments) }}</td>
            <td class="ps-td ps-td-num">{{ compactNumber(item.total_shares) }}</td>
            <td class="ps-td ps-td-num">{{ formatPercent(item.avg_view_percentage) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > 0" class="ps-footer">
      <div class="ps-pagination-left">
        <span class="ps-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
        <select v-model="filters.page_size" @change="handleSizeChange" class="ps-simple-select">
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="500">500</option>
        </select>
      </div>
      <div class="ps-pagination">
        <button class="pg-btn" :disabled="filters.page <= 1" @click="changePage(filters.page - 1)">← 上一页</button>
        <template v-for="p in visiblePages" :key="p">
          <span v-if="p === '...'" class="pg-ellipsis">…</span>
          <button v-else class="pg-btn pg-num" :class="{ active: p === filters.page }" @click="changePage(p)">{{ p }}</button>
        </template>
        <button class="pg-btn" :disabled="filters.page >= totalPages" @click="changePage(filters.page + 1)">下一页 →</button>
      </div>
    </div>
  </div>

  <!-- 平台详情抽屉 -->
  <el-drawer
    v-model="drawerVisible"
    direction="rtl"
    size="420px"
    :with-header="false"
    append-to-body
    class="ps-drawer"
  >
    <div v-if="activeItem" class="psd-wrap">
      <!-- 抽屉头部 -->
      <div class="psd-header">
        <div class="psd-header-info">
          <div class="psd-video-title">{{ activeItem.title || '未命名视频' }}</div>
          <div class="psd-account">{{ activeItem.account_name }}</div>
        </div>
        <button class="psd-close" @click="drawerVisible = false">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <!-- 视频预览 -->
      <div class="psd-video-wrap">
        <video v-if="activeItem.video_url" :src="activeItem.video_url" class="psd-video" controls preload="metadata" />
        <div v-else class="psd-video psd-video-empty">暂无视频</div>
      </div>

      <!-- 汇总数据 -->
      <div class="psd-section-title">汇总数据</div>
      <div class="psd-summary-grid">
        <div class="psd-summary-card">
          <div class="psd-card-label">总播放量</div>
          <div class="psd-card-value">{{ compactNumber(activeItem.total_views) }}</div>
        </div>
        <div class="psd-summary-card">
          <div class="psd-card-label">总点赞</div>
          <div class="psd-card-value">{{ compactNumber(activeItem.total_likes) }}</div>
        </div>
        <div class="psd-summary-card">
          <div class="psd-card-label">总评论</div>
          <div class="psd-card-value">{{ compactNumber(activeItem.total_comments) }}</div>
        </div>
        <div class="psd-summary-card">
          <div class="psd-card-label">总分享</div>
          <div class="psd-card-value">{{ compactNumber(activeItem.total_shares) }}</div>
        </div>
        <div class="psd-summary-card">
          <div class="psd-card-label">平均观看比</div>
          <div class="psd-card-value">{{ formatPercent(activeItem.avg_view_percentage) }}</div>
        </div>
      </div>

      <!-- 各平台数据 -->
      <div class="psd-section-title">各平台数据</div>
      <div v-if="!activeItem.metrics_channels?.length" class="psd-no-channels">暂无平台数据</div>
      <div
        v-for="ch in activeItem.metrics_channels"
        :key="`${ch.platform}-${ch.channel_id}`"
        class="psd-channel-card"
      >
        <div class="psd-ch-header">
          <span :class="['psd-platform-tag', `ps-platform-${ch.platform}`]">
            {{ PLATFORM_LABELS[ch.platform] || ch.platform }}
          </span>
          <span class="psd-ch-name">{{ ch.channel_name || ch.channel_id || '-' }}</span>
          <a v-if="ch.platform_video_url" :href="ch.platform_video_url" target="_blank" rel="noreferrer" class="psd-link" @click.stop>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          </a>
        </div>
        <div class="psd-ch-stats">
          <template v-if="ch.stats">
            <div class="psd-stat-row" v-if="statVal(ch, 'views') != null">
              <span class="psd-stat-label">播放量</span>
              <span class="psd-stat-val">{{ compactNumber(statVal(ch, 'views')) }}</span>
            </div>
            <div class="psd-stat-row" v-if="ch.stats.engaged_views != null">
              <span class="psd-stat-label">有效播放</span>
              <span class="psd-stat-val">{{ compactNumber(ch.stats.engaged_views) }}</span>
            </div>
            <div class="psd-stat-row" v-if="statVal(ch, 'likes') != null">
              <span class="psd-stat-label">点赞</span>
              <span class="psd-stat-val">{{ compactNumber(statVal(ch, 'likes')) }}</span>
            </div>
            <div class="psd-stat-row" v-if="statVal(ch, 'comments') != null">
              <span class="psd-stat-label">评论</span>
              <span class="psd-stat-val">{{ compactNumber(statVal(ch, 'comments')) }}</span>
            </div>
            <div class="psd-stat-row" v-if="statVal(ch, 'shares') != null">
              <span class="psd-stat-label">分享</span>
              <span class="psd-stat-val">{{ compactNumber(statVal(ch, 'shares')) }}</span>
            </div>
            <div class="psd-stat-row" v-if="ch.stats.average_view_percentage != null">
              <span class="psd-stat-label">平均观看比</span>
              <span class="psd-stat-val">{{ formatPercent(ch.stats.average_view_percentage) }}</span>
            </div>
            <div class="psd-stat-row" v-if="ch.stats.average_view_duration != null">
              <span class="psd-stat-label">平均观看时长</span>
              <span class="psd-stat-val">{{ formatSeconds(ch.stats.average_view_duration) }}</span>
            </div>
            <div class="psd-stat-row" v-if="ch.stats.reach_count != null">
              <span class="psd-stat-label">触达人数</span>
              <span class="psd-stat-val">{{ compactNumber(ch.stats.reach_count) }}</span>
            </div>
            <div class="psd-stat-row" v-if="ch.stats.save_count != null">
              <span class="psd-stat-label">收藏</span>
              <span class="psd-stat-val">{{ compactNumber(ch.stats.save_count) }}</span>
            </div>
          </template>
          <div v-else class="psd-no-stats">暂无数据</div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchAccounts } from '../api/accounts'
import { exportPublicationStats, fetchPublicationStats, syncPublicationMetrics } from '../api/video_publications'

const exporting = ref(false)

async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    syncDateFiltersFromMode()
    const response = await exportPublicationStats({
      platform: filters.platform || undefined,
      account_id: filters.account_id || undefined,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
      keyword: filters.keyword || undefined,
    })
    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    // 优先用后端 Content-Disposition 里的文件名，fallback 用日期
    const cd = response.headers?.['content-disposition'] || ''
    const match = cd.match(/filename\*?=(?:UTF-8'')?([^;]+)/i)
    const filename = match ? decodeURIComponent(match[1].trim()) : `数据统计_${filters.date_from || formatYmd(new Date())}.csv`
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

const route = useRoute()

const PLATFORM_LABELS = {
  tiktok: 'TikTok',
  youtube: 'YouTube',
  instagram: 'Instagram',
}

const filters = reactive({
  platform: '',
  account_id: '',
  date_mode: 'week',
  single_date: '',
  date_range: [],
  date_from: '',
  date_to: '',
  keyword: '',
  sort_by: 'published_at',
  sort_order: 'desc',
  page: 1,
  page_size: 20,
})

const loading = ref(false)
const items = ref([])
const total = ref(0)
const accountOptions = ref([])

// 抽屉
const drawerVisible = ref(false)
const activeItem = ref(null)

function openDetail(item) {
  activeItem.value = item
  drawerVisible.value = true
}

// stats 字段兼容 view_count/views, like_count/likes 等双名
function statVal(ch, key) {
  const s = ch.stats
  if (!s) return null
  if (key === 'views') return s.views ?? s.view_count ?? null
  if (key === 'likes') return s.likes ?? s.like_count ?? null
  if (key === 'comments') return s.comments ?? s.comment_count ?? null
  if (key === 'shares') return s.shares ?? s.share_count ?? null
  return s[key] ?? null
}

function formatSeconds(val) {
  if (val == null) return '-'
  const n = Math.round(Number(val))
  if (n < 60) return `${n}s`
  return `${Math.floor(n / 60)}m${n % 60}s`
}

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / filters.page_size)))
const startIdx = computed(() => total.value === 0 ? 0 : (filters.page - 1) * filters.page_size + 1)
const endIdx = computed(() => Math.min(filters.page * filters.page_size, total.value))

const visiblePages = computed(() => {
  const n = totalPages.value
  const cur = filters.page
  if (n <= 7) return Array.from({ length: n }, (_, i) => i + 1)
  const pages = []
  pages.push(1)
  if (cur > 3) pages.push('...')
  for (let p = Math.max(2, cur - 1); p <= Math.min(n - 1, cur + 1); p++) pages.push(p)
  if (cur < n - 2) pages.push('...')
  pages.push(n)
  return pages
})

function formatYmd(date) {
  const y = date.getFullYear()
  const m = `${date.getMonth() + 1}`.padStart(2, '0')
  const d = `${date.getDate()}`.padStart(2, '0')
  return `${y}-${m}-${d}`
}

function shiftDays(base, days) {
  const next = new Date(base)
  next.setDate(next.getDate() + days)
  return next
}

function syncDateFiltersFromMode() {
  const today = new Date()
  const todayYmd = formatYmd(today)
  if (filters.date_mode === 'day') {
    const value = filters.single_date || todayYmd
    filters.single_date = value
    filters.date_from = value
    filters.date_to = value
    return
  }
  if (filters.date_mode === 'week') {
    filters.date_from = formatYmd(shiftDays(today, -6))
    filters.date_to = todayYmd
    return
  }
  if (filters.date_mode === 'month') {
    filters.date_from = formatYmd(shiftDays(today, -29))
    filters.date_to = todayYmd
    return
  }
  const range = Array.isArray(filters.date_range) ? filters.date_range : []
  filters.date_from = range[0] || ''
  filters.date_to = range[1] || ''
}

function handleDateModeChange() {
  if (filters.date_mode === 'day' && !filters.single_date) {
    filters.single_date = formatYmd(new Date())
  }
  if (filters.date_mode === 'custom' && (!Array.isArray(filters.date_range) || !filters.date_range.length)) {
    filters.date_range = ['', '']
  }
  syncDateFiltersFromMode()
}

function sortMark(field) {
  if (filters.sort_by !== field) return ''
  return filters.sort_order === 'asc' ? ' ↑' : ' ↓'
}

function toggleSort(field) {
  if (filters.sort_by === field) {
    filters.sort_order = filters.sort_order === 'asc' ? 'desc' : 'asc'
  } else {
    filters.sort_by = field
    filters.sort_order = 'desc'
  }
  filters.page = 1
  load()
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function compactNumber(value) {
  if (value == null || value === '') return '-'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function formatPercent(value) {
  if (value == null || value === '') return '-'
  return `${Number(value).toFixed(1)}%`
}

async function loadAccounts() {
  try {
    const response = await fetchAccounts({ page: 1, page_size: 200 })
    accountOptions.value = response?.items || []
  } catch (e) {
    console.error(e)
  }
}

async function load() {
  loading.value = true
  try {
    syncDateFiltersFromMode()
    const response = await fetchPublicationStats({
      platform: filters.platform || undefined,
      account_id: filters.account_id || undefined,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
      keyword: filters.keyword || undefined,
      sort_by: filters.sort_by,
      sort_order: filters.sort_order,
      page: filters.page,
      page_size: filters.page_size,
    })
    items.value = response?.items || []
    total.value = Number(response?.total || 0)
  } catch (e) {
    console.error(e)
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  filters.page = 1
  load()
}

function resetFilters() {
  filters.platform = ''
  filters.account_id = ''
  filters.date_mode = 'week'
  filters.single_date = ''
  filters.date_range = []
  filters.keyword = ''
  filters.sort_by = 'published_at'
  filters.sort_order = 'desc'
  filters.page = 1
  syncDateFiltersFromMode()
  load()
}

function changePage(page) {
  filters.page = page
  load()
}

const syncing = ref(false)

async function handleSyncMetrics() {
  if (syncing.value) return
  syncing.value = true
  try {
    syncDateFiltersFromMode()
    const result = await syncPublicationMetrics({
      platform: filters.platform || undefined,
      account_id: filters.account_id || undefined,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
    })
    ElMessage.success(result.message || '同步任务已提交')
    await load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '同步失败，请稍后重试')
  } finally {
    syncing.value = false
  }
}

function handleSizeChange() {
  filters.page = 1
  load()
}

onMounted(async () => {
  // 读取 query 参数（从 AI博主页跳转过来时携带）
  if (route.query.account_id) {
    filters.account_id = route.query.account_id
  }
  syncDateFiltersFromMode()
  await Promise.all([loadAccounts(), load()])
})
</script>

<style scoped>
.ps-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* Header */
.ps-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.ps-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.ps-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* Filter bar */
.ps-filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 12px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
}

.ps-btn {
  height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.ps-btn-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
}

.ps-btn-primary:hover {
  opacity: 0.9;
}

.ps-btn-secondary {
  background: #f1f5f9;
  color: #475569;
  border: 1px solid #e2e8f0;
}

.ps-btn-secondary:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.ps-btn-sync {
  background: #f0fdf4;
  color: #15803d;
  border: 1px solid #bbf7d0;
  display: inline-flex;
  align-items: center;
}

.ps-btn-export {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
  display: inline-flex;
  align-items: center;
}

.ps-btn-export:hover {
  background: #dbeafe;
}

.ps-btn-export:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ps-btn-sync:hover:not(:disabled) {
  background: #dcfce7;
  border-color: #86efac;
}

.ps-btn-sync:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ps-count-badge {
  margin-left: auto;
  font-size: 13px;
  color: #64748b;
  white-space: nowrap;
}

/* Table */
.ps-table-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
  margin-bottom: 16px;
}

.ps-empty {
  padding: 60px 0;
  text-align: center;
  color: #94a3b8;
  font-size: 14px;
}

.ps-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1200px;
}

.ps-th {
  padding: 11px 14px;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-align: left;
  background: #f8fafc;
  border-bottom: 1px solid #e8edf5;
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
}

.ps-th:first-child { border-top-left-radius: 14px; }
.ps-th:last-child  { border-top-right-radius: 14px; }

.ps-th-video  { width: 110px; }
.ps-th-title  { min-width: 220px; }
.ps-th-num    { text-align: right; }

.ps-sort-btn {
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
  font-weight: 700;
  color: #64748b;
  cursor: pointer;
}

.ps-sort-btn:hover { color: #0f172a; }

.ps-tr {
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.15s;
}

.ps-tr:last-child { border-bottom: none; }
.ps-tr:hover { background: #f8faff; }

.ps-td {
  padding: 10px 14px;
  vertical-align: middle;
  font-size: 13px;
  color: #334155;
}

.ps-td-video { width: 110px; }

.ps-td-num {
  text-align: right;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
}

.ps-td-date {
  white-space: nowrap;
  font-size: 12px;
  color: #64748b;
}

.ps-td-title { max-width: 260px; }

.ps-video {
  width: 72px;
  height: 102px;
  border-radius: 8px;
  object-fit: cover;
  background: #0f172a;
  display: block;
}
.ps-video:fullscreen,
.ps-video:-webkit-full-screen,
.ps-video:-moz-full-screen {
  width: auto;
  height: 100%;
  object-fit: contain;
}
.psd-video:fullscreen,
.psd-video:-webkit-full-screen,
.psd-video:-moz-full-screen {
  width: auto;
  height: 100%;
  object-fit: contain;
}

.ps-video-empty {
  display: grid;
  place-items: center;
  color: #cbd5e1;
  font-size: 11px;
}

.ps-title-main {
  font-weight: 700;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 240px;
}

.ps-title-sub {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ps-account-name {
  font-weight: 500;
  white-space: nowrap;
}

.ps-platforms {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.ps-platform-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  text-decoration: none;
  white-space: nowrap;
}

.ps-platform-tiktok    { background: #f1f5f9; color: #0f172a; }
.ps-platform-youtube   { background: #fef2f2; color: #b91c1c; }
.ps-platform-instagram { background: #fff7ed; color: #c2410c; }

.ps-dash { color: #94a3b8; }

/* Footer pagination */
.ps-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0 4px;
  border-top: 1px solid #f1f5f9;
}

.ps-pagination-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ps-count-text {
  font-size: 13px;
  color: #64748b;
}

.ps-simple-select {
  height: 30px;
  padding: 0 8px;
  border: 1px solid #e2e8f0;
  border-radius: 7px;
  font-size: 13px;
  color: #334155;
  background: #fff;
  cursor: pointer;
}

.ps-pagination {
  display: flex;
  align-items: center;
  gap: 4px;
}

.pg-btn {
  height: 30px;
  padding: 0 12px;
  border-radius: 7px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.pg-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pg-btn:not(:disabled):hover {
  border-color: #6366f1;
  color: #6366f1;
}

.pg-num.active {
  background: #6366f1;
  border-color: #6366f1;
  color: #fff;
}

.pg-ellipsis {
  padding: 0 4px;
  color: #94a3b8;
}

/* Clickable rows */
.ps-tr { cursor: pointer; }

/* Drawer */
:deep(.ps-drawer .el-drawer__body) {
  padding: 0 !important;
  overflow-y: auto !important;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.psd-wrap {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: #f8fafc;
  overflow-y: auto;
  padding-bottom: 24px;
}

.psd-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 14px;
  background: #fff;
  border-bottom: 1px solid #e8edf5;
  flex-shrink: 0;
}

.psd-header-info { flex: 1; min-width: 0; }

.psd-video-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.psd-account {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.psd-close {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border: none;
  background: #f1f5f9;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  transition: background 0.15s;
}
.psd-close:hover { background: #e2e8f0; color: #0f172a; }

.psd-video-wrap {
  padding: 16px 20px;
  background: #fff;
  border-bottom: 1px solid #e8edf5;
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

.psd-video {
  width: 100%;
  max-width: 180px;
  height: 320px;
  border-radius: 10px;
  object-fit: cover;
  background: #0f172a;
  display: block;
}

.psd-video-empty {
  display: grid;
  place-items: center;
  color: #94a3b8;
  font-size: 13px;
}

.psd-section-title {
  padding: 14px 20px 8px;
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.psd-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 0 16px 12px;
}

.psd-summary-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.psd-card-label {
  font-size: 11px;
  color: #64748b;
  line-height: 1.3;
}

.psd-card-value {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}

.psd-no-channels {
  padding: 16px 20px;
  color: #94a3b8;
  font-size: 13px;
}

.psd-channel-card {
  margin: 0 16px 10px;
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 12px;
  overflow: hidden;
}

.psd-ch-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  background: #fafbfc;
}

.psd-platform-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  flex-shrink: 0;
}

.psd-ch-name {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.psd-link {
  flex-shrink: 0;
  color: #6366f1;
  display: flex;
  align-items: center;
}
.psd-link:hover { color: #4f46e5; }

.psd-ch-stats {
  padding: 8px 14px;
}

.psd-stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 5px 0;
  border-bottom: 1px solid #f8fafc;
}
.psd-stat-row:last-child { border-bottom: none; }

.psd-stat-label {
  font-size: 12px;
  color: #64748b;
}

.psd-stat-val {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}

.psd-no-stats {
  padding: 8px 0;
  font-size: 12px;
  color: #94a3b8;
}

/* Element Plus overrides */
:deep(.el-radio-button__inner) {
  border-radius: 8px !important;
  border-left: 1px solid var(--el-border-color) !important;
  font-size: 12px;
  padding: 7px 12px;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  border-radius: 8px;
}
</style>
