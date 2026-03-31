<template>
  <div class="settings-container">
    <el-card class="page-card">
      <template #header>
        <div class="header-row">
          <div>
            <div class="page-title">系统设置</div>
          </div>
        </div>
      </template>

      <!-- Seedance API 开关 -->
      <div class="setting-section">
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-name">使用 Seedance API</span>
            <span class="setting-desc">启用后将使用 Seedance API 生成视频，否则使用默认方式</span>
          </div>
          <el-switch
            v-model="systemSettings.use_seedance_api"
            :loading="systemLoading"
            @change="handleSystemSave"
          />
        </div>
      </div>

      <el-divider />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSystemSettings, updateSystemSettings } from '../api/settings'

const systemSettings = ref({ use_seedance_api: false })
const systemLoading = ref(false)

async function loadSystemSettings() {
  systemLoading.value = true
  try {
    const data = await fetchSystemSettings()
    systemSettings.value = { use_seedance_api: data.use_seedance_api ?? false }
  } catch (e) {
    ElMessage.error('加载系统设置失败')
  } finally {
    systemLoading.value = false
  }
}

async function handleSystemSave() {
  systemLoading.value = true
  try {
    const data = await updateSystemSettings(systemSettings.value)
    systemSettings.value = { use_seedance_api: data.use_seedance_api ?? false }
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    systemLoading.value = false
  }
}

onMounted(loadSystemSettings)
</script>

<style scoped>
.settings-container {
  animation: rise 0.35s ease;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #153f7f;
}

.setting-section {
  margin-bottom: 8px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.setting-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setting-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.setting-desc {
  font-size: 12px;
  color: #94a3b8;
}

.evo-pipeline-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6366f1;
  background: #eef2ff;
  border-radius: 8px;
  padding: 10px 14px;
}

.evo-pipeline-hint a {
  color: #4f46e5;
  font-weight: 600;
  text-decoration: underline;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
