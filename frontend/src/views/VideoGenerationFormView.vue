<template>
  <div class="vgf-page" v-loading="loading">
    <!-- Header -->
    <div class="vgf-header">
      <div class="vgf-header-left">
        <h1 class="vgf-title">视频生成工厂</h1>
        <div class="vgf-subtitle">合并AI博主与AI分析，生成最终的高质量视频</div>
      </div>
      <div class="vgf-header-actions">
        <button class="vg-btn vg-btn-cancel" @click="$router.push(`/dashboard/accounts/${accountId}`)">取消</button>
        <button
          class="vg-btn vg-btn-primary"
          :class="{ 'is-loading': batchGenerating }"
          :disabled="!batchIsReady || batchGenerating"
          @click="handleBatchGenerate"
        >
          <svg v-if="!batchGenerating" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          <svg v-else class="vg-spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          批量生成 {{ batchSelected.length > 0 ? `(${batchSelected.length})` : '' }}
        </button>
      </div>
    </div>

    <!-- Account Info -->
    <div class="vgf-account-bar">
      <span class="vgf-account-name">{{ account?.account_name || '加载中...' }}</span>
      <span v-if="account?.style_description" class="vgf-account-desc">{{ account.style_description }}</span>
    </div>

    <!-- Two-panel layout -->
    <div class="vgf-panels">
      <!-- Left: Blogger selection -->
      <div class="vgf-panel-left">
        <div class="vgf-panel-header">
          <span class="vgf-panel-title">选择博主</span>
          <span class="vgf-panel-badge">{{ checkedBloggerIds.length }} 已选</span>
        </div>

        <!-- Search input -->
        <div class="vgf-search-wrap">
          <input
            v-model="bloggerSearchQuery"
            class="vgf-search-input"
            placeholder="搜索博主名称..."
            @input="handleBloggerSearch"
          />
        </div>

        <!-- Bound bloggers -->
        <div v-if="boundBloggers.length > 0" class="vgf-blogger-group">
          <div class="vgf-group-label">★ 已绑定博主</div>
          <div
            v-for="b in boundBloggers"
            :key="b.id"
            class="vgf-blogger-item"
            :class="{ 'is-checked': checkedBloggerIds.includes(b.id) }"
            @click="toggleBlogger(b)"
          >
            <label class="vg-checkbox-wrapper" @click.stop>
              <input
                type="checkbox"
                class="vg-checkbox-input"
                :checked="checkedBloggerIds.includes(b.id)"
                @change="toggleBlogger(b)"
              />
              <span class="vg-checkbox-box"></span>
            </label>
            <img v-if="b.avatar_url" :src="b.avatar_url" class="vgf-blogger-avatar" />
            <div v-else class="vgf-blogger-avatar vgf-blogger-avatar-empty">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            </div>
            <div class="vgf-blogger-info">
              <div class="vgf-blogger-name">{{ b.blogger_name }}</div>
              <div v-if="b.blogger_handle" class="vgf-blogger-handle">@{{ b.blogger_handle }}</div>
            </div>
            <div v-if="bloggerTemplateCount[b.id] !== undefined" class="vgf-blogger-count">
              {{ bloggerTemplateCount[b.id] }}
            </div>
          </div>
        </div>

        <!-- Search results -->
        <div v-if="searchedBloggers.length > 0" class="vgf-blogger-group">
          <div class="vgf-group-label">搜索结果</div>
          <div
            v-for="b in searchedBloggers"
            :key="b.id"
            class="vgf-blogger-item"
            :class="{ 'is-checked': checkedBloggerIds.includes(b.id) }"
            @click="toggleBlogger(b)"
          >
            <label class="vg-checkbox-wrapper" @click.stop>
              <input
                type="checkbox"
                class="vg-checkbox-input"
                :checked="checkedBloggerIds.includes(b.id)"
                @change="toggleBlogger(b)"
              />
              <span class="vg-checkbox-box"></span>
            </label>
            <img v-if="b.avatar_url" :src="b.avatar_url" class="vgf-blogger-avatar" />
            <div v-else class="vgf-blogger-avatar vgf-blogger-avatar-empty">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            </div>
            <div class="vgf-blogger-info">
              <div class="vgf-blogger-name">{{ b.blogger_name }}</div>
              <div v-if="b.blogger_handle" class="vgf-blogger-handle">@{{ b.blogger_handle }}</div>
            </div>
          </div>
        </div>

        <div v-if="bloggerSearchLoading" class="vgf-blogger-empty">搜索中...</div>
        <div v-else-if="!loading && boundBloggers.length === 0 && !bloggerSearchQuery" class="vgf-blogger-empty">
          暂无绑定博主，请先绑定
        </div>
      </div>

      <!-- Right: Template list -->
      <div class="vgf-panel-right">
        <div class="vgf-panel-header">
          <span class="vgf-panel-title">已选模板</span>
          <div style="display:flex;gap:8px;align-items:center">
            <button class="vg-btn vg-btn-small" @click="selectRepeatables">一键选重复</button>
            <button class="vg-btn vg-btn-small" @click="selectAllUnused">一键选未用</button>
            <label class="vg-checkbox-wrapper">
              <input
                type="checkbox"
                class="vg-checkbox-input"
                :checked="isAllSelected"
                :indeterminate="isSomeSelected"
                @change="e => toggleSelectAll(e.target.checked)"
              />
              <span class="vg-checkbox-box" :class="{ 'is-indeterminate': isSomeSelected }"></span>
              <span class="vg-checkbox-label">全选</span>
            </label>
            <span style="font-size:13px;color:#64748b">已选 <strong style="color:#0f172a">{{ batchSelected.length }}</strong> / {{ allTemplates.length }}</span>
          </div>
        </div>

        <!-- Tag filter -->
        <div v-if="allTags.length > 0" class="vgf-tag-filter">
          <span class="vgf-tag-filter-label">按标签筛选：</span>
          <span
            v-for="tag in allTags"
            :key="tag.id"
            class="vgf-tag-chip"
            :class="{ 'is-active': selectedTagIds.includes(tag.id) }"
            @click="toggleTagFilter(tag.id)"
          >{{ tag.name }}</span>
        </div>

        <div v-if="checkedBloggerIds.length === 0 && selectedTagIds.length === 0" class="vgf-tpl-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" style="margin-bottom:8px"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
          <div>请先在左侧选择博主，或直接点击上方标签筛选模板</div>
        </div>

        <div v-else-if="checkedBloggerIds.length === 0" class="vgf-tpl-scroll" v-loading="templatesLoading">
          <div
            v-for="item in tagOnlyTemplates"
            :key="item.tpl.id"
            class="vgf-tpl-item"
            :class="{
              'is-selected': batchSelected.includes(item.tpl.id),
              'is-used': item.tpl.is_used,
            }"
            @click="toggleBatchItem(item.tpl.id)"
          >
            <label class="vg-checkbox-wrapper" @click.stop>
              <input
                type="checkbox"
                class="vg-checkbox-input"
                :checked="batchSelected.includes(item.tpl.id)"
                @change="toggleBatchItem(item.tpl.id)"
              />
              <span class="vg-checkbox-box"></span>
            </label>
            <img
              v-if="item.tpl.video_source?.thumbnail_url"
              :src="item.tpl.video_source.thumbnail_url"
              class="vgf-tpl-thumb"
            />
            <div v-else class="vgf-tpl-thumb vgf-tpl-thumb-empty">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            </div>
            <div class="vgf-tpl-info">
              <div class="vgf-tpl-title">{{ item.tpl.title || item.tpl.video_source?.video_title || '未命名模板' }}</div>
              <div class="vgf-tpl-meta">
                <span class="vgf-tpl-status" :class="`status-${item.tpl.process_status}`">{{ item.tpl.process_status }}</span>
                <span v-if="item.tpl.repeatable" class="vgf-tpl-repeatable-badge">可重复</span>
                <span v-if="item.tpl.is_used" class="vgf-tpl-used-badge">已使用</span>
                <span v-if="item.tpl.video_source?.duration" style="color:#94a3b8;font-size:11px">
                  {{ formatDuration(item.tpl.video_source.duration) }}
                </span>
              </div>
              <div v-if="item.tpl.tags?.length" class="vgf-tpl-tags">
                <span v-for="tag in item.tpl.tags" :key="tag.id" class="vgf-tpl-tag">{{ tag.name }}</span>
              </div>
              <div v-if="item.tpl.extracted_shots?.length" style="font-size:11px;color:#10b981">
                {{ item.tpl.extracted_shots.length }} 张造型图
              </div>
              <div v-else style="font-size:11px;color:#f59e0b">暂无造型图</div>
            </div>
          </div>

          <div v-if="!templatesLoading && tagOnlyTemplates.length === 0 && selectedTagIds.length > 0" class="vgf-tpl-empty">
            当前标签下暂无可用模板
          </div>
        </div>

        <div v-else class="vgf-tpl-scroll" v-loading="templatesLoading">
          <!-- Group by blogger -->
          <template v-for="bloggerId in checkedBloggerIds" :key="bloggerId">
            <div v-if="templatesByBlogger[bloggerId]" class="vgf-tpl-group">
              <div class="vgf-tpl-group-header">
                <img v-if="bloggerMap[bloggerId]?.avatar_url" :src="bloggerMap[bloggerId].avatar_url" class="vgf-tpl-group-avatar" />
                <div v-else class="vgf-tpl-group-avatar vgf-tpl-group-avatar-empty">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                </div>
                <span class="vgf-tpl-group-name">{{ bloggerMap[bloggerId]?.blogger_name }}</span>
                <span class="vgf-tpl-group-count">{{ templatesByBlogger[bloggerId].length }} 个模板</span>
              </div>

              <div
                v-for="item in templatesByBlogger[bloggerId]"
                :key="item.tpl.id"
                class="vgf-tpl-item"
                :class="{
                  'is-selected': batchSelected.includes(item.tpl.id),
                  'is-used': item.tpl.is_used,
                }"
                @click="toggleBatchItem(item.tpl.id)"
              >
                <label class="vg-checkbox-wrapper" @click.stop>
                  <input
                    type="checkbox"
                    class="vg-checkbox-input"
                    :checked="batchSelected.includes(item.tpl.id)"
                    @change="toggleBatchItem(item.tpl.id)"
                  />
                  <span class="vg-checkbox-box"></span>
                </label>
                <img
                  v-if="item.tpl.video_source?.thumbnail_url"
                  :src="item.tpl.video_source.thumbnail_url"
                  class="vgf-tpl-thumb"
                />
                <div v-else class="vgf-tpl-thumb vgf-tpl-thumb-empty">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                </div>
                <div class="vgf-tpl-info">
                  <div class="vgf-tpl-title">{{ item.tpl.title || item.tpl.video_source?.video_title || '未命名模板' }}</div>
                  <div class="vgf-tpl-meta">
                    <span class="vgf-tpl-status" :class="`status-${item.tpl.process_status}`">{{ item.tpl.process_status }}</span>
                    <span v-if="item.tpl.repeatable" class="vgf-tpl-repeatable-badge">可重复</span>
                    <span v-if="item.tpl.is_used" class="vgf-tpl-used-badge">已使用</span>
                    <span v-if="item.tpl.video_source?.duration" style="color:#94a3b8;font-size:11px">
                      {{ formatDuration(item.tpl.video_source.duration) }}
                    </span>
                  </div>
                  <div v-if="item.tpl.tags?.length" class="vgf-tpl-tags">
                    <span v-for="tag in item.tpl.tags" :key="tag.id" class="vgf-tpl-tag">{{ tag.name }}</span>
                  </div>
                  <div v-if="item.tpl.extracted_shots?.length" style="font-size:11px;color:#10b981">
                    {{ item.tpl.extracted_shots.length }} 张造型图
                  </div>
                  <div v-else style="font-size:11px;color:#f59e0b">暂无造型图</div>
                </div>
              </div>
            </div>
          </template>

          <div v-if="!templatesLoading && allTemplates.length === 0 && checkedBloggerIds.length > 0" class="vgf-tpl-empty">
            已选博主暂无可用模板
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchAccount, fetchAccountBloggers } from '../api/accounts'
import { searchBloggers } from '../api/tiktok_bloggers'
import { fetchTemplatesByBlogger, fetchTemplatesByTags } from '../api/video_ai_templates'
import { fetchTags } from '../api/tags'
import { createVideoTask } from '../api/video_tasks'

