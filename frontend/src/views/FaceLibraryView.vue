<template>
  <div class="fl-page">
    <div class="fl-header">
      <h2 class="fl-title">人脸库</h2>
      <button class="fl-btn-refresh" @click="loadTags" :disabled="loading">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round">
          <polyline points="1 4 1 10 7 10" />
          <path d="M3.51 15a9 9 0 1 0 .49-3.87" />
        </svg>
        刷新
      </button>
      <button class="fl-btn-config" @click="openConfigDialog">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
        AI配置
      </button>
    </div>

    <div v-if="loading" class="fl-loading">加载中...</div>

    <div v-else-if="tags.length === 0" class="fl-empty">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5"
        stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="8" r="4" />
        <path d="M6 21v-1a6 6 0 0 1 12 0v1" />
      </svg>
      <p>暂无标签，请先创建标签并关联视频</p>
    </div>

    <div v-else class="fl-grid">
      <div v-for="tag in tags" :key="tag.id" class="fl-card">
        <!-- 人脸图片 -->
        <div class="fl-photo-wrap">
          <img v-if="tag.face_photo?.face_photo_url" :src="tag.face_photo.face_photo_url"
            class="fl-photo" alt="人脸照片" />
          <div v-else class="fl-photo-placeholder">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"
              stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="4" />
              <path d="M6 21v-1a6 6 0 0 1 12 0v1" />
            </svg>
          </div>
          <!-- 加载中遮罩 -->
          <div v-if="loadingTags.has(tag.id)" class="fl-loading-mask">
            <div class="fl-spinner"></div>
          </div>
        </div>

        <!-- 标签信息 -->
        <div class="fl-info">
          <div class="fl-tag-name">
            <span v-if="tag.color" class="fl-color-dot" :style="{ background: tag.color }"></span>
            {{ tag.name }}
          </div>
          <div class="fl-meta">
            <span class="fl-video-count">{{ tag.video_count }} 个视频</span>
            <span v-if="tag.face_photo" class="fl-frame-index">第 {{ tag.face_photo.frame_index }} 帧</span>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="fl-actions">
          <button
            class="fl-btn-select"
            :disabled="loadingTags.has(tag.id) || tag.video_count === 0"
            @click="handleSelectFace(tag)"
          >
            <span v-if="loadingTags.has(tag.id)">AI选择中...</span>
            <span v-else-if="tag.face_photo">重新选择</span>
            <span v-else>选择人脸</span>
          </button>
        </div>
      </div>
    </div>

    <!-- AI配置弹窗 -->
    <el-dialog v-model="showConfigDialog" title="人脸选择 AI 配置" width="580px" align-center destroy-on-close @open="loadConfig">
      <div v-loading="loadingConfig" class="config-form">
        <div class="cf-row">
          <label class="cf-label">AI 模型</label>
          <el-input v-model="configForm.face_select_model" placeholder="gemini-3.1-pro-preview" />
          <span class="cf-hint">用于分析帧图片并选择最佳人脸的模型</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">选择提示词</label>
          <el-input
            v-model="configForm.face_select_prompt"
            type="textarea"
            :rows="6"
            placeholder="请输入人脸选择提示词，系统会自动在末尾追加 JSON 输出要求..."
          />
          <span class="cf-hint">AI 将根据此提示词从 10 张帧图片中选择最佳人脸（输出 selected: 1-10）</span>
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
import { ElMessage } from 'element-plus'
import { fetchTagsWithFaces, triggerFaceSelection } from '../api/faceLibrary'
import { fetchPipelineSettings, updatePipelineSettings } from '../api/settings'

const tags = ref([])
const loading = ref(false)
const loadingTags = ref(new Set())

// 配置弹窗
const showConfigDialog = ref(false)
const loadingConfig = ref(false)
const savingConfig = ref(false)
const configForm = ref({
  face_select_model: 'gemini-3.1-pro-preview',
  face_select_prompt: '',
})

