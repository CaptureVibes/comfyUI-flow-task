<template>
  <div class="vtfd-page" v-loading="loading">
    <!-- Header -->
    <div class="vtfd-header">
      <div class="vtfd-header-left">
        <h1 class="vtfd-title">{{ isEdit ? '编辑账号' : '新建账号' }}</h1>
        <div class="vtfd-subtitle">配置社交媒体账号基本信息和平台绑定</div>
      </div>
      <div class="vtfd-header-actions">
        <el-button @click="isEdit ? $router.push(`/dashboard/accounts/${route.params.id}`) : $router.push('/dashboard/accounts')">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
          {{ isEdit ? '保存修改' : '创建账号' }}
        </el-button>
      </div>
    </div>

    <!-- Main Content -->
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="vtfd-layout">
      
      <!-- Base Info Card -->
      <div class="vtfd-card vtfd-fw-card">
        <div class="vtfd-section">
          <div class="vtfd-section-header">
            <span class="vtfd-section-tag">基本信息</span>
          </div>

          <div class="ac-form-grid">
            <div class="ac-form-left">
              <el-form-item label="账号名称" prop="account_name">
                <el-input v-model="form.account_name" placeholder="请输入账号名称" clearable class="vtfd-beautiful-input" />
              </el-form-item>
              
              <el-form-item label="风格描述">
                <el-input
                  v-model="form.style_description"
                  type="textarea"
                  :rows="3"
                  placeholder="账号风格、定位描述"
                  class="vtfd-beautiful-input"
                />
              </el-form-item>

              <el-form-item label="模特长相描述">
                <el-input
                  v-model="form.model_appearance"
                  type="textarea"
                  :rows="3"
                  placeholder="模特长相描述（用于 AI 参考）"
                  class="vtfd-beautiful-input"
                />
              </el-form-item>
            </div>

            <div class="ac-form-right">
              <el-form-item label="账号头像">
                <el-upload
                  class="ac-avatar-uploader"
                  action=""
                  :show-file-list="false"
                  :auto-upload="true"
                  :http-request="handleAvatarUpload"
                  :before-upload="beforeAvatarUpload"
                >
                  <img v-if="form.avatar_url" :src="form.avatar_url" class="ac-avatar" />
                  <div v-else class="ac-avatar-uploader-icon" v-loading="uploadingAvatar">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    <div style="font-size: 12px; margin-top: 4px; color: #94a3b8">上传头像</div>
                  </div>
                </el-upload>
              </el-form-item>
            </div>
          </div>
        </div>
      </div>

      <!-- Bindings Card -->
      <div class="vtfd-card vtfd-fw-card vtfd-bindings-card">
        <div class="vtfd-section">
          <div class="vtfd-section-header" style="justify-content: space-between; display: flex; align-items: center;">
            <span class="vtfd-section-tag">平台绑定</span>
            <el-button type="primary" link @click="addBinding">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              添加平台
            </el-button>
          </div>

          <div class="bindings-grid">
            <div
              v-for="(binding, idx) in form.social_bindings"
              :key="idx"
              class="ac-binding-block"
            >
              <div class="ac-binding-header">
                <el-select
                  v-model="binding.platform"
                  placeholder="选择平台"
                  class="vtfd-beautiful-input"
                  style="width: 140px"
                  @change="handlePlatformChange(binding)"
                >
                  <el-option label="YouTube" value="youtube" />
                  <el-option label="TikTok" value="tiktok" />
                  <el-option label="Instagram" value="instagram" />
                </el-select>
                <button class="ac-binding-del" @click.prevent="removeBinding(idx)">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>

              <!-- 频道选择 (从 Open API 获取) -->
              <template v-if="binding.platform && channelsMap[binding.platform]?.length">
                <el-form-item :label="`${platformLabel(binding.platform)} 频道`">
                  <el-select
                    v-model="binding.channel_id"
                    placeholder="选择要绑定的频道"
                    class="vtfd-beautiful-input"
                    filterable
                    style="width: 100%"
                    @change="handleChannelSelect(binding)"
                  >
                    <el-option
                      v-for="channel in channelsMap[binding.platform]"
                      :key="channel.channel_id"
                      :label="`${channel.channel_name} (@${channel.username || 'N/A'})`"
                      :value="channel.channel_id"
                    >
                      <div style="display: flex; align-items: center; gap: 8px;">
                        <img
                          v-if="channel.thumbnail_url"
                          :src="channel.thumbnail_url"
                          style="width: 24px; height: 24px; border-radius: 50%;"
                        />
                        <span>{{ channel.channel_name }}</span>
                        <span style="color: #94a3b8; font-size: 12px;">(@{{ channel.username || 'N/A' }})</span>
                      </div>
                    </el-option>
                  </el-select>
                </el-form-item>
              </template>

              <!-- 手动输入 Channel ID (当没有从 API 获取到频道时) -->
              <template v-if="binding.platform && !channelsMap[binding.platform]?.length">
                <el-form-item :label="`${platformLabel(binding.platform)} Channel ID`">
                  <el-input
                    v-model="binding.channel_id"
                    :placeholder="`${platformLabel(binding.platform)} Channel ID`"
                    clearable
                    class="vtfd-beautiful-input"
                  />
                </el-form-item>
                <el-form-item :label="`${platformLabel(binding.platform)} 频道名称`">
                  <el-input
                    v-model="binding.channel_name"
                    placeholder="频道名称（用于显示）"
                    clearable
                    class="vtfd-beautiful-input"
                  />
                </el-form-item>
              </template>
            </div>
          </div>
          
          <div v-if="!form.social_bindings || form.social_bindings.length === 0" class="vtfd-images-empty" style="margin-top: 10px; padding: 30px;">
            <div class="vtfd-images-empty-text">尚未绑定任何平台，点击右上角添加</div>
          </div>
        </div>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createAccount, fetchAccount, patchAccount } from '../api/accounts'