const route = useRoute()
const router = useRouter()
const accountId = route.params.id

const loading = ref(false)
const batchGenerating = ref(false)
const templatesLoading = ref(false)

const account = ref(null)
const boundBloggers = ref([])
const searchedBloggers = ref([])
const bloggerSearchLoading = ref(false)
const bloggerSearchQuery = ref('')

// checkedBloggerIds: multi-select
const checkedBloggerIds = ref([])

// bloggerMap: id -> blogger object (for display in right panel)
const bloggerMap = ref({})

// templatesByBlogger: id -> [{tpl}]
const templatesByBlogger = ref({})
const tagOnlyTemplates = ref([])

// batchSelected
const batchSelected = ref([])

// tag filter
const allTags = ref([])
const selectedTagIds = ref([])

// allTemplates: flat list across all checked bloggers, repeatable first
const allTemplates = computed(() => {
  const items = checkedBloggerIds.value.length > 0
    ? checkedBloggerIds.value.flatMap(id => templatesByBlogger.value[id] || [])
    : tagOnlyTemplates.value
  return [...items].sort((a, b) => (b.tpl.repeatable ? 1 : 0) - (a.tpl.repeatable ? 1 : 0))
})

// template count badge per blogger
const bloggerTemplateCount = computed(() => {
  const map = {}
  for (const [id, items] of Object.entries(templatesByBlogger.value)) {
    map[id] = items.length
  }
  return map
})

