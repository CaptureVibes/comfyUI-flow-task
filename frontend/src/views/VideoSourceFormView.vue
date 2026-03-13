<template>
  <div class="vsf-page">
    <div class="vsf-back" @click="$router.push('/dashboard/video-library')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      返回视频库
    </div>

    <div class="vsf-card">
      <div class="vsf-header">
        <div class="vsf-icon-wrap">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.75" stroke-linecap="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z" fill="white" stroke="none"/></svg>
        </div>
        <div>
          <div class="vsf-title">批量添加视频</div>
          <div class="vsf-subtitle">支持一次粘贴多行 TikTok、YouTube 或 Instagram 链接，解析后统一设置标签并批量保存</div>
        </div>
      </div>

      <div class="vsf-url-block">
        <el-input
          v-model="urlText"
          type="textarea"
          :rows="6"
          resize="none"
          placeholder="每行一个链接，支持 TikTok / YouTube / Instagram"
          :disabled="parsing"
          class="vsf-url-textarea"
        />
        <div class="vsf-url-toolbar">
          <div class="vsf-url-hint">已识别 {{ inputUrls.length }} 条链接，重复链接会自动去重</div>
          <div class="vsf-url-actions">
            <el-button @click="reset" :disabled="parsing && !parsedItems.length">清空</el-button>
            <el-button
              type="primary"
              size="large"
              :loading="parsing"
              :disabled="inputUrls.length === 0 || parsedItems.length > 0"
              class="vsf-parse-btn"
              @click="handleParse"
            >
              {{ parsing ? '解析中...' : `解析 ${inputUrls.length || ''} 条链接` }}
            </el-button>
          </div>
        </div>
      </div>

      <el-alert
        v-if="parseError"
        :title="parseError"
        type="error"
        :closable="true"
        show-icon
        class="vsf-error"
        @close="parseError = ''"
      />

      <transition name="slide-up">
        <div v-if="parsedItems.length" class="vsf-preview">
          <el-divider>
            <span class="divider-text">解析结果 — 统一设置标签后批量保存</span>
          </el-divider>

          <div class="vsf-batch-summary">
            <div class="vsf-summary-card">
              <span>解析成功</span>
              <strong>{{ parsedCount }}</strong>
            </div>
            <div class="vsf-summary-card">
              <span>已存在</span>
              <strong>{{ existingCount }}</strong>
            </div>
            <div class="vsf-summary-card">
              <span>解析失败</span>
              <strong>{{ errorCount }}</strong>
            </div>
            <div class="vsf-summary-card">
              <span>可保存</span>
              <strong>{{ savableItems.length }}</strong>
            </div>
          </div>

          <div class="vsf-batch-config">
            <div class="vsf-batch-config-head">
              <h3>批量设置</h3>
              <span>以下标签和重复策略会一次性应用到本次所有待保存视频</span>
            </div>

            <div class="vsf-extra-row">
              <span class="vsf-extra-label">标签</span>
              <div class="vsf-tag-area">
                <span
                  v-for="tag in selectedTags"
                  :key="tag.id"
                  class="vsf-tag-chip"
                  :style="tag.color ? { background: tag.color + '22', borderColor: tag.color, color: tag.color } : {}"
                >
                  {{ tag.name }}
                  <button class="vsf-tag-remove" @click="removeTag(tag.id)">×</button>
                </span>

                <div class="vsf-tag-input-wrap">
                  <input
                    v-model="newTagName"
                    class="vsf-tag-input"
                    placeholder="+ 添加标签"
                    @keydown.enter.prevent="addOrCreateTag"
                    @focus="handleTagInputFocus"
                    @blur="onTagInputBlur"
                  />
                  <div v-if="showTagDropdown && filteredTags.length > 0" class="vsf-tag-dropdown">
                    <div
                      v-for="tag in filteredTags"
                      :key="tag.id"
                      class="vsf-tag-option"
                      @mousedown.prevent="selectTag(tag)"
                    >
                      <span class="vsf-tag-dot" :style="tag.color ? { background: tag.color } : {}" />
                      {{ tag.name }}
                    </div>
                  </div>
                </div>

                <span v-if="newTagName && !filteredTagExists" class="vsf-tag-hint">
                  按 Enter 新建「{{ newTagName }}」
                </span>
              </div>
            </div>

            <div class="vsf-extra-row" style="margin-top:10px">
              <span class="vsf-extra-label">可重复</span>
              <div class="vsf-repeat-toggle">
                <button
                  class="vsf-toggle-btn"
                  :class="{ active: repeatable }"
                  @click="repeatable = !repeatable"
                >
                  <span class="vsf-toggle-knob" />
                </button>
                <span class="vsf-toggle-text">{{ repeatable ? '是，可重复发送' : '否，仅发送一次' }}</span>
              </div>
            </div>
          </div>

          <div class="vsf-batch-list">
            <div
              v-for="item in parsedItems"
              :key="item._key"
              class="vsf-item-card"
              :class="`is-${item._parse_status}`"
            >
              <div class="vsf-item-media">
                <video
                  v-if="item.video_url"
                  :src="item.video_url"
                  :poster="item.thumbnail_url || undefined"
                  controls
                  class="vsf-video"
                />
                <div v-else-if="item.thumbnail_url" class="vsf-thumb-only">
                  <img :src="item.thumbnail_url" class="vsf-thumb-img" alt="thumbnail" />
                  <div class="vsf-noplay-hint">仅预览图，无直链</div>
                </div>
                <div v-else class="vsf-no-media">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>
                  <div style="color:#94a3b8;font-size:13px;margin-top:8px">无预览</div>
                </div>
              </div>

              <div class="vsf-item-body">
                <div class="vsf-item-top">
                  <el-tag :type="platformTagType(item.platform)" size="small">
                    {{ item.platform ? platformLabel(item.platform) : '未知平台' }}
                  </el-tag>
                  <span class="vsf-item-status" :class="`is-${item._parse_status}`">{{ itemStatusLabel(item) }}</span>
                </div>

                <div class="vsf-meta-title">{{ item.video_title || '(无标题)' }}</div>
                <div class="vsf-meta-grid">
                  <div class="vsf-meta-row">
                    <span class="vsf-meta-label">博主</span>
                    <span class="vsf-meta-val">{{ item.blogger_name || '-' }}</span>
                  </div>
                  <div class="vsf-meta-row">
                    <span class="vsf-meta-label">链接</span>
                    <span class="vsf-meta-val vsf-url-val" :title="item.source_url">{{ item.source_url }}</span>
                  </div>
                  <div class="vsf-meta-row" v-if="item.duration != null">
                    <span class="vsf-meta-label">时长</span>
                    <span class="vsf-meta-val">{{ formatDuration(item.duration) }}</span>
                  </div>
                  <div class="vsf-meta-row" v-if="item.publish_date">
                    <span class="vsf-meta-label">发布日期</span>
                    <span class="vsf-meta-val">{{ formatDate(item.publish_date) }}</span>
                  </div>
                </div>

                <div v-if="item.video_desc" class="vsf-meta-desc">{{ item.video_desc }}</div>
                <div v-if="item._error" class="vsf-item-error">{{ item._error }}</div>

                <div class="vsf-item-actions">
                  <el-link
                    v-if="item.source_url"
                    :href="item.source_url"
                    target="_blank"
                    type="primary"
                    :underline="false"
                  >前往原始链接</el-link>
                  <el-button v-if="item.existing_id" size="small" @click="$router.push(`/dashboard/video-library/${item.existing_id}`)">查看已存在视频</el-button>
                </div>
              </div>
            </div>
          </div>

          <div class="vsf-actions">
            <el-button type="primary" size="large" :loading="saving" :disabled="savableItems.length === 0" @click="handleSave">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
              保存 {{ savableItems.length }} 个视频
            </el-button>
            <el-button size="large" @click="reset">重新解析</el-button>
          </div>
        </div>
      </transition>

      <transition name="slide-up">
        <div v-if="saved" class="vsf-success">
          <div class="vsf-success-inner">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/></svg>
            <div class="vsf-success-title">批量保存完成</div>
            <div class="vsf-success-sub">成功创建 {{ saveSummary.created }} 个视频，已存在 {{ saveSummary.existing }} 个，失败 {{ saveSummary.failed }} 个</div>
            <div class="vsf-dl-hint">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0ea5e9" stroke-width="2" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              CDN 链接可能无法直接播放，可在视频库中点击「下载上传」将视频上传到永久存储后播放
            </div>
            <div class="vsf-success-btns">
              <el-button type="primary" @click="$router.push('/dashboard/video-library')">返回视频库</el-button>
              <el-button @click="addAnother">继续添加</el-button>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createVideoSource, downloadVideoSource, parseVideoUrl } from '../api/video_sources'
