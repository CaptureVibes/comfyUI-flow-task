<template>
  <div class="profile-view">
    <div class="profile-header">
      <h1>个人资料</h1>
      <p class="subtitle">管理您的个人信息和偏好设置</p>
    </div>

    <el-card class="profile-card" shadow="never">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        label-position="left"
        class="profile-form"
      >
        <!-- Avatar upload -->
        <el-form-item label="头像">
          <div class="avatar-section">
            <div class="avatar-preview" :class="{ 'has-avatar': form.avatar_url }">
              <img v-if="form.avatar_url" :src="form.avatar_url" alt="avatar" class="avatar-img" />
              <span v-else class="avatar-placeholder">{{ avatarLetter }}</span>
            </div>
            <div class="avatar-actions">
              <el-upload
                :auto-upload="false"
                :show-file-list="false"
                accept="image/png,image/jpeg,image/gif,image/webp"
                :on-change="handleAvatarSelect"
                :before-upload="beforeAvatarUpload"
              >
                <el-button size="small">
                  <el-icon><Camera /></el-icon>
                  选择图片
                </el-button>
              </el-upload>
              <el-button v-if="form.avatar_url" size="small" type="danger" plain @click="removeAvatar">
                移除
              </el-button>
              <span class="avatar-hint">支持 PNG、JPG、GIF，最大 2MB</span>
            </div>
          </div>
        </el-form-item>

        <!-- Username (read-only) -->
        <el-form-item label="用户名">
          <el-input v-model="profile.username" disabled />
          <span class="field-hint">用户名不可修改</span>
        </el-form-item>

        <!-- Display name -->
        <el-form-item label="显示名称" prop="display_name">
          <el-input
            v-model="form.display_name"
            placeholder="输入您的显示名称"
            maxlength="80"
            show-word-limit
            clearable
          />
          <span class="field-hint">将在界面上显示的名称，可使用中文、emoji 等</span>
        </el-form-item>

        <!-- Bio -->
        <el-form-item label="个性签名" prop="bio">
          <el-input
            v-model="form.bio"
            type="textarea"
            :rows="4"
            placeholder="写一句话介绍自己..."
            maxlength="500"
            show-word-limit
          />
        </el-form-item>

        <!-- Account info (read-only) -->
        <el-divider content-position="left">账户信息</el-divider>

        <el-form-item label="账户 ID">
          <el-input :value="profile.id || '-'" disabled class="id-input" />
          <span class="field-hint">您的唯一标识符</span>
        </el-form-item>

        <el-form-item label="角色">
          <el-tag :type="profile.is_admin ? 'danger' : 'primary'" size="large">
            {{ profile.is_admin ? '管理员' : '普通用户' }}
          </el-tag>
        </el-form-item>

        <el-form-item label="注册时间">
          <span class="static-value">{{ formatDate(profile.created_at) }}</span>
        </el-form-item>

        <!-- Actions -->
        <el-form-item>
          <div class="form-actions">
            <el-button type="primary" :loading="saving" @click="handleSave">
              保存更改
            </el-button>
            <el-button @click="handleReset">重置</el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Quick actions -->
    <el-card class="actions-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>快捷操作</span>
        </div>
      </template>
      <div class="quick-actions">
        <el-button @click="showPasswordDialog = true">
          <el-icon><Lock /></el-icon>
          修改密码
        </el-button>
      </div>
    </el-card>

    <!-- Change password dialog -->
    <el-dialog
      v-model="showPasswordDialog"
      title="修改密码"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="100px"
      >
        <el-form-item label="当前密码" prop="old_password">
          <el-input
            v-model="passwordForm.old_password"
            type="password"
            placeholder="请输入当前密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            placeholder="至少 6 个字符"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="passwordForm.confirm_password"
            type="password"
            placeholder="再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" :loading="changingPassword" @click="handleChangePassword">
          确认修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { Camera, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { changePassword, getProfile, updateProfile } from '../api/auth'
import { getUsername } from '../composables/useAuth'

const profile = reactive({
  id: '',
  username: '',
  display_name: null,
  bio: null,
  avatar_url: null,
  is_admin: false,
  created_at: null
})

const form = reactive({
  display_name: '',
  bio: '',
  avatar_url: ''
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const rules = {
  display_name: [
    { max: 80, message: '显示名称最多 80 个字符', trigger: 'blur' }
  ]
}

const passwordRules = {
  old_password: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, min: 6, message: '新密码至少 6 个字符', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== passwordForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

const formRef = ref(null)
const passwordFormRef = ref(null)
const saving = ref(false)
const changingPassword = ref(false)
const showPasswordDialog = ref(false)

const avatarLetter = computed(() => {
  const name = form.display_name || profile.username || ''
  return (name[0] || '?').toUpperCase()
})

async function loadProfile() {
  try {
    const data = await getProfile()
    Object.assign(profile, data)
    form.display_name = data.display_name || ''
    form.bio = data.bio || ''
    form.avatar_url = data.avatar_url || ''
  } catch (error) {
    // Silently fail - backend may not have migration applied yet
    console.warn('Failed to load profile:', error.response?.data?.detail || error.message)
  }
}

async function handleSave() {
  try {
    saving.value = true
    const payload = {
      display_name: form.display_name || null,
      bio: form.bio || null,
      avatar_url: form.avatar_url || null
    }
    const updated = await updateProfile(payload)
    Object.assign(profile, updated)
    ElMessage.success('个人资料已更新')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新失败')
  } finally {
    saving.value = false
  }
}

function handleReset() {
  form.display_name = profile.display_name || ''
  form.bio = profile.bio || ''
  form.avatar_url = profile.avatar_url || ''
}

// Avatar handling
async function handleAvatarSelect(file) {
  const valid = await beforeAvatarUpload(file.raw)
  if (!valid) return

  // Convert to base64
  const reader = new FileReader()
  reader.onload = (e) => {
    form.avatar_url = e.target.result
  }
  reader.readAsDataURL(file.raw)
}

async function beforeAvatarUpload(file) {
  const isImage = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'].includes(file.type)
  if (!isImage) {
    ElMessage.error('只能上传图片文件')
    return false
  }
  const isLt2M = file.size / 1024 / 1024 < 2
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB')
    return false
  }
  return true
}

function removeAvatar() {
  form.avatar_url = ''
}

async function handleChangePassword() {
  try {
    await passwordFormRef.value.validate()
    changingPassword.value = true
    await changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password
    })
    ElMessage.success('密码已修改，请重新登录')
    showPasswordDialog.value = false
    passwordFormRef.value.resetFields()
    // Optional: redirect to login
    // setTimeout(() => {
    //   logout()
    // }, 1500)
  } catch (error) {
    if (error.errors) {
      // Validation error
      return
    }
    ElMessage.error(error.response?.data?.detail || '修改密码失败')
  } finally {
    changingPassword.value = false
  }
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

onMounted(() => {
  loadProfile()
})
</script>

<style scoped>
.profile-view {
  max-width: 800px;
  margin: 0 auto;
  padding: var(--space-6) var(--space-4);
}

.profile-header {
  margin-bottom: var(--space-6);
}

.profile-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-2) 0;
}

.subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.profile-card,
.actions-card {
  margin-bottom: var(--space-4);
  border: 1px solid var(--border-color);
}

.profile-form {
  max-width: 600px;
}

.field-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
  display: block;
}

.static-value {
  font-size: 14px;
  color: var(--text-secondary);
}

/* Avatar section */
.avatar-section {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
}

.avatar-preview {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-full);
  overflow: hidden;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 3px solid var(--surface-tertiary);
}

.avatar-preview.has-avatar {
  background: transparent;
  border-color: var(--border-color);
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.avatar-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* Form actions */
.form-actions {
  display: flex;
  gap: var(--space-3);
  padding-top: var(--space-4);
}

/* Quick actions */
.card-header {
  font-weight: 600;
  color: var(--text-primary);
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.quick-actions .el-button {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* Divider */
:deep(.el-divider__text) {
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 14px;
}

/* ID input - ensure full UUID is visible */
:deep(.id-input .el-input__inner) {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  font-size: 12px;
}
</style>