function selectRepeatables() {
  batchSelected.value = allTemplates.value
    .filter(item => item.tpl.repeatable)
    .map(item => item.tpl.id)
}

const isAllSelected = computed(
  () => allTemplates.value.length > 0 && batchSelected.value.length === allTemplates.value.length
)
const isSomeSelected = computed(
  () => batchSelected.value.length > 0 && batchSelected.value.length < allTemplates.value.length
)
const batchIsReady = computed(() => batchSelected.value.length > 0 && !!account.value)

async function loadData() {
  loading.value = true
  try {
    const [acct, bloggers, tags] = await Promise.all([
      fetchAccount(accountId),
      fetchAccountBloggers(accountId),
      fetchTags(),
    ])
    account.value = acct
    boundBloggers.value = bloggers
    allTags.value = tags
    for (const b of bloggers) {
      bloggerMap.value[b.id] = b
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载初始数据失败')
  } finally {
    loading.value = false
  }
}

async function loadTemplatesForBlogger(bloggerId) {
  try {
    // by-blogger already returns tags inline; no need for per-item detail fetch
    const templates = await fetchTemplatesByBlogger(bloggerId, selectedTagIds.value)
    const items = templates.map(tpl => ({ tpl }))
    items.sort((a, b) => (b.tpl.repeatable ? 1 : 0) - (a.tpl.repeatable ? 1 : 0))
    templatesByBlogger.value[bloggerId] = items
  } catch {
    templatesByBlogger.value[bloggerId] = []
  }
}

async function reloadAllTemplates() {
  // Clear cache and reload for all checked bloggers
  for (const id of checkedBloggerIds.value) {
    delete templatesByBlogger.value[id]
  }
  tagOnlyTemplates.value = []
  batchSelected.value = []
  templatesLoading.value = true
  try {
    if (checkedBloggerIds.value.length > 0) {
      await Promise.all(checkedBloggerIds.value.map(id => loadTemplatesForBlogger(id)))
    } else if (selectedTagIds.value.length > 0) {
      const templates = await fetchTemplatesByTags(selectedTagIds.value)
      tagOnlyTemplates.value = templates.map(tpl => ({ tpl }))
    }
  } finally {
    templatesLoading.value = false
  }
}

async function toggleTagFilter(tagId) {
  const idx = selectedTagIds.value.indexOf(tagId)
  if (idx >= 0) selectedTagIds.value.splice(idx, 1)
  else selectedTagIds.value.push(tagId)
  await reloadAllTemplates()
}

async function toggleBlogger(blogger) {
  const id = blogger.id
  const idx = checkedBloggerIds.value.indexOf(id)
  if (idx >= 0) {
    checkedBloggerIds.value.splice(idx, 1)
    const tplIds = new Set((templatesByBlogger.value[id] || []).map(item => item.tpl.id))
    batchSelected.value = batchSelected.value.filter(tid => !tplIds.has(tid))
    delete templatesByBlogger.value[id]
    if (checkedBloggerIds.value.length === 0 && selectedTagIds.value.length > 0) {
      templatesLoading.value = true
      try {
        const templates = await fetchTemplatesByTags(selectedTagIds.value)
        tagOnlyTemplates.value = templates.map(tpl => ({ tpl }))
      } finally {
        templatesLoading.value = false
      }
    }
  } else {
    checkedBloggerIds.value.push(id)
    bloggerMap.value[id] = blogger
    tagOnlyTemplates.value = []
    templatesLoading.value = true
    await loadTemplatesForBlogger(id)
    templatesLoading.value = false
  }
}

let _searchTimer = null
function handleBloggerSearch() {
  clearTimeout(_searchTimer)
  const q = bloggerSearchQuery.value.trim()
  if (!q) {
    searchedBloggers.value = []
    return
  }
  bloggerSearchLoading.value = true
  _searchTimer = setTimeout(async () => {
    try {
      const results = await searchBloggers(q, 20)
      const boundIds = new Set(boundBloggers.value.map(b => b.id))
      searchedBloggers.value = results.filter(b => !boundIds.has(b.id))
    } catch {
      searchedBloggers.value = []
    } finally {
      bloggerSearchLoading.value = false
    }
  }, 300)
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  let s = Math.floor(seconds)
  if (s > 15) s = 15
  return `${s}s`
}

function toggleBatchItem(tplId) {
  const idx = batchSelected.value.indexOf(tplId)
  if (idx >= 0) batchSelected.value.splice(idx, 1)
  else batchSelected.value.push(tplId)
  console.log('toggleBatchItem:', tplId, 'batchSelected now:', batchSelected.value)
}

function toggleSelectAll(val) {
  if (val) batchSelected.value = allTemplates.value.map(item => item.tpl.id)
  else batchSelected.value = []
}

function selectAllUnused() {
  batchSelected.value = allTemplates.value
    .filter(item => !item.tpl.is_used)
    .map(item => item.tpl.id)
}

async function handleBatchGenerate() {
  console.log('DEBUG handleBatchGenerate start - batchSelected:', batchSelected.value.length, 'account:', !!account.value, 'batchGenerating:', batchGenerating.value)
  if (batchGenerating.value || !batchIsReady.value) {
    console.log('DEBUG: early return - batchGenerating:', batchGenerating.value, 'batchIsReady:', batchIsReady.value)
    return
  }
  batchGenerating.value = true
  console.log('DEBUG: allTemplates:', allTemplates.value.map(item => ({ id: item.tpl.id, title: item.tpl.title })))
  const selectedItems = allTemplates.value.filter(item => batchSelected.value.includes(item.tpl.id))
  console.log('DEBUG: batchSelected:', batchSelected.value)
  console.log('DEBUG: allTemplates count:', allTemplates.value.length)
  console.log('DEBUG: selectedItems count:', selectedItems.length)
  console.log('DEBUG: selectedItems:', selectedItems.map(item => ({ id: item.tpl.id, title: item.tpl.title })))
  console.log('DEBUG: first selectedItem:', JSON.stringify(selectedItems[0], null, 2))
  let successCount = 0
  let failCount = 0
  try {
    for (const item of selectedItems) {
      const tpl = item.tpl
      console.log('DEBUG: processing template:', tpl.id, 'duration:', tpl.video_source?.duration, 'shots count:', tpl.extracted_shots?.length)
      try {
        const duration = formatDuration(tpl.video_source?.duration)
        const shots = (tpl.extracted_shots || []).map(({ image_base64, ...rest }) => rest)
        console.log('DEBUG: calling createVideoTask with:', { account_id: accountId, template_id: tpl.id, final_prompt: tpl.prompt_description || '', duration, shots_count: shots.length })
        await createVideoTask({
          account_id: accountId,
          template_id: tpl.id,
          final_prompt: tpl.prompt_description || '',
          duration,
          shots,
        })
        console.log('DEBUG: createVideoTask success for template:', tpl.id)
        successCount++
      } catch (err) {
        console.error('DEBUG: createVideoTask error:', err)
        failCount++
      }
    }
    if (successCount > 0) ElMessage.success(`成功创建 ${successCount} 个生成任务${failCount > 0 ? `，${failCount} 个失败` : ''}`)
    else ElMessage.error('所有任务创建失败')
    router.push(`/dashboard/accounts/${accountId}`)
  } finally {
    batchGenerating.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.vgf-page {
  padding: 30px;
  max-width: 1200px;
  margin: 0 auto;
  min-height: 100vh;
  animation: vgf-fade-in 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes vgf-fade-in {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}

.vgf-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.vgf-title {
  font-size: 24px;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 4px 0;
  letter-spacing: -0.02em;
}

.vgf-subtitle {
  font-size: 14px;
  color: #64748b;
}

.vgf-header-actions {
  display: flex;
  gap: 12px;
}

.vgf-account-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  margin-bottom: 20px;
}

.vgf-account-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.vgf-account-desc {
  font-size: 13px;
  color: #64748b;
}

/* Two-panel layout */
.vgf-panels {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  height: calc(100vh - 200px);
}

.vgf-panel-left {
  width: 280px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 20px -10px rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.vgf-panel-right {
  flex: 1;
  min-width: 0;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 20px -10px rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.vgf-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 18px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.vgf-panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.vgf-panel-badge {
  font-size: 12px;
  background: #eef2ff;
  color: #4f46e5;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}

/* Search */
.vgf-search-wrap {
  padding: 12px 12px 8px;
  flex-shrink: 0;
}

.vgf-search-input {
  width: 100%;
  box-sizing: border-box;
  height: 34px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 13px;
  color: #0f172a;
  outline: none;
  transition: all 0.15s;
  font-family: inherit;
}

.vgf-search-input:focus {
  border-color: #818cf8;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.12);
}

/* Blogger list */
.vgf-blogger-group {
  padding: 0 8px 8px;
  overflow-y: auto;
}

.vgf-group-label {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  padding: 6px 8px 4px;
}

.vgf-blogger-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
  user-select: none;
}

.vgf-blogger-item:hover {
  background: #f1f5f9;
}

.vgf-blogger-item.is-checked {
  background: #eef2ff;
}

.vgf-blogger-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid #e2e8f0;
}

.vgf-blogger-avatar-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
}

.vgf-blogger-info {
  flex: 1;
  min-width: 0;
}

.vgf-blogger-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vgf-blogger-handle {
  font-size: 11px;
  color: #94a3b8;
}

.vgf-blogger-count {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  background: #f1f5f9;
  padding: 1px 7px;
  border-radius: 999px;
  flex-shrink: 0;
}

.vgf-blogger-empty {
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  padding: 24px 16px;
}

/* Template list */
.vgf-tpl-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.vgf-tpl-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 14px;
  padding: 40px;
}

.vgf-tpl-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vgf-tpl-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 4px 2px;
}

.vgf-tpl-group-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.vgf-tpl-group-avatar-empty {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.vgf-tpl-group-name {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.vgf-tpl-group-count {
  font-size: 12px;
  color: #94a3b8;
}

.vgf-tpl-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.12s;
  user-select: none;
}

.vgf-tpl-item:hover {
  border-color: #a5b4fc;
  background: #eef2ff;
}

.vgf-tpl-item.is-selected {
  border-color: #6366f1 !important;
  background: #eef2ff !important;
}

.vgf-tpl-item.is-used {
  opacity: 0.55;
}

.vgf-tpl-thumb {
  width: 52px;
  height: 52px;
  object-fit: cover;
  border-radius: 7px;
  flex-shrink: 0;
  border: 1px solid #e2e8f0;
}

.vgf-tpl-thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
}

.vgf-tpl-info {
  flex: 1;
  min-width: 0;
}

.vgf-tpl-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.vgf-tpl-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.vgf-tpl-status {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #64748b;
}

.vgf-tpl-status.status-success {
  background: #dcfce7;
  color: #166534;
}

.vgf-tpl-status.status-face_removing,
.vgf-tpl-status.status-splitting,
.vgf-tpl-status.status-understanding,
.vgf-tpl-status.status-imagegen {
  background: #fef9c3;
  color: #a16207;
}

.vgf-tpl-status.status-failed {
  background: #fee2e2;
  color: #991b1b;
}

/* Tag filter bar */
.vgf-tag-filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-bottom: 1px solid #f1f5f9;
  flex-shrink: 0;
}

