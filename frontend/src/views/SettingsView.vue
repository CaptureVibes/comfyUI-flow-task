<template>
  <div class="settings-container">
    <el-card class="page-card" v-loading="loading">
      <template #header>
        <div class="header-row">
          <div>
            <div class="page-title">系统设置</div>
            <div class="page-subtitle">配置 ComfyUI 服务器与 EvoLink AI 接口参数（仅管理员可修改）</div>
          </div>
        </div>
      </template>

      <el-form label-position="top" class="settings-form">
        <el-divider content-position="left">ComfyUI 服务器</el-divider>

        <el-form-item label="ComfyUI 服务器 IP / Host">
          <el-input
            v-model="form.comfyui_server_ip"
            placeholder="例如：34.59.208.230"
            clearable
            :disabled="saving || !canEdit"
            :readonly="!canEdit"
          />
        </el-form-item>

        <el-form-item label="端口列表">
          <el-input
            v-model="form.portsText"
            type="textarea"
            :rows="3"
            :disabled="saving || !canEdit"
            :readonly="!canEdit"
            placeholder="支持格式：8189-8198,8201"
          />
          <div class="ports-help">支持逗号分隔和区间写法，自动去重排序。</div>
        </el-form-item>

        <div class="ports-preview">
          <div class="preview-title">解析结果</div>
          <div v-if="parsedPorts.length" class="ports-tags">
            <el-tag v-for="port in parsedPorts" :key="port" type="info">:{{ port }}</el-tag>
          </div>
          <el-empty v-else description="暂无可用端口" :image-size="60" />
        </div>

        <el-divider content-position="left" style="margin-top: 24px">EvoLink AI 接口</el-divider>

        <el-form-item label="API Base URL">
          <el-input
            v-model="form.evolink_api_base_url"
            placeholder="https://api.evolink.ai"
            clearable
            :disabled="saving || !canEdit"
            :readonly="!canEdit"
          />
        </el-form-item>

        <el-form-item label="API Key">
          <el-input
            v-model="form.evolink_api_key"
            placeholder="Bearer token"
            show-password
            :disabled="saving || !canEdit"
            :readonly="!canEdit"
          />
        </el-form-item>
      </el-form>

      <div class="evo-pipeline-hint">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        AI 处理流程参数（模型、提示词、温度、输出格式等）在<router-link to="/dashboard/video-ai-templates">视频AI模板</router-link>页面右上角「流程配置」中按用户独立设置。
      </div>

      <div v-if="!canEdit" class="readonly-notice">
        <el-alert type="info" :closable="false" show-icon title="当前账号无权修改设置，仅供查看" />
      </div>

      <div v-if="canEdit" class="actions">
        <el-button type="primary" :loading="saving" @click="handleSave">保存系统设置</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchSystemSettings, updateSystemSettings } from '../api/settings'
import { isDuplicateRequestError } from '../api/http'
import { useAuth } from '../composables/useAuth'

const { isAdmin } = useAuth()
const canEdit = isAdmin()

const loading = ref(false)
const saving = ref(false)
const form = reactive({
  comfyui_server_ip: '',
  portsText: '',
  evolink_api_key: '',
  evolink_api_base_url: 'https://api.evolink.ai',
})

const parsedPorts = computed(() => {
  try {
    return parsePorts(form.portsText)
  } catch {
    return []
  }
})

function parsePorts(value) {
  const text = String(value || '').trim()
  if (!text) {
    return []
  }
  const result = new Set()
  const segments = text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  for (const segment of segments) {
    if (segment.includes('-')) {
      const [startRaw, endRaw] = segment.split('-', 2)
      const start = Number(startRaw)
      const end = Number(endRaw)
      if (!Number.isInteger(start) || !Number.isInteger(end)) {
        throw new Error('端口区间格式错误')
      }
      const minValue = Math.min(start, end)
      const maxValue = Math.max(start, end)
      for (let port = minValue; port <= maxValue; port += 1) {
        if (port < 1 || port > 65535) throw new Error('端口范围必须在 1-65535')
        result.add(port)
      }
      continue
    }
    const port = Number(segment)
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      throw new Error(`无效端口: ${segment}`)
    }
    result.add(port)
  }

  return [...result].sort((a, b) => a - b)
}

function toPortsText(ports) {
  return (ports || []).join(',')
}

async function loadSettings() {
  loading.value = true
  try {
    const data = await fetchSystemSettings()
    form.comfyui_server_ip = data.comfyui_server_ip || ''
    form.portsText = toPortsText(data.comfyui_ports || [])
    form.evolink_api_key = data.evolink_api_key || ''
    form.evolink_api_base_url = data.evolink_api_base_url || 'https://api.evolink.ai'
  } catch (error) {
    if (isDuplicateRequestError(error)) return
    ElMessage.error(error?.response?.data?.detail || '加载设置失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (saving.value) return

  let ports = []
  try {
    ports = parsePorts(form.portsText)
  } catch (error) {
    ElMessage.error(error?.message || '端口格式错误')
    return
  }

  saving.value = true
  try {
    const data = await updateSystemSettings({
      comfyui_server_ip: String(form.comfyui_server_ip || '').trim(),
      comfyui_ports: ports,
      evolink_api_key: form.evolink_api_key,
      evolink_api_base_url: form.evolink_api_base_url || 'https://api.evolink.ai',
    })
    form.comfyui_server_ip = data.comfyui_server_ip || ''
    form.portsText = toPortsText(data.comfyui_ports || ports)
    form.evolink_api_key = data.evolink_api_key || ''
    form.evolink_api_base_url = data.evolink_api_base_url || 'https://api.evolink.ai'
    ElMessage.success('系统设置已保存')
  } catch (error) {
    if (isDuplicateRequestError(error)) return
    ElMessage.error(error?.response?.data?.detail || '保存设置失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadSettings()
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

.page-subtitle {
  font-size: 13px;
  color: #60748f;
  margin-top: 2px;
}

.settings-form {
  max-width: 760px;
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
  margin-top: 8px;
  margin-bottom: 4px;
}

.evo-pipeline-hint a {
  color: #4f46e5;
  font-weight: 600;
  text-decoration: underline;
}

.ports-help {
  font-size: 12px;
  color: #6b7d98;
  margin-top: 8px;
}

.ports-preview {
  margin-top: 14px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #dce8fb;
  background: #f7fbff;
}

.preview-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f4b87;
  margin-bottom: 10px;
}

.ports-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.readonly-notice {
  margin-top: 18px;
}

.actions {
  margin-top: 18px;
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