import { createTag, fetchTags } from '../api/tags'

const router = useRouter()

const urlText = ref('')
const parsing = ref(false)
const saving = ref(false)
const saved = ref(false)
const parseError = ref('')
const parsedItems = ref([])
const saveSummary = ref({ created: 0, existing: 0, failed: 0 })
const PARSE_CONCURRENCY = 5

const allTags = ref([])
const selectedTagIds = ref([])
const newTagName = ref('')
const showTagDropdown = ref(false)
const tagsLoading = ref(false)
const repeatable = ref(false)

const inputUrls = computed(() => {
  const seen = new Set()
  return urlText.value
    .split(/\r?\n/)
    .map(item => item.trim())
    .filter(Boolean)
    .filter(item => {
      if (seen.has(item)) return false
      seen.add(item)
      return true
    })
})

const selectedTags = computed(() => allTags.value.filter(t => selectedTagIds.value.includes(t.id)))
const filteredTags = computed(() =>
  allTags.value.filter(t =>
    !selectedTagIds.value.includes(t.id) &&
    (!newTagName.value || t.name.toLowerCase().includes(newTagName.value.toLowerCase()))
  )
)
const filteredTagExists = computed(() =>
  allTags.value.some(t => t.name.toLowerCase() === newTagName.value.toLowerCase())
)

