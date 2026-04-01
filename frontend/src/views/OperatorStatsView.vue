<template>
  <div class="os-container">
    <div class="os-header">
      <h2 class="os-title">审核人统计</h2>
      <div class="os-filters">
        <input
          v-model="targetDate"
          type="date"
          class="os-date-input"
          @change="load"
        />
        <button class="os-btn os-btn-secondary" @click="clearDate">全部日期</button>
      </div>
    </div>

    <div v-if="loading" class="os-loading">加载中...</div>
    <div v-else-if="stats.length === 0" class="os-empty">暂无审核数据</div>

    <div v-else class="os-list">
      <div
        v-for="item in stats"
        :key="item.operator"
        class="os-card"
      >
        <div class="os-card-header" @click="toggle(item.operator)">
          <div class="os-operator-info">
            <span class="os-avatar">{{ item.operator[0].toUpperCase() }}</span>
            <span class="os-operator-name">{{ item.operator }}</span>
            <span class="os-badge">{{ item.count }} 条</span>
          </div>
          <svg
            class="os-chevron"
            :class="{ 'os-chevron-open': expanded.has(item.operator) }"
            width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2.5"
          >
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </div>

        <div v-if="expanded.has(item.operator)" class="os-subtasks">
          <div
            v-for="sub in item.sub_tasks"
            :key="sub.id"
            class="os-sub-row"
          >
            <video
              v-if="sub.result_video_url"
              :src="sub.result_video_url"
              class="os-thumb"
              muted
              preload="metadata"
              @mouseenter="e => e.target.play()"
              @mouseleave="e => { e.target.pause(); e.target.currentTime = 0 }"
            />
            <div v-else class="os-thumb os-thumb-empty">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="m10 8 6 4-6 4V8z"/></svg>
            </div>
            <div class="os-sub-info">
              <div class="os-sub-meta">
                <span class="os-status-badge" :class="`os-status-${sub.status}`">{{ STATUS_LABELS[sub.status] || sub.status }}</span>
                <span v-if="sub.has_ng === true" class="os-ng-tag">有穿帮</span>
                <span v-else-if="sub.has_ng === false" class="os-ng-tag os-ng-ok">无穿帮</span>
              </div>
              <div class="os-sub-score" v-if="sub.weighted_total_score != null">
                综合评分：<strong>{{ sub.weighted_total_score }}</strong>
              </div>
              <div class="os-sub-time" v-if="sub.updated_at">
                {{ formatTime(sub.updated_at) }}
              </div>
            </div>
            <router-link
              :to="`/dashboard/video-tasks/${sub.task_id}`"
              class="os-link-btn"
              target="_blank"
            >查看任务</router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchOperatorStats } from '../api/video_tasks.js'

const today = new Date().toISOString().slice(0, 10)
const targetDate = ref(today)
const loading = ref(false)
const stats = ref([])
const expanded = ref(new Set())

const STATUS_LABELS = {
  pending: '待处理',
  generating: '生成中',
  reviewing: '待决策',
  stashed: '暂存',
  decision_rejected: '决策未通过',
  queued: '队列中',
  publishing: '发布中',
  published: '已发布',
  publish_failed: '发布失败',
  abandoned: '已废弃',
}

async function load() {
  loading.value = true
  try {
    stats.value = await fetchOperatorStats(targetDate.value || null)
    // Auto-expand all operators
    expanded.value = new Set(stats.value.map(s => s.operator))
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function clearDate() {
  targetDate.value = ''
  load()
}

function toggle(operator) {
  if (expanded.value.has(operator)) {
    expanded.value.delete(operator)
  } else {
    expanded.value.add(operator)
  }
}

function formatTime(iso) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(load)
</script>

<style scoped>
.os-container {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 16px;
}

.os-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.os-title {
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}

.os-filters {
  display: flex;
  align-items: center;
  gap: 8px;
}

.os-date-input {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  color: #374151;
  outline: none;
}
.os-date-input:focus { border-color: #3b82f6; }

.os-btn {
  padding: 6px 14px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}
.os-btn-secondary { background: #f1f5f9; color: #475569; }
.os-btn-secondary:hover { background: #e2e8f0; }

.os-loading, .os-empty {
  text-align: center;
  color: #94a3b8;
  padding: 48px 0;
  font-size: 15px;
}

.os-list { display: flex; flex-direction: column; gap: 16px; }

.os-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}

.os-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  cursor: pointer;
  user-select: none;
}
.os-card-header:hover { background: #f8fafc; }

.os-operator-info { display: flex; align-items: center; gap: 10px; }

.os-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #3b82f6;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.os-operator-name { font-size: 15px; font-weight: 600; color: #1e293b; }

.os-badge {
  background: #eff6ff;
  color: #2563eb;
  border-radius: 20px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
}

.os-chevron { color: #94a3b8; transition: transform 0.2s; }
.os-chevron-open { transform: rotate(180deg); }

.os-subtasks {
  border-top: 1px solid #f1f5f9;
  display: flex;
  flex-direction: column;
}

.os-sub-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid #f8fafc;
}
.os-sub-row:last-child { border-bottom: none; }

.os-thumb {
  width: 80px;
  height: 52px;
  object-fit: cover;
  border-radius: 6px;
  flex-shrink: 0;
  background: #f1f5f9;
  cursor: pointer;
}
.os-thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.os-sub-info { flex: 1; min-width: 0; }

.os-sub-meta { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; flex-wrap: wrap; }

.os-status-badge {
  border-radius: 4px;
  padding: 1px 7px;
  font-size: 11px;
  font-weight: 600;
}
.os-status-reviewing         { background: #fef9c3; color: #854d0e; }
.os-status-stashed           { background: #fef3c7; color: #d97706; }
.os-status-decision_rejected { background: #fef2f2; color: #ef4444; }
.os-status-queued            { background: #ede9fe; color: #8b5cf6; }
.os-status-published         { background: #dcfce7; color: #15803d; }
.os-status-abandoned         { background: #fee2e2; color: #b91c1c; }

.os-ng-tag {
  border-radius: 4px;
  padding: 1px 7px;
  font-size: 11px;
  font-weight: 600;
  background: #fef2f2;
  color: #ef4444;
}
.os-ng-ok { background: #dcfce7; color: #15803d; }

.os-sub-score { font-size: 12px; color: #475569; }
.os-sub-score strong { color: #1e293b; }
.os-sub-time { font-size: 11px; color: #94a3b8; margin-top: 2px; }

.os-link-btn {
  padding: 5px 12px;
  background: #eff6ff;
  color: #2563eb;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  text-decoration: none;
  flex-shrink: 0;
  white-space: nowrap;
}
.os-link-btn:hover { background: #dbeafe; }
</style>
