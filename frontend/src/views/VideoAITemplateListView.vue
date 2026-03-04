<template>
  <div class="vai-page">
    <!-- Header -->
    <div class="vai-header">
      <h1 class="vai-title">视频AI模板</h1>
      <div class="vai-header-actions">
        <el-button class="vai-config-btn" @click="openConfig">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="margin-right:6px"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          流程配置
        </el-button>
        <el-button type="primary" class="vai-add-btn" @click="$router.push('/dashboard/video-ai-templates/new')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          新建模板
        </el-button>
      </div>
    </div>

    <!-- Card grid -->
    <div v-loading="loading" class="vai-grid">
      <div v-for="item in items" :key="item.id" class="vt-card" @click="goToDetail(item)">
        <!-- Header with status -->
        <div class="vt-header">
          <el-tag size="small" :type="statusType(item.process_status)" class="vt-status-tag">
            {{ statusLabel(item.process_status) }}
          </el-tag>
          <div class="vt-actions" @click.stop>
            <el-button
              v-if="canStart(item)"
              size="small"
              type="primary"
              :loading="actioning === item.id + '-start'"
              @click="handleStart(item)"
            >开始</el-button>
            <el-button
              v-if="canPause(item)"
              size="small"
              :loading="actioning === item.id + '-pause'"
              @click="handlePause(item)"
            >暂停</el-button>
            <el-button
              v-if="canResume(item)"
              size="small"
              type="success"
              :loading="actioning === item.id + '-resume'"
              @click="handleResume(item)"
            >继续</el-button>
            <el-button size="small" @click.stop="goToEdit(item)">编辑</el-button>
            <el-button
              size="small"
              type="danger"
              :loading="deleting === item.id"
              @click.stop="handleDelete(item)"
            >删除</el-button>
          </div>
        </div>

        <!-- Video preview -->
        <div v-if="item.video_source" class="vt-video-section" @click.stop>
          <div v-if="item.video_source.thumbnail_url" class="vt-thumb">
            <img :src="item.video_source.thumbnail_url" class="vt-thumb-img" />
            <div class="vt-thumb-overlay">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="white"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </div>
          </div>
          <div v-else class="vt-thumb-placeholder">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>
          </div>
          <div v-if="item.video_source.platform" class="vt-platform-badge">
            {{ platformLabel(item.video_source.platform) }}
          </div>
        </div>

        <!-- Content -->
        <div class="vt-content">
          <div class="vt-title">{{ item.title }}</div>
          <div v-if="item.description" class="vt-desc">{{ item.description }}</div>

          <!-- Error message -->
          <div v-if="item.process_error" class="vt-error">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>{{ item.process_error }}</span>
          </div>

          <!-- Meta info -->
          <div class="vt-meta">
            <span class="vt-date">{{ formatDate(item.updated_at) }}</span>
            <span v-if="item.video_source" class="vt-video-info">
              @{{ item.video_source.blogger_name || '未知' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Add new card -->
      <div class="vt-card vt-add" @click="$router.push('/dashboard/video-ai-templates/new')">
        <div class="vt-add-inner">
          <div class="vt-add-icon">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </div>
          <div class="vt-add-title">新建模板</div>
          <div class="vt-add-sub">关联视频源，AI自动处理</div>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <el-empty v-if="!loading && items.length === 0" description="暂无模板，点击「新建模板」开始" :image-size="80" />

    <!-- Pipeline Config Dialog -->
    <el-dialog
      v-model="showConfig"
      title="AI 处理流程配置"
      width="760px"
      :close-on-click-modal="false"
    >
      <div v-loading="configLoading" class="cfg-body">
        <div class="cfg-hint-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          API Key 和 Base URL 在<router-link to="/dashboard/settings" @click="showConfig=false">设置页面</router-link>配置，三个步骤共用同一 EvoLink Key。
        </div>

        <el-tabs v-model="configTab" type="border-card" class="cfg-tabs">
          <!-- Step 1 -->
          <el-tab-pane label="步骤一：视频理解" name="step1">
            <div class="cfg-step-desc">AI 理解视频全局内容，输出整体文字描述。此结果将作为背景信息展示在模板详情中。</div>
            <el-form label-position="top" class="cfg-form">
              <el-form-item label="模型名称">
                <el-input v-model="cfg.understand_model" placeholder="gemini-3.1-pro-preview（留空使用默认）" />
              </el-form-item>
              <el-form-item label="提示词 (Prompt)">
                <el-input v-model="cfg.understand_prompt" type="textarea" :rows="4"
                  placeholder="请描述这个视频的内容，包括场景、人物、服装风格等。" />
              </el-form-item>
              <el-form-item :label="`温度 (Temperature)：${cfg.understand_temperature.toFixed(1)}`">
                <el-slider v-model="cfg.understand_temperature" :min="0" :max="2" :step="0.1" />
              </el-form-item>
              <el-form-item label="输出格式">
                <el-radio-group v-model="cfg.understand_output_format">
                  <el-radio value="text">纯文本</el-radio>
                  <el-radio value="json">JSON</el-radio>
                  <el-radio value="markdown">Markdown</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-if="cfg.understand_output_format === 'json'" label="JSON 格式定义">
                <el-input
                  v-model="cfg.understand_json_schema"
                  type="textarea"
                  :rows="5"
                  placeholder='{\n  "overall_style": "...",\n  "color_palette": ["..."],\n  "theme": "..."\n}'
                  class="cfg-code-input"
                  :class="{ 'cfg-json-invalid': jsonErrors.understand }"
                  @input="validateJsonField('understand', cfg.understand_json_schema)"
                />
                <div v-if="jsonErrors.understand" class="cfg-json-error-msg">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                  {{ jsonErrors.understand }}
                </div>
                <div v-else-if="cfg.understand_json_schema.trim()" class="cfg-json-ok-msg">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                  JSON 格式正确
                </div>
                <div class="cfg-field-hint">此 JSON 格式将追加到提示词末尾，要求模型严格按格式输出。</div>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- Step 2 -->
          <el-tab-pane label="步骤二：造型提取" name="step2">
            <div class="cfg-step-desc">AI 分析视频中的穿搭造型，输出每个造型的文字描述列表。每个描述将作为步骤三的生图输入。</div>
            <el-form label-position="top" class="cfg-form">
              <el-form-item label="模型名称">
                <el-input v-model="cfg.extract_model" placeholder="gemini-3.1-pro-preview（留空使用默认）" />
              </el-form-item>
              <el-form-item label="提示词 (Prompt)">
                <el-input v-model="cfg.extract_prompt" type="textarea" :rows="4"
                  placeholder="请分析视频中出现的所有不同穿搭造型，以JSON数组格式返回每个造型的文字描述。" />
              </el-form-item>
              <el-form-item :label="`温度 (Temperature)：${cfg.extract_temperature.toFixed(1)}`">
                <el-slider v-model="cfg.extract_temperature" :min="0" :max="2" :step="0.1" />
              </el-form-item>
              <el-form-item label="输出格式">
                <el-radio-group v-model="cfg.extract_output_format">
                  <el-radio value="json">JSON（推荐）</el-radio>
                  <el-radio value="markdown">Markdown</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-if="cfg.extract_output_format === 'json'" label="JSON 格式定义">
                <el-input
                  v-model="cfg.extract_json_schema"
                  type="textarea"
                  :rows="6"
                  placeholder='[\n  {\n    "id": 1,\n    "description": "穿搭造型的详细文字描述",\n    "tags": ["风格标签"]\n  }\n]'
                  class="cfg-code-input"
                  :class="{ 'cfg-json-invalid': jsonErrors.extract }"
                  @input="validateJsonField('extract', cfg.extract_json_schema)"
                />
                <div v-if="jsonErrors.extract" class="cfg-json-error-msg">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                  {{ jsonErrors.extract }}
                </div>
                <div v-else-if="cfg.extract_json_schema.trim()" class="cfg-json-ok-msg">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                  JSON 格式正确
                </div>
                <div class="cfg-field-hint">此 JSON 格式将追加到提示词末尾，要求模型严格按格式输出。</div>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- Step 3 -->
          <el-tab-pane label="步骤三：生图配置" name="step3">
            <div class="cfg-step-desc">
              根据步骤二的每个造型描述，并发提交生图任务到 EvoLink，通过轮询 task_id 获取生成图片。共用设置页面中的 EvoLink Key。
            </div>
            <el-form label-position="top" class="cfg-form">
              <el-form-item label="生图模型名称">
                <el-input v-model="cfg.image_gen_model" placeholder="例如 gemini-3.1-flash-image-preview" />
              </el-form-item>
              <el-form-item label="Prompt 模板">
                <el-input
                  v-model="cfg.image_gen_prompt_template"
                  type="textarea"
                  :rows="4"
                  placeholder="Generate a fashion outfit image: {description}"
                />
                <div class="cfg-field-hint">使用 <code>{description}</code> 占位符引用步骤二中每个造型的文字描述。</div>
              </el-form-item>
              <div class="cfg-two-col">
                <el-form-item label="图片尺寸 (size)">
                  <el-select v-model="cfg.image_gen_size" style="width:100%">
                    <el-option value="auto" label="auto（自动）" />
                    <el-option value="1:1" label="1:1（正方形）" />
                    <el-option value="2:3" label="2:3（竖版）" />
                    <el-option value="3:2" label="3:2（横版）" />
                    <el-option value="3:4" label="3:4（竖版）" />
                    <el-option value="4:3" label="4:3（横版）" />
                    <el-option value="4:5" label="4:5（竖版）" />
                    <el-option value="5:4" label="5:4（横版）" />
                    <el-option value="9:16" label="9:16（手机竖屏）" />
                    <el-option value="16:9" label="16:9（宽屏）" />
                    <el-option value="21:9" label="21:9（超宽屏）" />
                  </el-select>
                </el-form-item>
                <el-form-item label="图片质量 (quality)">
                  <el-select v-model="cfg.image_gen_quality" style="width:100%">
                    <el-option value="0.5K" label="0.5K（低）" />
                    <el-option value="1K" label="1K（标准）" />
                    <el-option value="2K" label="2K（高，默认）" />
                    <el-option value="4K" label="4K（超高）" />
                  </el-select>
                </el-form-item>
              </div>
              <div class="cfg-job-flow">
                <div class="cfg-job-step">
                  <div class="cfg-job-step-icon">1</div>
                  <div class="cfg-job-step-text"><code>POST /v1/images/generations</code> 提交任务 → 获取 <code>task_id</code></div>
                </div>
                <div class="cfg-job-arrow">↓</div>
                <div class="cfg-job-step">
                  <div class="cfg-job-step-icon">2</div>
                  <div class="cfg-job-step-text"><code>GET /v1/tasks/{task_id}</code> 每 3s 轮询，直到 <code>completed</code></div>
                </div>
                <div class="cfg-job-arrow">↓</div>
                <div class="cfg-job-step">
                  <div class="cfg-job-step-icon">3</div>
                  <div class="cfg-job-step-text">从 <code>results[0]</code> 提取图片 URL，最大等待 300s</div>
                </div>
              </div>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>

      <template #footer>
        <el-button @click="showConfig = false">取消</el-button>
        <el-button type="primary" :loading="configSaving" :disabled="hasJsonError" @click="saveConfig">保存配置</el-button>
      </template>
    </el-dialog>

    <!-- Footer pagination -->
    <div v-if="total > pageSize" class="vai-footer">
      <span class="vai-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
      <div class="vai-pagination">
        <button class="pg-btn" :disabled="page <= 1" @click="goPage(page - 1)">← 上一页</button>
        <button class="pg-btn" :disabled="endIdx >= total" @click="goPage(page + 1)">下一页 →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchVideoAITemplates,
  startVideoAITemplate,
  pauseVideoAITemplate,
  resumeVideoAITemplate,
  deleteVideoAITemplate,
} from '../api/video_ai_templates'
import { fetchEvolinkSettings, updateEvolinkSettings } from '../api/settings'
import { isDuplicateRequestError } from '../api/http'

const router = useRouter()

const loading = ref(false)
const deleting = ref(null)
const actioning = ref(null)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 12

// Config dialog state
const showConfig = ref(false)
const configTab = ref('step1')
const configLoading = ref(false)
const configSaving = ref(false)

const cfg = reactive({
  // Step 1
  understand_model: '',
  understand_prompt: '',
  understand_temperature: 0.3,
  understand_output_format: 'text',
  understand_json_schema: '',
  // Step 2
  extract_model: '',
  extract_prompt: '',
  extract_temperature: 0.3,
  extract_output_format: 'json',
  extract_json_schema: '',
  // Step 3 (EvoLink job-based: POST /v1/images/generations → GET /v1/tasks/{id})
  image_gen_model: '',
  image_gen_prompt_template: '',
  image_gen_size: '1:1',
  image_gen_quality: '2K',
  // preserved: EvoLink connection (stays in settings page)
  api_key: '',
  api_base_url: 'https://api.evolink.ai',
})

// JSON validation errors for schema fields
const jsonErrors = reactive({ understand: '', extract: '' })

function validateJsonField(field, value) {
  const v = (value || '').trim()
  if (!v) { jsonErrors[field] = ''; return }
  try {
    JSON.parse(v)
    jsonErrors[field] = ''
  } catch (e) {
    jsonErrors[field] = e.message
  }
}

const hasJsonError = computed(() =>
  (cfg.understand_output_format === 'json' && !!jsonErrors.understand) ||
  (cfg.extract_output_format === 'json' && !!jsonErrors.extract)
)

async function openConfig() {
  showConfig.value = true
  configTab.value = 'step1'
  configLoading.value = true
  jsonErrors.understand = ''
  jsonErrors.extract = ''
  try {
    const data = await fetchEvolinkSettings()
    Object.assign(cfg, {
      understand_model: data.understand_model || '',
      understand_prompt: data.understand_prompt || '',
      understand_temperature: data.understand_temperature ?? 0.3,
      understand_output_format: data.understand_output_format || 'text',
      understand_json_schema: data.understand_json_schema || '',
      extract_model: data.extract_model || '',
      extract_prompt: data.extract_prompt || '',
      extract_temperature: data.extract_temperature ?? 0.3,
      extract_output_format: data.extract_output_format || 'json',
      extract_json_schema: data.extract_json_schema || '',
      image_gen_model: data.image_gen_model || '',
      image_gen_prompt_template: data.image_gen_prompt_template || '',
      image_gen_size: data.image_gen_size || '1:1',
      image_gen_quality: data.image_gen_quality || '2K',
      api_key: data.api_key || '',
      api_base_url: data.api_base_url || 'https://api.evolink.ai',
    })
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载配置失败')
  } finally {
    configLoading.value = false
  }
}

async function saveConfig() {
  if (hasJsonError.value) {
    ElMessage.error('请修正 JSON 格式错误后再保存')
    return
  }
  configSaving.value = true
  try {
    await updateEvolinkSettings({
      api_key: cfg.api_key,
      api_base_url: cfg.api_base_url,
      understand_model: cfg.understand_model,
      understand_prompt: cfg.understand_prompt,
      understand_temperature: cfg.understand_temperature,
      understand_output_format: cfg.understand_output_format,
      understand_json_schema: cfg.understand_json_schema,
      extract_model: cfg.extract_model,
      extract_prompt: cfg.extract_prompt,
      extract_temperature: cfg.extract_temperature,
      extract_output_format: cfg.extract_output_format,
      extract_json_schema: cfg.extract_json_schema,
      image_gen_model: cfg.image_gen_model,
      image_gen_prompt_template: cfg.image_gen_prompt_template,
      image_gen_size: cfg.image_gen_size,
      image_gen_quality: cfg.image_gen_quality,
    })
    ElMessage.success('配置已保存')
    showConfig.value = false
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    configSaving.value = false
  }
}

const startIdx = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize + 1)
const endIdx = computed(() => Math.min(page.value * pageSize, total.value))