const parsedCount = computed(() => parsedItems.value.filter(item => item._parse_status === 'parsed').length)
const existingCount = computed(() => parsedItems.value.filter(item => item._parse_status === 'existing').length)
const errorCount = computed(() => parsedItems.value.filter(item => item._parse_status === 'error').length)
const savableItems = computed(() => parsedItems.value.filter(item => item._parse_status === 'parsed'))

onMounted(() => {
  loadTags()
})

async function loadTags(force = false) {
  if (tagsLoading.value) return
  if (!force && allTags.value.length > 0) return
  tagsLoading.value = true
  try {
    allTags.value = await fetchTags()
  } catch {
    // ignore
  } finally {
    tagsLoading.value = false
  }
}

function selectTag(tag) {
  if (!selectedTagIds.value.includes(tag.id)) {
    selectedTagIds.value = [...selectedTagIds.value, tag.id]
  }
  newTagName.value = ''
  showTagDropdown.value = false
}

function removeTag(id) {
  selectedTagIds.value = selectedTagIds.value.filter(tid => tid !== id)
}

async function addOrCreateTag() {
  const name = newTagName.value.trim()
  if (!name) return
  const existing = allTags.value.find(t => t.name.toLowerCase() === name.toLowerCase())
  if (existing) {
    selectTag(existing)
    return
  }
  try {
    const tag = await createTag({ name })
    allTags.value = [...allTags.value, tag]
    selectTag(tag)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '创建标签失败')
  }
}

function onTagInputBlur() {
  setTimeout(() => {
    showTagDropdown.value = false
  }, 150)
}

async function handleTagInputFocus() {
  showTagDropdown.value = true
  if (allTags.value.length === 0) {
    await loadTags(true)
  }
}

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }
function platformLabel(p) { return PLATFORM_LABELS[p] || (p || '未知平台') }
function platformTagType(platform) {
  if (platform === 'youtube') return 'danger'
  if (platform === 'instagram') return 'warning'
  return 'primary'
}

function itemStatusLabel(item) {
  if (item._save_status === 'saved') return '已保存'
  if (item._save_status === 'failed') return '保存失败'
  if (item._parse_status === 'existing') return '已存在'
  if (item._parse_status === 'error') return '解析失败'
  return '待保存'
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
}

function formatDuration(seconds) {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

async function handleParse() {
  if (parsing.value || inputUrls.value.length === 0) return
  parsing.value = true
  parseError.value = ''
  parsedItems.value = []
  saved.value = false

  const items = new Array(inputUrls.value.length)
  let cursor = 0

  async function worker() {
    while (cursor < inputUrls.value.length) {
      const index = cursor++
      const sourceUrl = inputUrls.value[index]
      try {
        const result = await parseVideoUrl(sourceUrl)
        items[index] = {
          ...result,
          _key: `${sourceUrl}-${result.existing_id || 'new'}`,
          _parse_status: result.existing_id ? 'existing' : 'parsed',
          _error: '',
          _save_status: 'idle',
        }
      } catch (err) {
        items[index] = {
          _key: `${sourceUrl}-error`,
          source_url: sourceUrl,
          platform: null,
          blogger_name: null,
          video_title: null,
          video_desc: null,
          video_url: null,
          thumbnail_url: null,
          duration: null,
          publish_date: null,
          existing_id: null,
          _parse_status: 'error',
          _error: err?.response?.data?.detail || '解析失败，请检查链接是否有效',
          _save_status: 'idle',
        }
      }
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(PARSE_CONCURRENCY, inputUrls.value.length) }, () => worker())
  )

  parsedItems.value = items
  if (allTags.value.length === 0) {
    await loadTags(true)
  }
  if (items.every(item => item._parse_status === 'error')) {
    parseError.value = '所有链接都解析失败，请检查链接格式后重试'
  }
  parsing.value = false
}