import { uploadImageByFile } from '../api/tasks'
import { isDuplicateRequestError } from '../api/http'
import { fetchChannels } from '../api/video_publications'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => Boolean(route.params.id))

const loading = ref(false)
const saving = ref(false)
const uploadingAvatar = ref(false)
const formRef = ref(null)

// Open API 频道数据
const channelsMap = ref({
  youtube: [],
  tiktok: [],
  instagram: [],
})
const channelsLoading = ref(false)

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

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }

function platformLabel(p) { return PLATFORM_LABELS[p] || p }

// 加载 Open API 频道列表
async function loadChannels(platform) {
  // 避免重复加载
  if (channelsLoading.value) return
  // 如果已经加载过，不再重复加载
  if (channelsMap.value[platform]?.length > 0) return

  try {
    channelsLoading.value = true
    const response = await fetchChannels(platform, { is_active: true })
    channelsMap.value[platform] = response.data?.items || []
  } catch (err) {
    console.error(`加载 ${platform} 频道失败:`, err)
    // 静默失败，不弹窗提示，允许用户手动输入
    channelsMap.value[platform] = []
  } finally {
    channelsLoading.value = false
  }
}

// 监听平台选择变化，自动加载对应频道列表
async function handlePlatformChange(binding) {
  const oldPlatform = binding._prevPlatform
  const newPlatform = binding.platform

  // 清空之前的频道选择
  delete binding._prevPlatform
  binding.channel_id = ''
  binding.channel_name = ''

  // 如果平台变了，加载新的频道列表
  if (newPlatform && newPlatform !== oldPlatform) {
    await loadChannels(newPlatform)
  }
}

// 处理频道选择，保存频道名称
function handleChannelSelect(binding) {
  const channel = channelsMap.value[binding.platform]?.find(c => c.channel_id === binding.channel_id)
  if (channel) {
    binding.channel_name = channel.channel_name
  }
}

function addBinding() {
  form.social_bindings.push({
    platform: 'youtube',
    _prevPlatform: '',
    channel_id: '',
    channel_name: ''
  })
}

function removeBinding(idx) {
  form.social_bindings.splice(idx, 1)
}

async function handleAvatarUpload(options) {
  const { file } = options
  try {
    uploadingAvatar.value = true
    const res = await uploadImageByFile(file)
    if (res && res.url) {
      form.avatar_url = res.url
      ElMessage.success('头像上传成功')
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '头像上传失败')
  } finally {
    uploadingAvatar.value = false
  }
}

