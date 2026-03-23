<template>
  <div class="tp-page">
    <div class="tp-header">
      <h1 class="tp-title">主题词管理</h1>
      <div class="tp-header-actions">
        <button class="tp-btn tp-btn-config" @click="showConfigDialog = true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          AI配置
        </button>
        <button class="tp-btn tp-btn-primary" @click="showAddTopicDialog = true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          新建主题词
        </button>
      </div>
    </div>

    <!-- Topic list -->
    <div v-loading="loading" class="tp-grid">
      <div v-for="topic in topics" :key="topic.id" class="tp-card" @click="$router.push(`/dashboard/topics/${topic.id}`)">
        <div class="tp-card-body">
          <div class="tp-card-name">{{ topic.name }}</div>
          <div class="tp-card-stats">
            <span class="tp-stat">{{ topic.mother_keyword_count }} 个母题词</span>
            <span class="tp-stat">{{ topic.keyword_count }} 个关键词</span>
          </div>
          <div class="tp-card-time">{{ formatDate(topic.created_at) }}</div>
        </div>
        <div class="tp-card-actions" @click.stop>
          <button class="tp-icon-btn" @click="startEditTopic(topic)" title="编辑">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="tp-icon-btn tp-icon-btn-danger" @click="handleDeleteTopic(topic)" title="删除">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </div>
    </div>

    <el-empty v-if="!loading && topics.length === 0" description="暂无主题词，点击「新建主题词」开始" :image-size="80" />

    <!-- Pagination -->
    <div v-if="total > 0" class="tp-footer">
      <span class="tp-count-text">共 {{ total }} 条</span>
      <div class="tp-pagination">
        <button class="pg-btn" :disabled="page <= 1" @click="page--; loadTopics()">← 上一页</button>
        <button class="pg-btn" :disabled="page * pageSize >= total" @click="page++; loadTopics()">下一页 →</button>
      </div>
    </div>

    <!-- Add/Edit Topic Dialog -->
    <el-dialog v-model="showAddTopicDialog" :title="editingTopicId ? '编辑主题词' : '新建主题词'" width="420px" align-center destroy-on-close @close="resetTopicForm">
      <div style="padding: 0 4px">
        <label class="tp-form-label">主题词名称</label>
        <input v-model="topicFormName" class="tp-form-input" placeholder="请输入主题词名称" @keyup.enter="handleSaveTopic" />
      </div>
      <template #footer>
        <button class="dlg-btn-cancel" @click="showAddTopicDialog = false">取消</button>
        <button class="dlg-btn-primary" :disabled="!topicFormName.trim() || savingTopic" @click="handleSaveTopic">
          <span v-if="savingTopic" class="btn-spin"></span>
          {{ editingTopicId ? '保存' : '创建' }}
        </button>
      </template>
    </el-dialog>

    <!-- AI Config Dialog -->
    <el-dialog v-model="showConfigDialog" title="关键词生成 AI 配置" width="640px" align-center destroy-on-close @open="loadConfig">
      <div v-loading="loadingConfig" class="config-form">
        <div class="config-row">
          <label class="tp-form-label">模型名称</label>
          <input v-model="configForm.keyword_gen_model" class="tp-form-input" placeholder="gemini-3.1-pro-preview" />
        </div>
        <div class="config-row">
          <label class="tp-form-label">生成数量</label>
          <input v-model.number="configForm.keyword_gen_count" type="number" class="tp-form-input" placeholder="50" min="1" max="500" />
        </div>
        <div class="config-row">
          <label class="tp-form-label">Temperature</label>
          <input v-model.number="configForm.keyword_gen_temperature" type="number" class="tp-form-input" placeholder="0.7" step="0.1" min="0" max="2" />
        </div>
        <div class="config-row">
          <label class="tp-form-label">提示词模板 <span class="tp-form-hint">（{keyword} = 母题词，{count} = 生成数量）</span></label>
          <textarea v-model="configForm.keyword_gen_prompt" class="tp-form-textarea" rows="14" placeholder="请输入提示词模板..." />
        </div>
      </div>
      <template #footer>
        <button class="dlg-btn-cancel" @click="showConfigDialog = false">取消</button>
        <button class="dlg-btn-primary" :disabled="savingConfig" @click="handleSaveConfig">
          <span v-if="savingConfig" class="btn-spin"></span>
          保存配置
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchTopics, createTopic, patchTopic, deleteTopic, fetchKeywordGenConfig, updateKeywordGenConfig } from '../api/topics'

const loading = ref(false)
const topics = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// Topic form
const showAddTopicDialog = ref(false)
const topicFormName = ref('')
const editingTopicId = ref(null)
const savingTopic = ref(false)

// Config
const showConfigDialog = ref(false)
const loadingConfig = ref(false)
const savingConfig = ref(false)
const configForm = ref({
  keyword_gen_model: '',
  keyword_gen_prompt: '',
  keyword_gen_count: 50,
  keyword_gen_temperature: 0.7,
})

onMounted(() => loadTopics())

async function loadTopics() {
  loading.value = true
  try {
    const res = await fetchTopics({ page: page.value, page_size: pageSize.value })
    topics.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error('加载主题词失败')
  } finally {
    loading.value = false
  }
}