.vgf-tag-filter-label {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 600;
  white-space: nowrap;
}

.vgf-tag-chip {
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  padding: 2px 9px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.12s;
  user-select: none;
}

.vgf-tag-chip:hover {
  border-color: #a5b4fc;
  color: #4f46e5;
}

.vgf-tag-chip.is-active {
  background: #eef2ff;
  border-color: #6366f1;
  color: #4f46e5;
  font-weight: 600;
}

/* Tags on template card */
.vgf-tpl-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 2px;
}

.vgf-tpl-tag {
  font-size: 10px;
  font-weight: 500;
  color: #6366f1;
  background: #eef2ff;
  padding: 1px 6px;
  border-radius: 4px;
}

.vgf-tpl-repeatable-badge {
  font-size: 11px;
  font-weight: 600;
  color: #0369a1;
  background: #e0f2fe;
  padding: 1px 6px;
  border-radius: 5px;
}

.vgf-tpl-used-badge {
  font-size: 11px;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 1px 6px;
  border-radius: 5px;
}

/* Buttons */
.vg-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  height: 38px;
  padding: 0 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  outline: none;
  font-family: inherit;
  border: none;
}

.vg-btn-small {
  height: 30px;
  padding: 0 12px;
  font-size: 13px;
  border-radius: 6px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #475569;
}

