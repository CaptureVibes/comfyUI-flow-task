<template>
  <div class="al-page">
    <div class="al-header">
      <h1 class="al-title">AI博主</h1>
      <div style="display: flex; gap: 12px; align-items: center;">
        <el-button class="al-tasks-btn" @click="$router.push('/dashboard/daily-tasks')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          查看每日任务
        </el-button>
        <el-button type="primary" class="al-add-btn" @click="$router.push('/dashboard/accounts/new')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          新建账号
        </el-button>
      </div>
    </div>

    <!-- Card grid -->
    <div v-loading="loading" class="al-grid">
      <div
        v-for="item in items"
        :key="item.id"
        class="ac"
        @click="goToDetail(item)"
      >
        <!-- Avatar area -->
        <div class="ac-avatar-wrap">
          <img v-if="item.avatar_url" :src="item.avatar_url" class="ac-avatar-img" :alt="item.account_name" />
          <div v-else class="ac-avatar-placeholder">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
          </div>
          <!-- Platform badges -->
          <div class="ac-platforms">
            <span
              v-for="binding in (item.social_bindings || [])"
              :key="binding.platform"
              class="ac-platform-dot"
              :class="`ac-platform-${binding.platform}`"
              :title="platformLabel(binding.platform)"
            >{{ platformIcon(binding.platform) }}</span>
          </div>
        </div>

        <!-- Body -->
        <div class="ac-body">
          <div class="ac-name">{{ item.account_name }}</div>
          <div v-if="item.style_description" class="ac-style">{{ item.style_description }}</div>
          <div v-if="!item.social_bindings?.length && !item.tiktok_bloggers?.length" class="ac-no-binding">未绑定平台</div>

          <!-- Bound TikTok bloggers -->
          <div v-if="item.tiktok_bloggers?.length" class="ac-bloggers">
            <div
              v-for="blogger in item.tiktok_bloggers"
              :key="blogger.id"
              class="ac-blogger-chip"
              :title="blogger.blogger_name + (blogger.blogger_handle ? ' @' + blogger.blogger_handle : '')"
            >
              <img v-if="blogger.avatar_url" :src="blogger.avatar_url" class="ac-blogger-avatar" />
              <div v-else class="ac-blogger-avatar ac-blogger-avatar-ph">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
              </div>
              <span class="ac-blogger-name">{{ blogger.blogger_name }}</span>
            </div>
          </div>

          <div class="ac-footer">
            <div class="ac-binding-tags">
              <span
                v-for="binding in (item.social_bindings || [])"
                :key="binding.platform"
                class="ac-tag"
                :class="`ac-tag-${binding.platform}`"
              >{{ platformLabel(binding.platform) }}</span>
            </div>
            <div class="ac-actions" @click.stop>
              <button
                class="ac-btn ac-btn-edit"
                @click="$router.push(`/dashboard/accounts/${item.id}/edit`)"
              >编辑</button>
              <button
                class="ac-btn ac-btn-del"
                :class="{ loading: deleting === item.id }"
                @click="handleDelete(item)"
              >删除</button>
            </div>
          </div>
        </div>
      </div>

    </div>

    <el-empty v-if="!loading && items.length === 0" description="暂无账号，点击「新建账号」开始" :image-size="80" />

    <!-- Footer pagination -->
    <div v-if="total > 0" class="al-footer">
      <div class="al-pagination-left">
        <span class="al-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
        <select v-model="pageSize" @change="handleSizeChange(pageSize)" class="al-simple-select">
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="500">500</option>
        </select>
      </div>
      <div class="al-pagination">
        <button class="pg-btn" :disabled="page <= 1" @click="goPage(page - 1)">← 上一页</button>
        <button class="pg-btn" :disabled="endIdx >= total" @click="goPage(page + 1)">下一页 →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchAccounts, deleteAccount } from '../api/accounts'
import { isDuplicateRequestError } from '../api/http'

const router = useRouter()

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }
const PLATFORM_ICONS = { youtube: '▶', tiktok: '♪', instagram: '◈' }

const loading = ref(false)
const deleting = ref(null)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const startIdx = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const endIdx = computed(() => Math.min(page.value * pageSize.value, total.value))

function platformLabel(p) { return PLATFORM_LABELS[p] || p }
function platformIcon(p) { return PLATFORM_ICONS[p] || '●' }

