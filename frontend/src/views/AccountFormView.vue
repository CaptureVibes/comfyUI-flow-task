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
          <div class="vtfd-section-header" style="justify-content: space-between; display: flex; align-items: center;">
            <span class="vtfd-section-tag">基本信息</span>
            <el-button type="primary" @click="showAIGenDialog = true">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><path d="M12 2l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5z"/></svg>
              AI 生成账号
            </el-button>
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
              <el-form-item label="博主照片">
                <el-upload
                  class="ac-photo-uploader"
                  action=""
                  :show-file-list="false"
                  :auto-upload="true"
                  :http-request="handlePhotoUpload"
                  :before-upload="beforeAvatarUpload"
                >
                  <img v-if="form.photo_url" :src="form.photo_url" class="ac-photo" />
                  <div v-else class="ac-photo-uploader-icon" v-loading="uploadingPhoto">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    <div style="font-size: 11px; margin-top: 4px; color: #94a3b8">上传照片</div>
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
              <template v-if="binding.platform && shouldShowChannelSelect(binding.platform)">
                <el-form-item :label="`${platformLabel(binding.platform)} 频道`">
                  <el-select
                    v-model="binding.channel_id"
                    placeholder="选择要绑定的频道"
                    class="vtfd-beautiful-input"
                    filterable
                    style="width: 100%"
                    @visible-change="visible => handleChannelDropdownVisible(binding, visible)"
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
                    <el-option
                      v-if="isChannelsLoading(binding.platform)"
                      key="__loading__"
                      label="加载中..."
                      value="__loading__"
                      disabled
                    />
                  </el-select>
                </el-form-item>
              </template>

              <!-- 手动输入 Channel ID (当没有从 API 获取到频道时) -->
              <template v-if="binding.platform && shouldShowManualChannelInput(binding.platform)">
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

      <!-- 绑定标签卡片（仅编辑模式显示） -->
      <div v-if="isEdit" class="vtfd-card vtfd-fw-card">
        <div class="vtfd-section">
          <div class="vtfd-section-header" style="justify-content: space-between; display: flex; align-items: center;">
            <span class="vtfd-section-tag">绑定标签</span>
            <el-button type="primary" link @click="openTagBindDialog">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              绑定标签
            </el-button>
          </div>

          <div v-if="boundTags.length === 0" class="vtfd-images-empty" style="padding: 30px;">
            <div class="vtfd-images-empty-text">暂未绑定标签，绑定标签后可用于 AI 生成博主内容</div>
          </div>
          <div v-else class="tag-list">
            <div v-for="tag in boundTags" :key="tag.id" class="tag-bound-item">
              <span class="tag-dot" :style="tag.color ? { background: tag.color } : {}"></span>
              <span class="tag-name">{{ tag.name }}</span>
              <button class="ac-binding-del" @click="handleUnbindTag(tag)" :disabled="tagUnbindingId === tag.id">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- TikTok 博主绑定卡片（仅编辑模式显示） -->
      <div v-if="isEdit" class="vtfd-card vtfd-fw-card">
        <div class="vtfd-section">
          <div class="vtfd-section-header" style="justify-content: space-between; display: flex; align-items: center;">
            <span class="vtfd-section-tag">绑定 TikTok 博主</span>
            <el-button type="primary" link @click="showBindDialog = true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              绑定博主
            </el-button>
          </div>

          <div v-if="boundBloggers.length === 0" class="vtfd-images-empty" style="padding: 30px;">
            <div class="vtfd-images-empty-text">暂未绑定TikTok博主，绑定后可在生成页快速选择博主的模板</div>
          </div>

          <div v-else class="blogger-list">
            <div v-for="blogger in boundBloggers" :key="blogger.id" class="blogger-item">
              <img v-if="blogger.avatar_url" :src="blogger.avatar_url" class="blogger-avatar" />
              <div v-else class="blogger-avatar blogger-avatar-placeholder">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
              </div>
              <div class="blogger-info">
                <div class="blogger-name">{{ blogger.blogger_name }}</div>
                <div class="blogger-handle" v-if="blogger.blogger_handle">@{{ blogger.blogger_handle }}</div>
              </div>
              <button class="ac-binding-del" @click="handleUnbindBlogger(blogger)" :disabled="unbindingId === blogger.id">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </el-form>

    <!-- 标签绑定弹窗 -->
    <el-dialog v-model="showTagBindDialog" title="绑定标签" width="460px" :close-on-click-modal="false">
      <div v-if="allTags.length === 0" style="text-align: center; padding: 20px; color: #94a3b8;">暂无可用标签</div>
      <div v-else class="tag-bind-grid">
        <div
          v-for="tag in allTags"
          :key="tag.id"
          class="tag-bind-item"
          :class="{ 'is-bound': isBoundTag(tag.id) }"
          @click="!isBoundTag(tag.id) && handleBindTag(tag)"
        >
          <span class="tag-dot" :style="tag.color ? { background: tag.color } : {}"></span>
          <span>{{ tag.name }}</span>
          <span v-if="isBoundTag(tag.id)" style="margin-left: auto; font-size: 12px; color: #10b981; font-weight: 600;">已绑定</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="showTagBindDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- AI 生成弹窗 -->
    <el-dialog v-model="showAIGenDialog" title="AI 生成账号" width="520px" :close-on-click-modal="!aiGenerating" :close-on-press-escape="!aiGenerating">
      <div v-if="!aiGenerating">
        <div style="font-size: 13px; color: #64748b; margin-bottom: 16px;">
          选择标签，AI 将分析标签关联的视频（最多10个），自动生成博主名称和头像。
        </div>
        <div style="font-size: 13px; font-weight: 600; color: #334155; margin-bottom: 10px;">选择标签</div>
        <div v-if="allTags.length === 0" style="color: #94a3b8; font-size: 13px; padding: 12px 0;">暂无可用标签，请先在视频库中创建标签。</div>
        <div v-else class="ai-tag-select-grid">
          <div
            v-for="tag in allTags"
            :key="tag.id"
            class="ai-tag-chip"
            :class="{ selected: aiGenSelectedTagIds.includes(tag.id) }"
            @click="toggleAITag(tag.id)"
          >
            <span class="tag-dot" :style="tag.color ? { background: tag.color } : {}"></span>
            {{ tag.name }}
          </div>
        </div>
      </div>
      <div v-else class="ai-gen-progress">
        <el-steps :active="aiProgressStep" finish-status="success" simple style="margin-bottom: 20px;">
          <el-step title="视频分析" />
          <el-step title="名称生成" />
          <el-step title="照片候选" />
          <el-step title="待选照片" />
          <el-step title="头像生成" />
          <el-step title="完成" />
        </el-steps>
        <div class="ai-gen-status-text">
          <span class="ai-gen-spinner" v-if="aiProgressStep < 6"></span>
          {{ aiStatusText }}
        </div>
      </div>
      <template #footer>
        <el-button @click="showAIGenDialog = false" :disabled="aiGenerating">取消</el-button>
        <template v-if="!aiGenerating">
          <el-button
            v-if="aiLastStatus === 'failed'"
            @click="handleResumeAIGeneration"
          >
            断点续跑
          </el-button>
          <el-button
            v-if="aiLastStatus === 'failed'"
            type="warning"
            @click="handleRestartAIGeneration"
          >
            重新生成
          </el-button>
          <el-button
            type="primary"
            @click="startAIGeneration"
            :disabled="aiGenSelectedTagIds.length === 0"
          >
            {{ aiLastStatus === 'failed' ? '重选标签生成' : '开始生成' }}
          </el-button>
        </template>
      </template>
    </el-dialog>

    <!-- 绑定博主弹窗 -->
    <el-dialog v-model="showBindDialog" title="搜索并绑定博主" width="480px" :close-on-click-modal="false">
      <el-input
        v-model="bloggerSearchQ"
        placeholder="输入博主名或 handle 搜索..."
        clearable
        @input="handleBloggerSearch"
        style="margin-bottom: 12px;"
      >
        <template #prefix>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </template>
      </el-input>

      <div v-if="bloggerSearchLoading" style="text-align: center; padding: 20px; color: #94a3b8;">搜索中...</div>

      <div v-else-if="bloggerSearchResults.length === 0" style="text-align: center; padding: 20px; color: #94a3b8;">
        {{ '未找到匹配的博主' }}
      </div>

      <div v-else class="blogger-search-list">
        <div
          v-for="b in bloggerSearchResults"
          :key="b.id"
          class="blogger-search-item"
          :class="{ 'is-bound': isBound(b.id) }"
          @click="!isBound(b.id) && handleBindBlogger(b)"
        >
          <img v-if="b.avatar_url" :src="b.avatar_url" class="blogger-avatar blogger-avatar-sm" />
          <div v-else class="blogger-avatar blogger-avatar-sm blogger-avatar-placeholder">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
          </div>
          <div class="blogger-info">
            <div class="blogger-name">{{ b.blogger_name }}</div>
            <div class="blogger-handle" v-if="b.blogger_handle">@{{ b.blogger_handle }}</div>
          </div>
          <span v-if="isBound(b.id)" style="font-size: 12px; color: #10b981; font-weight: 600;">已绑定</span>
          <el-button v-else type="primary" size="small" :loading="bindingId === b.id" @click.stop="handleBindBlogger(b)">绑定</el-button>
        </div>
      </div>

      <template #footer>
        <el-button @click="showBindDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  createAccount, fetchAccount, patchAccount,
  fetchAccountBloggers, bindBlogger, unbindBlogger,
  fetchAccountTags, bindTagToAccount, unbindTagFromAccount,
  triggerAIAccountGeneration, fetchAIGenerationStatus,
  resumeAIAccountGeneration, restartAIAccountGeneration,
} from '../api/accounts'
import { fetchTags, fetchTagsVideoCount } from '../api/tags'
import { searchBloggers } from '../api/tiktok_bloggers'
import { uploadImageByFile } from '../api/tasks'
import { isDuplicateRequestError } from '../api/http'
import { fetchChannels } from '../api/video_publications'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => Boolean(route.params.id))