function beforeAvatarUpload(file) {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 5

  if (!isImage) {
    ElMessage.error('只能上传图片文件！')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 5MB！')
    return false
  }
  return true
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

    // 加载已绑定平台的频道列表
    for (const binding of form.social_bindings) {
      if (binding.platform) {
        binding._prevPlatform = binding.platform
        await loadChannels(binding.platform)
      }
    }
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
        router.push(`/dashboard/accounts/${route.params.id}`)
      } else {
        const created = await createAccount(payload)
        ElMessage.success('已创建')
        router.push(`/dashboard/accounts/${created.id}`)
      }
    } catch (err) {
      if (isDuplicateRequestError(err)) return
      ElMessage.error(err?.response?.data?.detail || '保存失败')
    } finally {
      saving.value = false
    }
  })
}

onMounted(async () => {
  await loadAccount()
  // 如果是新建，预加载 YouTube 频道列表
  if (!isEdit.value) {
    await loadChannels('youtube')
  }
})
</script>

<style scoped>
.vtfd-page {
  padding: 30px;
  max-width: 1200px;
  margin: 0 auto;
  min-height: 100vh;
  animation: vtfd-fade-in 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes vtfd-fade-in {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}

.vtfd-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.vtfd-title {
  font-size: 24px;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 6px 0;
  letter-spacing: -0.02em;
}

.vtfd-subtitle {
  font-size: 14px;
  color: #64748b;
}

.vtfd-header-actions {
  display: flex;
  gap: 12px;
}

.vtfd-layout {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Card base */
.vtfd-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 20px -10px rgba(0,0,0,0.05);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.vtfd-fw-card {
  width: 100%;
}

.vtfd-section {
  padding: 24px;
}

.vtfd-section-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.vtfd-section-tag {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
  background: #f1f5f9;
  padding: 4px 12px;
  border-radius: 8px;
  letter-spacing: 0.5px;
}

/* Grid layout for base info */
.ac-form-grid {
  display: flex;
  gap: 40px;
}

.ac-form-left {
  flex: 1;
}

.ac-form-right {
  width: 160px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* Base form overrides */
:deep(.el-form-item__label) {
  font-weight: 600;
  color: #334155;
  padding-bottom: 6px;
}

/* Beautiful Inputs */
.vtfd-beautiful-input :deep(.el-input__wrapper),
.vtfd-beautiful-input :deep(.el-textarea__inner) {
  background-color: #f8fafc;
  border-radius: 10px;
  box-shadow: none !important;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.vtfd-beautiful-input :deep(.el-input__wrapper:hover),
.vtfd-beautiful-input :deep(.el-textarea__inner:hover) {
  background-color: #f1f5f9;
}

.vtfd-beautiful-input :deep(.el-input__wrapper.is-focus),
.vtfd-beautiful-input :deep(.el-textarea__inner:focus) {
  background-color: #ffffff;
  border-color: #818cf8;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}

/* Fix input contrast inside binding blocks */
.ac-binding-block .vtfd-beautiful-input :deep(.el-input__wrapper),
.ac-binding-block .vtfd-beautiful-input :deep(.el-select__wrapper) {
  background-color: #ffffff;
}

.ac-binding-block .vtfd-beautiful-input :deep(.el-input__wrapper:hover),
.ac-binding-block .vtfd-beautiful-input :deep(.el-select__wrapper:hover) {
  background-color: #f1f5f9;
}

/* Avatar Upload */
.ac-avatar-uploader {
  margin-top: 10px;
}

.ac-avatar-uploader :deep(.el-upload) {
  border: 2px dashed #cbd5e1;
  border-radius: 50%;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  width: 120px;
  height: 120px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f8fafc;
  transition: all 0.2s ease;
}

.ac-avatar-uploader :deep(.el-upload:hover) {
  border-color: #818cf8;
  background: #eef2ff;
}

.ac-avatar {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  object-fit: cover;
  display: block;
}

.ac-avatar-uploader-icon {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

/* Bindings Grid */
.bindings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.ac-binding-block {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 20px;
  transition: all 0.2s;
}

.ac-binding-block:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(0,0,0,0.03);
  transform: translateY(-2px);
}

.ac-binding-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #cbd5e1;
}

.ac-binding-del {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #fef2f2;
  color: #ef4444;
  border: 1px solid #fecaca;
  cursor: pointer;
  transition: all 0.15s;
}

.ac-binding-del:hover {
  background: #fee2e2;
  border-color: #fca5a5;
  color: #dc2626;
  transform: scale(1.05);
}

/* Empty texts */
.vtfd-images-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px dashed #e2e8f0;
}

.vtfd-images-empty-text {
  font-size: 13px;
  color: #94a3b8;
  font-weight: 500;
}
</style>
