<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <div class="page-title">账号配置</div>
        <div class="page-subtitle">管理社交媒体账号及各平台绑定信息</div>
      </div>
      <el-button type="primary" @click="$router.push('/dashboard/accounts/new')">+ 新建账号</el-button>
    </div>

    <div v-loading="loading" class="card-grid">
      <el-card
        v-for="item in items"
        :key="item.id"
        class="account-card"
        shadow="hover"
      >
        <div class="card-header">
          <div class="avatar-wrap">
            <el-avatar
              v-if="item.avatar_url"
              :src="item.avatar_url"
              :size="40"
            />
            <el-avatar v-else :size="40" icon="User" />
          </div>
          <div class="card-ops">
            <el-button
              size="small"
              plain
              @click="$router.push(`/dashboard/accounts/${item.id}/edit`)"
            >编辑</el-button>
            <el-button
              size="small"
              type="danger"
              plain
              :loading="deleting === item.id"
              @click="handleDelete(item)"
            >删除</el-button>
          </div>
        </div>

        <div class="account-name">{{ item.account_name }}</div>
        <div v-if="item.style_description" class="account-style">{{ item.style_description }}</div>

        <div class="bindings">
          <el-tag
            v-for="binding in (item.social_bindings || [])"
            :key="binding.platform"
            size="small"
            class="binding-tag"
          >{{ platformLabel(binding.platform) }}</el-tag>
        </div>
      </el-card>
    </div>

    <el-empty v-if="!loading && items.length === 0" description="暂无账号，点击「新建账号」开始" />

    <div v-if="total > pageSize" class="pagination">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadData"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchAccounts, deleteAccount } from '../api/accounts'
import { isDuplicateRequestError } from '../api/http'

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }

const loading = ref(false)
const deleting = ref(null)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

function platformLabel(p) { return PLATFORM_LABELS[p] || p }

async function loadData() {
  loading.value = true
  try {
    const data = await fetchAccounts({ page: page.value, page_size: pageSize })
    items.value = data.items || []
    total.value = data.total || 0
  } catch (err) {
    if (isDuplicateRequestError(err)) return
    ElMessage.error(err?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(item) {
  try {
    await ElMessageBox.confirm(`确定删除账号「${item.account_name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
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
.page-container {
  padding: 24px;
  animation: rise 0.35s ease;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #153f7f;
}

.page-subtitle {
  font-size: 13px;
  color: #60748f;
  margin-top: 2px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.account-card {
  border-radius: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.card-ops {
  display: flex;
  gap: 4px;
}

.account-name {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 4px;
}

.account-style {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.bindings {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.binding-tag {
  border-radius: 4px;
}

.pagination {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