const loading = ref(false)
const saving = ref(false)
const uploadingAvatar = ref(false)
const uploadingPhoto = ref(false)
const formRef = ref(null)

// Open API 频道数据
const channelsMap = ref({
  youtube: [],
  tiktok: [],
  instagram: [],
})
const channelPageState = reactive({
  youtube: { page: 0, total: 0, loading: false, loaded: false },
  tiktok: { page: 0, total: 0, loading: false, loaded: false },
  instagram: { page: 0, total: 0, loading: false, loaded: false },
})

const form = reactive({
  account_name: '',
  style_description: '',
  model_appearance: '',
  avatar_url: '',
  photo_url: '',
  social_bindings: [],
})

const rules = {
  account_name: [{ required: true, message: '请输入账号名称', trigger: 'blur' }],
}

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }
const CHANNEL_PAGE_SIZE = 50

function platformLabel(p) { return PLATFORM_LABELS[p] || p }

function isChannelsLoading(platform) {
  return platform ? channelPageState[platform]?.loading : false
}

function shouldShowChannelSelect(platform) {
  if (!platform) return false
  const state = channelPageState[platform]
  return !!(channelsMap.value[platform]?.length || state?.loading || state?.loaded)
}

function shouldShowManualChannelInput(platform) {
  if (!platform) return false
  const state = channelPageState[platform]
  return !!(state?.loaded && !state?.loading && !(channelsMap.value[platform]?.length))
}

