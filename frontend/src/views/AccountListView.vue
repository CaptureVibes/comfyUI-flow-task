<template>
  <div class="al-page">
    <div class="al-header">
      <h1 class="al-title">AI博主</h1>
      <div style="display: flex; gap: 12px; align-items: center;">
        <el-button class="al-tasks-btn" @click="$router.push('/dashboard/daily-tasks')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          查看每日任务
        </el-button>
        <el-button class="al-config-btn" @click="openAISettings">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          AI博主配置
        </el-button>
        <el-button
          class="al-config-btn"
          @click="handleBulkGenerateAIAccounts"
          :loading="bulkGenerating"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M12 5v14"/><path d="M5 12h14"/><path d="M4 4h16v16H4z" opacity=".2"/></svg>
          一键生成AI博主
        </el-button>
        <el-button
          class="al-restart-btn"
          @click="handleBulkContinueAIGeneration"
          :loading="bulkRestarting"
          :disabled="items.length === 0"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
          一键继续 AI 生成
        </el-button>
        <el-button type="primary" class="al-add-btn" @click="$router.push('/dashboard/accounts/new')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          新建账号
        </el-button>
      </div>
    </div>

    <!-- AI博主配置弹窗 -->
    <el-dialog
      v-model="showAISettingsDialog"
      title="AI博主配置"
      width="700px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-loading="aiSettingsLoading" class="ai-cfg-body">

        <!-- 阶段一：视频理解 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">阶段一：视频理解</span>
            <span class="ai-cfg-desc">从标签关联的全部视频里随机抽样，生成理解结果并用于名称生成</span>
          </div>
          <el-form-item label="分析样本数">
            <el-input-number v-model="aiSettingsForm.ai_account_analysis_sample_size" :min="1" :max="50" style="width: 160px" />
          </el-form-item>
          <el-form-item label="视频分析提示词">
            <el-input v-model="aiSettingsForm.ai_account_video_prompt" type="textarea" :rows="4" placeholder="请输入视频分析提示词..." />
          </el-form-item>
          <el-form-item label="视频理解模型">
            <el-input v-model="aiSettingsForm.ai_account_video_model" placeholder="e.g. gemini-2.5-flash" />
          </el-form-item>
        </div>

        <!-- 阶段二：名称生成 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">阶段二：名称生成</span>
            <span class="ai-cfg-desc">基于视频描述，调用 Gemini 生成博主名称</span>
          </div>
          <el-form-item label="名称生成提示词">
            <el-input v-model="aiSettingsForm.ai_account_name_prompt" type="textarea" :rows="4" placeholder="请输入名称生成提示词..." />
          </el-form-item>
          <el-form-item label="名称生成模型">
            <el-input v-model="aiSettingsForm.ai_account_name_model" placeholder="e.g. gemini-2.5-flash" />
          </el-form-item>
        </div>

        <!-- 阶段三：照片候选生成 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">阶段三：照片候选生成</span>
            <span class="ai-cfg-desc">随机选择最多 3 个不同视频，每个视频并发生成 3 张照片候选，用户后续手动选择一张进入头像生成</span>
          </div>
          <el-form-item label="视频理解提示词（阶段3-1）">
            <el-input v-model="aiSettingsForm.ai_account_photo_video_prompt" type="textarea" :rows="3" placeholder="描述视频中人物外貌特征，用于生成写实人物照片..." />
          </el-form-item>
          <el-form-item label="照片生成提示词（阶段3-2）">
            <el-input v-model="aiSettingsForm.ai_account_photo_image_prompt" type="textarea" :rows="3" placeholder="Nano2 生图提示词前缀，将与视频描述拼接后调用生图..." />
          </el-form-item>
        </div>

        <!-- 阶段四：头像生成 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">阶段四：头像生成</span>
            <span class="ai-cfg-desc">基于人工选中的照片候选和视频描述生成博主头像</span>
          </div>
          <el-form-item label="头像生成提示词">
            <el-input v-model="aiSettingsForm.ai_account_avatar_prompt" type="textarea" :rows="4" placeholder="请输入头像生成提示词..." />
          </el-form-item>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">
            <el-form-item label="头像生成模型">
              <el-input v-model="aiSettingsForm.ai_account_avatar_model" placeholder="e.g. nano2" />
            </el-form-item>
            <el-form-item label="头像尺寸">
              <el-select v-model="aiSettingsForm.ai_account_avatar_size" style="width:100%">
                <el-option label="1:1 (正方形)" value="1:1" />
                <el-option label="9:16 (竖版)" value="9:16" />
                <el-option label="16:9 (横版)" value="16:9" />
                <el-option label="3:4" value="3:4" />
              </el-select>
            </el-form-item>
            <el-form-item label="头像质量">
              <el-select v-model="aiSettingsForm.ai_account_avatar_quality" style="width:100%">
                <el-option label="1K" value="1K" />
                <el-option label="2K" value="2K" />
                <el-option label="4K" value="4K" />
              </el-select>
            </el-form-item>
          </div>
        </div>

      </div>
      <template #footer>
        <el-button @click="showAISettingsDialog = false">取消</el-button>
        <el-button type="primary" :loading="aiSettingsSaving" @click="saveAISettings">保存配置</el-button>
      </template>
    </el-dialog>

    <!-- Card grid -->
    <div v-loading="loading" class="al-grid">
      <div
        v-for="item in items"
        :key="item.id"
        class="ac"
        @click="goToDetail(item)"
      >
        <!-- Media area -->
        <div class="ac-media-wrap">
          <img
            v-if="item.photo_url"
            :src="item.photo_url"
            class="ac-photo-img"
            :alt="`${item.account_name} 照片`"
            @click.stop="previewMedia(item, 'photo')"
          />
          <div v-else class="ac-photo-placeholder">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.7"><path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14l-5.5-5.5a2 2 0 0 0-2.828 0L4 21V5z"/><circle cx="15" cy="9" r="2"/></svg>
            <span>暂无照片</span>
          </div>
          <button
            type="button"
            class="ac-avatar-float"
            :class="{ 'is-clickable': !!item.avatar_url }"
            @click.stop="previewMedia(item, 'avatar')"
          >
            <img v-if="item.avatar_url" :src="item.avatar_url" class="ac-avatar-img" :alt="`${item.account_name} 头像`" />
            <div v-else class="ac-avatar-placeholder">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            </div>
          </button>
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
          <div class="ac-name-row">
            <div class="ac-name">{{ item.account_name }}</div>
            <span v-if="item.ai_generation_status && item.ai_generation_status !== 'idle'" class="ac-ai-status" :class="`is-${item.ai_generation_status}`">
              {{ aiGenerationStatusLabel(item.ai_generation_status) }}
            </span>
          </div>
          <div v-if="item.style_description" class="ac-style">{{ item.style_description }}</div>
          <div v-if="!item.social_bindings?.length && !item.tiktok_bloggers?.length" class="ac-no-binding">未绑定平台</div>

          <!-- Bound tags -->
          <div v-if="item.bound_tags && item.bound_tags.length > 0" class="ac-tags">
            <div
              v-for="tag in item.bound_tags"
              :key="tag.id"
              class="ac-tag-chip"
            >
              <span class="ac-tag-dot" :style="tag.color ? { background: tag.color } : {}"></span>
              {{ tag.name }}
            </div>
          </div>

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

    <el-dialog
      v-model="previewVisible"
      width="min(92vw, 960px)"
      top="5vh"
      append-to-body
      class="ac-preview-dialog"
    >
      <img v-if="previewImage.url" :src="previewImage.url" :alt="previewImage.title" class="ac-preview-image" />
      <template #header>
        <div class="ac-preview-title">{{ previewImage.title }}</div>
      </template>
    </el-dialog>

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
import { bulkGenerateAIAccounts, fetchAccounts, deleteAccount, restartAIAccountGeneration, resumeAIAccountGeneration } from '../api/accounts'
import { isDuplicateRequestError } from '../api/http'
import { fetchPipelineSettings, updatePipelineSettings } from '../api/settings'

