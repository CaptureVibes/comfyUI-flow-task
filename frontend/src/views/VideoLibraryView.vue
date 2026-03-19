<template>
  <div class="vl-page">
    <!-- ── Header ── -->
    <div class="vl-header">
      <h1 class="vl-title">视频库</h1>

      <div class="vl-header-actions">
        <el-button class="vl-tag-mgr-btn" @click="openTagManager">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px;flex-shrink:0"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
          标签管理
          <span v-if="tags.length" class="vl-tag-count">{{ tags.length }}</span>
        </el-button>
        <el-button class="vl-create-tpl-btn" :loading="batchCreatingTemplate" @click="handleBatchCreateTemplates">
          <svg v-if="!batchCreatingTemplate" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          一键生成模板
        </el-button>
        <el-button class="vl-dl-all-btn" :loading="downloadingAll" @click="handleDownloadAll">
          <svg v-if="!downloadingAll" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          下载全部视频
        </el-button>
        <el-button type="primary" class="vl-add-btn" @click="$router.push('/dashboard/video-library/new')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          添加视频
        </el-button>
      </div>
    </div>

    <!-- ── Stats row ── -->
    <div class="vl-stats">
      <div class="stat-card">
        <div class="stat-top">
          <span class="stat-label">总视频数</span>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.75"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z" fill="#6366f1" stroke="none"/></svg>
        </div>
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-sub">
          <span class="stat-green">+{{ stats.recent_count }}</span> 本周新增
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-top">
          <span class="stat-label">YOUTUBE</span>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="#ef4444"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.97C18.88 4 12 4 12 4s-6.88 0-8.59.45A2.78 2.78 0 0 0 1.46 6.42 29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58 2.78 2.78 0 0 0 1.95 1.97C5.12 20 12 20 12 20s6.88 0 8.59-.45a2.78 2.78 0 0 0 1.95-1.97A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02" fill="white"/></svg>
        </div>
        <div class="stat-value">{{ stats.youtube_count }}</div>
        <div class="stat-sub">YouTube 视频</div>
      </div>
      <div class="stat-card">
        <div class="stat-top">
          <span class="stat-label">TIKTOK</span>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="#000"><path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1-2.89-2.89 2.89 2.89 0 0 1 2.89-2.89c.28 0 .54.04.79.1V9.01a6.33 6.33 0 0 0-.79-.05 6.34 6.34 0 0 0-6.34 6.34 6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.33-6.34V8.69a8.18 8.18 0 0 0 4.78 1.52V6.76a4.86 4.86 0 0 1-1.01-.07z"/></svg>
        </div>
        <div class="stat-value">{{ stats.tiktok_count }}</div>
        <div class="stat-sub">TikTok 视频</div>
      </div>
      <div class="stat-card">
        <div class="stat-top">
          <span class="stat-label">本周新增</span>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="1.75"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        </div>
        <div class="stat-value">{{ stats.recent_count }}</div>
        <div class="stat-sub">最近 7 天</div>
      </div>
    </div>

    <!-- ── Filter bar ── -->
    <div class="vl-filterbar">
      <!-- Platform tabs -->
      <div class="vl-platform-tabs">
        <button
          v-for="tab in PLATFORM_TABS"
          :key="tab.value"
          class="vl-tab"
          :class="{ active: platform === tab.value }"
          @click="switchPlatform(tab.value)"
        >
          <span v-if="tab.value === 'youtube'" class="tab-icon-yt">▶</span>
          <span v-else-if="tab.value === 'tiktok'" class="tab-icon-tt">♪</span>
          <span v-else-if="tab.value === 'instagram'" class="tab-icon-ins">◈</span>
          {{ tab.label }}
        </button>
      </div>

      <!-- Blogger search (searchable dropdown) -->
      <div class="vl-blogger-search-wrap" v-click-outside="closeBloggerDropdown">
        <div class="vl-search-wrap" style="position:relative">
          <svg class="vl-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            v-model="bloggerSearchInput"
            class="vl-search-input"
            :placeholder="selectedBlogger ? selectedBlogger.label : '搜索博主...'"
            :class="{ 'has-selection': selectedBlogger }"
            @input="onBloggerSearchInput"
            @focus="bloggerDropdownOpen = true"
          />
          <button v-if="selectedBlogger || bloggerSearchInput" class="vl-search-clear" @click="clearBloggerFilter">✕</button>
        </div>
        <!-- Dropdown list -->
        <div v-if="bloggerDropdownOpen && filteredBloggerOptions.length" class="vl-blogger-dropdown">
          <div
            v-for="opt in filteredBloggerOptions"
            :key="opt.value"
            class="vl-blogger-option"
            :class="{ active: selectedBloggerId === opt.value }"
            @mousedown.prevent="selectBlogger(opt)"
          >
            <img v-if="opt.avatar" :src="opt.avatar" class="vl-blogger-opt-avatar" />
            <div v-else class="vl-blogger-opt-avatar-ph">{{ opt.label.charAt(0) }}</div>
            <div class="vl-blogger-opt-info">
              <span class="vl-blogger-opt-name">{{ opt.label }}</span>
              <span v-if="opt.handle" class="vl-blogger-opt-handle">@{{ opt.handle }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="bloggerDropdownOpen && bloggerSearchInput && !filteredBloggerOptions.length" class="vl-blogger-dropdown">
          <div class="vl-blogger-no-result">无匹配博主</div>
        </div>
      </div>

      <div class="vl-blogger-search-wrap" v-click-outside="closeTagDropdown">
        <div class="vl-search-wrap" style="position:relative">
          <svg class="vl-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            v-model="tagSearchInput"
            class="vl-search-input"
            :placeholder="selectedTagFilterSummary || '搜索标签...'"
            :class="{ 'has-selection': selectedTagFilterIds.length > 0 }"
            @input="onTagSearchInput"
            @focus="tagDropdownOpen = true"
          />
          <button v-if="selectedTagFilterIds.length || tagSearchInput" class="vl-search-clear" @click="clearTagFilter">✕</button>
        </div>
        <div v-if="tagDropdownOpen && filteredTagOptions.length" class="vl-blogger-dropdown">
          <div
            v-for="tag in filteredTagOptions"
            :key="tag.id"
            class="vl-blogger-option"
            :class="{ active: selectedTagFilterIds.includes(tag.id) }"
            @mousedown.prevent="toggleTagFilter(tag)"
          >
            <span class="vl-tag-opt-dot" :style="{ background: tag.color || '#94a3b8' }"></span>
            <div class="vl-blogger-opt-info">
              <span class="vl-blogger-opt-name">{{ tag.name }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="tagDropdownOpen && tagSearchInput && !filteredTagOptions.length" class="vl-blogger-dropdown">
          <div class="vl-blogger-no-result">无匹配标签</div>
        </div>
      </div>
    </div>

    <!-- ── Card grid ── -->
    <div v-loading="loading" class="vl-grid">
      <div v-for="item in items" :key="item.id" class="vc" @click="goToDetail(item)">
        <!-- Thumbnail -->
        <div class="vc-thumb" @click.stop="openPlayer(item)">
          <img
            v-if="item.thumbnail_url"
            :src="item.thumbnail_url"
            class="vc-thumb-img"
            :alt="item.video_title"
          />
          <div v-else class="vc-thumb-placeholder" :style="thumbGradient(item.platform)">
            <span class="vc-platform-icon">{{ platformEmoji(item.platform) }}</span>
          </div>
          <div class="vc-thumb-overlay">
            <div class="vc-play-btn">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="white"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </div>
          </div>
          <div class="vc-badge">{{ platformShort(item.platform) }}</div>
          <span v-if="isAdmin() && item.owner_username" class="vc-owner-badge">{{ item.owner_username }}</span>
        </div>

        <!-- Body -->
        <div class="vc-body">
          <div class="vc-title" :title="item.video_title">{{ item.video_title || '(无标题)' }}</div>
          <div class="vc-blogger">
            <span
              class="vc-at"
              :class="{ 'vc-at-linked': item.tiktok_blogger }"
              @click.stop="item.tiktok_blogger && selectBlogger({ value: item.tiktok_blogger.id, label: item.tiktok_blogger.blogger_name, handle: item.tiktok_blogger.blogger_handle, avatar: item.tiktok_blogger.avatar_url })"
            >@{{ (item.tiktok_blogger?.blogger_name || item.blogger_name) || '未知博主' }}</span>
            <span v-if="item.view_count != null" class="vc-views">· {{ formatCount(item.view_count) }} 次播放</span>
          </div>

          <!-- Tags + repeatable row -->
          <div v-if="item.tags?.length || item.repeatable" class="vc-tag-row">
            <span
              v-for="tag in item.tags"
              :key="tag.id"
              class="vc-tag"
              :style="tag.color ? { background: tag.color + '22', borderColor: tag.color, color: tag.color } : {}"
            >{{ tag.name }}</span>
            <span v-if="item.repeatable" class="vc-repeat-badge">可重复</span>
          </div>

          <!-- Download status bar -->
          <div v-if="item.download_status === 'downloading'" class="vc-dl-status vc-dl-ing">
            <span class="vc-dl-spin"></span> 下载上传中...
          </div>
          <div v-else-if="item.download_status === 'done'" class="vc-dl-status vc-dl-done">
            ✓ 已上传可播放
          </div>
          <div v-else-if="item.download_status === 'failed'" class="vc-dl-status vc-dl-fail">
            ✗ 下载失败
          </div>

          <div class="vc-footer">
            <span class="vc-date">{{ formatDate(item.publish_date || item.created_at) }}</span>
            <div class="vc-actions">
              <button
                v-if="!item.local_video_url && item.download_status !== 'downloading'"
                class="vc-btn vc-btn-dl"
                :class="{ loading: downloading === item.id }"
                @click.stop="handleDownload(item)"
              >{{ item.download_status === 'failed' ? '重试上传' : '下载上传' }}</button>
              <button
                v-if="templateMap[item.id]"
                class="vc-btn vc-btn-tpl vc-btn-tpl-exists"
                @click.stop="router.push(`/dashboard/video-ai-templates/${templateMap[item.id]}/edit`)"
              >跳转模板</button>
              <button
                v-else-if="item.download_status === 'done'"
                class="vc-btn vc-btn-tpl"
                :class="{ loading: creatingTemplate === item.id }"
                @click.stop="handleCreateTemplate(item)"
              >生成模板</button>
              <button
                class="vc-btn vc-btn-del"
                :class="{ loading: deleting === item.id }"
                @click.stop="handleDelete(item)"
              >删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Empty ── -->
    <el-empty v-if="!loading && items.length === 0" description="暂无视频，尝试更换筛选条件或点击「添加视频」" :image-size="80" />

    <!-- ── Footer ── -->
    <div v-if="total > 0" class="vl-footer">
      <div class="vl-pagination-left">
        <span class="vl-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
        <select v-model="pageSize" @change="handleSizeChange(pageSize)" class="vl-simple-select">
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="500">500</option>
        </select>
      </div>
      <div class="vl-pagination">
        <button class="pg-btn" :disabled="page <= 1" @click="goPage(page - 1)">← 上一页</button>
        <!-- Page number buttons -->
        <template v-for="p in visiblePages" :key="p">
          <span v-if="p === '...'" class="pg-ellipsis">…</span>
          <button v-else class="pg-btn pg-num" :class="{ active: p === page }" @click="goPage(p)">{{ p }}</button>
        </template>
        <button class="pg-btn" :disabled="endIdx >= total" @click="goPage(page + 1)">下一页 →</button>
        <!-- Jump to page -->
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
  </div>

  <!-- ── Video player dialog ── -->
  <el-dialog
    v-model="playerVisible"
    :title="playerItem?.video_title || '视频播放'"
    width="800px"
    align-center
    destroy-on-close
  >
    <div class="player-wrap">
      <video
        v-if="playerItem?.local_video_url || playerItem?.video_url"
        :src="playerItem.local_video_url || playerItem.video_url"
        controls
        autoplay
        class="player-video"
      />
      <div v-else class="player-nourl">
        <el-empty description="暂无可播放地址，请先点击「下载上传」" :image-size="80" />
        <el-link :href="playerItem?.source_url" target="_blank" type="primary">前往原始链接观看</el-link>
      </div>
    </div>
    <div v-if="playerItem" class="player-meta">
      <span>@{{ playerItem.blogger_name || '-' }}</span>
      <el-divider direction="vertical" />
      <span>{{ platformShort(playerItem.platform) }}</span>
      <el-divider direction="vertical" />
      <span v-if="playerItem.view_count != null">{{ formatCount(playerItem.view_count) }} 次播放</span>
    </div>
  </el-dialog>

  <!-- ── Tag Manager Dialog ── -->
  <el-dialog
    v-model="tagMgrVisible"
    title="标签管理"
    width="480px"
    align-center
    destroy-on-close
    class="tag-mgr-dialog"
  >
    <div class="tm-body">
      <!-- Tag list -->
      <div class="tm-list" v-if="tags.length">
        <div v-for="tag in tags" :key="tag.id" class="tm-item-wrap">
          <!-- Tag row: click to select -->
          <div
            class="tm-item"
            :class="{
              'tm-item-selected': selectedTagId === tag.id && editingTagId !== tag.id,
              'tm-item-editing': editingTagId === tag.id
            }"
            @click="selectTag(tag)"
          >
            <span
              class="tm-color-dot"
              :style="{ background: tag.color || '#94a3b8' }"
            ></span>
            <span
              class="tm-chip"
              :style="tag.color ? { background: tag.color + '22', color: tag.color, borderColor: tag.color + '55' } : {}"
            >{{ tag.name }}</span>
            <span class="tm-spacer"></span>
            <!-- Edit button (name only) -->
            <button
              class="tm-edit-btn"
              :class="{ active: editingTagId === tag.id }"
              @click.stop="editingTagId === tag.id ? cancelEditTag() : startEditTag(tag)"
              title="编辑标签名称"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <!-- Delete button -->
            <button
              class="tm-del-btn"
              :disabled="deletingTagId === tag.id"
              @click.stop="handleDeleteTag(tag)"
              title="删除标签"
            >
              <svg v-if="deletingTagId !== tag.id" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
              <span v-else class="tm-del-spin"></span>
            </button>
          </div>

          <!-- Inline edit panel (name only) -->
          <div v-if="editingTagId === tag.id" class="tm-edit-panel">
            <input
              v-model.trim="editingTagName"
              class="tm-input tm-edit-input"
              placeholder="标签名称"
              maxlength="50"
              @keyup.enter="saveEditTag(tag)"
            />
            <div class="tm-edit-actions">
              <button class="tm-cancel-btn" @click="cancelEditTag">取消</button>
              <button
                class="tm-save-btn"
                :disabled="!editingTagName || savingTagId === tag.id"
                @click="saveEditTag(tag)"
              >
                <span v-if="savingTagId === tag.id">保存中…</span>
                <span v-else>保存</span>
              </button>
            </div>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无标签，快来创建第一个吧" :image-size="60" style="padding: 16px 0" />

      <!-- Quick color picker: shows when a tag is selected -->
      <div v-if="selectedTagId" class="tm-quick-colors-wrap">
        <div class="tm-quick-colors-label">
          点击颜色即可修改「{{ tags.find(t => t.id === selectedTagId)?.name }}」的颜色
          <span v-if="updatingColorId" class="tm-updating-hint">更新中…</span>
        </div>
        <div class="tm-preset-colors">
          <span
            v-for="c in PRESET_COLORS"
            :key="c"
            class="tm-preset-dot"
            :class="{ selected: tags.find(t => t.id === selectedTagId)?.color === c }"
            :style="{ background: c }"
            @click="handleQuickColorChange(c)"
          ></span>
        </div>
      </div>

      <!-- Divider -->
      <div class="tm-divider"></div>

      <!-- Create new tag -->
      <div class="tm-create">
        <div class="tm-create-title">创建新标签</div>
        <div class="tm-create-row">
          <input
            v-model.trim="newTagName"
            class="tm-input"
            placeholder="标签名称"
            maxlength="50"
            @keyup.enter="handleCreateTag"
          />
          <span class="tm-color-preview" :style="{ background: newTagColor }"></span>
          <button
            class="tm-create-btn"
            :disabled="!newTagName || creatingTag"
            @click="handleCreateTag"
          >
            <span v-if="creatingTag">创建中…</span>
            <span v-else>+ 创建</span>
          </button>
        </div>
        <!-- Preset colors for new tag -->
        <div class="tm-preset-colors">
          <span
            v-for="c in PRESET_COLORS"
            :key="c"
            class="tm-preset-dot"
            :class="{ selected: newTagColor === c }"
            :style="{ background: c }"
            @click="newTagColor = c"
          ></span>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, onActivated, onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchVideoSources, fetchVideoSourceStats, deleteVideoSource, downloadVideoSource, downloadAllVideosZip } from '../api/video_sources'
