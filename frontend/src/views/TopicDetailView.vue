<template>
  <div class="td-page">
    <!-- Back + title + actions -->
    <div class="td-header">
      <button class="td-back-btn" @click="$router.push('/dashboard/topics')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
        返回
      </button>
      <h1 class="td-title">{{ topic?.name || '加载中...' }}</h1>
      <button class="td-btn td-btn-refresh" @click="handleRefresh" :disabled="refreshing">
        <svg :class="{ 'icon-spinning': refreshing }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
        刷新
      </button>
      <button class="td-btn td-btn-ai-batch" :disabled="batchGenerating" @click="handleBatchGenerate">
        <span v-if="batchGenerating" class="btn-spin"></span>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5z"/></svg>
        一键AI生成关键词
      </button>
      <button class="td-btn td-btn-primary" @click="showAddMkDialog = true">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        添加母题词
      </button>
    </div>

    <!-- Status summary cards -->
    <div v-if="genStatus && genStatus.total > 0" class="status-bar">
      <div class="status-item">
        <span class="status-num">{{ genStatus.total }}</span>
        <span class="status-label">总计</span>
      </div>
      <div class="status-item status-item-idle">
        <span class="status-num">{{ genStatus.idle }}</span>
        <span class="status-label">待生成</span>
      </div>
      <div class="status-item status-item-pending">
        <span class="status-num">{{ genStatus.pending }}</span>
        <span class="status-label">排队中</span>
      </div>
      <div class="status-item status-item-generating">
        <span class="status-num">{{ genStatus.generating }}</span>
        <span class="status-label">生成中</span>
      </div>
      <div class="status-item status-item-done">
        <span class="status-num">{{ genStatus.done }}</span>
        <span class="status-label">已完成</span>
      </div>
      <div class="status-item status-item-failed">
        <span class="status-num">{{ genStatus.failed }}</span>
        <span class="status-label">失败</span>
      </div>
    </div>

    <div v-loading="loading" class="td-body">
      <!-- Mother keyword cards -->
      <div v-for="mk in motherKeywords" :key="mk.id" class="mk-card">
        <div class="mk-header">
          <div class="mk-name-row">
            <span class="mk-name">{{ mk.name }}</span>
            <span v-if="mk.gen_status === 'pending'" class="mk-status mk-status-pending">排队中</span>
            <span v-else-if="mk.gen_status === 'generating'" class="mk-status mk-status-generating"><span class="btn-spin-sm"></span>生成中</span>
            <span v-else-if="mk.gen_status === 'failed'" class="mk-status mk-status-failed" :title="mk.gen_error">失败</span>
            <span v-else-if="mk.gen_status === 'done'" class="mk-status mk-status-done">已生成</span>
            <span class="mk-kw-count">{{ mk.keywords?.length || 0 }} 个关键词</span>
          </div>
          <div class="mk-actions">
            <button class="td-btn td-btn-ai" :disabled="mk.gen_status === 'pending' || mk.gen_status === 'generating'" @click="handleGenerate(mk)">
              <span v-if="mk.gen_status === 'pending' || mk.gen_status === 'generating'" class="btn-spin"></span>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5z"/></svg>
              AI生成关键词
            </button>
            <button class="td-icon-btn" @click="startEditMk(mk)" title="编辑">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button class="td-icon-btn td-icon-btn-danger" @click="handleDeleteMk(mk)" title="删除">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>

        <!-- Keywords -->
        <div class="kw-list">
          <div v-for="kw in mk.keywords" :key="kw.id" class="kw-tag">
            <span class="kw-text">{{ kw.keyword }}</span>
            <button class="kw-del" @click="handleDeleteKw(mk, kw)" title="删除">×</button>
          </div>
          <!-- Inline add keyword -->
          <div class="kw-add-inline">
            <input
              v-model="mk._newKw"
              class="kw-add-input"
              placeholder="+ 添加关键词"
              @keyup.enter="handleAddKw(mk)"
            />
          </div>
        </div>
      </div>

      <el-empty v-if="!loading && motherKeywords.length === 0" description="暂无母题词，点击「添加母题词」开始" :image-size="60" />
    </div>

    <!-- Pagination -->
    <div v-if="mkTotal > mkPageSize" class="td-footer">
      <span class="td-count-text">共 {{ mkTotal }} 个母题词</span>
      <div class="td-pagination">
        <button class="pg-btn" :disabled="mkPage <= 1" @click="mkPage--; loadMotherKeywords()">← 上一页</button>
        <span class="pg-info">{{ mkPage }} / {{ Math.ceil(mkTotal / mkPageSize) }}</span>
        <button class="pg-btn" :disabled="mkPage * mkPageSize >= mkTotal" @click="mkPage++; loadMotherKeywords()">下一页 →</button>
      </div>
    </div>

    <!-- Add/Edit Mother Keyword Dialog -->
    <el-dialog v-model="showAddMkDialog" :title="editingMkId ? '编辑母题词' : '批量添加母题词'" width="480px" align-center destroy-on-close @close="resetMkForm">
      <div style="padding: 0 4px">
        <template v-if="editingMkId">
          <label class="td-form-label">母题词名称</label>
          <input v-model="mkFormName" class="td-form-input" placeholder="请输入母题词" @keyup.enter="handleSaveMk" />
        </template>
        <template v-else>
          <label class="td-form-label">母题词名称 <span class="td-form-hint">（每行一个，支持批量添加）</span></label>
          <textarea v-model="mkFormName" class="td-form-textarea" rows="8" placeholder="请输入母题词，每行一个&#10;例如：&#10;minimalist fashion&#10;street style&#10;vintage outfit" />
          <div v-if="batchCount > 0" class="td-batch-count">将创建 {{ batchCount }} 个母题词</div>
        </template>
      </div>
      <template #footer>
        <button class="dlg-btn-cancel" @click="showAddMkDialog = false">取消</button>
        <button class="dlg-btn-primary" :disabled="!mkFormName.trim() || savingMk" @click="handleSaveMk">
          <span v-if="savingMk" class="btn-spin"></span>
          {{ editingMkId ? '保存' : `批量添加 (${batchCount})` }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchTopic,
  fetchMotherKeywords,
  fetchGenStatus,
  createMotherKeyword,
  patchMotherKeyword,
  deleteMotherKeyword,
  createKeyword,
  deleteKeyword,
  generateKeywords,
  batchGenerateKeywords,
} from '../api/topics'