function hasMoreChannels(platform) {
  if (!platform) return false
  const state = channelPageState[platform]
  if (!state) return false
  if (!state.loaded) return true
  if (state.total === 0) return false
  return channelsMap.value[platform].length < state.total
}

async function loadChannels(platform, { reset = false } = {}) {
  if (!platform || !channelPageState[platform]) return
  const state = channelPageState[platform]
  if (state.loading) return
  if (reset) {
    channelsMap.value[platform] = []
    state.page = 0
    state.total = 0
    state.loaded = false
  }
  if (state.loaded && !hasMoreChannels(platform)) return

  const nextPage = state.page + 1
  try {
    state.loading = true
    const response = await fetchChannels(platform, { isActive: true, page: nextPage, pageSize: CHANNEL_PAGE_SIZE })
    const data = response?.data || {}
    const pageItems = data.items || []
    state.page = Number(data.page || nextPage)
    state.total = Number(data.total || 0)
    state.loaded = true
    channelsMap.value[platform] = reset ? pageItems : [...channelsMap.value[platform], ...pageItems]
  } catch (err) {
    console.error(`加载 ${platform} 频道失败:`, err)
    // 静默失败，不弹窗提示，允许用户手动输入
    if (reset) {
      channelsMap.value[platform] = []
      state.loaded = true
      state.total = 0
      state.page = 1
    }
  } finally {
    state.loading = false
  }
}

