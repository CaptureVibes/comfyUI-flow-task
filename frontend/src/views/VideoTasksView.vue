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
          @change="onDateChange"
          style="width: 180px;"
          :clearable="false"
        />
        <!-- Blogger search dropdown -->
        <div class="vt-blogger-search-wrap" v-click-outside="closeBloggerDropdown">
          <div class="vt-search-wrap" style="position:relative">
            <svg class="vt-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input
              v-model="bloggerSearchInput"
              class="vt-search-input"
              :placeholder="selectedBlogger ? selectedBlogger.label : '筛选AI博主...'"
              :class="{ 'has-selection': selectedBlogger }"
              @input="onBloggerSearchInput"
              @focus="bloggerDropdownOpen = true"
            />
            <button v-if="selectedBlogger || bloggerSearchInput" class="vt-search-clear" @click="clearBloggerFilter">✕</button>
          </div>
          <!-- Dropdown list -->
          <div v-if="bloggerDropdownOpen && filteredBloggerOptions.length" class="vt-blogger-dropdown">
            <div
              v-for="opt in filteredBloggerOptions"
              :key="opt.value"
              class="vt-blogger-option"
              :class="{ active: selectedBloggerId === opt.value }"
              @mousedown.prevent="selectBlogger(opt)"
            >
              <img v-if="opt.avatar" :src="opt.avatar" class="vt-blogger-opt-avatar" />
              <div v-else class="vt-blogger-opt-avatar-ph">{{ opt.label.charAt(0) }}</div>
              <div class="vt-blogger-opt-info">
                <span class="vt-blogger-opt-name">{{ opt.label }}</span>
                <span v-if="opt.handle" class="vt-blogger-opt-handle">@{{ opt.handle }}</span>
              </div>
            </div>
          </div>
          <div v-else-if="bloggerDropdownOpen && bloggerSearchInput && !filteredBloggerOptions.length" class="vt-blogger-dropdown">
            <div class="vt-blogger-no-result">无匹配博主</div>
          </div>
        </div>
        <button
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
          class="vt-btn vt-btn-warning"
          :class="{ 'is-loading': continuingScoring }"
          :disabled="continuingScoring || !(taskStats.scoring > 0)"
          @click="handleResumeScoring"
        >
          <svg v-if="!continuingScoring" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.13-3.36L23 10M1 14l5.36 4.36A9 9 0 0 0 20.49 15"/></svg>
          <svg v-else class="vt-spinner" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          一键继续AI打分
        </button>
        <button
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

    <!-- Stats row -->
    <div class="vt-stats">
      <div
        class="vt-stat-card"
        :class="{ 'vt-stat-active': activeFilter === 'pending' }"
        style="--stat-color: #64748b; --stat-bg: #f1f5f9;"
        @click="toggleFilter('pending')"
      >
        <div class="vt-stat-top">
          <span class="vt-stat-label">待处理</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        </div>
        <div class="vt-stat-value">{{ taskStats.pending || 0 }}</div>
        <div class="vt-stat-sub">pending</div>
      </div>
      <div
        class="vt-stat-card"
        :class="{ 'vt-stat-active': activeFilter === 'generating' }"
        style="--stat-color: #3b82f6; --stat-bg: #eff6ff;"
        @click="toggleFilter('generating')"
      >
        <div class="vt-stat-top">
          <span class="vt-stat-label">生成中</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
        </div>
        <div class="vt-stat-value">{{ taskStats.generating || 0 }}</div>
        <div class="vt-stat-sub">generating</div>
      </div>
      <div
        class="vt-stat-card"
        :class="{ 'vt-stat-active': activeFilter === 'scoring' }"
        style="--stat-color: #9333ea; --stat-bg: #fdf4ff;"
        @click="toggleFilter('scoring')"
      >
        <div class="vt-stat-top">
          <span class="vt-stat-label">AI打分中</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9333ea" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        </div>
        <div class="vt-stat-value">{{ taskStats.scoring || 0 }}</div>
        <div class="vt-stat-sub">scoring</div>
      </div>
      <div
        class="vt-stat-card"
        :class="{ 'vt-stat-active': activeFilter === 'reviewing' }"
        style="--stat-color: #854d0e; --stat-bg: #fef9c3;"
        @click="toggleFilter('reviewing')"
      >
        <div class="vt-stat-top">
          <span class="vt-stat-label">待决策</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#854d0e" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><circle cx="12" cy="17" r="0.5"/></svg>
        </div>
        <div class="vt-stat-value">{{ taskStats.reviewing || 0 }}</div>
        <div class="vt-stat-sub">reviewing</div>
      </div>
      <div
        class="vt-stat-card"
        :class="{ 'vt-stat-active': activeFilter === 'pending_publish' }"
        style="--stat-color: #d97706; --stat-bg: #fef3c7;"
        @click="toggleFilter('pending_publish')"
      >
        <div class="vt-stat-top">
          <span class="vt-stat-label">待发布</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        </div>
        <div class="vt-stat-value">{{ taskStats.pending_publish || 0 }}</div>
        <div class="vt-stat-sub">pending_publish</div>
      </div>
      <div
        class="vt-stat-card"
        :class="{ 'vt-stat-active': activeFilter === 'queued' }"
        style="--stat-color: #8b5cf6; --stat-bg: #ede9fe;"
        @click="toggleFilter('queued')"
      >
        <div class="vt-stat-top">
          <span class="vt-stat-label">队列中</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2"><rect x="2" y="7" width="20" height="10" rx="2"/><line x1="12" y1="17" x2="12" y2="21"/><line x1="8" y1="21" x2="16" y2="21"/></svg>
        </div>
        <div class="vt-stat-value">{{ taskStats.queued || 0 }}</div>
        <div class="vt-stat-sub">queued</div>
      </div>
      <div
        class="vt-stat-card"
        :class="{ 'vt-stat-active': activeFilter === 'published' }"
        style="--stat-color: #10b981; --stat-bg: #dcfce7;"
        @click="toggleFilter('published')"
      >
        <div class="vt-stat-top">
          <span class="vt-stat-label">已发布</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        </div>
        <div class="vt-stat-value">{{ taskStats.published || 0 }}</div>
        <div class="vt-stat-sub">published</div>
      </div>
      <div
        class="vt-stat-card"
        :class="{ 'vt-stat-active': activeFilter === 'abandoned' }"
        style="--stat-color: #ef4444; --stat-bg: #fee2e2;"
        @click="toggleFilter('abandoned')"
      >
        <div class="vt-stat-top">
          <span class="vt-stat-label">已废弃</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
        </div>
        <div class="vt-stat-value">{{ taskStats.abandoned || 0 }}</div>
        <div class="vt-stat-sub">abandoned</div>
      </div>
    </div>

    <div v-loading="loading" class="vt-content">
      <div v-if="!loading && filteredTasks.length === 0" class="vt-empty">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        <p>{{ activeFilter ? `暂无「${STATUS_LABELS[activeFilter]}」状态的任务` : '该日期下暂无任务' }}</p>
      </div>

      <div v-else class="vt-list">
        <div v-for="(task, idx) in filteredTasks" :key="task.id" class="vt-card">

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
            <!-- Go to account to publish -->
            <button
              v-if="task.status === 'pending_publish' && task.account_id"
              class="vt-publish-btn"
              @click="router.push(`/dashboard/accounts/${task.account_id}`)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              前往发布
            </button>
            <!-- Delete -->
            <button
              v-if="task.status === 'pending' || task.status === 'generating'"
              class="vt-delete-btn"
              @click="handleDelete(task)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
              删除
            </button>
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
              <div v-if="task.tags?.length" class="vt-tags">
                <span
                  v-for="tag in task.tags"
                  :key="tag.id"
                  class="vt-tag-chip"
                  :style="tag.color ? { '--vt-tag-color': tag.color } : {}"
                >
                  <span class="vt-tag-dot"></span>
                  {{ tag.name }}
                </span>
              </div>
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

    <!-- Footer pagination -->
    <div v-if="total > 0" class="vt-footer">
      <div class="vt-pagination-left">
        <span class="vt-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
        <select v-model="pageSize" @change="handleSizeChange(pageSize)" class="vt-simple-select">
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>
      </div>
      <div class="vt-pg">
        <button class="pg-btn" :disabled="currentPage <= 1" @click="onPageChange(currentPage - 1)">← 上一页</button>
        <template v-for="p in visiblePages" :key="p">
          <span v-if="p === '...'" class="pg-ellipsis">…</span>
          <button v-else class="pg-btn pg-num" :class="{ active: p === currentPage }" @click="onPageChange(p)">{{ p }}</button>
        </template>
        <button class="pg-btn" :disabled="endIdx >= total" @click="onPageChange(currentPage + 1)">下一页 →</button>
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

    <ConfirmDeleteDialog
      v-model="deleteDialogVisible"
      :title="`删除任务「${deleteTarget?.account_name || '未知账号'} · ${deleteTarget?.template_title || '未知模板'}」`"
      description="此操作将同时删除所有关联子任务，且不可恢复。"
      :loading="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchVideoTasks, uploadVideoTasks, fetchVideoTaskResults, fetchVideoTaskStats, deleteVideoTask, resumeVideoTaskScoring } from '../api/video_tasks.js'
