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

      <!-- 频道状态检查 -->
      <div class="setting-section">
        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-name">平台频道授权状态检查</span>
            <span class="setting-desc">
              自动每天北京时间 10:00 执行，查询所有已绑定频道的授权状态，将被禁用的频道标记为「已禁用」。
            </span>
          </div>
          <button
            class="check-btn"
            :class="{ loading: channelChecking }"
            :disabled="channelChecking"
            @click="handleCheckChannelStatus"
          >
            <span v-if="channelChecking" class="check-spin"></span>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="flex-shrink:0"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
            {{ channelChecking ? '检查中…' : '立即检查' }}
          </button>
        </div>
        <div v-if="channelCheckResult" class="check-result" :class="channelCheckResult.type">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="flex-shrink:0">
            <path v-if="channelCheckResult.type === 'success'" d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline v-if="channelCheckResult.type === 'success'" points="22 4 12 14.01 9 11.01"/>
            <circle v-else cx="12" cy="12" r="10"/><line v-if="channelCheckResult.type !== 'success'" x1="12" y1="8" x2="12" y2="12"/><line v-if="channelCheckResult.type !== 'success'" x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {{ channelCheckResult.message }}
        </div>
      </div>

      <el-divider />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSystemSettings, updateSystemSettings, triggerCheckChannelStatus } from '../api/settings'

const systemSettings = ref({ use_seedance_api: false })
const systemLoading = ref(false)

const channelChecking = ref(false)
const channelCheckResult = ref(null)

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

async function handleCheckChannelStatus() {
  if (channelChecking.value) return
  channelChecking.value = true
  channelCheckResult.value = null
  try {
    const res = await triggerCheckChannelStatus()
    const changed = res.changed ?? 0
    const checked = res.checked ?? 0
    channelCheckResult.value = {
      type: 'success',
      message: checked === 0
        ? '暂无绑定频道，无需检查'
        : changed === 0
          ? `已检查 ${checked} 个频道，全部状态正常`
          : `已检查 ${checked} 个频道，${changed} 个状态已更新`,
    }
  } catch (e) {
    channelCheckResult.value = {
      type: 'error',
      message: e?.response?.data?.detail || '检查失败，请稍后重试',
    }
  } finally {
    channelChecking.value = false
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

.check-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 16px;
  border-radius: 9px;
  border: 1.5px solid #6366f1;
  background: #fff;
  color: #6366f1;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.15s;
}
.check-btn:hover:not(:disabled) {
  background: #6366f1;
  color: #fff;
}
.check-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.check-btn.loading {
  border-color: #a5b4fc;
  color: #a5b4fc;
}

.check-spin {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(99,102,241,0.3);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  flex-shrink: 0;
}

.check-result {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
}
.check-result.success {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #15803d;
}
.check-result.error {
  background: #fff1f2;
  border: 1px solid #fda4af;
  color: #be123c;
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

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
