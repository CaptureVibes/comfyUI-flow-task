<template>
  <div class="vtfd-page" v-loading="loading">
    <!-- Header -->
    <div class="vtfd-header">
      <div class="vtfd-header-left">
        <h1 class="vtfd-title">视频生成工厂</h1>
        <div class="vtfd-subtitle">合并账号配置与AI分析，生成最终的高质量视频</div>
      </div>
      <div class="vtfd-header-actions">
        <el-button @click="$router.push(`/dashboard/accounts/${accountId}`)">取消</el-button>
        <!-- 单模板模式 -->
        <el-button
          v-if="!batchMode"
          type="primary"
          :loading="generating"
          @click="handleGenerate"
          :disabled="!isReady"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          开始生成阶段
        </el-button>
        <!-- 批量模式 -->
        <el-button
          v-else
          type="primary"
          :loading="batchGenerating"
          @click="handleBatchGenerate"
          :disabled="!batchIsReady"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          批量生成 {{ batchSelected.length > 0 ? `(${batchSelected.length})` : '' }}
        </el-button>
      </div>
    </div>

    <div class="vg-layout">
      <!-- Left side: Form & Context -->
      <div class="vg-left">
        <!-- Account Context Card -->
        <div class="vtfd-card">
          <div class="vtfd-section">
            <div class="vtfd-section-header">
              <span class="vtfd-section-tag">当前账号信息</span>
            </div>
            <div class="vg-info-grid">
              <div class="vg-info-item">
                <div class="vg-info-label">账号名称</div>
                <div class="vg-info-value">{{ account?.account_name || '加载中...' }}</div>
              </div>
              <div class="vg-info-item">
                <div class="vg-info-label">风格描述</div>
                <div class="vg-info-value">{{ account?.style_description || '暂无描述' }}</div>
              </div>
              <div class="vg-info-item">
                <div class="vg-info-label">模特长相描述</div>
                <div class="vg-info-value">{{ account?.model_appearance || '暂无描述' }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Template Selection Card -->
        <div class="vtfd-card">
          <div class="vtfd-section">
            <div class="vtfd-section-header" style="justify-content: space-between;">
              <span class="vtfd-section-tag">{{ batchMode ? '按博主批量选择模板' : '选择视频模板' }}</span>
              <el-button size="small" @click="toggleMode">
                {{ batchMode ? '切换到单模板模式' : '按博主批量选择' }}
              </el-button>
            </div>

            <!-- 单模板模式 -->
            <el-form v-if="!batchMode" label-position="top">
              <el-form-item label="关联AI模板" required>
                <el-select
                  v-model="selectedTemplateId"
                  placeholder="请选择已经分析并生图完的模板"
                  class="vtfd-beautiful-input"
                  style="width: 100%"
                  @change="handleTemplateChange"
                  filterable
                >
                  <el-option
                    v-for="tpl in templateList"
                    :key="tpl.id"
                    :label="tpl.title || tpl.video_source?.title || '未命名模板'"
                    :value="tpl.id"
                  >
                    <span>{{ tpl.title || tpl.video_source?.title || '未命名模板' }}</span>
                    <span style="color: #94a3b8; font-size: 12px; margin-left: 10px;">{{ tpl.process_status }}</span>
                  </el-option>
                </el-select>
              </el-form-item>
            </el-form>

            <!-- 批量模式 -->
            <template v-else>
              <!-- Step 1: 选博主 -->
              <div class="batch-step">
                <div class="batch-step-label">① 选择博主</div>
                <el-select
                  v-model="selectedBlogger"
                  placeholder="请选择博主"
                  class="vtfd-beautiful-input"
                  style="width: 100%"
                  filterable
                  @change="handleBloggerChange"
                >
                  <el-option
                    v-for="b in bloggerList"
                    :key="b"
                    :label="b"
                    :value="b"
                  />
                </el-select>
              </div>

              <!-- Step 2: 选模板 -->
              <template v-if="selectedBlogger">
                <div class="batch-step" style="margin-top: 16px;">
                  <div class="batch-step-label" style="display: flex; justify-content: space-between; align-items: center;">
                    <span>② 选择视频模板</span>
                    <div style="display: flex; gap: 8px; align-items: center;">
                      <el-checkbox
                        :model-value="isAllSelected"
                        :indeterminate="isSomeSelected"
                        @change="toggleSelectAll"
                      >全选</el-checkbox>
                      <span style="font-size: 12px; color: #94a3b8;">已选 {{ batchSelected.length }} / {{ bloggerTemplates.length }}</span>
                    </div>
                  </div>

                  <div class="batch-tpl-list" v-loading="batchLoading">
                    <div
                      v-for="item in bloggerTemplates"
                      :key="item.tpl.id"
                      class="batch-tpl-item"
                      :class="{ 'batch-tpl-selected': batchSelected.includes(item.tpl.id) }"
                      @click="toggleBatchItem(item.tpl.id)"
                    >
                      <el-checkbox
                        :model-value="batchSelected.includes(item.tpl.id)"
                        @click.stop
                        @change="toggleBatchItem(item.tpl.id)"
                      />
                      <img
                        v-if="item.tpl.video_source?.thumbnail_url"
                        :src="item.tpl.video_source.thumbnail_url"
                        class="batch-tpl-thumb"
                      />
                      <div v-else class="batch-tpl-thumb batch-tpl-thumb-empty">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                      </div>
                      <div class="batch-tpl-info">
                        <div class="batch-tpl-title">{{ item.tpl.title || item.tpl.video_source?.video_title || '未命名模板' }}</div>
                        <div class="batch-tpl-meta">
                          <span class="batch-tpl-status" :class="`status-${item.tpl.process_status}`">{{ item.tpl.process_status }}</span>
                          <span v-if="item.tpl.video_source?.duration" style="color: #94a3b8; font-size: 11px;">
                            {{ formatDuration(item.tpl.video_source.duration) }}
                          </span>
                        </div>
                        <div v-if="item.tpl.extracted_shots?.length" style="font-size: 11px; color: #10b981;">
                          {{ item.tpl.extracted_shots.length }} 张造型图
                        </div>
                        <div v-else style="font-size: 11px; color: #f59e0b;">暂无造型图</div>
                      </div>
                    </div>
                    <div v-if="!batchLoading && bloggerTemplates.length === 0" class="batch-empty">
                      该博主暂无可用模板
                    </div>
                  </div>
                </div>
              </template>
            </template>
          </div>
        </div>

        <!-- Prompt Builder Card (单模板模式) -->
        <div class="vtfd-card" v-if="!batchMode && selectedTemplate">
          <div class="vtfd-section">
            <div class="vtfd-section-header" style="justify-content: space-between;">
              <span class="vtfd-section-tag">组装最终 Prompt</span>
              <div>
                <el-button size="small" @click="resetPrompt" style="margin-right: 8px;">重置为默认组合</el-button>
                <el-button
                  size="small"
                  :type="isPromptEditMode ? 'success' : 'primary'"
                  plain
                  @click="isPromptEditMode = !isPromptEditMode"
                >
                  <svg v-if="!isPromptEditMode" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px;"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px;"><polyline points="20 6 9 17 4 12"/></svg>
                  {{ isPromptEditMode ? '完成编辑' : '手动修改' }}
                </el-button>
              </div>
            </div>

            <div v-if="!isPromptEditMode" class="vg-prompt-box markdown-body" v-html="renderedFinalPrompt"></div>

            <template v-else>
              <div style="font-size: 13px; color: #64748b; margin-bottom: 12px;">此处内容为调用图生视频或文生图大模型的输入，您可以手动微调。</div>
              <el-input
                v-model="finalPrompt"
                type="textarea"
                :rows="20"
                class="vtfd-beautiful-input"
                placeholder="最终Prompt..."
              />
            </template>
          </div>
        </div>
      </div>

      <!-- Right side: Template Preview (单模板模式) -->
      <div class="vg-right" v-if="!batchMode && selectedTemplate">
        <div class="vtfd-card">
          <div class="vtfd-section">
            <div class="vtfd-section-header">
              <span class="vtfd-section-tag">模板预览</span>
            </div>

            <div class="vg-preview-video">
              <div class="vg-preview-label" style="display: flex; justify-content: space-between; align-items: center;">
                <span>原始视频</span>
                <span v-if="selectedTemplate.video_source?.duration" style="font-size: 12px; color: #64748b; font-weight: normal; margin-right: 8px;">
                  时长: {{ formatDuration(selectedTemplate.video_source.duration) }}
                </span>
              </div>
              <video
                v-if="selectedTemplate.video_source?.local_video_url"
                :src="selectedTemplate.video_source.local_video_url"
                controls
                class="vg-video"
              ></video>
              <div v-else class="vg-video-empty">暂无原始视频</div>
            </div>

            <div class="vg-preview-shots" v-if="selectedTemplate.extracted_shots?.length">
              <div class="vg-preview-label">造型图 / 分镜图</div>
              <div class="vg-shot-grid">
                <img
                  v-for="(shot, idx) in selectedTemplate.extracted_shots"
                  :key="idx"
                  :src="shot.image_url"
                  class="vg-shot-img"
                />
              </div>
            </div>

            <div class="vg-preview-analysis">
              <div class="vg-preview-label">模板 AI 分析内容</div>
              <div class="vg-analysis-box markdown-body" v-html="renderedAnalysis"></div>
            </div>
          </div>
        </div>
      </div>

      <div class="vg-right-empty" v-else-if="!batchMode">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        <div style="margin-top: 16px; color: #94a3b8;">请在左侧选择一个视频模板进行预览和生成</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchAccount } from '../api/accounts'
