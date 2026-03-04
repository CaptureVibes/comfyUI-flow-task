<template>
  <el-card class="page-card" v-loading="loading">
    <template #header>
      <div class="header-row">
        <div>
          <div class="page-title">{{ isEdit ? '编辑账号' : '新建账号' }}</div>
          <div class="page-subtitle">配置社交媒体账号基本信息和平台绑定</div>
        </div>
      </div>
    </template>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="form-body">
      <el-form-item label="账号名称" prop="account_name">
        <el-input v-model="form.account_name" placeholder="请输入账号名称" clearable />
      </el-form-item>

      <el-form-item label="风格描述">
        <el-input
          v-model="form.style_description"
          type="textarea"
          :rows="3"
          placeholder="账号风格、定位描述"
        />
      </el-form-item>

      <el-form-item label="模特长相描述">
        <el-input
          v-model="form.model_appearance"
          type="textarea"
          :rows="3"
          placeholder="模特长相描述（用于 AI 参考）"
        />
      </el-form-item>

      <el-form-item label="头像 URL">
        <el-input v-model="form.avatar_url" placeholder="https://..." clearable />
      </el-form-item>

      <el-divider>平台绑定</el-divider>

      <div class="bindings-section">
        <div
          v-for="(binding, idx) in form.social_bindings"
          :key="idx"
          class="binding-block"
        >
          <div class="binding-header">
            <el-select v-model="binding.platform" placeholder="选择平台" style="width: 140px">
              <el-option label="YouTube" value="youtube" />
              <el-option label="TikTok" value="tiktok" />
              <el-option label="Instagram" value="instagram" />
            </el-select>
            <el-button type="danger" size="small" plain @click="removeBinding(idx)">移除</el-button>
          </div>

          <!-- YouTube fields -->
          <template v-if="binding.platform === 'youtube'">
            <el-form-item label="Channel ID">
              <el-input v-model="binding.channel_id" placeholder="UCxxxxxx" clearable />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="binding.api_key" placeholder="AIzaxxxx" clearable show-password />
            </el-form-item>
            <el-form-item label="Refresh Token">
              <el-input v-model="binding.refresh_token" clearable show-password />
            </el-form-item>
          </template>

          <!-- TikTok fields -->
          <template v-if="binding.platform === 'tiktok'">
            <el-form-item label="Open ID">
              <el-input v-model="binding.open_id" clearable />
            </el-form-item>
            <el-form-item label="Access Token">
              <el-input v-model="binding.access_token" clearable show-password />
            </el-form-item>
            <el-form-item label="Refresh Token">
              <el-input v-model="binding.refresh_token" clearable show-password />
            </el-form-item>
            <el-form-item label="Expires In (秒)">
              <el-input-number v-model="binding.expires_in" :min="0" />
            </el-form-item>
          </template>

          <!-- Instagram fields -->
          <template v-if="binding.platform === 'instagram'">
            <el-form-item label="User ID">
              <el-input v-model="binding.user_id" clearable />
            </el-form-item>
            <el-form-item label="Access Token">
              <el-input v-model="binding.access_token" clearable show-password />
            </el-form-item>
            <el-form-item label="Account Type">
              <el-input v-model="binding.account_type" placeholder="BUSINESS / PERSONAL" clearable />
            </el-form-item>
          </template>
        </div>

        <el-button plain @click="addBinding">+ 添加平台绑定</el-button>
      </div>
    </el-form>

    <div class="actions">
      <el-button type="primary" :loading="saving" @click="handleSave">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
      <el-button @click="$router.push('/dashboard/accounts')">取消</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createAccount, fetchAccount, patchAccount } from '../api/accounts'
import { isDuplicateRequestError } from '../api/http'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => Boolean(route.params.id))

const loading = ref(false)
const saving = ref(false)
const formRef = ref(null)

const form = reactive({
  account_name: '',
  style_description: '',
  model_appearance: '',
  avatar_url: '',
  social_bindings: [],
})

const rules = {
  account_name: [{ required: true, message: '请输入账号名称', trigger: 'blur' }],
}

function addBinding() {
  form.social_bindings.push({ platform: 'youtube', channel_id: '', api_key: '', refresh_token: '' })
}

function removeBinding(idx) {
  form.social_bindings.splice(idx, 1)
}

async function loadAccount() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const data = await fetchAccount(route.params.id)
    form.account_name = data.account_name || ''
    form.style_description = data.style_description || ''
    form.model_appearance = data.model_appearance || ''
    form.avatar_url = data.avatar_url || ''
    form.social_bindings = data.social_bindings ? JSON.parse(JSON.stringify(data.social_bindings)) : []
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (saving.value) return
  await formRef.value?.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      const payload = {
        account_name: form.account_name.trim(),
        style_description: form.style_description || null,
        model_appearance: form.model_appearance || null,
        avatar_url: form.avatar_url || null,
        social_bindings: form.social_bindings.length > 0 ? form.social_bindings : null,
      }
      if (isEdit.value) {
        await patchAccount(route.params.id, payload)
        ElMessage.success('已保存')
      } else {
        await createAccount(payload)
        ElMessage.success('已创建')
      }
      router.push('/dashboard/accounts')
    } catch (err) {
      if (isDuplicateRequestError(err)) return
      ElMessage.error(err?.response?.data?.detail || '保存失败')
    } finally {
      saving.value = false
    }
  })
}

onMounted(loadAccount)
</script>

<style scoped>
.page-card {
  animation: rise 0.35s ease;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.form-body {
  max-width: 700px;
}

.bindings-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 700px;
}

.binding-block {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px;
  background: #f8fafc;
}

.binding-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
