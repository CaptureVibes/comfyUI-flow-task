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
        <el-button type="primary" :loading="generating" @click="handleGenerate" :disabled="!isReady">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          开始生成阶段
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
            <div class="vtfd-section-header">
              <span class="vtfd-section-tag">选择视频模板</span>
            </div>
            <el-form label-position="top">
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
                    <span style="color: #94a3b8; font-size: 12px; margin-left: 10px;">{{ tpl.state }}</span>
                  </el-option>
                </el-select>
              </el-form-item>
            </el-form>
          </div>
        </div>

        <!-- Prompt Builder Card -->
        <div class="vtfd-card" v-if="selectedTemplate">
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

      <!-- Right side: Template Preview -->
      <div class="vg-right" v-if="selectedTemplate">
        <div class="vtfd-card">
          <div class="vtfd-section">
            <div class="vtfd-section-header">
              <span class="vtfd-section-tag">模板预览</span>
            </div>
            
            <div class="vg-preview-video">
              <div class="vg-preview-label">原始视频</div>
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
      
      <div class="vg-right-empty" v-else>
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
    // 1. Fetch account
    account.value = await fetchAccount(accountId)
    // 2. Fetch ALL templates for the dropdown
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

async function handleGenerate() {
  if (generating.value || !isReady.value) return
  generating.value = true
  try {
    const payload = {
      account_id: accountId,
      template_id: selectedTemplateId.value,
      final_prompt: finalPrompt.value
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
</style>