import { fetchVideoAITemplates, fetchVideoAITemplate } from '../api/video_ai_templates'
import { createVideoGeneration } from '../api/video_generations'
import { renderMarkdown } from '../utils/markdown'

const route = useRoute()
const router = useRouter()
const accountId = route.params.id

const loading = ref(false)
const generating = ref(false)

const account = ref(null)
const templateList = ref([])

const selectedTemplateId = ref('')
const selectedTemplate = ref(null)

const finalPrompt = ref('')
const isPromptEditMode = ref(false)

// ── Batch mode ──
const batchMode = ref(false)
const batchLoading = ref(false)
const batchGenerating = ref(false)
const selectedBlogger = ref('')
const bloggerTemplates = ref([])  // [{tpl}]
const batchSelected = ref([])     // selected template ids

const bloggerList = computed(() => {
  const names = new Set()
  for (const tpl of templateList.value) {
    const name = tpl.video_source?.blogger_name
    if (name) names.add(name)
  }
  return [...names].sort()
})

const isAllSelected = computed(
  () => bloggerTemplates.value.length > 0 && batchSelected.value.length === bloggerTemplates.value.length
)
const isSomeSelected = computed(
  () => batchSelected.value.length > 0 && batchSelected.value.length < bloggerTemplates.value.length
)
const batchIsReady = computed(() => batchSelected.value.length > 0 && !!account.value)