import { batchCreateAndStartTemplates, createVideoAITemplate, startVideoAITemplate, fetchTemplatesByVideoSourceIds } from '../api/video_ai_templates'
import { fetchTags, createTag, updateTag, deleteTag } from '../api/tags'
import { fetchBloggers } from '../api/tiktok_bloggers'
import { isDuplicateRequestError } from '../api/http'
import { useAuth, getToken } from '../composables/useAuth'

const { isAdmin } = useAuth()
// v-click-outside directive: close dropdown when clicking outside
const vClickOutside = {
  mounted(el, binding) {
    el._clickOutsideHandler = (e) => { if (!el.contains(e.target)) binding.value(e) }
    document.addEventListener('click', el._clickOutsideHandler)
  },
  unmounted(el) { document.removeEventListener('click', el._clickOutsideHandler) },
}

const router = useRouter()
const route = useRoute()

const PLATFORM_TABS = [
  { label: '全部', value: '' },
  { label: 'TikTok', value: 'tiktok' },
  { label: 'YouTube', value: 'youtube' },
  { label: 'Instagram', value: 'instagram' },
]

const loading = ref(false)
const deleting = ref(null)
const downloading = ref(null)
const creatingTemplate = ref(null)
const items = ref([])
const total = ref(0)
const stats = ref({ total: 0, youtube_count: 0, tiktok_count: 0, recent_count: 0 })
const templateMap = ref({})
const playerVisible = ref(false)
const playerItem = ref(null)
const downloadingAll = ref(false)

