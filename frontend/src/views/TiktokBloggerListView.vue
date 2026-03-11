<template>
  <div class="bl-page">
    <div class="bl-header">
      <h1 class="bl-title">TikTok博主</h1>
      <el-button type="primary" class="bl-add-btn" @click="showAddDialog = true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        新建博主
      </el-button>
    </div>

    <!-- Platform filter tabs -->
    <div class="bl-tabs">
      <button
        v-for="tab in platformTabs"
        :key="tab.value"
        class="bl-tab"
        :class="{ active: selectedPlatform === tab.value }"
        @click="selectedPlatform = tab.value; page = 1; loadData()"
      >{{ tab.label }}</button>
    </div>

    <!-- Card grid -->
    <div v-loading="loading" class="bl-grid">
      <div v-for="item in items" :key="item.id" class="bc">
        <!-- Avatar -->
        <div class="bc-avatar-wrap">
          <img v-if="item.avatar_url" :src="item.avatar_url" class="bc-avatar-img" :alt="item.blogger_name" />
          <div v-else class="bc-avatar-placeholder" :style="{ background: avatarColor(item.blogger_name) }">
            {{ item.blogger_name?.charAt(0)?.toUpperCase() || '?' }}
          </div>
          <span class="bc-platform-badge" :class="`bc-platform-${item.platform}`">
            {{ platformIcon(item.platform) }}
          </span>
        </div>

        <!-- Body -->
        <div class="bc-body">
          <div class="bc-name">{{ item.blogger_name }}</div>
          <div v-if="item.blogger_handle" class="bc-handle">@{{ item.blogger_handle }}</div>
          <div class="bc-count">{{ item.video_count }} 个视频</div>

          <div class="bc-actions" @click.stop>
            <button class="bc-btn bc-btn-view" @click="viewVideos(item)">查看视频</button>
            <button class="bc-btn bc-btn-del" :class="{ loading: deleting === item.id }" @click="handleDelete(item)">删除</button>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-if="!loading && items.length === 0" description="暂无博主，点击「新建博主」开始" :image-size="80" />

    <!-- Pagination -->
    <div v-if="total > 0" class="bl-footer">
      <div class="bl-pagination-left">
        <span class="bl-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
        <select v-model="pageSize" @change="page = 1; loadData()" class="bl-simple-select">
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>
      </div>
      <div class="bl-pagination">
        <button class="pg-btn" :disabled="page <= 1" @click="goPage(page - 1)">← 上一页</button>
        <button class="pg-btn" :disabled="endIdx >= total" @click="goPage(page + 1)">下一页 →</button>
      </div>
    </div>

    <!-- Add dialog -->
    <el-dialog v-model="showAddDialog" title="新建博主" width="480px" @close="profileUrl = ''">
      <div class="add-dialog-body">
        <p class="add-hint">粘贴该博主的主页链接（如 https://www.tiktok.com/@username），系统将自动解析博主信息。</p>
        <el-input
          v-model="profileUrl"
          placeholder="https://www.tiktok.com/@username"
          :disabled="adding"
        />
      </div>
      <template #footer>
        <el-button @click="showAddDialog = false" :disabled="adding">取消</el-button>
        <el-button type="primary" :loading="adding" :disabled="!profileUrl.trim()" @click="handleAdd">
          解析并添加
        </el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchBloggers, createBlogger, deleteBlogger } from '../api/tiktok_bloggers'

const router = useRouter()

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const deleting = ref(null)
const selectedPlatform = ref('')
const showAddDialog = ref(false)
const profileUrl = ref('')
const adding = ref(false)

const platformTabs = [
  { label: '全部', value: '' },
  { label: 'TikTok', value: 'tiktok' },
  { label: 'YouTube', value: 'youtube' },
  { label: 'Instagram', value: 'instagram' },
]

const startIdx = computed(() => (page.value - 1) * pageSize.value + 1)
const endIdx = computed(() => Math.min(page.value * pageSize.value, total.value))

async function loadData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (selectedPlatform.value) params.platform = selectedPlatform.value
    const res = await fetchBloggers(params)
    items.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    ElMessage.error('加载博主列表失败')
  } finally {
    loading.value = false
  }
}

function goPage(p) {
  page.value = p
  loadData()
}