// ── Single template ──
const isReady = computed(() => !!account.value && !!selectedTemplate.value && !!finalPrompt.value)

const renderedAnalysis = computed(() => {
  if (!selectedTemplate.value?.prompt_description) return ''
  return renderMarkdown(selectedTemplate.value.prompt_description)
})

const renderedFinalPrompt = computed(() => {
  if (!finalPrompt.value) return '<span style="color:#94a3b8">暂无内容，请选择模板生成</span>'
  return renderMarkdown(finalPrompt.value)
})

async function loadData() {
  loading.value = true
  try {
    account.value = await fetchAccount(accountId)
    const templatesRes = await fetchVideoAITemplates({ page: 1, page_size: 100 })
    templateList.value = templatesRes.items || []
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载初始数据失败')
  } finally {
    loading.value = false
  }
}

async function handleTemplateChange(tplId) {
  if (!tplId) {
    selectedTemplate.value = null
    finalPrompt.value = ''
    return
  }
  loading.value = true
  try {
    const data = await fetchVideoAITemplate(tplId)
    selectedTemplate.value = data
    resetPrompt()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载模板详情失败')
  } finally {
    loading.value = false
  }
}

function resetPrompt() {
  if (!account.value || !selectedTemplate.value) return
  const style = account.value.style_description ? `【风格描述】\n${account.value.style_description}\n\n` : ''
  const appearance = account.value.model_appearance ? `【模特长相描述】\n${account.value.model_appearance}\n\n` : ''
  const analysis = selectedTemplate.value.prompt_description ? `【动作与分镜画面】\n${selectedTemplate.value.prompt_description}` : ''
  finalPrompt.value = `${style}${appearance}${analysis}`
}