const route = useRoute()
const topicId = route.params.id

const loading = ref(false)
const refreshing = ref(false)
const topic = ref(null)
const motherKeywords = ref([])
const mkPage = ref(1)
const mkPageSize = ref(20)
const mkTotal = ref(0)

// Gen status
const genStatus = ref(null)
const batchGenerating = ref(false)
let statusPollTimer = null

// MK form
const showAddMkDialog = ref(false)
const mkFormName = ref('')
const editingMkId = ref(null)
const savingMk = ref(false)

function parseBatchNames(text) {
  return text.split('\n')
    .map(l => l.trim())
    .filter(Boolean)
    .map(l => l.replace(/^\d+[\.\)、]\s*/, ''))
    .map(l => l.replace(/^\*+\s*/, ''))
    .map(l => l.replace(/^-\s+/, ''))
    .map(l => l.trim())
    .filter(Boolean)
}

const batchCount = computed(() => {
  if (editingMkId.value) return 0
  return parseBatchNames(mkFormName.value).length
})

onMounted(async () => {
  await loadTopicBasic()
  await Promise.all([loadMotherKeywords(), loadGenStatus()])
  if (hasRunningTasks()) {
    batchGenerating.value = true
    startStatusPolling()
  }
})

onBeforeUnmount(() => stopStatusPolling())

// ── Data loading ──

async function loadTopicBasic() {
  try {
    const data = await fetchTopic(topicId)
    topic.value = data
  } catch {
    ElMessage.error('加载主题词详情失败')
  }
}

async function loadMotherKeywords() {
  loading.value = true
  try {
    const res = await fetchMotherKeywords(topicId, { page: mkPage.value, page_size: mkPageSize.value })
    motherKeywords.value = res.items.map(mk => ({ ...mk, _newKw: '' }))
    mkTotal.value = res.total
  } catch {
    ElMessage.error('加载母题词失败')
  } finally {
    loading.value = false
  }
}

async function loadGenStatus() {
  try {
    genStatus.value = await fetchGenStatus(topicId)
  } catch { /* ignore */ }
}

function hasRunningTasks() {
  return genStatus.value && (genStatus.value.pending > 0 || genStatus.value.generating > 0)
}

// ── Status polling (lightweight, only polls gen-status) ──

function startStatusPolling() {
  stopStatusPolling()
  statusPollTimer = setTimeout(async () => {
    await loadGenStatus()
    if (hasRunningTasks()) {
      startStatusPolling()
    } else {
      batchGenerating.value = false
      // Final refresh of the MK list to show new keywords
      await loadMotherKeywords()
    }
  }, 5000)
}

function stopStatusPolling() {
  if (statusPollTimer) {
    clearTimeout(statusPollTimer)
    statusPollTimer = null
  }
}