async function handleSave() {
  if (saving.value || savableItems.value.length === 0) return
  saving.value = true
  saveSummary.value = { created: 0, existing: 0, failed: 0 }

  for (const item of parsedItems.value) {
    if (item._parse_status !== 'parsed') continue
    item._save_status = 'saving'
    try {
      const { data: result, status } = await createVideoSource({
        source_url: item.source_url,
        platform: item.platform,
        blogger_name: item.blogger_name,
        video_title: item.video_title,
        video_desc: item.video_desc,
        video_url: item.video_url,
        thumbnail_url: item.thumbnail_url,
        view_count: item.view_count,
        like_count: item.like_count,
        favorite_count: item.favorite_count,
        comment_count: item.comment_count,
        share_count: item.share_count,
        publish_date: item.publish_date,
        duration: item.duration,
        width: item.width,
        height: item.height,
        aspect_ratio: item.aspect_ratio,
        extra: item.extra,
        tag_ids: selectedTagIds.value,
        repeatable: repeatable.value,
      })

      if (status === 200) {
        item._save_status = 'existing'
        item.existing_id = result.id
        saveSummary.value.existing += 1
      } else {
        item._save_status = 'saved'
        item.saved_id = result.id
        saveSummary.value.created += 1
        try { await downloadVideoSource(result.id) } catch { /* ignore */ }
      }
    } catch (err) {
      item._save_status = 'failed'
      item._error = err?.response?.data?.detail || '保存失败'
      saveSummary.value.failed += 1
    }
  }

  saving.value = false
  saved.value = true
  ElMessage.success(`批量保存完成，成功 ${saveSummary.value.created} 个`)
}

function reset() {
  urlText.value = ''
  parseError.value = ''
  parsedItems.value = []
  selectedTagIds.value = []
  repeatable.value = false
  newTagName.value = ''
  saved.value = false
  saveSummary.value = { created: 0, existing: 0, failed: 0 }
}

function addAnother() {
  reset()
}
</script>

<style scoped>
.vsf-page {
  padding: 28px 32px;
  animation: rise 0.3s ease;
}

.vsf-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  margin-bottom: 20px;
  transition: color 0.15s;
}
.vsf-back:hover { color: #6366f1; }

.vsf-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 20px;
  padding: 32px;
  max-width: 1100px;
  box-shadow: 0 4px 16px rgba(0,0,0,.06);
}

.vsf-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 28px;
}