function formatDuration(seconds) {
  if (!seconds) return '0s'
  let s = Math.floor(seconds)
  if (s > 15) s = 15
  return `${s}s`
}

function buildPromptForTemplate(tpl) {
  const style = account.value?.style_description ? `【风格描述】\n${account.value.style_description}\n\n` : ''
  const appearance = account.value?.model_appearance ? `【模特长相描述】\n${account.value.model_appearance}\n\n` : ''
  const analysis = tpl.prompt_description ? `【动作与分镜画面】\n${tpl.prompt_description}` : ''
  return `${style}${appearance}${analysis}`
}

// ── Mode toggle ──
function toggleMode() {
  batchMode.value = !batchMode.value
  if (batchMode.value) {
    selectedBlogger.value = ''
    bloggerTemplates.value = []
    batchSelected.value = []
  }
}

// ── Batch blogger selection ──
async function handleBloggerChange(blogger) {
  batchSelected.value = []
  bloggerTemplates.value = []
  if (!blogger) return
  batchLoading.value = true
  try {
    // Filter from already-loaded templateList by blogger_name, then fetch full details
    const matching = templateList.value.filter(t => t.video_source?.blogger_name === blogger)
    // Fetch full template details (with extracted_shots)
    const details = await Promise.all(matching.map(t => fetchVideoAITemplate(t.id).catch(() => t)))
    bloggerTemplates.value = details.map(tpl => ({ tpl }))
  } catch (err) {
    ElMessage.error('加载模板失败')
  } finally {
    batchLoading.value = false
  }
}

function toggleBatchItem(tplId) {
  const idx = batchSelected.value.indexOf(tplId)
  if (idx >= 0) batchSelected.value.splice(idx, 1)
  else batchSelected.value.push(tplId)
}

function toggleSelectAll(val) {
  if (val) batchSelected.value = bloggerTemplates.value.map(item => item.tpl.id)
  else batchSelected.value = []
}