// Tag manager state
const tagMgrVisible = ref(false)
const tags = ref([])
const newTagName = ref('')
const newTagColor = ref('#6366f1')
const creatingTag = ref(false)
const deletingTagId = ref(null)
const editingTagId = ref(null)
const editingTagName = ref('')
const editingTagColor = ref('')
const savingTagId = ref(null)
const selectedTagId = ref(null)
const updatingColorId = ref(null)
const PRESET_COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#ef4444', '#f59e0b', '#10b981', '#06b6d4', '#3b82f6', '#64748b']
const batchCreatingTemplate = ref(false)
let pollTimer = null
let searchTimer = null

// State synced with URL query
const page = ref(Number(route.query.page) || 1)
const pageSize = ref(Number(route.query.page_size) || 20)
const platform = ref(route.query.platform || '')
const bloggerSearch = ref('')  // kept for URL compat but unused
const selectedBloggerId = ref(route.query.tiktok_blogger_id || null)
const selectedTagFilterIds = ref(
  String(route.query.tag_ids || '')
    .split(',')
    .map(v => v.trim())
    .filter(Boolean)
)
const bloggerOptions = ref([])
// Blogger searchable dropdown state
const bloggerSearchInput = ref('')
const bloggerDropdownOpen = ref(false)
const selectedBlogger = ref(null)  // { value, label, handle, avatar }
const filteredBloggerOptions = computed(() => {
  const q = bloggerSearchInput.value.trim().toLowerCase()
  if (!q) return bloggerOptions.value
  return bloggerOptions.value.filter(o =>
    o.label.toLowerCase().includes(q) || (o.handle || '').toLowerCase().includes(q)
  )
})
const tagSearchInput = ref('')
const tagDropdownOpen = ref(false)
const selectedTagFilterSummary = computed(() => {
  if (!selectedTagFilterIds.value.length) return ''
  const names = tags.value
    .filter(t => selectedTagFilterIds.value.includes(t.id))
    .map(t => t.name)
    .filter(Boolean)
  if (!names.length) return `${selectedTagFilterIds.value.length} 个标签`
  if (names.length <= 2) return names.join('、')
  return `${names[0]}、${names[1]} 等 ${names.length} 个标签`
})
const filteredTagOptions = computed(() => {
  const q = tagSearchInput.value.trim().toLowerCase()
  if (!q) return tags.value
  return tags.value.filter(t => (t.name || '').toLowerCase().includes(q))
})
const jumpPage = ref(page.value)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const startIdx = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const endIdx = computed(() => Math.min(page.value * pageSize.value, total.value))