import { fetchBloggers } from '../api/tiktok_bloggers.js'
import { isDuplicateRequestError } from '../api/http.js'
import ConfirmDeleteDialog from '../components/ConfirmDeleteDialog.vue'

// v-click-outside directive: close dropdown when clicking outside
const vClickOutside = {
  mounted(el, binding) {
    el._clickOutsideHandler = (e) => { if (!el.contains(e.target)) binding.value(e) }
    document.addEventListener('click', el._clickOutsideHandler)
  },
  unmounted(el) {
    document.removeEventListener('click', el._clickOutsideHandler)
  }
}

const STATUS_LABELS = {
  pending: '待处理',
  generating: '生成中',
  scoring: 'AI打分中',
  reviewing: '待决策',
  pending_publish: '待发布',
  queued: '队列中',
  publishing: '发布中',
  published: '已发布',
  publish_failed: '发布失败',
  abandoned: '已废弃',
}

const router = useRouter()
const today = new Date().toISOString().slice(0, 10)
const targetDate = ref(today)
const tasks = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const uploading = ref(false)
const fetchingResults = ref(false)
const continuingScoring = ref(false)
const taskStats = ref({})
const activeFilter = ref(null)

// Blogger searchable dropdown state
const bloggers = ref([])
const bloggerOptions = ref([])
const bloggerSearchInput = ref('')
const bloggerDropdownOpen = ref(false)
const selectedBlogger = ref(null)  // { value, label, handle, avatar }
const selectedBloggerId = ref(null)