function platformIcon(platform) {
  const icons = { tiktok: '♪', youtube: '▶', instagram: '◈' }
  return icons[platform] || '●'
}

const AVATAR_COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6']
function avatarColor(name) {
  let hash = 0
  for (const c of (name || '?')) hash = (hash * 31 + c.charCodeAt(0)) & 0xffff
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

function viewVideos(item) {
  router.push({ name: 'video-library', query: { tiktok_blogger_id: item.id } })
}

async function handleDelete(item) {
  try {
    await ElMessageBox.confirm(`确认删除博主「${item.blogger_name}」？删除后视频关联将断开，视频本身不受影响。`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  deleting.value = item.id
  try {
    await deleteBlogger(item.id)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) {
    ElMessage.error('删除失败')
  } finally {
    deleting.value = null
  }
}

async function handleAdd() {
  adding.value = true
  try {
    await createBlogger({ profile_url: profileUrl.value.trim() })
    ElMessage.success('博主添加成功')
    showAddDialog.value = false
    profileUrl.value = ''
    await loadData()
  } catch (e) {
    const msg = e.response?.data?.detail || '解析失败，请检查链接是否正确'
    ElMessage.error(msg)
  } finally {
    adding.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.bl-page { padding: 24px 28px; }
.bl-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.bl-title { font-size: 22px; font-weight: 700; color: #1e1e2e; margin: 0; }
.bl-tabs { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.bl-tab { padding: 6px 16px; border-radius: 20px; border: 1.5px solid #e2e8f0; background: #fff; cursor: pointer; font-size: 13px; color: #64748b; transition: all 0.15s; }
.bl-tab.active { background: #6366f1; color: #fff; border-color: #6366f1; }
.bl-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; min-height: 100px; }

.bc { background: #fff; border-radius: 12px; border: 1.5px solid #e2e8f0; padding: 16px; cursor: default; transition: box-shadow 0.15s; display: flex; flex-direction: column; gap: 12px; }
.bc:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }

.bc-avatar-wrap { position: relative; display: flex; justify-content: center; }
.bc-avatar-img { width: 72px; height: 72px; border-radius: 50%; object-fit: cover; }
.bc-avatar-placeholder { width: 72px; height: 72px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; color: #fff; }
.bc-platform-badge { position: absolute; bottom: 0; right: calc(50% - 42px); width: 22px; height: 22px; border-radius: 50%; font-size: 12px; display: flex; align-items: center; justify-content: center; border: 2px solid #fff; }
.bc-platform-tiktok { background: #000; color: #fff; }
.bc-platform-youtube { background: #ff0000; color: #fff; }
.bc-platform-instagram { background: #e1306c; color: #fff; }

.bc-body { display: flex; flex-direction: column; gap: 4px; }
.bc-name { font-size: 15px; font-weight: 600; color: #1e1e2e; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bc-handle { font-size: 12px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bc-count { font-size: 12px; color: #6366f1; font-weight: 500; }
.bc-actions { display: flex; gap: 8px; margin-top: 8px; }
.bc-btn { flex: 1; padding: 5px 0; border-radius: 6px; border: 1.5px solid; font-size: 12px; cursor: pointer; font-weight: 500; transition: all 0.15s; background: transparent; }
.bc-btn-view { border-color: #6366f1; color: #6366f1; }
.bc-btn-view:hover { background: #6366f1; color: #fff; }
.bc-btn-del { border-color: #ef4444; color: #ef4444; }
.bc-btn-del:hover { background: #ef4444; color: #fff; }
.bc-btn-del.loading { opacity: 0.6; pointer-events: none; }

.bl-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 24px; }
.bl-pagination-left { display: flex; align-items: center; gap: 12px; }
.bl-count-text { font-size: 13px; color: #64748b; }
.bl-simple-select { padding: 4px 8px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; }
.bl-pagination { display: flex; gap: 8px; }
.pg-btn { padding: 6px 14px; border-radius: 6px; border: 1.5px solid #e2e8f0; background: #fff; cursor: pointer; font-size: 13px; color: #374151; }
.pg-btn:disabled { opacity: 0.4; cursor: default; }
.pg-btn:not(:disabled):hover { background: #f1f5f9; }

.add-dialog-body { display: flex; flex-direction: column; gap: 12px; }
.add-hint { font-size: 13px; color: #64748b; margin: 0; line-height: 1.5; }
</style>