.vsf-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.vsf-title {
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}
.vsf-subtitle { font-size: 13px; color: #64748b; margin-top: 3px; }

.vsf-url-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.vsf-url-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.vsf-url-hint {
  font-size: 12px;
  color: #64748b;
}

.vsf-url-actions {
  display: flex;
  gap: 10px;
}

.vsf-parse-btn {
  min-width: 160px;
  font-weight: 600;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
}

.vsf-error { margin-bottom: 16px; border-radius: 10px; }
.vsf-preview { margin-top: 8px; }
.divider-text { font-size: 13px; font-weight: 600; color: #475569; }

.vsf-batch-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.vsf-summary-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #64748b;
  font-size: 12px;
}

.vsf-summary-card strong {
  color: #0f172a;
  font-size: 22px;
}

.vsf-batch-config {
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  margin-bottom: 20px;
}

.vsf-batch-config-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.vsf-batch-config-head h3 {
  margin: 0;
  font-size: 16px;
  color: #0f172a;
}

.vsf-batch-config-head span {
  font-size: 12px;
  color: #64748b;
}

.vsf-batch-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.vsf-item-card {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
}

.vsf-item-card.is-existing {
  border-color: #fde68a;
  background: #fffdf5;
}

.vsf-item-card.is-error {
  border-color: #fecaca;
  background: #fffafa;
}

.vsf-item-media {
  border-radius: 12px;
  overflow: hidden;
  background: #0f172a;
  aspect-ratio: 16 / 9;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vsf-video { width: 100%; height: 100%; object-fit: contain; display: block; }
.vsf-thumb-only { position: relative; width: 100%; height: 100%; }
.vsf-thumb-img { width: 100%; height: 100%; object-fit: cover; }

.vsf-noplay-hint {
  position: absolute;
  bottom: 8px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 12px;
  color: rgba(255,255,255,.7);
  background: rgba(0,0,0,.4);
  padding: 4px;
}

.vsf-no-media {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 160px;
}

.vsf-item-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vsf-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.vsf-item-status {
  font-size: 12px;
  font-weight: 700;
  border-radius: 999px;
  padding: 4px 10px;
  background: #e2e8f0;
  color: #475569;
}

.vsf-item-status.is-parsed,
.vsf-item-status.is-saved {
  background: #dcfce7;
  color: #15803d;
}

.vsf-item-status.is-existing {
  background: #fef3c7;
  color: #b45309;
}

.vsf-item-status.is-error,
.vsf-item-status.is-failed {
  background: #fee2e2;
  color: #b91c1c;
}

.vsf-meta-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.4;
}

.vsf-meta-desc {
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.vsf-meta-grid { display: flex; flex-direction: column; gap: 8px; }
.vsf-meta-row { display: flex; gap: 12px; align-items: flex-start; }
.vsf-meta-label {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  min-width: 56px;
  text-transform: uppercase;
  letter-spacing: .04em;
  padding-top: 1px;
}
.vsf-meta-val { font-size: 14px; color: #334155; word-break: break-all; }
.vsf-url-val { font-size: 12px; color: #94a3b8; word-break: break-all; }

.vsf-item-error {
  font-size: 12px;
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  padding: 10px 12px;
  border-radius: 10px;
}

.vsf-item-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: auto;
}

.vsf-extra-row { display: flex; gap: 12px; align-items: flex-start; }
.vsf-extra-label {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  min-width: 56px;
  text-transform: uppercase;
  letter-spacing: .04em;
  padding-top: 6px;
  flex-shrink: 0;
}

.vsf-tag-area {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  flex: 1;
}

.vsf-tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #f8fafc;
  font-size: 12px;
  color: #475569;
}

.vsf-tag-remove {
  border: none;
  background: transparent;
  cursor: pointer;
  color: inherit;
  font-size: 14px;
  line-height: 1;
  padding: 0;
}

.vsf-tag-input-wrap { position: relative; }
.vsf-tag-input {
  border: 1px dashed #cbd5e1;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  outline: none;
  min-width: 120px;
  background: #fff;
}
.vsf-tag-input:focus {
  border-color: #818cf8;
}

.vsf-tag-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 180px;
  max-height: 220px;
  overflow: auto;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
  z-index: 10;
}

.vsf-tag-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-size: 13px;
  color: #334155;
  cursor: pointer;
}
.vsf-tag-option:hover { background: #f8fafc; }

.vsf-tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #818cf8;
  flex-shrink: 0;
}

.vsf-tag-hint {
  font-size: 12px;
  color: #64748b;
}

.vsf-repeat-toggle { display: flex; align-items: center; gap: 10px; }
.vsf-toggle-btn {
  position: relative;
  width: 44px;
  height: 24px;
  border-radius: 999px;
  border: none;
  background: #cbd5e1;
  cursor: pointer;
  padding: 0;
  transition: background 0.15s;
}
.vsf-toggle-btn.active { background: #6366f1; }
.vsf-toggle-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.15s;
}
.vsf-toggle-btn.active .vsf-toggle-knob { transform: translateX(20px); }
.vsf-toggle-text { font-size: 13px; color: #475569; }

.vsf-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 24px;
}

.vsf-success {
  margin-top: 20px;
}

.vsf-success-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 20px 20px;
  border-radius: 18px;
  background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);
  border: 1px solid #dcfce7;
}

.vsf-success-title {
  font-size: 24px;
  font-weight: 800;
  color: #065f46;
}

.vsf-success-sub {
  font-size: 14px;
  color: #047857;
  text-align: center;
}

.vsf-dl-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #0369a1;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 999px;
  padding: 8px 14px;
}

.vsf-success-btns {
  display: flex;
  gap: 12px;
  margin-top: 6px;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.25s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

@media (max-width: 900px) {
  .vsf-batch-summary,
  .vsf-batch-list {
    grid-template-columns: 1fr;
  }

  .vsf-item-card {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .vsf-page { padding: 18px; }
  .vsf-card { padding: 20px; }
  .vsf-header { align-items: flex-start; }
  .vsf-url-toolbar,
  .vsf-batch-config-head,
  .vsf-actions,
  .vsf-success-btns {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