const filteredBloggerOptions = computed(() => {
  const q = bloggerSearchInput.value.trim().toLowerCase()
  if (!q) return bloggerOptions.value
  return bloggerOptions.value.filter(o =>
    o.label.toLowerCase().includes(q) || (o.handle || '').toLowerCase().includes(q)
  )
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const startIdx = computed(() => total.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1)
const endIdx = computed(() => Math.min(currentPage.value * pageSize.value, total.value))
const jumpPage = ref(1)

const visiblePages = computed(() => {
  const n = totalPages.value
  const cur = currentPage.value
  if (n <= 7) return Array.from({ length: n }, (_, i) => i + 1)
  const pages = []
  pages.push(1)
  if (cur > 3) pages.push('...')
  for (let p = Math.max(2, cur - 1); p <= Math.min(n - 1, cur + 1); p++) pages.push(p)
  if (cur < n - 2) pages.push('...')
  pages.push(n)
  return pages
})

const filteredTasks = computed(() => tasks.value)

function toggleFilter(status) {
  if (activeFilter.value === status) {
    activeFilter.value = null
  } else {
    activeFilter.value = status
  }
  currentPage.value = 1
  loadTasks()
}

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
    const res = await fetchVideoTasks(targetDate.value, {
      tiktokBloggerId: selectedBloggerId.value,
      status: activeFilter.value || undefined,
      page: currentPage.value,
      pageSize: pageSize.value,
    })
    tasks.value = res.items
    total.value = res.total
    loadStats()
  } catch (e) {
    if (!isDuplicateRequestError(e)) {
      ElMessage.error('加载任务失败')
    }
  } finally {
    loading.value = false
  }
}

function onDateChange() {
  currentPage.value = 1
  loadTasks()
}

function onPageChange(page) {
  const target = Math.max(1, Math.min(page, totalPages.value))
  if (target === currentPage.value) return
  currentPage.value = target
  jumpPage.value = target
  loadTasks()
}