// Generate visible page numbers with ellipsis
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

const PLATFORM_COLORS = {
  youtube: 'linear-gradient(135deg, #ff0000 0%, #cc0000 100%)',
  tiktok: 'linear-gradient(135deg, #010101 0%, #69c9d0 100%)',
  instagram: 'linear-gradient(135deg, #833ab4 0%, #fd1d1d 50%, #fcb045 100%)',
}
const PLATFORM_EMOJIS = { youtube: '▶', tiktok: '♪', instagram: '◈' }
const PLATFORM_SHORTS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }
const DEFAULT_GRAD = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'

function thumbGradient(p) { return { background: PLATFORM_COLORS[p] || DEFAULT_GRAD } }
function platformEmoji(p) { return PLATFORM_EMOJIS[p] || '🎬' }
function platformShort(p) { return PLATFORM_SHORTS[p] || (p || '其他') }

function formatCount(n) {
  if (n == null) return '-'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

function syncUrl() {
  const query = {}
  if (page.value > 1) query.page = String(page.value)
  if (pageSize.value !== 20) query.page_size = String(pageSize.value)
  if (platform.value) query.platform = platform.value
  if (selectedBloggerId.value) query.tiktok_blogger_id = selectedBloggerId.value
  if (selectedTagFilterIds.value.length) query.tag_ids = selectedTagFilterIds.value.join(',')
  router.replace({ query })
}

async function loadStats() {
  try {
    const params = {}
    if (platform.value) params.platform = platform.value
    if (selectedBloggerId.value) params.tiktok_blogger_id = selectedBloggerId.value
    if (selectedTagFilterIds.value.length) params.tag_ids = selectedTagFilterIds.value.join(',')
    stats.value = await fetchVideoSourceStats(params)
  } catch { /* ignore */ }
}

async function loadData(silent = false) {
  if (!silent) loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (platform.value) params.platform = platform.value
    if (selectedBloggerId.value) {
      params.tiktok_blogger_id = selectedBloggerId.value
    }
    if (selectedTagFilterIds.value.length) {
      params.tag_ids = selectedTagFilterIds.value.join(',')
    }

    const data = await fetchVideoSources(params)
    items.value = data.items || []
    total.value = data.total || 0
    schedulePollIfNeeded()
    const ids = items.value.map(i => i.id)
    if (ids.length) {
      templateMap.value = await fetchTemplatesByVideoSourceIds(ids)
    }
  } catch (err) {
    if (isDuplicateRequestError(err)) return
    if (!silent) ElMessage.error(err?.response?.data?.detail || '加载失败')
  } finally {
    if (!silent) loading.value = false
  }
}