function goToDetail(item) {
  router.push(`/dashboard/accounts/${item.id}`)
}

async function loadData() {
  loading.value = true
  try {
    const data = await fetchAccounts({ page: page.value, page_size: pageSize.value })
    items.value = data.items || []
    total.value = data.total || 0
  } catch (err) {
    if (isDuplicateRequestError(err)) return
    ElMessage.error(err?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function goPage(p) {
  page.value = p
  loadData()
}

function handleSizeChange(val) {
  pageSize.value = val
  page.value = 1
  loadData()
}

async function handleDelete(item) {
  try {
    await ElMessageBox.confirm(
      `确定删除账号「${item.account_name}」？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning', customClass: 'premium-delete-dialog' }
    )
  } catch { return }

  deleting.value = item.id
  try {
    await deleteAccount(item.id)
    ElMessage.success('已删除')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = null
  }
}

onMounted(loadData)
</script>

<style scoped>
.al-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
}

.al-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}

.al-title {
  font-size: 26px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.03em;
  margin: 0;
}

.al-add-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
}

/* Grid */
.al-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 20px;
  margin-bottom: 28px;
}

/* Account card */
.ac {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,.05);
  transition: box-shadow 0.2s, transform 0.2s;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}

.ac:hover {
  box-shadow: 0 8px 24px rgba(0,0,0,.1);
  transform: translateY(-2px);
}

/* Avatar */
.ac-avatar-wrap {
  position: relative;
  height: 120px;
  background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.ac-avatar-img {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,.12);
}

.ac-avatar-placeholder {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,.08);
}

.ac-platforms {
  position: absolute;
  bottom: 10px;
  right: 10px;
  display: flex;
  gap: 4px;
}

.ac-platform-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,.2);
}

.ac-platform-youtube { background: #ef4444; }
.ac-platform-tiktok  { background: #010101; }
.ac-platform-instagram { background: linear-gradient(135deg, #f59e0b, #ef4444, #8b5cf6); }

/* Body */
.ac-body {
  padding: 14px 16px 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.ac-name {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ac-style {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
  flex: 1;
}

.ac-no-binding {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 10px;
  flex: 1;
}

.ac-bloggers {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.ac-blogger-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  background: #f8faff;
  border: 1px solid #e0e7ff;
  border-radius: 20px;
  padding: 3px 8px 3px 3px;
  max-width: 100%;
}

.ac-blogger-avatar {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.ac-blogger-avatar-ph {
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ac-blogger-name {
  font-size: 11px;
  font-weight: 500;
  color: #4f46e5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100px;
}

.ac-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #f1f5f9;
  padding-top: 10px;
  margin-top: 4px;
}

.ac-binding-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.ac-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
}

.ac-tag-youtube  { background: #fef2f2; color: #dc2626; }
.ac-tag-tiktok   { background: #f1f5f9; color: #0f172a; }
.ac-tag-instagram { background: #fef3c7; color: #92400e; }

.ac-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.ac-btn {
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 7px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  flex-shrink: 0;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ac-btn-edit:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.ac-btn-del {
  border-color: #fecaca;
  color: #dc2626;
  background: #fef2f2;
}

.ac-btn-del:hover {
  border-color: #fca5a5;
  color: #b91c1c;
  background: #fee2e2;
}

.ac-btn.loading {
  opacity: 0.5;
  pointer-events: none;
}

/* Footer */
.al-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0 8px;
  border-top: 1px solid #f1f5f9;
}

.al-pagination-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.al-count-text {
  font-size: 13px;
  color: #94a3b8;
}

.al-simple-select {
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  padding: 0 4px;
}

.al-simple-select:hover {
  color: #64748b;
}

.al-pagination {
  display: flex;
  gap: 8px;
}

.pg-btn {
  font-size: 13px;
  font-weight: 500;
  padding: 7px 16px;
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

.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (max-width: 640px) {
  .al-page { padding: 16px; }
  .al-grid { grid-template-columns: 1fr 1fr; gap: 12px; }
}

.al-tasks-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(99,102,241,0.2) !important;
  background: rgba(99,102,241,0.05) !important;
  color: #4f46e5 !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}

.al-tasks-btn:hover {
  background: rgba(99,102,241,0.12) !important;
  border-color: rgba(99,102,241,0.4) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99,102,241,0.15);
}

.al-tasks-btn:active {
  transform: translateY(1px);
}
</style>