async function loadTags() {
  loading.value = true
  try {
    tags.value = await fetchTagsWithFaces()
  } catch {
    ElMessage.error('加载人脸库失败')
  } finally {
    loading.value = false
  }
}

async function handleSelectFace(tag) {
  if (loadingTags.value.has(tag.id)) return
  loadingTags.value = new Set([...loadingTags.value, tag.id])
  try {
    const result = await triggerFaceSelection(tag.id)
    // 更新对应 tag 的 face_photo
    const idx = tags.value.findIndex(t => t.id === tag.id)
    if (idx !== -1) {
      tags.value[idx] = { ...tags.value[idx], face_photo: result }
    }
    ElMessage.success('人脸选择成功')
  } catch (err) {
    const msg = err?.response?.data?.detail || '人脸选择失败，请稍后重试'
    ElMessage.error(msg)
  } finally {
    const next = new Set(loadingTags.value)
    next.delete(tag.id)
    loadingTags.value = next
  }
}

function openConfigDialog() {
  showConfigDialog.value = true
}

async function loadConfig() {
  loadingConfig.value = true
  try {
    const data = await fetchPipelineSettings()
    configForm.value.face_select_model = data.face_select_model || 'gemini-3.1-pro-preview'
    configForm.value.face_select_prompt = data.face_select_prompt || ''
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loadingConfig.value = false
  }
}

async function handleSaveConfig() {
  savingConfig.value = true
  try {
    await updatePipelineSettings(configForm.value)
    ElMessage.success('配置已保存')
    showConfigDialog.value = false
  } catch {
    ElMessage.error('保存配置失败')
  } finally {
    savingConfig.value = false
  }
}

onMounted(loadTags)
</script>

<style scoped>
.fl-page {
  padding: 24px;
  max-width: 1400px;
}

.fl-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.fl-title {
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.fl-btn-refresh,
.fl-btn-config {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.fl-btn-refresh:hover:not(:disabled),
.fl-btn-config:hover:not(:disabled) { background: #f8fafc; }
.fl-btn-refresh:disabled,
.fl-btn-config:disabled { opacity: 0.5; cursor: not-allowed; }

.fl-loading {
  color: #94a3b8;
  padding: 40px;
  text-align: center;
}

.fl-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 80px 20px;
  color: #94a3b8;
  font-size: 14px;
}

.fl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}

.fl-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s;
}
.fl-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }

.fl-photo-wrap {
  position: relative;
  width: 100%;
  padding-top: 100%;
  background: #f8fafc;
}

.fl-photo {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.fl-photo-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
}

.fl-loading-mask {
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,0.75);
  display: flex;
  align-items: center;
  justify-content: center;
}

.fl-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid #e2e8f0;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: fl-spin 0.8s linear infinite;
}

@keyframes fl-spin {
  to { transform: rotate(360deg); }
}

.fl-info {
  padding: 12px 12px 8px;
  flex: 1;
}

.fl-tag-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fl-color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.fl-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.fl-actions {
  padding: 0 12px 12px;
}

.fl-btn-select {
  width: 100%;
  padding: 7px 0;
  border: none;
  border-radius: 6px;
  background: #6366f1;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.fl-btn-select:hover:not(:disabled) { background: #4f46e5; }
.fl-btn-select:disabled { background: #c7d2fe; cursor: not-allowed; }

/* 配置弹窗样式 */
.config-form {
  min-height: 120px;
}

.cf-row {
  margin-bottom: 18px;
}

.cf-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 6px;
}

.cf-hint {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

.dlg-btn-cancel,
.dlg-btn-primary {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  margin-left: 8px;
}

.dlg-btn-cancel {
  background: #f1f5f9;
  color: #475569;
}
.dlg-btn-cancel:hover { background: #e2e8f0; }

.dlg-btn-primary {
  background: #6366f1;
  color: #fff;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.dlg-btn-primary:hover:not(:disabled) { background: #4f46e5; }
.dlg-btn-primary:disabled { background: #c7d2fe; cursor: not-allowed; }

.btn-spin {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: fl-spin 0.8s linear infinite;
}
</style>