async function handleChannelDropdownVisible(binding, visible) {
  if (!binding?.platform) return
  if (!visible) {
    detachChannelScrollListener(binding)
    return
  }
  if (!channelPageState[binding.platform].loaded) {
    await loadChannels(binding.platform, { reset: true })
  }
  await attachChannelScrollListener(binding)
}

function detachChannelScrollListener(binding) {
  if (binding?._channelScrollEl && binding?._channelScrollHandler) {
    binding._channelScrollEl.removeEventListener('scroll', binding._channelScrollHandler)
  }
  delete binding?._channelScrollEl
  delete binding?._channelScrollHandler
}

async function attachChannelScrollListener(binding) {
  await nextTick()
  detachChannelScrollListener(binding)
  const wraps = Array.from(document.querySelectorAll('.el-select-dropdown__wrap'))
  const target = wraps.at(-1)
  if (!target) return
  const onScroll = async () => {
    const nearBottom = target.scrollTop + target.clientHeight >= target.scrollHeight - 24
    if (nearBottom && hasMoreChannels(binding.platform)) {
      await loadChannels(binding.platform)
    }
  }
  target.addEventListener('scroll', onScroll, { passive: true })
  binding._channelScrollEl = target
  binding._channelScrollHandler = onScroll
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
    await loadChannels(newPlatform, { reset: true })
  }
}

// 处理频道选择，保存频道名称
function handleChannelSelect(binding) {
  const channel = channelsMap.value[binding.platform]?.find(c => c.channel_id === binding.channel_id)
  if (channel) {
    binding.channel_name = channel.channel_name
  }
}

async function addBinding() {
  form.social_bindings.push({
    platform: 'youtube',
    _prevPlatform: '',
    channel_id: '',
    channel_name: ''
  })
  await loadChannels('youtube', { reset: true })
}