const router = useRouter()

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }
const PLATFORM_ICONS = { youtube: '▶', tiktok: '♪', instagram: '◈' }

const loading = ref(false)
const deleting = ref(null)
const bulkGenerating = ref(false)
const bulkRestarting = ref(false)
const items = ref([])
const previewVisible = ref(false)
const previewImage = ref({ url: '', title: '' })
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// AI 博主配置弹窗
const showAISettingsDialog = ref(false)
const aiSettingsLoading = ref(false)
const aiSettingsSaving = ref(false)
const aiSettingsForm = ref({
  _pipeline: null,
  ai_account_analysis_sample_size: 10,
  ai_account_video_prompt: '',
  ai_account_video_model: 'gemini-3.1-pro-preview',
  ai_account_name_prompt: '',
  ai_account_name_model: 'gemini-2.5-flash',
  ai_account_avatar_prompt: '',
  ai_account_avatar_model: 'gemini-3.1-flash-image-preview',
  ai_account_avatar_size: '1:1',
  ai_account_avatar_quality: '1K',
  ai_account_photo_video_prompt: '',
  ai_account_photo_image_prompt: '',
})

async function openAISettings() {
  showAISettingsDialog.value = true
  aiSettingsLoading.value = true
  try {
    const data = await fetchPipelineSettings()
    aiSettingsForm.value._pipeline = data
    aiSettingsForm.value.ai_account_analysis_sample_size = data.ai_account_analysis_sample_size ?? 10
    aiSettingsForm.value.ai_account_video_prompt = data.ai_account_video_prompt || ''
    aiSettingsForm.value.ai_account_video_model = data.ai_account_video_model || 'gemini-3.1-pro-preview'
    aiSettingsForm.value.ai_account_name_prompt = data.ai_account_name_prompt || ''
    aiSettingsForm.value.ai_account_name_model = data.ai_account_name_model || 'gemini-2.5-flash'
    aiSettingsForm.value.ai_account_avatar_prompt = data.ai_account_avatar_prompt || ''
    aiSettingsForm.value.ai_account_avatar_model = data.ai_account_avatar_model || 'gemini-3.1-flash-image-preview'
    aiSettingsForm.value.ai_account_avatar_size = data.ai_account_avatar_size || '1:1'
    aiSettingsForm.value.ai_account_avatar_quality = data.ai_account_avatar_quality || '1K'
    aiSettingsForm.value.ai_account_photo_video_prompt = data.ai_account_photo_video_prompt || ''
    aiSettingsForm.value.ai_account_photo_image_prompt = data.ai_account_photo_image_prompt || ''
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载配置失败')
  } finally {
    aiSettingsLoading.value = false
  }
}

