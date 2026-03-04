<template>
  <el-card class="page-card">
    <template #header>
      <div class="header-row">
        <div>
          <div class="page-title">用户管理</div>
          <div class="page-subtitle">管理系统用户账户</div>
        </div>
        <el-button type="primary" @click="showCreateDialog = true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
            style="margin-right:5px">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          新建用户
        </el-button>
      </div>
    </template>

    <el-table :data="users" v-loading="loading" class="user-table">
      <el-table-column label="用户名" prop="username" />
      <el-table-column label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_admin ? 'warning' : 'info'" size="small">
            {{ row.is_admin ? '管理员' : '普通用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="right">
        <template #default="{ row }">
          <el-button
            v-if="row.username !== currentUsername"
            type="danger"
            size="small"
            text
            @click="handleDelete(row)"
          >删除</el-button>
          <el-tag v-else type="info" size="small">当前账号</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <!-- Change password section -->
    <el-divider />
    <div class="section-title">修改我的密码</div>
    <el-form :model="pwForm" label-position="top" class="pw-form" style="max-width:400px">
      <el-form-item label="当前密码">
        <el-input v-model="pwForm.old_password" type="password" show-password clearable />
      </el-form-item>
      <el-form-item label="新密码（至少6位）">
        <el-input v-model="pwForm.new_password" type="password" show-password clearable />
      </el-form-item>
      <el-form-item label="确认新密码">
        <el-input v-model="pwForm.confirm_password" type="password" show-password clearable />
      </el-form-item>
      <el-button type="primary" :loading="changingPw" @click="handleChangePassword">保存新密码</el-button>
    </el-form>
  </el-card>

  <!-- Create user dialog -->
  <el-dialog v-model="showCreateDialog" title="新建用户" width="400px" destroy-on-close>
    <el-form :model="createForm" label-position="top">
      <el-form-item label="用户名">
        <el-input v-model="createForm.username" clearable placeholder="3-50 个字符" />
      </el-form-item>
      <el-form-item label="密码（至少6位）">
        <el-input v-model="createForm.password" type="password" show-password clearable />
      </el-form-item>
      <el-form-item label="角色">
        <el-switch
          v-model="createForm.is_admin"
          active-text="管理员"
          inactive-text="普通用户"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showCreateDialog = false">取消</el-button>
      <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, createUser, deleteUser, changePassword } from '../api/auth'
import { useAuth } from '../composables/useAuth'
import { formatTime } from '../utils/datetime'

const { getUsername } = useAuth()
const currentUsername = getUsername()

const loading = ref(false)
const users = ref([])

const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = reactive({ username: '', password: '', is_admin: false })

const changingPw = ref(false)
const pwForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

async function loadUsers() {
  loading.value = true
  try {
    const res = await listUsers()
    users.value = res.items
  } catch {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!createForm.username.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (createForm.password.length < 6) {
    ElMessage.warning('密码至少6位')
    return
  }
  creating.value = true
  try {
    await createUser({ ...createForm })
    ElMessage.success('用户创建成功')
    showCreateDialog.value = false
    Object.assign(createForm, { username: '', password: '', is_admin: false })
    await loadUsers()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确认删除用户「${row.username}」？`, '删除用户', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
  try {
    await deleteUser(row.id)
    ElMessage.success('已删除')
    await loadUsers()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  }
}

async function handleChangePassword() {
  if (!pwForm.old_password || !pwForm.new_password) {
    ElMessage.warning('请填写完整')
    return
  }
  if (pwForm.new_password !== pwForm.confirm_password) {
    ElMessage.warning('两次密码不一致')
    return
  }
  changingPw.value = true
  try {
    await changePassword({ old_password: pwForm.old_password, new_password: pwForm.new_password })
    ElMessage.success('密码修改成功')
    Object.assign(pwForm, { old_password: '', new_password: '', confirm_password: '' })
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '修改失败')
  } finally {
    changingPw.value = false
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.page-card {
  margin: var(--space-6);
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.user-table {
  width: 100%;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-4);
}

.pw-form {
  margin-top: var(--space-2);
}
</style>
