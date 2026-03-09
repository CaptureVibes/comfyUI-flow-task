<template>
  <div class="task-config-page">
    <el-page-header @back="goBack" title="返回">
      <template #content>
        <span class="text-large font-600">任务配置</span>
      </template>
    </el-page-header>

    <div v-loading="loading" class="config-content">
      <!-- Round 1 -->
      <el-card class="round-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>第一轮 AI 打分</span>
            <el-switch v-model="config.round1_enabled" />
          </div>
        </template>
        <el-form :model="config" label-width="100px" label-position="left">
          <el-form-item label="提示词">
            <el-input
              v-model="config.round1_prompt"
              type="textarea"
              :rows="4"
              placeholder="输入第一轮 AI 打分的提示词..."
            />
          </el-form-item>
          <el-form-item label="模型">
            <el-input
              v-model="config.round1_model"
              placeholder="输入模型名称，如: gemini-2.0-flash"
            />
          </el-form-item>
          <el-form-item label="通过阈值">
            <el-slider
              v-model="config.round1_threshold"
              :min="0"
              :max="100"
              :step="1"
              show-input
              :marks="{ 0: '0', 50: '50', 100: '100' }"
            />
            <span class="hint">分数达到此阈值可进入第二轮</span>
          </el-form-item>
          <el-form-item label="权重">
            <el-input-number
              v-model="config.round1_weight"
              :min="0"
              :max="1"
              :step="0.05"
              :precision="2"
              style="width: 100%"
            />
            <span class="hint">最终得分 = 第一轮评分 × {{ config.round1_weight }} + 第二轮评分 × {{ config.round2_weight }}</span>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- Round 2 -->
      <el-card class="round-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>第二轮 AI 打分</span>
            <el-switch v-model="config.round2_enabled" />
          </div>
        </template>
        <el-form :model="config" label-width="100px" label-position="left">
          <el-form-item label="提示词">
            <el-input
              v-model="config.round2_prompt"
              type="textarea"
              :rows="4"
              placeholder="输入第二轮 AI 打分的提示词..."
            />
          </el-form-item>
          <el-form-item label="模型">
            <el-input
              v-model="config.round2_model"
              placeholder="输入模型名称，如: gemini-2.0-flash"
            />
          </el-form-item>
          <el-form-item label="通过阈值">
            <el-slider
              v-model="config.round2_threshold"
              :min="0"
              :max="100"
              :step="1"
              show-input
              :marks="{ 0: '0', 50: '50', 100: '100' }"
            />
            <span class="hint">第二轮的通过阈值（仅用于标记）</span>
          </el-form-item>
          <el-form-item label="权重">
            <el-input-number
              v-model="config.round2_weight"
              :min="0"
              :max="1"
              :step="0.05"
              :precision="2"
              style="width: 100%"
            />
            <span class="hint">最终得分 = 第一轮评分 × {{ config.round1_weight }} + 第二轮评分 × {{ config.round2_weight }}</span>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- Final Threshold -->
      <el-card class="round-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span>最终阈值</span>
          </div>
        </template>
        <el-form :model="config" label-width="100px" label-position="left">
          <el-form-item label="通过阈值">
            <el-slider
              v-model="config.final_threshold"
              :min="0"
              :max="100"
              :step="1"
              show-input
              :marks="{ 0: '0', 50: '50', 100: '100' }"
            />
            <span class="hint">加权平均分数达到此阈值才能进入「待审核」状态</span>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- Save button -->
      <div class="actions">
        <el-button type="primary" size="large" @click="saveConfig" :loading="saving">
          保存配置
        </el-button>
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
  round1_enabled: true,
  round1_prompt: '',
  round1_model: 'gemini-2.0-flash',
  round1_threshold: 60,
  round1_weight: 0.7,
  round2_enabled: true,
  round2_prompt: '',
  round2_model: 'gemini-2.0-flash',
  round2_threshold: 70,
  round2_weight: 0.3,
  final_threshold: 65,
})

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
  // Validate weights sum to 1
  const sum = config.round1_weight + config.round2_weight
  if (Math.abs(sum - 1) > 0.01) {
    ElMessage.warning(`权重之和应为 1.0，当前为 ${sum.toFixed(2)}`)
    return
  }

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

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.task-config-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.config-content {
  margin-top: 24px;
}

.round-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.actions {
  display: flex;
  justify-content: center;
  margin-top: 32px;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

:deep(.el-slider__runway) {
  margin-right: 16px;
}
</style>