async function saveAISettings() {
  if (aiSettingsSaving.value) return
  aiSettingsSaving.value = true
  try {
    const base = aiSettingsForm.value._pipeline || {}
    const payload = {
      ...base,
      ai_account_analysis_sample_size: aiSettingsForm.value.ai_account_analysis_sample_size,
      ai_account_video_prompt: aiSettingsForm.value.ai_account_video_prompt,
      ai_account_video_model: aiSettingsForm.value.ai_account_video_model,
      ai_account_name_prompt: aiSettingsForm.value.ai_account_name_prompt,
      ai_account_name_model: aiSettingsForm.value.ai_account_name_model,
      ai_account_avatar_prompt: aiSettingsForm.value.ai_account_avatar_prompt,
      ai_account_avatar_model: aiSettingsForm.value.ai_account_avatar_model,
      ai_account_avatar_size: aiSettingsForm.value.ai_account_avatar_size,
      ai_account_avatar_quality: aiSettingsForm.value.ai_account_avatar_quality,
      ai_account_photo_video_prompt: aiSettingsForm.value.ai_account_photo_video_prompt,
      ai_account_photo_image_prompt: aiSettingsForm.value.ai_account_photo_image_prompt,
    }
    await updatePipelineSettings(payload)
    ElMessage.success('配置已保存')
    showAISettingsDialog.value = false
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    aiSettingsSaving.value = false
  }
}

const startIdx = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const endIdx = computed(() => Math.min(page.value * pageSize.value, total.value))