function startEditTopic(topic) {
  editingTopicId.value = topic.id
  topicFormName.value = topic.name
  showAddTopicDialog.value = true
}

function resetTopicForm() {
  editingTopicId.value = null
  topicFormName.value = ''
}

async function handleSaveTopic() {
  if (!topicFormName.value.trim()) return
  savingTopic.value = true
  try {
    if (editingTopicId.value) {
      await patchTopic(editingTopicId.value, { name: topicFormName.value.trim() })
      ElMessage.success('更新成功')
    } else {
      await createTopic({ name: topicFormName.value.trim() })
      ElMessage.success('创建成功')
    }
    showAddTopicDialog.value = false
    resetTopicForm()
    await loadTopics()
  } catch (e) {
    ElMessage.error(editingTopicId.value ? '更新失败' : '创建失败')
  } finally {
    savingTopic.value = false
  }
}

async function handleDeleteTopic(topic) {
  try {
    await ElMessageBox.confirm(`确定删除主题词「${topic.name}」？所有母题词和关键词将一并删除。`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteTopic(topic.id)
    ElMessage.success('已删除')
    await loadTopics()
  } catch { /* cancelled */ }
}

async function loadConfig() {
  loadingConfig.value = true
  try {
    const data = await fetchKeywordGenConfig()
    configForm.value = { ...data }
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loadingConfig.value = false
  }
}

async function handleSaveConfig() {
  savingConfig.value = true
  try {
    await updateKeywordGenConfig(configForm.value)
    ElMessage.success('配置已保存')
    showConfigDialog.value = false
  } catch {
    ElMessage.error('保存配置失败')
  } finally {
    savingConfig.value = false
  }
}

function formatDate(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
</script>

<style scoped>
.tp-page { padding: 28px 32px; max-width: 1200px; }
.tp-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.tp-title { font-size: 22px; font-weight: 700; color: var(--text-primary, #1e293b); margin: 0; }
.tp-header-actions { display: flex; gap: 10px; }

.tp-btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 18px; border-radius: 8px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .15s; }
.tp-btn-primary { background: #6366f1; color: #fff; }
.tp-btn-primary:hover { background: #4f46e5; }
.tp-btn-config { background: #f1f5f9; color: #475569; }
.tp-btn-config:hover { background: #e2e8f0; }

.tp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; min-height: 100px; }

.tp-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 20px; cursor: pointer; transition: all .15s;
  display: flex; justify-content: space-between; align-items: flex-start;
}
.tp-card:hover { border-color: #6366f1; box-shadow: 0 2px 12px rgba(99,102,241,.1); }
.tp-card-name { font-size: 16px; font-weight: 600; color: #1e293b; margin-bottom: 8px; }
.tp-card-stats { display: flex; gap: 16px; margin-bottom: 6px; }
.tp-stat { font-size: 12px; color: #64748b; }
.tp-card-time { font-size: 11px; color: #94a3b8; }

.tp-card-actions { display: flex; gap: 4px; flex-shrink: 0; }
.tp-icon-btn {
  width: 30px; height: 30px; border-radius: 6px; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  background: transparent; color: #94a3b8; transition: all .15s;
}
.tp-icon-btn:hover { background: #f1f5f9; color: #475569; }
.tp-icon-btn-danger:hover { background: #fef2f2; color: #ef4444; }

.tp-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 20px; }
.tp-count-text { font-size: 13px; color: #94a3b8; }
.tp-pagination { display: flex; gap: 8px; }
.pg-btn { padding: 6px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #fff; color: #475569; font-size: 13px; cursor: pointer; transition: all .15s; }
.pg-btn:hover:not(:disabled) { border-color: #6366f1; color: #6366f1; }
.pg-btn:disabled { opacity: .4; cursor: not-allowed; }

/* Form */
.tp-form-label { display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 6px; }
.tp-form-hint { font-weight: 400; color: #94a3b8; font-size: 12px; }
.tp-form-input {
  width: 100%; padding: 9px 12px; border: 1px solid #d1d5db; border-radius: 8px;
  font-size: 14px; outline: none; transition: border .15s; box-sizing: border-box;
}
.tp-form-input:focus { border-color: #6366f1; }
.tp-form-textarea {
  width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px;
  font-size: 13px; outline: none; resize: vertical; font-family: monospace;
  line-height: 1.6; transition: border .15s; box-sizing: border-box;
}
.tp-form-textarea:focus { border-color: #6366f1; }

.config-form { display: flex; flex-direction: column; gap: 16px; padding: 0 4px; }
.config-row {}

/* Dialog buttons */
.dlg-btn-cancel { padding: 8px 18px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; color: #374151; font-size: 13px; cursor: pointer; }
.dlg-btn-cancel:hover { background: #f9fafb; }
.dlg-btn-primary { padding: 8px 18px; border: none; border-radius: 8px; background: #6366f1; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.dlg-btn-primary:hover { background: #4f46e5; }
.dlg-btn-primary:disabled { opacity: .5; cursor: not-allowed; }

.btn-spin {
  width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.3);
  border-top-color: #fff; border-radius: 50%; animation: spin .6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