const STATUS_CONFIG = {
  pending: { label: '待处理', type: 'info' },
  running: { label: '处理中', type: 'warning' },
  paused: { label: '已暂停', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
}

function statusType(status) {
  return STATUS_CONFIG[status]?.type || 'info'
}

function statusLabel(status) {
  return STATUS_CONFIG[status]?.label || status
}

function canStart(item) {
  return item.process_status === 'pending' || item.process_status === 'paused' || item.process_status === 'failed'
}

function canPause(item) {
  return item.process_status === 'running'
}

function canResume(item) {
  return item.process_status === 'paused'
}

function platformLabel(p) {
  const labels = { youtube: 'YouTube', tiktok: 'TikTok' }
  return labels[p] || (p || '其他')
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

async function loadData() {
  loading.value = true
  try {
    const data = await fetchVideoAITemplates({ page: page.value, page_size: pageSize })
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

function goToDetail(item) {
  router.push(`/dashboard/video-ai-templates/${item.id}/edit`)
}

function goToEdit(item) {
  router.push(`/dashboard/video-ai-templates/${item.id}/edit`)
}

async function handleStart(item) {
  actioning.value = item.id + '-start'
  try {
    await startVideoAITemplate(item.id)
    ElMessage.success('已开始处理')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '启动失败')
  } finally {
    actioning.value = null
  }
}

async function handlePause(item) {
  actioning.value = item.id + '-pause'
  try {
    await pauseVideoAITemplate(item.id)
    ElMessage.success('已暂停')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '暂停失败')
  } finally {
    actioning.value = null
  }
}

async function handleResume(item) {
  actioning.value = item.id + '-resume'
  try {
    await resumeVideoAITemplate(item.id)
    ElMessage.success('已继续处理')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '继续失败')
  } finally {
    actioning.value = null
  }
}

async function handleDelete(item) {
  try {
    await ElMessageBox.confirm(
      `确定删除模板「${item.title}」？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch { return }

  deleting.value = item.id
  try {
    await deleteVideoAITemplate(item.id)
    ElMessage.success('已删除')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = null
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* Page layout */
.vai-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
}

.vai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}

.vai-title {
  font-size: 26px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.03em;
  margin: 0;
}

.vai-header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.vai-config-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  border: 1px solid #c7d2fe;
  color: #4338ca;
  background: #eef2ff;
}

.vai-config-btn:hover {
  background: #e0e7ff;
  border-color: #6366f1;
}

.vai-add-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
}

/* Config dialog */
.cfg-body {
  min-height: 320px;
}

.cfg-hint-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6366f1;
  background: #eef2ff;
  border-radius: 8px;
  padding: 8px 14px;
  margin-bottom: 14px;
}

.cfg-hint-bar a {
  color: #4f46e5;
  font-weight: 600;
  text-decoration: underline;
}

.cfg-tabs {
  border-radius: 10px;
  overflow: hidden;
}

.cfg-step-desc {
  font-size: 13px;
  color: #64748b;
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 20px;
  border-left: 3px solid #6366f1;
}

.cfg-form {
  padding-top: 4px;
}

.cfg-field-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  line-height: 1.4;
}

.cfg-field-hint code {
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: monospace;
  color: #6366f1;
}

.cfg-code-input :deep(textarea) {
  font-family: 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.cfg-json-invalid :deep(.el-textarea__inner) {
  border-color: #f56565 !important;
  box-shadow: 0 0 0 2px rgba(245, 101, 101, 0.15) !important;
}

.cfg-json-error-msg {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #dc2626;
  margin-top: 5px;
  font-family: 'Menlo', 'Consolas', monospace;
}

.cfg-json-ok-msg {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #16a34a;
  margin-top: 5px;
}

/* Step 3 job flow diagram */
.cfg-job-flow {
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  padding: 16px 20px;
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cfg-job-step {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cfg-job-step-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #6366f1;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cfg-job-step-text {
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.cfg-job-step-text code {
  background: #e0e7ff;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: monospace;
  color: #4338ca;
  font-size: 11px;
}

.cfg-job-arrow {
  font-size: 16px;
  color: #94a3b8;
  padding-left: 8px;
  line-height: 1;
}

/* Card grid */
.vai-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  margin-bottom: 28px;
}

/* Template card */
.vt-card {
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

.vt-card:hover {
  box-shadow: 0 8px 24px rgba(0,0,0,.1);
  transform: translateY(-2px);
}

.vt-add {
  border: 2px dashed #c7d2fe;
  background: #fafbff;
  min-height: 300px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vt-add:hover {
  border-color: #6366f1;
  background: #eef2ff;
  transform: none;
  box-shadow: none;
}

.vt-add-inner {
  text-align: center;
}

.vt-add-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: #eef2ff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  transition: background 0.2s;
}

.vt-add:hover .vt-add-icon {
  background: #c7d2fe;
}

.vt-add-title {
  font-size: 16px;
  font-weight: 700;
  color: #3730a3;
  margin-bottom: 4px;
}

.vt-add-sub {
  font-size: 13px;
  color: #818cf8;
}

/* Header */
.vt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
}

.vt-status-tag {
  font-weight: 600;
  font-size: 11px;
}

.vt-actions {
  display: flex;
  gap: 6px;
}

/* Video section */
.vt-video-section {
  position: relative;
  aspect-ratio: 16/9;
  overflow: hidden;
  background: #0f172a;
}

.vt-thumb {
  width: 100%;
  height: 100%;
  position: relative;
}

.vt-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.3s;
}

.vt-card:hover .vt-thumb-img {
  transform: scale(1.04);
}

.vt-thumb-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.vt-card:hover .vt-thumb-overlay {
  background: rgba(0,0,0,0.35);
}

.vt-thumb-overlay svg {
  opacity: 0;
  transform: scale(0.8);
  transition: all 0.2s;
}

.vt-card:hover .vt-thumb-overlay svg {
  opacity: 1;
  transform: scale(1);
}

.vt-thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
}

.vt-platform-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  backdrop-filter: blur(4px);
}

/* Content */
.vt-content {
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.vt-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
}

.vt-desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}

.vt-error {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #fef2f2;
  border-radius: 8px;
  color: #dc2626;
  font-size: 12px;
  margin-bottom: 12px;
}

.vt-meta {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #94a3b8;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.vt-video-info {
  font-weight: 500;
  color: #64748b;
}

/* Footer */
.vai-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0 8px;
  border-top: 1px solid #f1f5f9;
}

.vai-count-text {
  font-size: 13px;
  color: #94a3b8;
}

.vai-pagination {
  display: flex;
  gap: 8px;
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

.pg-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .vai-grid { grid-template-columns: 1fr; }
  .vai-header { flex-direction: column; gap: 12px; align-items: stretch; }
  .vai-header-actions { flex-wrap: wrap; }
  .vt-actions { flex-wrap: wrap; }
}
</style>