.vg-btn-small:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.vg-btn-cancel {
  background: #fff;
  border: 1px solid #e2e8f0 !important;
  color: #475569;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.vg-btn-cancel:hover {
  border-color: #cbd5e1 !important;
  background: #f8fafc;
  color: #0f172a;
  transform: translateY(-1px);
}

.vg-btn-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  box-shadow: 0 4px 12px rgba(99,102,241,0.25);
}

.vg-btn-primary:hover:not(:disabled) {
  box-shadow: 0 6px 16px rgba(99,102,241,0.35);
  transform: translateY(-1px);
}

.vg-btn-primary:disabled {
  background: #c7d2fe;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

.is-loading {
  pointer-events: none;
  opacity: 0.8;
}

.vg-spinner {
  animation: vg-spin 1s linear infinite;
}

@keyframes vg-spin {
  100% { transform: rotate(360deg); }
}

/* Custom Checkbox */
.vg-checkbox-wrapper {
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.vg-checkbox-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.vg-checkbox-box {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 2px solid #cbd5e1;
  background: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  position: relative;
  flex-shrink: 0;
}

.vg-checkbox-input:checked + .vg-checkbox-box {
  background: #6366f1;
  border-color: #6366f1;
}

.vg-checkbox-input:checked + .vg-checkbox-box::after {
  content: '';
  position: absolute;
  width: 4px;
  height: 7px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
  top: 1px;
}

.vg-checkbox-box.is-indeterminate {
  background: #6366f1;
  border-color: #6366f1;
}

.vg-checkbox-box.is-indeterminate::after {
  content: '';
  position: absolute;
  width: 8px;
  height: 2px;
  background: white;
  border: none;
  transform: none;
  top: 5px;
}

.vg-checkbox-label {
  margin-left: 7px;
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

.vg-checkbox-wrapper:hover .vg-checkbox-box:not(.is-indeterminate) {
  border-color: #94a3b8;
}

.vg-checkbox-input:checked + .vg-checkbox-box:hover {
  background: #4f46e5;
  border-color: #4f46e5;
}
</style>
