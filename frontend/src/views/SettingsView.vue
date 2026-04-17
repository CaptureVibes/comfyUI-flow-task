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
              自动每小时执行一次，手动触发时会实时推送每个频道的检查结果。
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
        <div v-if="channelCheckLogs.length" ref="channelCheckLogListRef" class="check-log-list">
          <div
            v-for="item in channelCheckLogs"
            :key="item.id"
            class="check-log-item"
            :class="item.type"
          >
            <div class="check-log-top">
              <div class="check-log-channel-wrap">
                <span class="check-log-platform">{{ formatPlatformLabel(item.platform) }}</span>
                <span class="check-log-channel-name">{{ item.channelName || '未命名频道' }}</span>
              </div>
              <span class="check-log-result-badge" :class="`tone-${item.type}`">{{ item.resultLabel }}</span>
            </div>
            <div class="check-log-summary">{{ item.summary }}</div>
            <div v-if="item.currentStatus" class="check-log-status-line">
              <template v-if="item.previousStatus && item.previousStatus !== item.currentStatus">
                <span class="check-status-chip is-ghost">{{ formatChannelStatus(item.previousStatus) }}</span>
                <span class="check-log-arrow">→</span>
              </template>
              <span class="check-status-chip" :class="statusChipClass(item.currentStatus)">
                {{ formatChannelStatus(item.currentStatus) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <el-divider />
    </el-card>
  </div>
</template>

<script setup>
import { nextTick, ref, onBeforeUnmount, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSystemSettings, streamCheckChannelStatus, updateSystemSettings } from '../api/settings'

const systemSettings = ref({ use_seedance_api: false })
const systemLoading = ref(false)

const channelChecking = ref(false)
const channelCheckResult = ref(null)
const channelCheckLogs = ref([])
const channelCheckLogListRef = ref(null)
let channelCheckController = null

const PLATFORM_LABELS = {
  douyin: '抖音',
  xiaohongshu: '小红书',
  rednote: '小红书',
  kuaishou: '快手',
  wechat: '微信',
  weixin: '微信',
  wechat_channels: '视频号',
  weixin_channels: '视频号',
  video_account: '视频号',
  tiktok: 'TikTok',
  bilibili: 'Bilibili',
  youtube: 'YouTube',
}

const CHANNEL_STATUS_META = {
  active: { label: '正常授权', className: 'is-active' },
  disabled: { label: '已禁用', className: 'is-disabled' },
}

const RESULT_LABELS = {
  updated: '已同步',
  unchanged: '状态正常',
  not_found: '状态未知',
  request_failed: '检查失败',
}

function formatPlatformLabel(platform) {
  if (!platform) return '频道'
  return PLATFORM_LABELS[platform] || platform.toUpperCase()
}

function formatChannelStatus(status) {
  if (!status) return '未知状态'
  return CHANNEL_STATUS_META[status]?.label || status
}

function statusChipClass(status) {
  return CHANNEL_STATUS_META[status]?.className || 'is-neutral'
}

function resultTone(result) {
  if (result === 'updated') return 'success'
  if (result === 'request_failed') return 'error'
  return 'info'
}

function formatResultLabel(result) {
  return RESULT_LABELS[result] || '检查完成'
}

function buildCheckSummary(data) {
  const previousStatusLabel = formatChannelStatus(data?.previous_status)
  const currentStatusLabel = formatChannelStatus(data?.current_status)

  if (data?.result === 'updated') {
    return previousStatusLabel === currentStatusLabel
      ? '检测到授权状态变更，系统已完成同步。'
      : `授权状态已从${previousStatusLabel}同步为${currentStatusLabel}。`
  }
  if (data?.result === 'unchanged') {
    return `授权状态稳定，当前保持${currentStatusLabel}。`
  }
  if (data?.result === 'not_found') {
    return '上游暂未返回明确的授权状态，系统保持本地状态不变。'
  }
  if (data?.result === 'request_failed') {
    return '授权接口请求失败，本地状态未被修改。'
  }
  return data?.message || '检查已完成。'
}

async function scrollChannelCheckLogsToBottom() {
  await nextTick()
  const el = channelCheckLogListRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

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
  channelCheckController?.abort()
  channelCheckController = new AbortController()
  channelChecking.value = true
  channelCheckResult.value = { type: 'info', message: '正在建立检查连接…' }
  channelCheckLogs.value = []
  try {
    await streamCheckChannelStatus({
      signal: channelCheckController.signal,
      onEvent: ({ event, data }) => {
        if (event === 'queued') {
          channelCheckResult.value = { type: 'info', message: data?.message || '检查任务已创建，等待执行' }
          return
        }

        if (event === 'started') {
          const total = data?.total ?? 0
          channelCheckResult.value = {
            type: 'info',
            message: total > 0 ? `开始检查，共 ${total} 个频道` : (data?.message || '开始检查频道授权状态'),
          }
          return
        }

        if (event === 'progress') {
          const changed = data?.changed ?? 0
          const index = data?.index ?? 0
          const total = data?.total ?? 0
          channelCheckResult.value = {
            type: 'info',
            message: `正在检查 ${index} / ${total} 个频道，已更新 ${changed} 个状态`,
          }
          channelCheckLogs.value = [
            ...channelCheckLogs.value,
            {
              id: `${Date.now()}-${index}-${data?.channel_id || 'unknown'}`,
              type: resultTone(data?.result),
              platform: data?.platform || '',
              channelName: data?.channel_name || '',
              resultLabel: formatResultLabel(data?.result),
              previousStatus: data?.previous_status || null,
              currentStatus: data?.current_status || null,
              summary: buildCheckSummary(data),
            }
          ].slice(-200)
          void scrollChannelCheckLogsToBottom()
          return
        }

        if (event === 'completed' || event === 'aborted') {
          const checked = data?.checked ?? 0
          const total = data?.total ?? checked
          const changed = data?.changed ?? 0
          channelCheckResult.value = {
            type: event === 'completed' ? 'success' : 'error',
            message: event === 'completed'
              ? (
                checked === 0
                  ? '暂无绑定频道，无需检查'
                  : changed === 0
                    ? `已检查 ${checked} 个频道，全部状态正常`
                    : `已检查 ${checked} / ${total} 个频道，${changed} 个状态已更新`
              )
              : `检查已中断，已处理 ${checked} / ${total} 个频道`,
          }
          return
        }

        if (event === 'error') {
          throw new Error(data?.message || '检查失败，请稍后重试')
        }
      }
    })
  } catch (e) {
    if (e?.name === 'AbortError') {
      return
    }
    channelCheckResult.value = {
      type: 'error',
      message: e?.message || e?.response?.data?.detail || '检查失败，请稍后重试',
    }
  } finally {
    channelChecking.value = false
    channelCheckController = null
  }
}

onMounted(loadSystemSettings)
onBeforeUnmount(() => {
  channelCheckController?.abort()
})
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
.check-result.info {
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  color: #4338ca;
}
.check-result.error {
  background: #fff1f2;
  border: 1px solid #fda4af;
  color: #be123c;
}

.check-log-list {
  margin-top: 10px;
  max-height: 240px;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.check-log-item {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #334155;
  border-bottom: 1px solid #e2e8f0;
}

.check-log-item:last-child {
  border-bottom: 0;
}

.check-log-item.success {
  background: linear-gradient(180deg, rgba(240, 253, 244, 0.92), rgba(240, 253, 244, 0.78));
}

.check-log-item.error {
  background: linear-gradient(180deg, rgba(255, 241, 242, 0.95), rgba(255, 241, 242, 0.82));
}

.check-log-item.info {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92));
}

.check-log-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.check-log-channel-wrap {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex: 1;
  flex-wrap: wrap;
  min-width: 0;
}

.check-log-channel-name {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.25;
  word-break: break-word;
}

.check-log-platform {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #ddeafe;
  color: #3155a6;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.check-log-result-badge {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.check-log-result-badge.tone-success {
  background: #dcfce7;
  color: #166534;
}

.check-log-result-badge.tone-error {
  background: #ffe4e6;
  color: #be123c;
}

.check-log-result-badge.tone-info {
  background: #e2e8f0;
  color: #475569;
}

.check-log-summary {
  font-size: 12.5px;
  line-height: 1.5;
  color: #475569;
}

.check-log-status-line {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.check-log-arrow {
  color: #94a3b8;
  font-size: 13px;
  font-weight: 700;
}

.check-status-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.check-status-chip.is-active {
  background: #dcfce7;
  color: #166534;
}

.check-status-chip.is-disabled {
  background: #fee2e2;
  color: #b91c1c;
}

.check-status-chip.is-neutral {
  background: #e2e8f0;
  color: #475569;
}

.check-status-chip.is-ghost {
  background: rgba(226, 232, 240, 0.7);
  color: #64748b;
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