function switchPlatform(val) {
  platform.value = val
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
  loadStats()
}

function onSearchInput() {
  // kept for any legacy call, now unused
}

function onBloggerSearchInput() {
  bloggerDropdownOpen.value = true
}

function closeBloggerDropdown() {
  bloggerDropdownOpen.value = false
  // If nothing selected, clear input
  if (!selectedBlogger.value) bloggerSearchInput.value = ''
}

function onTagSearchInput() {
  tagDropdownOpen.value = true
}

function closeTagDropdown() {
  tagDropdownOpen.value = false
  if (!selectedTagFilterIds.value.length) tagSearchInput.value = ''
}

function selectBlogger(opt) {
  selectedBlogger.value = opt
  selectedBloggerId.value = opt.value
  bloggerSearchInput.value = ''
  bloggerDropdownOpen.value = false
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
  loadStats()
}

function toggleTagFilter(tag) {
  const exists = selectedTagFilterIds.value.includes(tag.id)
  if (exists) {
    selectedTagFilterIds.value = selectedTagFilterIds.value.filter(id => id !== tag.id)
  } else {
    selectedTagFilterIds.value = [...selectedTagFilterIds.value, tag.id]
  }
  tagSearchInput.value = ''
  tagDropdownOpen.value = true
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
  loadStats()
}

function clearSearch() {
  bloggerSearch.value = ''
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
  loadStats()
}

async function handleCreateTemplate(item) {
  creatingTemplate.value = item.id
  try {
    const tpl = await createVideoAITemplate({
      title: item.video_title || item.blogger_name || '新模板',
      description: '',
      video_source_id: item.id,
    })
    await startVideoAITemplate(tpl.id)
    templateMap.value = { ...templateMap.value, [item.id]: tpl.id }
    router.push(`/dashboard/video-ai-templates/${tpl.id}/edit`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '创建模板失败')
  } finally {
    creatingTemplate.value = null
  }
}

function schedulePollIfNeeded() {
  clearTimeout(pollTimer)
  const hasDownloading = items.value.some(i => i.download_status === 'downloading')
  if (hasDownloading) {
    pollTimer = setTimeout(() => loadData(true), 3000)
  }
}

function goPage(p) {
  const target = Math.max(1, Math.min(p, totalPages.value))
  if (target === page.value) return
  page.value = target
  jumpPage.value = target
  syncUrl()
  loadData()
}

function handleSizeChange(val) {
  pageSize.value = val
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
  loadStats()
}

function doJump() {
  const p = parseInt(jumpPage.value)
  if (!isNaN(p)) goPage(p)
}

function openPlayer(item) {
  playerItem.value = item
  playerVisible.value = true
}

function goToDetail(item) {
  syncUrl()
  router.push(`/dashboard/video-library/${item.id}`)
}

async function handleDownload(item) {
  downloading.value = item.id
  item.download_status = 'downloading'
  try {
    await downloadVideoSource(item.id)
    ElMessage.success('已开始下载，稍后自动更新状态')
    schedulePollIfNeeded()
  } catch (err) {
    item.download_status = null
    ElMessage.error(err?.response?.data?.detail || '启动下载失败')
  } finally {
    downloading.value = null
  }
}

