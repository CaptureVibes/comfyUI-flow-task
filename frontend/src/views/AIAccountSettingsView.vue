<template>
  <div class="aias-page" v-loading="loading">
    <div class="aias-header">
      <div class="aias-header-left">
        <h1 class="aias-title">AI博主配置</h1>
        <div class="aias-subtitle">配置 AI 生成博主名称、头像和照片时使用的提示词和模型</div>
      </div>
      <div class="aias-header-actions">
        <el-button type="primary" :loading="saving" @click="handleSave">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right:6px"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
          保存配置
        </el-button>
      </div>
    </div>

    <div class="aias-layout">

      <!-- 视频分析阶段 -->
      <div class="aias-card">
        <div class="aias-section">
          <div class="aias-section-header">
            <span class="aias-section-tag">阶段一：视频理解</span>
            <span class="aias-section-desc">并发分析选中标签对应的视频，生成文字描述</span>
          </div>
          <el-form-item label="视频分析提示词">
            <el-input
              v-model="form.ai_account_video_prompt"
              type="textarea"
              :rows="5"
              placeholder="请输入视频分析提示词，AI 将根据此提示词理解视频内容..."
              class="aias-input"
            />
          </el-form-item>
          <el-form-item label="视频理解模型">
            <el-input v-model="form.ai_account_video_model" placeholder="e.g. gemini-3.1-pro-preview" class="aias-input" />
          </el-form-item>
        </div>
      </div>

      <!-- 名称生成阶段 -->
      <div class="aias-card">
        <div class="aias-section">
          <div class="aias-section-header">
            <span class="aias-section-tag">阶段二：名称生成</span>
            <span class="aias-section-desc">基于视频描述，调用 Gemini 生成博主名称</span>
          </div>
          <el-form-item label="名称生成提示词">
            <el-input
              v-model="form.ai_account_name_prompt"
              type="textarea"
              :rows="5"
              placeholder="请输入名称生成提示词，AI 将基于视频内容描述生成博主名称..."
              class="aias-input"
            />
          </el-form-item>
          <el-form-item label="名称生成模型">
            <el-input v-model="form.ai_account_name_model" placeholder="e.g. gemini-3.1-pro-preview" class="aias-input" />
          </el-form-item>
        </div>
      </div>

      <!-- 头像生成阶段 -->
      <div class="aias-card">
        <div class="aias-section">
          <div class="aias-section-header">
            <span class="aias-section-tag">阶段三：头像生成</span>
            <span class="aias-section-desc">基于视频描述，调用 Nano2 生成博主头像</span>
          </div>
          <el-form-item label="头像生成提示词">
            <el-input
              v-model="form.ai_account_avatar_prompt"
              type="textarea"
              :rows="5"
              placeholder="请输入头像生成提示词，AI 将基于视频内容描述生成博主头像..."
              class="aias-input"
            />
          </el-form-item>
          <div class="aias-row">
            <el-form-item label="头像生成模型" class="aias-row-item">
              <el-input v-model="form.ai_account_avatar_model" placeholder="e.g. nano2" class="aias-input" />
            </el-form-item>
            <el-form-item label="头像尺寸" class="aias-row-item">
              <el-select v-model="form.ai_account_avatar_size" class="aias-input">
                <el-option label="1:1 (正方形)" value="1:1" />
                <el-option label="9:16 (竖版)" value="9:16" />
                <el-option label="16:9 (横版)" value="16:9" />
                <el-option label="3:4" value="3:4" />
              </el-select>
            </el-form-item>
            <el-form-item label="头像质量" class="aias-row-item">
              <el-select v-model="form.ai_account_avatar_quality" class="aias-input">
                <el-option label="1K" value="1K" />
                <el-option label="2K" value="2K" />
                <el-option label="4K" value="4K" />
              </el-select>
            </el-form-item>
          </div>
        </div>
      </div>

      <!-- 照片生成阶段 -->
      <div class="aias-card">
        <div class="aias-section">
          <div class="aias-section-header">
            <span class="aias-section-tag">阶段四：照片生成</span>
            <span class="aias-section-desc">随机选取一个视频，先用 Gemini 生成描述，再用 Nano2 生成照片</span>
          </div>
          <el-form-item label="视频理解提示词（阶段4-1）">
            <el-input
              v-model="form.ai_account_photo_video_prompt"
              type="textarea"
              :rows="4"
              placeholder="请描述视频中人物的外貌特征、肤色、发型、表情、体型等，用于生成写实人物照片..."
              class="aias-input"
            />
          </el-form-item>
          <el-form-item label="照片生成提示词（阶段4-2）">
            <el-input
              v-model="form.ai_account_photo_image_prompt"
              type="textarea"
              :rows="4"
              placeholder="请输入 Nano2 生图提示词前缀，将与视频描述拼接后调用生图..."
              class="aias-input"
            />
          </el-form-item>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchPipelineSettings, updatePipelineSettings } from '../api/settings'