function platformLabel(p) { return PLATFORM_LABELS[p] || p }
function platformIcon(p) { return PLATFORM_ICONS[p] || '●' }
function aiGenerationStatusLabel(status) {
  const map = {
    pending: '排队中',
    video_analyzing: '分析视频',
    name_generating: '生成名称',
    photo_generating: '生成照片候选',
    awaiting_photo_selection: '待选照片',
    avatar_generating: '生成头像',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

function previewMedia(item, type) {
  const isAvatar = type === 'avatar'
  const url = isAvatar ? item.avatar_url : item.photo_url
  if (!url) return
  previewImage.value = {
    url,
    title: `${item.account_name}${isAvatar ? '头像' : '照片'}`
  }
  previewVisible.value = true
}

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

async function handleBulkContinueAIGeneration() {
  if (bulkRestarting.value) return

  const runningStatuses = ['pending', 'video_analyzing', 'name_generating', 'photo_generating', 'avatar_generating']
  const waitingSelectionAccounts = items.value.filter(i => i.ai_generation_status === 'awaiting_photo_selection')
  const runningAccounts = items.value.filter(i => runningStatuses.includes(i.ai_generation_status))
  const actionableAccounts = items.value.filter(i => ['failed', 'idle'].includes(i.ai_generation_status))
  if (actionableAccounts.length === 0) {
    if (waitingSelectionAccounts.length > 0) {
      ElMessage.info(`有 ${waitingSelectionAccounts.length} 个账号正在等待人工选照片`)
    } else if (runningAccounts.length > 0) {
      ElMessage.info(`有 ${runningAccounts.length} 个账号正在运行或排队中，无需重复继续`)
    } else {
      ElMessage.info('没有需要继续的 AI 生成任务')
    }
    return
  }

  const failedAccounts = actionableAccounts.filter(i => i.ai_generation_status === 'failed')
  const resumableAccounts = actionableAccounts.filter(i => i.ai_generation_status !== 'failed')

  try {
    await ElMessageBox.confirm(
      `确定继续 ${actionableAccounts.length} 个任务？失败任务将从头重跑，其余可继续任务将断点续跑。${runningAccounts.length ? `另有 ${runningAccounts.length} 个账号正在运行或排队中，本次将跳过。` : ''}${waitingSelectionAccounts.length ? `另有 ${waitingSelectionAccounts.length} 个账号等待人工选照片，本次将跳过。` : ''}`,
      '确认继续',
      { confirmButtonText: '确认继续', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  bulkRestarting.value = true
  try {
    await Promise.all([
      ...failedAccounts.map(i => restartAIAccountGeneration(i.id)),
      ...resumableAccounts.map(i => resumeAIAccountGeneration(i.id)),
    ])
    ElMessage.success(`已继续 ${actionableAccounts.length} 个任务`)
    await loadData()
  } catch (err) {
    ElMessage.error('一键继续失败')
  } finally {
    bulkRestarting.value = false
  }
}

async function handleBulkGenerateAIAccounts() {
  if (bulkGenerating.value) return

  try {
    await ElMessageBox.confirm(
      '将根据“已有关联视频、但尚未绑定任何 AI 博主账号”的标签批量创建账号，并统一进入后端队列排队生成。确定继续？',
      '确认生成',
      { confirmButtonText: '开始生成', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  bulkGenerating.value = true
  try {
    const result = await bulkGenerateAIAccounts()
    if (result.status === 'no_tags') {
      ElMessage.info('没有可生成的标签，所有有视频的标签都已绑定 AI 博主')
      return
    }
    ElMessage.success(`已创建并入队 ${result.created_count || 0} 个 AI 博主`)
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '一键生成失败')
  } finally {
    bulkGenerating.value = false
  }
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

/* Media */
.ac-media-wrap {
  position: relative;
  height: 168px;
  background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
  overflow: hidden;
}

.ac-photo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  cursor: zoom-in;
}

.ac-photo-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 12px;
  background: linear-gradient(135deg, #eef2ff 0%, #f8fafc 100%);
}

.ac-avatar-float {
  position: absolute;
  left: 14px;
  bottom: 14px;
  width: 72px;
  height: 72px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ac-avatar-float.is-clickable {
  cursor: zoom-in;
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

.ac-media-tip {
  position: absolute;
  top: 10px;
  left: 10px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(6px);
  padding: 4px 8px;
  border-radius: 999px;
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

.ac-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.ac-name {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex: 1;
}

.ac-ai-status {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
}

.ac-ai-status.is-pending,
.ac-ai-status.is-video_analyzing,
.ac-ai-status.is-name_generating,
.ac-ai-status.is-photo_generating,
.ac-ai-status.is-avatar_generating {
  background: #dbeafe;
  color: #1d4ed8;
}

.ac-ai-status.is-awaiting_photo_selection {
  background: #fef3c7;
  color: #b45309;
}

.ac-ai-status.is-failed {
  background: #fee2e2;
  color: #b91c1c;
}

.ac-ai-status.is-completed {
  background: #dcfce7;
  color: #15803d;
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

/* Account card bound tags */
.ac-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.ac-tag-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 12px;
  color: #334155;
  font-weight: 500;
}

.ac-tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
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

.ac-preview-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.ac-preview-image {
  display: block;
  width: 100%;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 12px;
  background: #f8fafc;
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

.al-config-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(139,92,246,0.2) !important;
  background: rgba(139,92,246,0.05) !important;
  color: #7c3aed !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}

.al-config-btn:hover {
  background: rgba(139,92,246,0.12) !important;
  border-color: rgba(139,92,246,0.4) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(139,92,246,0.15);
}

.al-config-btn:active {
  transform: translateY(1px);
}

.al-restart-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(245,158,11,0.2) !important;
  background: rgba(245,158,11,0.05) !important;
  color: #d97706 !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}

.al-restart-btn:hover {
  background: rgba(245,158,11,0.12) !important;
  border-color: rgba(245,158,11,0.4) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(245,158,11,0.15);
}

.al-restart-btn:active {
  transform: translateY(1px);
}

.al-restart-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
  box-shadow: none !important;
}

/* AI 配置弹窗内容 */
.ai-cfg-body {
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 4px;
}

.ai-cfg-section {
  background: #f8fafc;
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 16px;
  border: 1px solid #e2e8f0;
}

.ai-cfg-section:last-child { margin-bottom: 0; }

.ai-cfg-section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.ai-cfg-tag {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  background: #e2e8f0;
  padding: 3px 10px;
  border-radius: 6px;
  white-space: nowrap;
}

.ai-cfg-desc {
  font-size: 12px;
  color: #94a3b8;
}
</style>