async function handleDelete(item) {
  try {
    await ElMessageBox.confirm(
      `确定删除视频「${item.video_title || '无标题'}」？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        customClass: 'premium-delete-dialog',
      }
    )
  } catch { return }

  deleting.value = item.id
  try {
    await deleteVideoSource(item.id)
    ElMessage.success('已删除')
    await Promise.all([loadData(), loadStats()])
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = null
  }
}

async function handleBatchCreateTemplates() {
  batchCreatingTemplate.value = true
  try {
    await batchCreateAndStartTemplates()
    ElMessage.success('已触发批量生成模板，后台处理中…')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '批量创建模板失败')
  } finally {
    batchCreatingTemplate.value = false
  }
}

async function handleDownloadAll() {
  downloadingAll.value = true
  ElMessage.info('正在打包视频，请稍候…')
  try {
    const blob = await downloadAllVideosZip(getToken())
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = 'videos.zip'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(blobUrl), 10000)
    ElMessage.success('打包完成，已开始下载')
  } catch (err) {
    ElMessage.error(err?.message || '下载失败')
  } finally {
    downloadingAll.value = false
  }
}

async function loadTags() {
  try {
    tags.value = await fetchTags()
    if (selectedTagFilterIds.value.length) {
      selectedTagFilterIds.value = selectedTagFilterIds.value.filter(id => tags.value.some(t => t.id === id))
    }
    if (!selectedTagFilterIds.value.length) {
      tagSearchInput.value = ''
    }
  } catch { /* ignore */ }
}

async function openTagManager() {
  selectedTagId.value = null
  editingTagId.value = null
  tagMgrVisible.value = true
  await loadTags()
}

async function handleCreateTag() {
  if (!newTagName.value || creatingTag.value) return
  creatingTag.value = true
  try {
    await createTag({ name: newTagName.value, color: newTagColor.value })
    newTagName.value = ''
    newTagColor.value = '#6366f1'
    await loadTags()
    ElMessage.success('标签创建成功')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '创建失败')
  } finally {
    creatingTag.value = false
  }
}

function selectTag(tag) {
  if (editingTagId.value === tag.id) return
  selectedTagId.value = selectedTagId.value === tag.id ? null : tag.id
}

async function handleQuickColorChange(color) {
  if (!selectedTagId.value || updatingColorId.value) return
  const tag = tags.value.find(t => t.id === selectedTagId.value)
  if (!tag || tag.color === color) return
  updatingColorId.value = tag.id
  try {
    await updateTag(tag.id, { name: tag.name, color })
    tag.color = color
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '颜色更新失败')
  } finally {
    updatingColorId.value = null
  }
}

function startEditTag(tag) {
  selectedTagId.value = null
  editingTagId.value = tag.id
  editingTagName.value = tag.name
  editingTagColor.value = tag.color || '#6366f1'
}

function cancelEditTag() {
  editingTagId.value = null
  editingTagName.value = ''
  editingTagColor.value = ''
}

async function saveEditTag(tag) {
  if (!editingTagName.value || savingTagId.value) return
  savingTagId.value = tag.id
  try {
    await updateTag(tag.id, { name: editingTagName.value, color: tag.color })
    tag.name = editingTagName.value
    cancelEditTag()
    ElMessage.success('标签已更新')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '更新失败')
  } finally {
    savingTagId.value = null
  }
}

async function handleDeleteTag(tag) {
  try {
    await ElMessageBox.confirm(
      `确定删除标签「${tag.name}」？已使用该标签的视频将自动解除关联。`,
      '删除标签',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  deletingTagId.value = tag.id
  try {
    await deleteTag(tag.id)
    await loadTags()
    ElMessage.success('已删除')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    deletingTagId.value = null
  }
}

async function loadBloggers() {
  try {
    const res = await fetchBloggers({ page: 1, page_size: 200 })
    bloggerOptions.value = (res.data.items || []).map(b => ({
      value: b.id,
      label: b.blogger_name,
      handle: b.blogger_handle,
      avatar: b.avatar_url,
    }))
    // Restore selectedBlogger from URL param
    if (selectedBloggerId.value) {
      const found = bloggerOptions.value.find(o => o.value === selectedBloggerId.value)
      if (found) selectedBlogger.value = found
    }
  } catch { /* ignore */ }
}

function clearBloggerFilter() {
  selectedBlogger.value = null
  selectedBloggerId.value = null
  bloggerSearchInput.value = ''
  bloggerDropdownOpen.value = false
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
  loadStats()
}

function clearTagFilter() {
  selectedTagFilterIds.value = []
  tagSearchInput.value = ''
  tagDropdownOpen.value = false
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
  loadStats()
}

onMounted(() => {
  loadStats()
  loadData()
  loadTags()
  loadBloggers()
})

// When navigating back from detail page (keep-alive scenario),
// re-sync state from URL and reload data
onActivated(() => {
  const q = route.query
  page.value = Number(q.page) || 1
  pageSize.value = Number(q.page_size) || 20
  platform.value = q.platform || ''
  selectedBloggerId.value = q.tiktok_blogger_id || null
  selectedTagFilterIds.value = String(q.tag_ids || '')
    .split(',')
    .map(v => v.trim())
    .filter(Boolean)
  if (!selectedBloggerId.value) selectedBlogger.value = null
  jumpPage.value = page.value
  loadStats()
  loadData()
  loadTags()
})

onUnmounted(() => {
  clearTimeout(pollTimer)
  clearTimeout(searchTimer)
})
</script>

<style scoped>
/* ── Page layout ── */
.vl-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
}

.vl-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}

.vl-title {
  font-size: 26px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.03em;
  margin: 0;
}

.vl-tag-mgr-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  border: 1px solid #e2e8f0;
  color: #475569;
  background: #fff;
}

.vl-tag-mgr-btn:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.vl-tag-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  margin-left: 6px;
  background: #6366f1;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  border-radius: 9px;
}

/* ── Tag Manager Dialog ── */
.tm-body {
  padding: 0;
}

/* Tag list */
.tm-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 360px;
  overflow-y: auto;
  margin-bottom: 12px;
  padding-right: 2px;
}

.tm-list::-webkit-scrollbar { width: 4px; }
.tm-list::-webkit-scrollbar-track { background: transparent; }
.tm-list::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 4px; }

.tm-item-wrap {
  display: flex;
  flex-direction: column;
  border-radius: 10px;
}

.tm-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1.5px solid #f1f5f9;
  transition: all 0.15s;
  cursor: pointer;
}

.tm-item:hover {
  background: #f0f4ff;
  border-color: #c7d2fe;
}

.tm-item:not(.tm-item-editing) { cursor: pointer; }

.tm-item.tm-item-selected {
  background: #eef2ff;
  border-color: #a5b4fc;
}

.tm-item.tm-item-editing {
  background: #eef2ff;
  border-color: #a5b4fc;
  border-radius: 10px 10px 0 0;
  border-bottom: none;
}

/* Color dot */
.tm-color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 2px rgba(255,255,255,0.8), 0 0 0 3px rgba(0,0,0,0.1);
}

/* Tag chip */
.tm-chip {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tm-spacer { flex: 1; }

/* Icon buttons */
.tm-edit-btn,
.tm-del-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 7px;
  border: none;
  background: transparent;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}

.tm-edit-btn:hover,
.tm-edit-btn.active {
  background: #eef2ff;
  color: #6366f1;
}

.tm-del-btn:hover:not(:disabled) {
  background: #fee2e2;
  color: #ef4444;
}

.tm-del-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Inline edit panel */
.tm-edit-panel {
  background: #f0f3ff;
  border: 1.5px solid #a5b4fc;
  border-top: none;
  border-radius: 0 0 10px 10px;
  padding: 8px 12px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tm-edit-input {
  width: 100%;
  box-sizing: border-box;
  height: 34px !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  color: #334155 !important;
  padding: 0 10px !important;
  border-radius: 7px !important;
  border: 1px solid #c7d2fe !important;
  background: rgba(255, 255, 255, 0.85) !important;
  box-shadow: inset 0 1px 2px rgba(99, 102, 241, 0.06) !important;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s !important;
}

.tm-edit-input:focus {
  border-color: #6366f1 !important;
  background: #fff !important;
  box-shadow: inset 0 1px 2px rgba(99, 102, 241, 0.08), 0 0 0 2px rgba(99, 102, 241, 0.12) !important;
  outline: none;
}

.tm-edit-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
}

.tm-cancel-btn {
  height: 30px;
  padding: 0 14px;
  border-radius: 7px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.tm-cancel-btn:hover { background: #f1f5f9; }

.tm-save-btn {
  height: 30px;
  padding: 0 16px;
  border-radius: 7px;
  border: none;
  background: #6366f1;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.tm-save-btn:hover:not(:disabled) { background: #4f46e5; }
.tm-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Quick color picker */
.tm-quick-colors-wrap {
  margin-bottom: 12px;
  padding: 12px 14px;
  background: #f8faff;
  border: 1.5px solid #e0e7ff;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tm-quick-colors-label {
  font-size: 12px;
  color: #6366f1;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tm-updating-hint {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 400;
}

/* Divider */
.tm-divider {
  height: 1px;
  background: #f1f5f9;
  margin: 4px 0 16px;
}

/* Create section */
.tm-create {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tm-create-title {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  letter-spacing: -0.01em;
}

.tm-create-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tm-input {
  flex: 1;
  height: 40px;
  padding: 0 14px;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  font-size: 14px;
  color: #334155;
  background: #f8fafc;
  outline: none;
  transition: border-color 0.15s, background 0.15s;
}

.tm-input:focus {
  border-color: #6366f1;
  background: #fff;
}

.tm-color-preview {
  display: block;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: 2px solid #e2e8f0;
  flex-shrink: 0;
  transition: border-color 0.15s;
}

.tm-create-btn {
  height: 40px;
  padding: 0 18px;
  border-radius: 10px;
  border: none;
  background: #6366f1;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.tm-create-btn:hover:not(:disabled) { background: #4f46e5; }
.tm-create-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Color preset dots */
.tm-preset-colors {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.tm-preset-dot {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  cursor: pointer;
  border: 2.5px solid transparent;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.tm-preset-dot:hover {
  transform: scale(1.18);
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.tm-preset-dot.selected {
  border-color: #1e293b;
  transform: scale(1.15);
  box-shadow: 0 0 0 3px rgba(30,41,59,0.15);
}

/* Spinner */
.tm-del-spin {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid #fca5a5;
  border-top-color: #ef4444;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.vl-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.vl-dl-all-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  border: 1px solid #e2e8f0;
  color: #475569;
  background: #fff;
}

.vl-dl-all-btn:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.vl-create-tpl-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  border: 1px solid #a7f3d0;
  color: #059669;
  background: #ecfdf5;
}

.vl-create-tpl-btn:hover {
  background: #d1fae5;
  border-color: #34d399;
}

.vl-add-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
}

/* ── Stats ── */
.vl-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
}

.stat-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.stat-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #94a3b8;
}

.stat-value {
  font-size: 32px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
  margin-bottom: 6px;
  letter-spacing: -0.03em;
}

.stat-sub {
  font-size: 12px;
  color: #94a3b8;
}

.stat-green {
  color: #10b981;
  font-weight: 600;
}

/* ── Filter bar ── */
.vl-filterbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.vl-platform-tabs {
  display: flex;
  gap: 6px;
  background: #f1f5f9;
  border-radius: 12px;
  padding: 4px;
}

.vl-tab {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: 9px;
  border: none;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.vl-tab:hover {
  color: #334155;
  background: #e2e8f0;
}

.vl-tab.active {
  background: #fff;
  color: #4f46e5;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}

.tab-icon-yt { color: #ef4444; }
.tab-icon-tt { color: #000; }
.tab-icon-ins { color: #c026d3; }

.vl-search-wrap {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1;
  max-width: 260px;
}

.vl-search-icon {
  position: absolute;
  left: 10px;
  color: #94a3b8;
  pointer-events: none;
}

.vl-search-input {
  width: 100%;
  height: 36px;
  padding: 0 32px 0 32px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 13px;
  color: #334155;
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
}

.vl-search-input:focus {
  border-color: #6366f1;
}

.vl-search-input::placeholder {
  color: #cbd5e1;
}

.vl-search-clear {
  position: absolute;
  right: 10px;
  font-size: 11px;
  color: #94a3b8;
  background: none;
  border: none;
  cursor: pointer;
  line-height: 1;
  padding: 2px;
}

.vl-search-clear:hover {
  color: #64748b;
}

/* ── Card grid ── */
.vl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 28px;
}

/* ── Video card ── */
.vc {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,.05);
  transition: box-shadow 0.2s, transform 0.2s;
  cursor: pointer;
}

.vc:hover {
  box-shadow: 0 8px 24px rgba(0,0,0,.1);
  transform: translateY(-2px);
}

/* Thumbnail */
.vc-thumb {
  position: relative;
  aspect-ratio: 16/9;
  cursor: pointer;
  overflow: hidden;
  background: #0f172a;
}

.vc-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.3s;
}

.vc:hover .vc-thumb-img {
  transform: scale(1.04);
}

.vc-thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vc-platform-icon {
  font-size: 36px;
  opacity: 0.5;
}

.vc-thumb-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.vc:hover .vc-thumb-overlay {
  background: rgba(0,0,0,0.35);
}

.vc-play-btn {
  opacity: 0;
  transform: scale(0.8);
  transition: opacity 0.2s, transform 0.2s;
  background: rgba(255,255,255,0.15);
  border-radius: 50%;
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}

.vc:hover .vc-play-btn {
  opacity: 1;
  transform: scale(1);
}

.vc-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(0,0,0,0.55);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  backdrop-filter: blur(4px);
  letter-spacing: .03em;
}

.vc-owner-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  background: #f3e8ff;
  color: #9333ea;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  letter-spacing: .03em;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Card body */
.vc-body {
  padding: 14px 16px 12px;
}

.vc-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
  min-height: 2.8em;
}

.vc-blogger {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vc-at {
  font-weight: 600;
  color: #475569;
}

.vc-views {
  color: #94a3b8;
}

.vc-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #f1f5f9;
  padding-top: 10px;
  margin-top: 4px;
}

.vc-date {
  font-size: 11px;
  color: #94a3b8;
}

.vc-actions {
  display: flex;
  gap: 6px;
}

.vc-btn {
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 7px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
}

.vc-btn:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.vc-btn-del {
  border-color: #fecaca;
  color: #dc2626;
  background: #fef2f2;
}

.vc-btn-del:hover {
  border-color: #fca5a5;
  color: #b91c1c;
  background: #fee2e2;
}

.vc-btn-dl:hover {
  border-color: #0ea5e9;
  color: #0ea5e9;
  background: #f0f9ff;
}

.vc-btn-tpl {
  border-color: #c7d2fe;
  color: #4f46e5;
  background: #eef2ff;
}

.vc-btn-tpl:hover {
  border-color: #6366f1;
  color: #4338ca;
  background: #e0e7ff;
}

.vc-btn-tpl-exists {
  border-color: #fed7aa;
  color: #c2410c;
  background: #fff7ed;
}

.vc-btn-tpl-exists:hover {
  border-color: #fb923c;
  color: #9a3412;
  background: #ffedd5;
}

/* Download status bar */
.vc-dl-status {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 6px;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.vc-dl-ing {
  background: #fef9c3;
  color: #a16207;
}

.vc-dl-done {
  background: #dcfce7;
  color: #166534;
}

.vc-dl-fail {
  background: #fee2e2;
  color: #991b1b;
}

.vc-dl-spin {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid #a16207;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.vc-btn.loading {
  opacity: 0.5;
  pointer-events: none;
}

/* ── Footer ── */
.vl-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0 8px;
  border-top: 1px solid #f1f5f9;
  flex-wrap: wrap;
  gap: 12px;
}

.vl-pagination-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.vl-count-text {
  font-size: 13px;
  color: #94a3b8;
}

.vl-simple-select {
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  padding: 0 4px;
}

.vl-simple-select:hover {
  color: #64748b;
}

.vl-pagination {
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

.pg-jump-input::-webkit-inner-spin-button,
.pg-jump-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
}

.pg-jump-go {
  padding: 7px 12px;
}

/* ── Player dialog ── */
.player-wrap {
  background: #000;
  border-radius: 10px;
  overflow: hidden;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.player-video {
  width: 100%;
  max-height: 460px;
  display: block;
}

.player-nourl {
  padding: 40px;
  text-align: center;
  background: #fff;
  width: 100%;
}

.player-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #64748b;
  margin-top: 14px;
  padding: 0 2px;
}

/* ── Animation ── */
@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Tags + repeatable on card */
.vc-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin: 6px 0 4px;
}

.vc-tag {
  display: inline-block;
  padding: 2px 8px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
  line-height: 1.6;
}

.vc-repeat-badge {
  display: inline-block;
  padding: 2px 8px;
  background: #ecfdf5;
  border: 1px solid #6ee7b7;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
  color: #059669;
  line-height: 1.6;
}

/* Responsive */
@media (max-width: 1200px) {
  .vl-stats { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .vl-page { padding: 16px; }
  .vl-stats { grid-template-columns: repeat(2, 1fr); }
  .vl-grid { grid-template-columns: 1fr 1fr; gap: 12px; }
  .vl-filterbar { gap: 10px; }
}

/* Blogger selector */
.vl-blogger-search-wrap {
  position: relative;
}
.vl-search-input.has-selection {
  color: #6366f1;
  font-weight: 500;
}
.vl-search-input.has-selection::placeholder {
  color: #6366f1;
  font-weight: 500;
  opacity: 1;
}
.vl-blogger-dropdown {
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
  overflow: hidden;
  max-height: 260px;
  overflow-y: auto;
}
.vl-blogger-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.1s;
}
.vl-blogger-option:hover, .vl-blogger-option.active {
  background: #f1f5f9;
}
.vl-blogger-opt-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}
.vl-blogger-opt-avatar-ph {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #6366f1;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.vl-tag-opt-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  flex-shrink: 0;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.08);
}
.vl-blogger-opt-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.vl-blogger-opt-name {
  font-size: 13px;
  font-weight: 500;
  color: #1e1e2e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.vl-blogger-opt-handle {
  font-size: 11px;
  color: #94a3b8;
}
.vl-blogger-no-result {
  padding: 12px 16px;
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
}

/* Linked blogger name in card is clickable */
.vc-at-linked {
  cursor: pointer;
  color: #6366f1;
  text-decoration: underline dotted;
}
.vc-at-linked:hover { color: #4f46e5; }
</style>