const loading = ref(false)
const saving = ref(false)

const form = reactive({
  // 视频理解
  ai_account_video_prompt: '',
  ai_account_video_model: 'gemini-3.1-pro-preview',
  // 名称生成
  ai_account_name_prompt: '',
  ai_account_name_model: 'gemini-3.1-pro-preview',
  // 头像生成
  ai_account_avatar_prompt: '',
  ai_account_avatar_model: 'nano2',
  ai_account_avatar_size: '1:1',
  ai_account_avatar_quality: '1K',
  // 照片生成
  ai_account_photo_video_prompt: '',
  ai_account_photo_image_prompt: '',
  // 保留其他字段，保存时透传
  _pipeline: null,
})

async function loadSettings() {
  loading.value = true
  try {
    const data = await fetchPipelineSettings()
    form._pipeline = data
    form.ai_account_video_prompt = data.ai_account_video_prompt || ''
    form.ai_account_video_model = data.ai_account_video_model || 'gemini-3.1-pro-preview'
    form.ai_account_name_prompt = data.ai_account_name_prompt || ''
    form.ai_account_name_model = data.ai_account_name_model || 'gemini-3.1-pro-preview'
    form.ai_account_avatar_prompt = data.ai_account_avatar_prompt || ''
    form.ai_account_avatar_model = data.ai_account_avatar_model || 'nano2'
    form.ai_account_avatar_size = data.ai_account_avatar_size || '1:1'
    form.ai_account_avatar_quality = data.ai_account_avatar_quality || '1K'
    form.ai_account_photo_video_prompt = data.ai_account_photo_video_prompt || ''
    form.ai_account_photo_image_prompt = data.ai_account_photo_image_prompt || ''
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载配置失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (saving.value) return
  saving.value = true
  try {
    const base = form._pipeline || {}
    const payload = {
      ...base,
      ai_account_video_prompt: form.ai_account_video_prompt,
      ai_account_video_model: form.ai_account_video_model,
      ai_account_name_prompt: form.ai_account_name_prompt,
      ai_account_name_model: form.ai_account_name_model,
      ai_account_avatar_prompt: form.ai_account_avatar_prompt,
      ai_account_avatar_model: form.ai_account_avatar_model,
      ai_account_avatar_size: form.ai_account_avatar_size,
      ai_account_avatar_quality: form.ai_account_avatar_quality,
      ai_account_photo_video_prompt: form.ai_account_photo_video_prompt,
      ai_account_photo_image_prompt: form.ai_account_photo_image_prompt,
    }
    await updatePipelineSettings(payload)
    ElMessage.success('配置已保存')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.aias-page {
  padding: 30px;
  max-width: 900px;
  margin: 0 auto;
  min-height: 100vh;
  animation: aias-fade-in 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes aias-fade-in {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}

.aias-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.aias-title {
  font-size: 24px;
  font-weight: 800;
  color: #0f172a;
  margin: 0 0 6px 0;
  letter-spacing: -0.02em;
}

.aias-subtitle {
  font-size: 14px;
  color: #64748b;
}

.aias-layout {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.aias-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 20px -10px rgba(0,0,0,0.05);
  overflow: hidden;
}

.aias-section {
  padding: 24px;
}

.aias-section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.aias-section-tag {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
  background: #f1f5f9;
  padding: 4px 12px;
  border-radius: 8px;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

.aias-section-desc {
  font-size: 13px;
  color: #94a3b8;
}

.aias-input :deep(.el-input__wrapper),
.aias-input :deep(.el-textarea__inner),
.aias-input :deep(.el-select__wrapper) {
  background-color: #f8fafc;
  border-radius: 10px;
  box-shadow: none !important;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.aias-input :deep(.el-input__wrapper:hover),
.aias-input :deep(.el-textarea__inner:hover) {
  background-color: #f1f5f9;
}

.aias-input :deep(.el-input__wrapper.is-focus),
.aias-input :deep(.el-textarea__inner:focus) {
  background-color: #ffffff;
  border-color: #818cf8;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
}

:deep(.el-form-item__label) {
  font-weight: 600;
  color: #334155;
  padding-bottom: 6px;
}

.aias-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}

.aias-row-item {
  flex: 1;
}

</style>