function handleSizeChange(val) {
  pageSize.value = val
  currentPage.value = 1
  jumpPage.value = 1
  loadTasks()
}

function doJump() {
  const p = parseInt(jumpPage.value)
  if (!isNaN(p)) onPageChange(p)
}

async function loadStats() {
  try {
    taskStats.value = await fetchVideoTaskStats(targetDate.value, { tiktokBloggerId: selectedBloggerId.value })
  } catch { /* ignore */ }
}

async function handleUpload() {
  if (tasks.value.length === 0) {
    ElMessage.warning('当前没有可上传的任务')
    return
  }
  uploading.value = true
  try {
    const res = await uploadVideoTasks(targetDate.value)
    ElMessage.success(res.message || '后台上传任务已启动')
    await pollUntilStatusChanges(['pending'], ['generating', 'scoring', 'pending_publish', 'published', 'abandoned'])
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

// 轮询直到所有符合 fromStatuses 的任务都离开这些状态（变为 toStatuses 之一）
// 最多轮询 30 次，每次间隔 2s
async function pollUntilStatusChanges(fromStatuses, toStatuses, maxAttempts = 30, intervalMs = 2000) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, intervalMs))
    await loadTasks()
    const stillWaiting = tasks.value.some(t => fromStatuses.includes(t.status))
    if (!stillWaiting) break
  }
}

async function handleFetchResults() {
  if (tasks.value.length === 0) {
    ElMessage.warning('当前没有可获取结果的任务')
    return
  }
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

async function handleResumeScoring() {
  if (!targetDate.value) return
  if (!(taskStats.value.scoring > 0)) {
    ElMessage.warning('当前没有 AI 打分中的任务')
    return
  }
  continuingScoring.value = true
  try {
    const res = await resumeVideoTaskScoring(targetDate.value)
    ElMessage.success(res.message || 'AI 打分继续任务已加入队列')
    await loadTasks()
    await loadStats()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '继续 AI 打分失败')
  } finally {
    continuingScoring.value = false
  }
}

const deleteDialogVisible = ref(false)
const deleteTarget = ref(null)
const deleting = ref(false)