// ── Refresh ──

async function handleRefresh() {
  refreshing.value = true
  try {
    await Promise.all([loadTopicBasic(), loadMotherKeywords(), loadGenStatus()])
    if (hasRunningTasks()) {
      batchGenerating.value = true
      startStatusPolling()
    }
  } finally {
    refreshing.value = false
  }
}

// ── Mother Keyword ──

function startEditMk(mk) {
  editingMkId.value = mk.id
  mkFormName.value = mk.name
  showAddMkDialog.value = true
}

function resetMkForm() {
  editingMkId.value = null
  mkFormName.value = ''
}

async function handleSaveMk() {
  if (!mkFormName.value.trim()) return
  savingMk.value = true
  try {
    if (editingMkId.value) {
      await patchMotherKeyword(editingMkId.value, { name: mkFormName.value.trim() })
      ElMessage.success('更新成功')
    } else {
      const names = parseBatchNames(mkFormName.value)
      const result = await createMotherKeyword(topicId, { names })
      ElMessage.success(`已添加 ${result.length} 个母题词`)
    }
    showAddMkDialog.value = false
    resetMkForm()
    await Promise.all([loadMotherKeywords(), loadGenStatus()])
  } catch {
    ElMessage.error('操作失败')
  } finally {
    savingMk.value = false
  }
}

