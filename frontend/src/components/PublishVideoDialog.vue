<template>
  <el-dialog
    v-model="visible"
    title="发布视频到平台"
    width="600px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div v-loading="loading" class="pvd-content">
      <!-- 视频预览 -->
      <div v-if="videoUrl" class="pvd-video-preview">
        <video :src="videoUrl" class="pvd-preview-video" preload="metadata" controls />
      </div>

      <!-- 基本信息 -->
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="pvd-form">
        <el-form-item label="视频标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入视频标题" maxlength="500" show-word-limit />
        </el-form-item>

        <el-form-item label="视频描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入视频描述（可选）"
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="标签">
          <el-select
            v-model="form.tags"
            multiple
            filterable
            allow-create
            placeholder="请输入或选择标签（可选）"
            style="width: 100%"
          >
            <el-option
              v-for="tag in commonTags"
              :key="tag"
              :label="tag"
              :value="tag"
            />
          </el-select>
        </el-form-item>

        <!-- 发布渠道 -->
        <div class="pvd-section">
          <div class="pvd-section-title">发布渠道</div>
          <div class="pvd-channels-list">
            <div
              v-for="binding in availableBindings"
              :key="binding.platform"
              class="pvd-channel-item"
              :class="{ 'pvd-channel-selected': selectedChannels.has(binding.platform) }"
              @click="toggleChannel(binding)"
            >
              <div class="pvd-channel-info">
                <div class="pvd-platform-badge" :class="`pvd-platform-${binding.platform}`">
                  {{ platformLabel(binding.platform) }}
                </div>
                <div v-if="binding.channel_name" class="pvd-channel-name">
                  {{ binding.channel_name }}
                </div>
              </div>
              <div class="pvd-channel-check">
                <el-checkbox :model-value="selectedChannels.has(binding.platform)" @change="toggleChannel(binding)" />
              </div>
            </div>
          </div>
          <div v-if="!availableBindings.length" class="pvd-no-channels">
            该账号尚未绑定任何平台，请先在编辑页面绑定平台
          </div>
        </div>

        <!-- 渠道自定义配置 -->
        <div v-if="selectedChannels.size > 0" class="pvd-section">
          <div class="pvd-section-title">渠道配置</div>
          <div
            v-for="platform in Array.from(selectedChannels)"
            :key="platform"
            class="pvd-channel-config"
          >
            <div class="pvd-config-header">
              <span class="pvd-config-platform">{{ platformLabel(platform) }}</span>
            </div>
            <el-form-item :label="`${platformLabel(platform)} 标题`">
              <el-input
                v-model="channelConfigs[platform].title"
                :placeholder="form.title || '使用默认标题'"
                clearable
              />
            </el-form-item>
            <el-form-item :label="`${platformLabel(platform)} 描述`">
              <el-input
                v-model="channelConfigs[platform].description"
                type="textarea"
                :rows="2"
                :placeholder="form.description || '使用默认描述'"
              />
            </el-form-item>
            <el-form-item :label="`${platformLabel(platform)} 标签`">
              <el-select
                v-model="channelConfigs[platform].tags"
                multiple
                filterable
                allow-create
                placeholder="使用默认标签"
                style="width: 100%"
              />
            </el-form-item>
          </div>
        </div>
      </el-form>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="publishing" :disabled="selectedChannels.size === 0" @click="handlePublish">
        发布到 {{ selectedChannels.size }} 个平台
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createPublication } from '../api/video_publications'

const props = defineProps({
  modelValue: Boolean,
  videoUrl: String,
  account: Object,
  subTask: Object,
})

