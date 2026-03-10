<template>
  <el-dialog
    v-model="visible"
    title="删除确认"
    width="420px"
    align-center
    :close-on-click-modal="false"
    @close="handleCancel"
  >
    <div class="cdd-body">
      <div class="cdd-icon">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="12"/>
          <line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <div class="cdd-text">
        <p class="cdd-title">{{ title }}</p>
        <p class="cdd-desc">{{ description }}</p>
      </div>
    </div>
    <template #footer>
      <div class="cdd-footer">
        <button class="cdd-btn cdd-btn-cancel" @click="handleCancel">取消</button>
        <button class="cdd-btn cdd-btn-delete" :disabled="loading" @click="handleConfirm">
          <svg v-if="loading" class="cdd-spinner" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          删除
        </button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  title: { type: String, default: '确定要删除吗？' },
  description: { type: String, default: '此操作不可恢复。' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])

const visible = defineModel({ default: false })

function handleConfirm() {
  emit('confirm')
}

function handleCancel() {
  visible.value = false
  emit('cancel')
}
</script>

<style scoped>
.cdd-body {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 4px 0 8px;
}

.cdd-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  background: #fef2f2;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cdd-text {
  flex: 1;
  min-width: 0;
}

.cdd-title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 6px;
  line-height: 1.4;
}

.cdd-desc {
  font-size: 13px;
  color: #64748b;
  margin: 0;
  line-height: 1.5;
}

.cdd-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.cdd-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 34px;
  padding: 0 18px;
  border-radius: 7px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  font-family: inherit;
  transition: all 0.15s;
}

.cdd-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.cdd-btn-cancel {
  background: #f1f5f9;
  color: #475569;
}
.cdd-btn-cancel:hover:not(:disabled) { background: #e2e8f0; }

.cdd-btn-delete {
  background: #ef4444;
  color: #fff;
}
.cdd-btn-delete:hover:not(:disabled) { background: #dc2626; }

@keyframes cdd-spin { to { transform: rotate(360deg); } }
.cdd-spinner { animation: cdd-spin 0.8s linear infinite; }
</style>
