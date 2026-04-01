<template>
  <div class="tc-page">
    <!-- Header -->
    <div class="tc-header">
      <button class="tc-back-btn" @click="goBack">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
        返回
      </button>
      <span class="tc-header-divider"></span>
      <h1 class="tc-title">任务配置</h1>
    </div>

    <div v-loading="loading" class="tc-body">

      <!-- ── 发布候选池配置 ── -->
      <div class="tc-card">
        <div class="tc-card-header">
          <div class="tc-card-title-wrap">
            <span class="tc-card-icon tc-icon-blue">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
            </span>
            <span class="tc-card-title">发布候选池配置</span>
          </div>
        </div>
        <div class="tc-card-body">
          <div class="tc-info-box">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" style="flex-shrink:0;margin-top:1px"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <p>
              有穿帮（has_ng=true）→ 直接废弃；<br>
              AI 感 ≥ 进入候选池分数线 → 进入发布队列；<br>
              AI 感 &lt; 丢弃分数线 → 废弃；<br>
              中间区间 → 按比例随机进入候选池。
            </p>
          </div>

          <div class="tc-field">
            <label class="tc-label">
              AI 感进入候选池分数线
              <span class="tc-threshold-val">{{ config.score_threshold_high }}</span>
            </label>
            <div class="tc-slider-wrap">
              <input
                v-model.number="config.score_threshold_high"
                type="range" :min="0" :max="100" :step="1"
                class="tc-slider"
                :style="sliderStyle(config.score_threshold_high)"
              />
              <div class="tc-slider-marks">
                <span>0</span><span>多维度加权总分达到此值进入候选池</span><span>100</span>
              </div>
            </div>
          </div>

          <div class="tc-field">
            <label class="tc-label">
              AI 感丢弃分数线
              <span class="tc-threshold-val">{{ config.score_threshold_low }}</span>
            </label>
            <div class="tc-slider-wrap">
              <input
                v-model.number="config.score_threshold_low"
                type="range" :min="0" :max="100" :step="1"
                class="tc-slider"
                :style="sliderStyle(config.score_threshold_low)"
              />
              <div class="tc-slider-marks">
                <span>0</span><span>低于此分数直接废弃</span><span>100</span>
              </div>
            </div>
          </div>

          <div class="tc-field">
            <label class="tc-label">
              中间区间进入候选池比例
              <span class="tc-threshold-val">{{ Math.round(config.pool_ratio * 100) }}%</span>
            </label>
            <div class="tc-slider-wrap">
              <input
                v-model.number="config.pool_ratio"
                type="range" :min="0" :max="1" :step="0.01"
                class="tc-slider"
                :style="sliderStyle(config.pool_ratio * 100)"
              />
              <div class="tc-slider-marks">
                <span>0%</span><span>中间区间内随机进入候选池的概率</span><span>100%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 自动发布 AI 生成内容 ── -->
      <div class="tc-card">
        <div class="tc-card-header">
          <div class="tc-card-title-wrap">
            <span class="tc-card-icon tc-icon-orange">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            </span>
            <span class="tc-card-title">自动发布 AI 生成标题 / 描述 / 标签</span>
          </div>
          <el-switch v-model="config.auto_publish_enabled" />
        </div>
        <div class="tc-card-body">
          <div class="tc-info-box">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" style="flex-shrink:0;margin-top:1px"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <p>启用后，自动发布前会调用 AI 分析视频内容，生成标题、描述和 hashtag。AI 必须返回 JSON 格式：<code class="tc-code">{"title":"...","desc":"...","hashtag":["..."]}</code></p>
          </div>
          <template v-if="config.auto_publish_enabled">
            <div class="tc-field" style="margin-top:16px">
              <label class="tc-label">模型</label>
              <input
                v-model="config.auto_publish_model"
                class="tc-input"
                placeholder="如: gemini-3.1-pro-preview"
              />
            </div>
            <div class="tc-field">
              <label class="tc-label">提示词</label>
              <textarea
                v-model="config.auto_publish_prompt"
                class="tc-textarea"
                rows="8"
                placeholder="请输入提示词，告诉 AI 如何根据视频内容生成标题、描述和标签。AI 必须输出 JSON 格式。"
              />
            </div>
          </template>
        </div>
      </div>

      <!-- ── Save ── -->
      <div class="tc-actions">
        <button class="tc-save-btn" :class="{ loading: saving }" :disabled="saving" @click="saveConfig">
          <span v-if="saving" class="tc-btn-spin"></span>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" style="margin-right:6px"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
          {{ saving ? '保存中…' : '保存配置' }}
        </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchTaskConfig, updateTaskConfig } from '../api/video_task_config'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)