function removeBinding(idx) {
  detachChannelScrollListener(form.social_bindings[idx])
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

async function handlePhotoUpload(options) {
  const { file } = options
  try {
    uploadingPhoto.value = true
    const res = await uploadImageByFile(file)
    if (res && res.url) {
      form.photo_url = res.url
      ElMessage.success('照片上传成功')
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '照片上传失败')
  } finally {
    uploadingPhoto.value = false
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
    form.photo_url = data.photo_url || ''
    form.social_bindings = data.social_bindings ? JSON.parse(JSON.stringify(data.social_bindings)) : []
    boundBloggers.value = data.tiktok_bloggers || []
    boundTags.value = data.bound_tags || []

    // 加载已绑定平台的频道列表
    for (const binding of form.social_bindings) {
      if (binding.platform) {
        binding._prevPlatform = binding.platform
        await loadChannels(binding.platform, { reset: true })
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
        photo_url: form.photo_url || null,
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

// ── 标签绑定 ──────────────────────────────────────────────────────────────────
const boundTags = ref([])
const showTagBindDialog = ref(false)
const allTags = ref([])
const tagBindingId = ref(null)
const tagUnbindingId = ref(null)

async function loadBoundTags() {
  if (!isEdit.value) return
  try {
    boundTags.value = await fetchAccountTags(route.params.id)
  } catch {
    // fallback
  }
}

async function loadAllTags() {
  try {
    allTags.value = await fetchTags()
  } catch {
    allTags.value = []
  }
}

function isBoundTag(tagId) {
  return boundTags.value.some(t => t.id === tagId)
}

async function openTagBindDialog() {
  await loadAllTags()
  showTagBindDialog.value = true
}

async function handleBindTag(tag) {
  if (tagBindingId.value) return
  tagBindingId.value = tag.id
  try {
    await bindTagToAccount(route.params.id, tag.id)
    if (!boundTags.value.some(t => t.id === tag.id)) {
      boundTags.value.push(tag)
    }
    ElMessage.success(`已绑定标签：${tag.name}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '绑定失败')
  } finally {
    tagBindingId.value = null
  }
}

async function handleUnbindTag(tag) {
  if (tagUnbindingId.value) return
  tagUnbindingId.value = tag.id
  try {
    await unbindTagFromAccount(route.params.id, tag.id)
    boundTags.value = boundTags.value.filter(t => t.id !== tag.id)
    ElMessage.success(`已解绑标签：${tag.name}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '解绑失败')
  } finally {
    tagUnbindingId.value = null
  }
}

// ── AI 生成 ──────────────────────────────────────────────────────────────────
const showAIGenDialog = ref(false)
const aiGenSelectedTagIds = ref([])
const aiGenerating = ref(false)
const aiProgressStep = ref(0)
const aiStatusText = ref('')
const currentAccountId = ref(null)  // 新建账号时，保存后的 ID
const aiLastStatus = ref('idle')  // 记录上次的生成状态，用于显示续跑/重试按钮
let _aiPollTimer = null

const AI_STATUS_MAP = {
  pending: { step: 0, text: '等待处理...' },
  video_analyzing: { step: 1, text: '正在分析视频...' },
  name_generating: { step: 2, text: '正在生成博主名称...' },
  photo_generating: { step: 3, text: '正在生成照片候选...' },
  awaiting_photo_selection: { step: 4, text: '等待人工选择照片...' },
  avatar_generating: { step: 5, text: '正在生成博主头像...' },
  completed: { step: 6, text: '生成完成！' },
  failed: { step: -1, text: '生成失败' },
}

function toggleAITag(tagId) {
  const idx = aiGenSelectedTagIds.value.indexOf(tagId)
  if (idx === -1) aiGenSelectedTagIds.value.push(tagId)
  else aiGenSelectedTagIds.value.splice(idx, 1)
}

async function startAIGeneration() {
  if (aiGenSelectedTagIds.value.length === 0) {
    ElMessage.warning('请至少选择一个标签')
    return
  }
  if (aiGenerating.value) return

  // 先检查选中标签下是否有视频
  try {
    const result = await fetchTagsVideoCount(aiGenSelectedTagIds.value)
    if (result.total_video_count === 0) {
      ElMessage.error('选中的标签没有关联的视频，无法生成博主内容')
      return
    }
  } catch (err) {
    ElMessage.error('检查标签视频失败')
    return
  }

  // 新建模式：先自动创建账号（用临时占位名，AI生成后会覆盖）
  if (!isEdit.value && !currentAccountId.value) {
    try {
      aiStatusText.value = '正在创建账号...'
      const payload = {
        account_name: form.account_name.trim() || '新建账号（AI生成中）',
        style_description: form.style_description || null,
        model_appearance: form.model_appearance || null,
        avatar_url: form.avatar_url || null,
        photo_url: form.photo_url || null,
        social_bindings: form.social_bindings.length > 0 ? form.social_bindings : null,
      }
      const created = await createAccount(payload)
      currentAccountId.value = created.id
    } catch (err) {
      if (isDuplicateRequestError(err)) return
      ElMessage.error(err?.response?.data?.detail || '创建账号失败')
      return
    }
  }

  aiGenerating.value = true
  aiProgressStep.value = 0
  aiStatusText.value = '正在提交任务...'

  const accountId = currentAccountId.value || route.params.id
  try {
    await triggerAIAccountGeneration(accountId, aiGenSelectedTagIds.value)
    pollAIStatus()
  } catch (err) {
    aiGenerating.value = false
    ElMessage.error(err?.response?.data?.detail || '启动生成失败')
  }
}

function pollAIStatus() {
  clearTimeout(_aiPollTimer)
  const accountId = currentAccountId.value || route.params.id
  _aiPollTimer = setTimeout(async () => {
    try {
      const status = await fetchAIGenerationStatus(accountId)
      const mapped = AI_STATUS_MAP[status.status] || { step: 0, text: status.status }
      aiLastStatus.value = status.status
      aiProgressStep.value = mapped.step
      aiStatusText.value = mapped.text

      if (status.status === 'completed') {
        aiGenerating.value = false
        if (status.generated_name) form.account_name = status.generated_name
        if (status.generated_avatar_url) form.avatar_url = status.generated_avatar_url
        if (status.generated_photo_url) form.photo_url = status.generated_photo_url
        showAIGenDialog.value = false
        ElMessage.success('AI 生成完成，已填充账号信息')
        // 新建模式：跳转到编辑页保存生成结果
        if (!isEdit.value && currentAccountId.value) {
          router.push(`/dashboard/accounts/${currentAccountId.value}/edit`)
        }
        return
      }
      if (status.status === 'awaiting_photo_selection') {
        aiGenerating.value = false
        showAIGenDialog.value = false
        if (status.generated_name) form.account_name = status.generated_name
        ElMessage.info('照片候选已生成，请在账号详情页选择一张后继续生成头像')
        router.push(`/dashboard/accounts/${accountId}`)
        return
      }
      if (status.status === 'failed') {
        aiGenerating.value = false
        ElMessage.error(`AI 生成失败：${status.error_message}`)
        return
      }
      if (aiGenerating.value) pollAIStatus()
    } catch {
      if (aiGenerating.value) pollAIStatus()
    }
  }, 2000)
}

async function handleResumeAIGeneration() {
  if (aiGenerating.value) return
  const accountId = currentAccountId.value || route.params.id
  if (!accountId) return
  aiGenerating.value = true
  aiProgressStep.value = 0
  aiStatusText.value = '正在恢复任务...'
  try {
    await resumeAIAccountGeneration(accountId)
    pollAIStatus()
  } catch (err) {
    aiGenerating.value = false
    ElMessage.error(err?.response?.data?.detail || '恢复失败')
  }
}

async function handleRestartAIGeneration() {
  if (aiGenerating.value) return
  const accountId = currentAccountId.value || route.params.id
  if (!accountId) return
  aiGenerating.value = true
  aiProgressStep.value = 0
  aiStatusText.value = '正在重新生成...'
  try {
    await restartAIAccountGeneration(accountId)
    pollAIStatus()
  } catch (err) {
    aiGenerating.value = false
    ElMessage.error(err?.response?.data?.detail || '重试失败')
  }
}

watch(showAIGenDialog, async (val) => {
  if (val) {
    aiGenSelectedTagIds.value = boundTags.value.map(t => t.id)
    await loadAllTags()
    if (isEdit.value || currentAccountId.value) {
      // Load bound tags for existing account
      const accountId = currentAccountId.value || route.params.id
      try {
        boundTags.value = await fetchAccountTags(accountId)
        aiGenSelectedTagIds.value = boundTags.value.map(t => t.id)
      } catch { /* silent */ }
    }
    // 如果账号已存在，加载当前生成状态
    const accountId = currentAccountId.value || route.params.id
    if (accountId) {
      try {
        const status = await fetchAIGenerationStatus(accountId)
        aiLastStatus.value = status.status
        if (status.status === 'awaiting_photo_selection') {
          showAIGenDialog.value = false
          aiGenerating.value = false
          ElMessage.info('该账号正在等待人工选择照片，请前往详情页继续')
          router.push(`/dashboard/accounts/${accountId}`)
          return
        }
        // 如果正在生成中，自动恢复轮询
        const runningStatuses = ['pending', 'video_analyzing', 'name_generating', 'photo_generating', 'avatar_generating']
        if (runningStatuses.includes(status.status)) {
          aiGenerating.value = true
          const mapped = AI_STATUS_MAP[status.status] || { step: 0, text: status.status }
          aiProgressStep.value = mapped.step
          aiStatusText.value = mapped.text
          pollAIStatus()
        }
      } catch { /* ignore */ }
    }
  } else {
    clearTimeout(_aiPollTimer)
  }
})

// ── TikTok 博主绑定 ───────────────────────────────────────────────────────────
const boundBloggers = ref([])
const showBindDialog = ref(false)
const bloggerSearchQ = ref('')
const bloggerSearchResults = ref([])
const bloggerSearchLoading = ref(false)
const bindingId = ref(null)
const unbindingId = ref(null)

watch(showBindDialog, (val) => {
  if (val) {
    bloggerSearchQ.value = ''
    handleBloggerSearch()
  } else {
    bloggerSearchResults.value = []
  }
})

let _searchTimer = null
function handleBloggerSearch() {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(async () => {
    bloggerSearchLoading.value = true
    try {
      bloggerSearchResults.value = await searchBloggers(bloggerSearchQ.value, 30)
    } catch {
      bloggerSearchResults.value = []
    } finally {
      bloggerSearchLoading.value = false
    }
  }, 300)
}

function isBound(bloggerId) {
  return boundBloggers.value.some(b => b.id === bloggerId)
}

async function loadBoundBloggers() {
  if (!isEdit.value) return
  try {
    boundBloggers.value = await fetchAccountBloggers(route.params.id)
  } catch {
    // fallback: keep whatever was loaded from account response
  }
}

async function handleBindBlogger(blogger) {
  if (bindingId.value) return
  bindingId.value = blogger.id
  try {
    await bindBlogger(route.params.id, blogger.id)
    if (!boundBloggers.value.some(b => b.id === blogger.id)) {
      boundBloggers.value.push(blogger)
    }
    ElMessage.success(`已绑定：${blogger.blogger_name}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '绑定失败')
  } finally {
    bindingId.value = null
  }
}

async function handleUnbindBlogger(blogger) {
  if (unbindingId.value) return
  unbindingId.value = blogger.id
  try {
    await unbindBlogger(route.params.id, blogger.id)
    boundBloggers.value = boundBloggers.value.filter(b => b.id !== blogger.id)
    ElMessage.success(`已解绑：${blogger.blogger_name}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '解绑失败')
  } finally {
    unbindingId.value = null
  }
}

onMounted(async () => {
  await loadAccount()
  await loadBoundBloggers()
  await loadBoundTags()
  // 如果是新建，预加载 YouTube 频道列表
  if (!isEdit.value) {
    await loadChannels('youtube', { reset: true })
  }
})

onUnmounted(() => {
  clearTimeout(_aiPollTimer)
  clearTimeout(_searchTimer)
  for (const binding of form.social_bindings) {
    detachChannelScrollListener(binding)
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

/* Blogger binding */
.blogger-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.blogger-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.blogger-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid #e2e8f0;
}

.blogger-avatar-sm {
  width: 32px;
  height: 32px;
}

.blogger-avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
}

.blogger-info {
  flex: 1;
  min-width: 0;
}

.blogger-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.blogger-handle {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

.blogger-search-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.blogger-search-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.blogger-search-item:hover:not(.is-bound) {
  background: #f1f5f9;
}

.blogger-search-item.is-bound {
  opacity: 0.6;
  cursor: default;
}

/* Photo upload */
.ac-photo-uploader {
  margin-top: 4px;
}

.ac-photo-uploader :deep(.el-upload) {
  border: 2px dashed #cbd5e1;
  border-radius: 12px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  width: 120px;
  height: 80px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f8fafc;
  transition: all 0.2s ease;
}

.ac-photo-uploader :deep(.el-upload:hover) {
  border-color: #818cf8;
  background: #eef2ff;
}

.ac-photo {
  width: 120px;
  height: 80px;
  border-radius: 12px;
  object-fit: cover;
  display: block;
}

.ac-photo-uploader-icon {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

/* Tag bound list */
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-bound-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 13px;
  color: #334155;
}

.tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #818cf8;
  flex-shrink: 0;
}

.tag-name {
  font-weight: 500;
}

/* Tag bind dialog */
.tag-bind-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
}

.tag-bind-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  font-size: 13px;
  color: #334155;
}

.tag-bind-item:hover:not(.is-bound) {
  background: #f1f5f9;
}

.tag-bind-item.is-bound {
  opacity: 0.6;
  cursor: default;
}

/* AI tag select */
.ai-tag-select-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.ai-tag-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  font-size: 13px;
  color: #334155;
  transition: all 0.15s;
}

.ai-tag-chip:hover {
  border-color: #818cf8;
  background: #eef2ff;
}

.ai-tag-chip.selected {
  border-color: #818cf8;
  background: #eef2ff;
  color: #6366f1;
  font-weight: 600;
}

/* AI gen progress */
.ai-gen-progress {
  padding: 8px 0;
}

.ai-gen-status-text {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #64748b;
  justify-content: center;
  margin-top: 8px;
}

.ai-gen-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #e2e8f0;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