function handleDelete(task) {
  deleteTarget.value = task
  deleteDialogVisible.value = true
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteVideoTask(deleteTarget.value.id)
    deleteDialogVisible.value = false
    deleteTarget.value = null
    ElMessage.success('任务已删除')
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

async function loadBloggers() {
  try {
    const res = await fetchBloggers()
    // API 返回的是 { items: [], total, page, page_size }
    const items = res.data?.items || []
    bloggers.value = items
    bloggerOptions.value = items.map(b => ({
      value: b.id,
      label: b.blogger_name || b.id,
      handle: b.blogger_handle,
      avatar: b.avatar_url
    }))
  } catch (e) {
    console.error('Failed to load bloggers:', e)
    bloggers.value = []
    bloggerOptions.value = []
  }
}

function onBloggerSearchInput() {
  bloggerDropdownOpen.value = true
}

function closeBloggerDropdown() {
  bloggerDropdownOpen.value = false
  // If nothing selected, clear input
  if (!selectedBlogger.value) bloggerSearchInput.value = ''
}

function selectBlogger(opt) {
  selectedBlogger.value = opt
  selectedBloggerId.value = opt.value
  bloggerSearchInput.value = ''
  bloggerDropdownOpen.value = false
  currentPage.value = 1
  loadTasks()
}

function clearBloggerFilter() {
  selectedBlogger.value = null
  selectedBloggerId.value = null
  bloggerSearchInput.value = ''
  bloggerDropdownOpen.value = false
  currentPage.value = 1
  loadTasks()
}

onMounted(() => {
  loadTasks()
  loadStats()
  loadBloggers()
})
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

.vt-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.vt-tag-chip {
  --vt-tag-color: #6366f1;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--vt-tag-color) 12%, white);
  border: 1px solid color-mix(in srgb, var(--vt-tag-color) 22%, white);
  color: color-mix(in srgb, var(--vt-tag-color) 78%, #111827);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.vt-tag-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--vt-tag-color);
  flex: 0 0 auto;
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

.vt-btn-warning {
  background: linear-gradient(135deg, #f59e0b, #ea580c);
  color: #fff;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.25);
}

.vt-btn-warning:hover:not(:disabled) {
  box-shadow: 0 6px 16px rgba(245, 158, 11, 0.35);
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
.vt-status-scoring         { background: #fdf4ff; color: #9333ea; }
.vt-status-reviewing       { background: #fef9c3; color: #854d0e; }
.vt-status-pending_publish { background: #fef3c7; color: #d97706; }
.vt-status-queued          { background: #ede9fe; color: #8b5cf6; }
.vt-status-publishing      { background: #ede9fe; color: #7c3aed; }
.vt-status-published       { background: #dcfce7; color: #15803d; }
.vt-status-abandoned       { background: #fee2e2; color: #b91c1c; }

.vt-publish-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 13px;
  color: #7c3aed;
  background: #ede9fe;
  border: none;
  cursor: pointer;
  padding: 5px 10px;
  border-radius: 6px;
  font-weight: 500;
  transition: background 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}
.vt-publish-btn:hover { background: #ddd6fe; }

.vt-delete-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 13px;
  color: #b91c1c;
  background: #fee2e2;
  border: none;
  cursor: pointer;
  padding: 5px 10px;
  border-radius: 6px;
  font-weight: 500;
  transition: background 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
}
.vt-delete-btn:hover { background: #fecaca; }

/* ── Stats row ── */
.vt-stats {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
  margin-bottom: 24px;
}

.vt-stat-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
  cursor: pointer;
  transition: all 0.2s ease;
}

.vt-stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,.08);
}

.vt-stat-active {
  background: var(--stat-bg) !important;
  border-color: var(--stat-color) !important;
  box-shadow: 0 0 0 2px var(--stat-bg), 0 0 0 4px var(--stat-color) !important;
}

.vt-stat-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.vt-stat-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #94a3b8;
}

.vt-stat-value {
  font-size: 30px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
  margin-bottom: 5px;
  letter-spacing: -0.03em;
}

.vt-stat-sub {
  font-size: 11px;
  color: #94a3b8;
  font-family: monospace;
}

/* Blogger search dropdown */
.vt-blogger-search-wrap {
  position: relative;
}

.vt-search-wrap {
  display: flex;
  align-items: center;
  position: relative;
  background: #fff;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  padding: 0 10px;
  height: 36px;
  transition: all 0.2s;
}

.vt-search-wrap:hover {
  border-color: #cbd5e1;
}

.vt-search-wrap:focus-within {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.vt-search-icon {
  color: #94a3b8;
  flex-shrink: 0;
  margin-right: 6px;
}

.vt-search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 13px;
  color: #0f172a;
  background: transparent;
  height: 100%;
  min-width: 0;
}

.vt-search-input::placeholder {
  color: #94a3b8;
}

.vt-search-input.has-selection {
  color: #6366f1;
  font-weight: 500;
}

.vt-search-input.has-selection::placeholder {
  color: #6366f1;
  font-weight: 500;
  opacity: 1;
}

.vt-search-clear {
  border: none;
  background: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  line-height: 1;
  margin-left: 4px;
}

.vt-search-clear:hover {
  color: #64748b;
}

.vt-blogger-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 220px;
  max-width: 300px;
  background: #fff;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  z-index: 1000;
  max-height: 300px;
  overflow-y: auto;
  padding: 4px;
}

.vt-blogger-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.1s;
  border-radius: 8px;
}

.vt-blogger-option:hover,
.vt-blogger-option.active {
  background: #f1f5f9;
}

.vt-blogger-opt-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.vt-blogger-opt-avatar-ph {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.vt-blogger-opt-info {
  flex: 1;
  min-width: 0;
}

.vt-blogger-opt-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vt-blogger-opt-handle {
  display: block;
  font-size: 11px;
  color: #94a3b8;
}

.vt-blogger-no-result {
  padding: 12px 16px;
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
}

.vt-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0 8px;
  border-top: 1px solid #f1f5f9;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
}

.vt-pagination-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.vt-count-text {
  font-size: 13px;
  color: #94a3b8;
}

.vt-simple-select {
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  padding: 0 4px;
}

.vt-simple-select:hover {
  color: #64748b;
}

.vt-pg {
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
  transition: all 0.15s;
}

.pg-btn:hover:not(:disabled) {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.pg-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

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

.pg-jump-input:focus {
  border-color: #6366f1;
}

.pg-jump-go {
  padding: 7px 12px;
}
</style>