const config = reactive({
  score_threshold_high: 60,
  score_threshold_low: 20,
  pool_ratio: 0.75,
  auto_publish_enabled: false,
  auto_publish_model: 'gemini-3.1-pro-preview',
  auto_publish_prompt: '',
})

function sliderStyle(val) {
  const pct = `${val}%`
  return {
    background: `linear-gradient(to right, #6366f1 ${pct}, #e2e8f0 ${pct})`,
  }
}

async function loadConfig() {
  loading.value = true
  try {
    const data = await fetchTaskConfig()
    Object.assign(config, data)
  } catch (error) {
    ElMessage.error('加载配置失败: ' + (error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    await updateTaskConfig(config)
    ElMessage.success('配置已保存')
  } catch (error) {
    ElMessage.error('保存配置失败: ' + (error.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

function goBack() {
  router.back()
}

onMounted(loadConfig)
</script>

<style scoped>
.tc-page {
  padding: 28px 32px;
  max-width: 860px;
  margin: 0 auto;
  animation: rise 0.3s ease;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── Header ── */
.tc-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}

.tc-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 34px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.tc-back-btn:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.tc-header-divider {
  width: 1px;
  height: 18px;
  background: #e2e8f0;
}

.tc-title {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
  letter-spacing: -0.02em;
}

/* ── Cards ── */
.tc-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tc-card {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e8ecf4;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  overflow: hidden;
}

.tc-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 24px;
  border-bottom: 1px solid #f1f5f9;
  background: #fafbff;
}

.tc-card-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tc-card-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  flex-shrink: 0;
}

.tc-icon-blue   { background: #eff6ff; color: #3b82f6; }
.tc-icon-orange { background: #fff7ed; color: #f59e0b; }

.tc-card-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.tc-card-body {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Form fields ── */
.tc-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.tc-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.tc-threshold-val {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  background: #6366f1;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.tc-input {
  height: 40px;
  padding: 0 12px;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  font-size: 14px;
  color: #334155;
  background: #fff;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  width: 100%;
  box-sizing: border-box;
}

.tc-input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
}

.tc-textarea {
  padding: 10px 12px;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  font-size: 14px;
  color: #334155;
  background: #fff;
  outline: none;
  resize: vertical;
  line-height: 1.6;
  transition: border-color 0.15s, box-shadow 0.15s;
  font-family: inherit;
  width: 100%;
  box-sizing: border-box;
}

.tc-textarea:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
}

/* ── Slider ── */
.tc-slider-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tc-slider {
  -webkit-appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 3px;
  outline: none;
  cursor: pointer;
}

.tc-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  border: 2.5px solid #6366f1;
  box-shadow: 0 2px 6px rgba(99,102,241,0.3);
  cursor: pointer;
  transition: box-shadow 0.15s;
}

.tc-slider::-webkit-slider-thumb:hover {
  box-shadow: 0 2px 10px rgba(99,102,241,0.5);
}

.tc-slider-marks {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #94a3b8;
  padding: 0 2px;
}

/* ── Info box ── */
.tc-info-box {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 13px;
  color: #4338ca;
  line-height: 1.6;
}

.tc-info-box p { margin: 0; }

.tc-code {
  background: #e0e7ff;
  color: #3730a3;
  border-radius: 4px;
  padding: 1px 6px;
  font-family: monospace;
  font-size: 12px;
}

/* ── Actions ── */
.tc-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  padding: 8px 0 16px;
}

.tc-save-btn {
  display: inline-flex;
  align-items: center;
  height: 42px;
  padding: 0 28px;
  border-radius: 11px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.15s;
  box-shadow: 0 3px 10px rgba(99,102,241,0.35);
}

.tc-save-btn:hover:not(:disabled) {
  opacity: 0.92;
  transform: translateY(-1px);
}

.tc-save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.tc-btn-spin {
  display: inline-block;
  width: 15px;
  height: 15px;
  border: 2.5px solid rgba(255,255,255,0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  margin-right: 8px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