const emit = defineEmits(['update:modelValue', 'success'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }
const commonTags = ['AI', '人工智能', '科技', '短视频', '热门', '推荐']

const loading = ref(false)
const publishing = ref(false)
const formRef = ref(null)

const form = reactive({
  title: '',
  description: '',
  tags: [],
})

const rules = {
  title: [{ required: true, message: '请输入视频标题', trigger: 'blur' }],
}

// 可用的绑定平台
const availableBindings = computed(() => {
  return props.account?.social_bindings || []
})

// 已选择的平台
const selectedChannels = ref(new Set())

// 每个平台的配置
const channelConfigs = ref({})

function platformLabel(p) { return PLATFORM_LABELS[p] || p }

function toggleChannel(binding) {
  const platform = binding.platform
  if (selectedChannels.value.has(platform)) {
    selectedChannels.value.delete(platform)
    delete channelConfigs.value[platform]
  } else {
    selectedChannels.value.add(platform)
    channelConfigs.value[platform] = {
      platform,
      channel_id: binding.channel_id,
      title: '',
      description: '',
      tags: [],
      privacy_level: 'public',
    }
  }
}

async function handlePublish() {
  if (selectedChannels.value.size === 0) {
    ElMessage.warning('请至少选择一个发布平台')
    return
  }

  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  publishing.value = true
  try {
    const channels = Array.from(selectedChannels.value).map(platform => {
      const config = channelConfigs.value[platform]
      return {
        platform,
        channel_id: config.channel_id,
        title: config.title || undefined,
        description: config.description || undefined,
        tags: config.tags?.length ? config.tags : undefined,
        privacy_level: config.privacy_level,
      }
    })

    const payload = {
      sub_task_id: props.subTask.id, // 必需：子任务 ID
      video_url: props.videoUrl,
      title: form.title,
      description: form.description || undefined,
      tags: form.tags?.length ? form.tags : undefined,
      channels,
    }

    const result = await createPublication(payload)

    ElMessage.success('发布任务创建成功，正在后台处理...')
    emit('success', result)
    handleClose()
  } catch (err) {
    console.error('发布失败:', err)
    ElMessage.error(err?.response?.data?.detail || err?.message || '发布失败，请稍后重试')
  } finally {
    publishing.value = false
  }
}

function handleClose() {
  visible.value = false
  // 重置表单
  form.title = ''
  form.description = ''
  form.tags = []
  selectedChannels.value.clear()
  channelConfigs.value = {}
}

// 监听打开，初始化数据
watch(() => props.modelValue, (val) => {
  if (val && props.subTask) {
    // 从子任务数据初始化标题
    form.title = props.subTask.title || ''
    form.description = props.subTask.description || ''
    form.tags = props.subTask.tags ? [...props.subTask.tags] : []
  }
})
</script>

<style scoped>
.pvd-content {
  padding: 8px 0;
}

.pvd-video-preview {
  margin-bottom: 20px;
  border-radius: 8px;
  overflow: hidden;
  background: #0f172a;
}

.pvd-preview-video {
  width: 100%;
  max-height: 300px;
  display: block;
  margin: 0 auto;
}

.pvd-form {
  max-height: 500px;
  overflow-y: auto;
  padding-right: 8px;
}

.pvd-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.pvd-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 12px;
}

.pvd-channels-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pvd-channel-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.pvd-channel-item:hover {
  border-color: #cbd5e1;
  background: #f1f5f9;
}

.pvd-channel-item.pvd-channel-selected {
  border-color: #6366f1;
  background: #eef2ff;
}

.pvd-channel-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pvd-platform-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 6px;
}

.pvd-platform-youtube { background: #fef2f2; color: #dc2626; }
.pvd-platform-tiktok { background: #f1f5f9; color: #0f172a; }
.pvd-platform-instagram { background: #fef3c7; color: #92400e; }

.pvd-channel-name {
  font-size: 13px;
  color: #475569;
  font-weight: 500;
}

.pvd-channel-check {
  flex-shrink: 0;
}

.pvd-no-channels {
  padding: 30px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
  background: #f8fafc;
  border-radius: 8px;
}

.pvd-channel-config {
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 12px;
}

.pvd-config-header {
  margin-bottom: 12px;
}

.pvd-config-platform {
  font-size: 13px;
  font-weight: 600;
  color: #6366f1;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  font-size: 13px;
  color: #475569;
}
</style>