async function handleDeleteMk(mk) {
  try {
    await ElMessageBox.confirm(`确定删除母题词「${mk.name}」？其下所有关键词将一并删除。`, '确认删除', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await deleteMotherKeyword(mk.id)
    ElMessage.success('已删除')
    await Promise.all([loadMotherKeywords(), loadGenStatus()])
  } catch { /* cancelled */ }
}

// ── Keyword ──

async function handleAddKw(mk) {
  const text = (mk._newKw || '').trim()
  if (!text) return
  try {
    await createKeyword(mk.id, { keyword: text })
    mk._newKw = ''
    await loadMotherKeywords()
  } catch {
    ElMessage.error('添加关键词失败')
  }
}

async function handleDeleteKw(mk, kw) {
  try {
    await deleteKeyword(kw.id)
    mk.keywords = mk.keywords.filter(k => k.id !== kw.id)
  } catch {
    ElMessage.error('删除关键词失败')
  }
}

// ── AI Generation ──

async function handleGenerate(mk) {
  try {
    await generateKeywords(mk.id)
    mk.gen_status = 'pending'
    ElMessage.success('已提交生成')
    await loadGenStatus()
    batchGenerating.value = true
    startStatusPolling()
  } catch (e) {
    const msg = e?.response?.data?.detail || 'AI生成关键词失败'
    ElMessage.error(msg)
  }
}

async function handleBatchGenerate() {
  batchGenerating.value = true
  try {
    const res = await batchGenerateKeywords(topicId)
    if (res.queued === 0) {
      ElMessage.info('所有母题词已生成关键词，无需重复生成')
      batchGenerating.value = false
      return
    }
    ElMessage.success(`已提交 ${res.queued} 个母题词进行AI生成`)
    await loadGenStatus()
    startStatusPolling()
  } catch (e) {
    const msg = e?.response?.data?.detail || '批量生成失败'
    ElMessage.error(msg)
    batchGenerating.value = false
  }
}
</script>

<style scoped>
.td-page { padding: 28px 32px; max-width: 1100px; }
.td-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
.td-back-btn {
  display: inline-flex; align-items: center; gap: 4px; padding: 6px 12px;
  border: 1px solid #e2e8f0; border-radius: 6px; background: #fff; color: #64748b;
  font-size: 13px; cursor: pointer; transition: all .15s;
}
.td-back-btn:hover { border-color: #6366f1; color: #6366f1; }
.td-title { font-size: 20px; font-weight: 700; color: #1e293b; margin: 0; flex: 1; }

.td-btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 16px; border-radius: 8px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .15s; }
.td-btn-primary { background: #6366f1; color: #fff; }
.td-btn-primary:hover { background: #4f46e5; }
.td-btn-refresh { background: #f1f5f9; color: #475569; }
.td-btn-refresh:hover { background: #e2e8f0; }
.td-btn-refresh:disabled { opacity: .5; cursor: not-allowed; }
.td-btn-ai { background: linear-gradient(135deg, #8b5cf6, #6366f1); color: #fff; }
.td-btn-ai:hover { opacity: .9; }
.td-btn-ai:disabled { opacity: .5; cursor: not-allowed; }
.td-btn-ai-batch { background: linear-gradient(135deg, #f59e0b, #f97316); color: #fff; }
.td-btn-ai-batch:hover { opacity: .9; }
.td-btn-ai-batch:disabled { opacity: .5; cursor: not-allowed; }

.icon-spinning { animation: spin .8s linear infinite; }

.td-icon-btn {
  width: 28px; height: 28px; border-radius: 6px; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  background: transparent; color: #94a3b8; transition: all .15s;
}
.td-icon-btn:hover { background: #f1f5f9; color: #475569; }
.td-icon-btn-danger:hover { background: #fef2f2; color: #ef4444; }

/* Status bar */
.status-bar {
  display: flex; gap: 12px; margin-bottom: 20px; padding: 14px 20px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
}
.status-item { display: flex; flex-direction: column; align-items: center; min-width: 60px; }
.status-num { font-size: 20px; font-weight: 700; color: #1e293b; line-height: 1.2; }
.status-label { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.status-item-idle .status-num { color: #64748b; }
.status-item-pending .status-num { color: #d97706; }
.status-item-generating .status-num { color: #2563eb; }
.status-item-done .status-num { color: #16a34a; }
.status-item-failed .status-num { color: #dc2626; }

.td-body { display: flex; flex-direction: column; gap: 16px; min-height: 100px; }

/* Mother Keyword Card */
.mk-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 18px 20px; transition: border .15s;
}
.mk-card:hover { border-color: #cbd5e1; }
.mk-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.mk-name-row { display: flex; align-items: baseline; gap: 10px; }
.mk-name { font-size: 15px; font-weight: 600; color: #1e293b; }
.mk-kw-count { font-size: 12px; color: #94a3b8; }
.mk-status { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; display: inline-flex; align-items: center; gap: 4px; }
.mk-status-pending { background: #fef3c7; color: #92400e; }
.mk-status-generating { background: #dbeafe; color: #1e40af; }
.mk-status-failed { background: #fef2f2; color: #dc2626; cursor: help; }
.mk-status-done { background: #dcfce7; color: #166534; }
.btn-spin-sm { width: 10px; height: 10px; border: 1.5px solid rgba(30,64,175,.3); border-top-color: #1e40af; border-radius: 50%; animation: spin .6s linear infinite; }
.mk-actions { display: flex; gap: 6px; align-items: center; }

/* Keywords */
.kw-list { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.kw-tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; background: #f1f5f9; border-radius: 6px;
  font-size: 13px; color: #334155; transition: all .15s;
}
.kw-tag:hover { background: #e2e8f0; }
.kw-del {
  width: 16px; height: 16px; border: none; background: transparent;
  color: #94a3b8; font-size: 14px; cursor: pointer; display: flex;
  align-items: center; justify-content: center; border-radius: 50%;
  transition: all .15s; line-height: 1; padding: 0;
}
.kw-del:hover { background: #fecaca; color: #dc2626; }

.kw-add-inline { display: inline-flex; }
.kw-add-input {
  border: 1px dashed #d1d5db; border-radius: 6px; padding: 4px 10px;
  font-size: 13px; color: #475569; outline: none; width: 140px;
  background: transparent; transition: all .15s;
}
.kw-add-input:focus { border-color: #6366f1; border-style: solid; width: 200px; }
.kw-add-input::placeholder { color: #94a3b8; }

/* Pagination */
.td-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 20px; }
.td-count-text { font-size: 13px; color: #94a3b8; }
.td-pagination { display: flex; gap: 8px; align-items: center; }
.pg-btn { padding: 6px 14px; border: 1px solid #e2e8f0; border-radius: 6px; background: #fff; color: #475569; font-size: 13px; cursor: pointer; transition: all .15s; }
.pg-btn:hover:not(:disabled) { border-color: #6366f1; color: #6366f1; }
.pg-btn:disabled { opacity: .4; cursor: not-allowed; }
.pg-info { font-size: 13px; color: #64748b; }

/* Form */
.td-form-label { display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 6px; }
.td-form-input {
  width: 100%; padding: 9px 12px; border: 1px solid #d1d5db; border-radius: 8px;
  font-size: 14px; outline: none; transition: border .15s; box-sizing: border-box;
}
.td-form-input:focus { border-color: #6366f1; }
.td-form-hint { font-weight: 400; color: #94a3b8; font-size: 12px; }
.td-form-textarea {
  width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px;
  font-size: 14px; outline: none; resize: vertical; line-height: 1.6;
  transition: border .15s; box-sizing: border-box;
}
.td-form-textarea:focus { border-color: #6366f1; }
.td-batch-count { margin-top: 8px; font-size: 12px; color: #6366f1; font-weight: 500; }

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