// ── Generate ──
async function handleGenerate() {
  if (generating.value || !isReady.value) return
  generating.value = true
  try {
    let image = ''
    let duration = '0s'
    let shots = []
    if (selectedTemplate.value?.video_source) {
      image = selectedTemplate.value.video_source.thumbnail_url || selectedTemplate.value.video_source.cover_url || ''
      duration = formatDuration(selectedTemplate.value.video_source.duration)
    }
    if (selectedTemplate.value?.extracted_shots) {
      shots = selectedTemplate.value.extracted_shots.map(({ image_base64, ...rest }) => rest)
    }
    const payload = {
      account_id: accountId,
      template_id: selectedTemplateId.value,
      final_prompt: finalPrompt.value,
      image,
      duration,
      shots
    }
    await createVideoGeneration(payload)
    ElMessage.success('视频生成任务已进入流水线阶段！')
    router.push(`/dashboard/accounts/${accountId}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '开始生成失败')
  } finally {
    generating.value = false
  }
}

async function handleBatchGenerate() {
  if (batchGenerating.value || !batchIsReady.value) return
  batchGenerating.value = true
  const selectedItems = bloggerTemplates.value.filter(item => batchSelected.value.includes(item.tpl.id))
  let successCount = 0
  let failCount = 0
  try {
    for (const item of selectedItems) {
      const tpl = item.tpl
      try {
        const image = tpl.video_source?.thumbnail_url || tpl.video_source?.cover_url || ''
        const duration = formatDuration(tpl.video_source?.duration)
        const shots = (tpl.extracted_shots || []).map(({ image_base64, ...rest }) => rest)
        const finalP = buildPromptForTemplate(tpl)
        await createVideoGeneration({
          account_id: accountId,
          template_id: tpl.id,
          final_prompt: finalP,
          image,
          duration,
          shots,
        })
        successCount++
      } catch {
        failCount++
      }
    }
    if (successCount > 0) ElMessage.success(`成功创建 ${successCount} 个生成任务${failCount > 0 ? `，${failCount} 个失败` : ''}`)
    else ElMessage.error('所有任务创建失败')
    router.push(`/dashboard/accounts/${accountId}`)
  } finally {
    batchGenerating.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.vtfd-page {
  padding: 30px;
  max-width: 1400px;
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

/* Layout */
.vg-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.vg-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
}

.vg-right {
  width: 480px;
  flex-shrink: 0;
}

.vg-right-empty {
  width: 480px;
  flex-shrink: 0;
  background: #f8fafc;
  border-radius: 16px;
  border: 1px dashed #cbd5e1;
  height: 500px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

/* Cards */
.vtfd-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 20px -10px rgba(0,0,0,0.05);
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

/* Custom Grid */
.vg-info-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px;
  border: 1px solid #f1f5f9;
}

.vg-info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.vg-info-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.vg-info-value {
  font-size: 14px;
  color: #0f172a;
  line-height: 1.5;
}

/* Previews */
.vg-preview-label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 8px;
  border-left: 3px solid #6366f1;
  padding-left: 8px;
}

.vg-preview-video {
  margin-bottom: 24px;
}

.vg-video {
  width: 100%;
  border-radius: 12px;
  background: #000;
}

.vg-video-empty {
  height: 200px;
  background: #f1f5f9;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 13px;
}

.vg-preview-shots {
  margin-bottom: 24px;
}

.vg-shot-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.vg-shot-img {
  width: 100%;
  aspect-ratio: 9/16;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.vg-preview-analysis {
  background: #f8fafc;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #f1f5f9;
}

.vg-analysis-box {
  font-size: 13px;
  line-height: 1.6;
  color: #334155;
  max-height: 300px;
  overflow-y: auto;
}

.vg-prompt-box {
  background: #f8fafc;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
  min-height: 400px;
}

/* ── Batch mode ── */
.batch-step-label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 10px;
}

.batch-tpl-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 480px;
  overflow-y: auto;
  padding-right: 4px;
}

.batch-tpl-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.batch-tpl-item:hover {
  border-color: #a5b4fc;
  background: #eef2ff;
}

.batch-tpl-selected {
  border-color: #6366f1 !important;
  background: #eef2ff !important;
}

.batch-tpl-thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
  border: 1px solid #e2e8f0;
}

.batch-tpl-thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
}

.batch-tpl-info {
  flex: 1;
  min-width: 0;
}

.batch-tpl-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.batch-tpl-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.batch-tpl-status {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #64748b;
}

.batch-tpl-status.status-success {
  background: #dcfce7;
  color: #166534;
}

.batch-tpl-status.status-face_removing,
.batch-tpl-status.status-splitting,
.batch-tpl-status.status-understanding,
.batch-tpl-status.status-imagegen {
  background: #fef9c3;
  color: #a16207;
}

.batch-tpl-status.status-failed {
  background: #fee2e2;
  color: #991b1b;
}

.batch-empty {
  text-align: center;
  color: #94a3b8;
  padding: 32px 0;
  font-size: 14px;
}
</style>
