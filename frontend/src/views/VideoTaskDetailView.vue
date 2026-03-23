<template>
  <div class="vtd-page">
    <!-- Header -->
    <div class="vtd-header">
      <button class="vtd-back-btn" @click="router.back()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
        返回任务列表
      </button>
      <div v-if="task" class="vtd-header-info">
        <span class="vtd-info-item">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" style="margin-right:4px"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          {{ accountName }}
        </span>
        <span class="vtd-sep">·</span>
        <span
          class="vtd-info-item vtd-template"
          :class="{ 'vtd-template-link': task.template_id }"
          @click="task.template_id && router.push(`/dashboard/video-ai-templates/${task.template_id}/edit`)"
        >{{ templateTitle }}</span>
        <span class="vtd-sep">·</span>
        <span class="vtd-info-item">{{ task.target_date }}</span>
        <span class="vtd-sep">·</span>
        <span class="vtd-status-badge" :class="`vtd-status-${task.status}`">
          {{ STATUS_LABELS[task.status] || task.status }}
        </span>
        <div v-if="task.tags?.length" class="vtd-tags">
          <span
            v-for="tag in task.tags"
            :key="tag.id"
            class="vtd-tag-chip"
            :style="tag.color ? { '--vtd-tag-color': tag.color } : {}"
          >
            <span class="vtd-tag-dot"></span>
            {{ tag.name }}
          </span>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" v-loading="true" class="vtd-loading"></div>

    <!-- Task Detail -->
    <div v-else-if="task" class="vtd-body">

      <!-- Top row: Timeline + Prompt -->
      <div class="vtd-top-row">
        <!-- Timeline -->
        <div class="vtd-timeline-card">
          <div class="vtd-section-label">任务进度</div>
          <div class="vtd-timeline">
            <div
              v-for="(step, i) in timeline"
              :key="step.key"
              class="vtd-timeline-item"
              :class="{ active: step.active, done: step.done, current: step.current }"
            >
              <div class="vtd-tl-left">
                <div class="vtd-tl-dot">
                  <svg v-if="step.done" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                  <div v-else-if="step.current" class="vtd-tl-pulse"></div>
                </div>
                <div v-if="i < timeline.length - 1" class="vtd-tl-line"></div>
              </div>
              <div class="vtd-tl-content">
                <div class="vtd-tl-title">{{ step.label }}</div>
                <div v-if="step.desc" class="vtd-tl-desc">{{ step.desc }}</div>
                <!-- AI Scores for scoring step -->
                <div v-if="step.key === 'scoring' && hasReviewingScores()" class="vtd-tl-scores">
                  <div
                    v-for="sub in reviewingSubTasks()"
                    :key="sub.id"
                    class="vtd-tl-score-item"
                    :class="{ 'vtd-tl-score-selected': sub.selected, 'vtd-tl-score-abandoned': sub.status === 'abandoned' }"
                  >
                    <span class="vtd-tl-score-index">#{{ sub.sub_index }}</span>
                    <span
                      v-if="sub.ai_score !== null && sub.ai_score !== undefined"
                      class="vtd-tl-score-value"
                      :class="getAiScoreClass(sub.ai_score)"
                    >
                      {{ sub.ai_score }}分
                    </span>
                    <span
                      v-else-if="sub.round1_score !== null && sub.round1_score !== undefined"
                      class="vtd-tl-score-value"
                      :class="getAiScoreClass(sub.round1_score)"
                    >
                      R1 {{ sub.round1_score }}分
                    </span>
                    <span v-if="sub.round1_score !== null" class="vtd-tl-score-rounds">
                      R1: {{ sub.round1_score }}
                      <span v-if="sub.round2_score !== null"> | R2: {{ sub.round2_score }}</span>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Prompt (collapsible) -->
        <div class="vtd-prompt-card">
          <div class="vtd-prompt-header" @click="promptExpanded = !promptExpanded">
            <span class="vtd-section-label">生成 Prompt</span>
            <svg
              width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round"
              :style="{ transform: promptExpanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }"
            ><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <div class="vtd-prompt-text" :class="{ collapsed: !promptExpanded }">{{ task.prompt }}</div>
          <button v-if="!promptExpanded" class="vtd-prompt-expand" @click="promptExpanded = true">
            展开全部
          </button>
        </div>
      </div>

      <div v-if="task.original_video" class="vtd-original-card">
        <div class="vtd-original-header">
          <span class="vtd-section-label" style="margin-bottom:0;">关联原视频</span>
          <button
            v-if="task.original_video.id"
            class="vtd-original-link"
            @click="router.push(`/dashboard/video-library/${task.original_video.id}`)"
          >
            查看视频详情
          </button>
        </div>
        <div class="vtd-original-grid">
          <div class="vtd-original-player">
            <video
              v-if="task.original_video.local_video_url || task.original_video.video_url"
              :src="task.original_video.local_video_url || task.original_video.video_url"
              controls
              class="vtd-original-video"
              preload="metadata"
            />
            <div v-else class="vtd-original-placeholder">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
              <span>暂无原视频地址</span>
            </div>
          </div>
          <div class="vtd-original-meta">
            <div class="vtd-original-title">{{ task.original_video.video_title || '无标题原视频' }}</div>
            <div class="vtd-original-info">@{{ task.original_video.blogger_name || '未知博主' }}</div>
            <div v-if="task.original_video.platform" class="vtd-original-info">{{ task.original_video.platform }}</div>
            <a
              v-if="task.original_video.source_url"
              class="vtd-original-source"
              :href="task.original_video.source_url"
              target="_blank"
              rel="noopener noreferrer"
            >
              打开原始链接
            </a>
          </div>
        </div>
      </div>

      <!-- 3 Sub-task Cards -->
      <div class="vtd-subtasks">
        <div
          v-for="sub in task.sub_tasks"
          :key="sub.id"
          class="vtd-sub-card"
          :class="{ 'vtd-sub-selected': sub.selected, 'vtd-sub-abandoned': sub.status === 'abandoned' }"
        >
          <!-- Card Header -->
          <div class="vtd-sub-header">
            <div class="vtd-sub-index">#{{ sub.sub_index }}</div>
            <span class="vtd-status-badge" :class="`vtd-status-${sub.status}`">
              {{ STATUS_LABELS[sub.status] || sub.status }}
            </span>
            <div v-if="sub.selected" class="vtd-selected-badge">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
              已选中
            </div>
            <!-- AI Score Badge -->
            <div v-if="sub.ai_score !== null && sub.ai_score !== undefined" class="vtd-ai-score" :class="getAiScoreClass(sub.ai_score)">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              {{ sub.ai_score }}分
            </div>
          </div>

          <!-- Video Player -->
          <div class="vtd-sub-video-wrap">
            <video
              v-if="sub.result_video_url"
              :src="sub.result_video_url"
              controls
              class="vtd-sub-video"
              preload="metadata"
            />
            <div v-else class="vtd-sub-video-placeholder">
              <svg v-if="sub.status === 'generating'" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              <svg v-else width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
              <span>{{ sub.status === 'generating' ? '生成中...' : '暂无视频' }}</span>
            </div>
          </div>

          <!-- AI Score Details -->
          <div v-if="hasAiScores(sub)" class="vtd-ai-details">
            <div class="vtd-ai-details-header" @click="toggleAiReason(sub.id)">
              <span class="vtd-ai-details-title">AI 评分详情</span>
              <svg
                width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round"
                :style="{ transform: aiReasonExpanded[sub.id] ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }"
              ><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <div class="vtd-ai-scores">
              <div class="vtd-ai-score-item">
                <span class="vtd-ai-round">第一轮</span>
                <span class="vtd-ai-score-value" :class="getAiScoreClass(sub.round1_score)">
                  {{ sub.round1_score }}分
                </span>
              </div>
              <div v-if="sub.round2_score !== null" class="vtd-ai-score-item">
                <span class="vtd-ai-round">第二轮</span>
                <span class="vtd-ai-score-value" :class="getAiScoreClass(sub.round2_score)">
                  {{ sub.round2_score }}分
                </span>
              </div>
              <div v-if="sub.ai_score !== null && sub.ai_score !== undefined" class="vtd-ai-score-item vtd-ai-final">
                <span class="vtd-ai-round">综合得分</span>
                <span class="vtd-ai-score-value" :class="getAiScoreClass(sub.ai_score)">
                  {{ sub.ai_score }}分
                </span>
              </div>
            </div>

            <!-- Collapsible reasons -->
            <div v-if="aiReasonExpanded[sub.id]">
              <div v-if="sub.round1_reason" class="vtd-ai-reason">
                <div class="vtd-ai-reason-label">第一轮评分理由</div>
                <div class="vtd-ai-reason-text">{{ sub.round1_reason }}</div>
              </div>
              <div v-if="sub.round2_reason" class="vtd-ai-reason">
                <div class="vtd-ai-reason-label">第二轮评分理由</div>
                <div class="vtd-ai-reason-text">{{ sub.round2_reason }}</div>
              </div>
            </div>
          </div>

          <!-- AI Scoring Error -->
          <div v-if="sub.scoring_error" class="vtd-scoring-error">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span class="vtd-error-text">{{ sub.scoring_error }}</span>
          </div>

          <!-- Scoring Section -->
          <div class="vtd-manual-note">
            <div class="vtd-manual-note-label">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" style="margin-right:5px;flex-shrink:0"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              人工评分
            </div>

            <!-- Step 1: Critical Checks -->
            <div class="vtd-critical-section">
              <div class="vtd-critical-title">关键穿帮检测</div>
              <div class="vtd-critical-checks">
                <label
                  v-for="ck in CRITICAL_CHECKS"
                  :key="ck.key"
                  class="vtd-critical-item"
                  :class="{
                    'vtd-critical-pass': criticalChecks[sub.id]?.[ck.key] === true,
                    'vtd-critical-fail': criticalChecks[sub.id]?.[ck.key] === false,
                  }"
                >
                  <span class="vtd-critical-label">{{ ck.label }}</span>
                  <span class="vtd-critical-desc">{{ ck.desc }}</span>
                  <div class="vtd-critical-btns">
                    <button
                      class="vtd-ck-btn vtd-ck-pass"
                      :class="{ active: criticalChecks[sub.id]?.[ck.key] === true }"
                      @click="setCriticalCheck(sub, ck.key, true)"
                    >Pass</button>
                    <button
                      class="vtd-ck-btn vtd-ck-fail"
                      :class="{ active: criticalChecks[sub.id]?.[ck.key] === false }"
                      @click="setCriticalCheck(sub, ck.key, false)"
                    >Fail</button>
                  </div>
                </label>
              </div>
              <div v-if="sub.critical_fail === true" class="vtd-critical-verdict vtd-verdict-fail">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                穿帮 FAIL — 无需打分
              </div>
              <div v-else-if="sub.critical_fail === false" class="vtd-critical-verdict vtd-verdict-pass">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
                通过关键检测
              </div>
            </div>

            <!-- Step 2: Dimension Scoring (only if not critical_fail) -->
            <div v-if="sub.critical_fail !== true" class="vtd-dimension-section">
              <div class="vtd-dimension-title">多维度评分</div>
              <div class="vtd-dimension-grid">
                <div
                  v-for="dim in DIMENSIONS"
                  :key="dim.key"
                  class="vtd-dim-item"
                >
                  <div class="vtd-dim-header">
                    <span class="vtd-dim-name">{{ dim.label }}</span>
                    <span class="vtd-dim-weight">权重 {{ dim.weight }}%</span>
                  </div>
                  <div class="vtd-dim-desc">{{ dim.desc }}</div>
                  <div class="vtd-dim-scores-grid">
                    <button
                      v-for="s in [0,1,2,3,4,5]"
                      :key="s"
                      class="vtd-dim-score-btn"
                      :class="[`vtd-score-${s}`, { active: dimensionScores[sub.id]?.[dim.key] === s }]"
                      @click="setDimensionScore(sub, dim.key, s)"
                    >
                      <span class="vtd-dim-btn-num">{{ s }}</span>
                      <span class="vtd-dim-btn-label">{{ SCORE_LABELS[s] }}</span>
                    </button>
                  </div>
                </div>
              </div>
              <!-- Weighted Total -->
              <div v-if="sub.weighted_total_score != null" class="vtd-weighted-total">
                综合得分：
                <span class="vtd-weighted-value" :class="getWeightedScoreClass(sub.weighted_total_score)">
                  {{ sub.weighted_total_score }}
                </span>
                <span class="vtd-weighted-max">/ 100</span>
              </div>
            </div>

            <!-- Note textarea -->
            <div class="vtd-note-reason-col" style="margin-top: 8px;">
              <div class="vtd-note-col-label">评分备注</div>
              <textarea
                v-model="manualNotes[sub.id]"
                class="vtd-note-textarea"
                placeholder="输入评分理由或备注..."
                rows="3"
                @blur="handleSaveNote(sub)"
              />
            </div>

            <!-- Auto-save indicator -->
            <div v-if="savingNote[sub.id]" class="vtd-autosave-indicator">保存中...</div>
          </div>

          <!-- Actions -->
          <div class="vtd-sub-actions">
            <el-button
              v-if="sub.status === 'reviewing'"
              type="primary"
              size="small"
              :loading="selecting === sub.id"
              @click="handleSelect(sub)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:4px"><polyline points="20 6 9 17 4 12"/></svg>
              选择此版本
            </el-button>

            <el-button
              v-if="sub.status === 'pending_publish' && sub.selected"
              type="success"
              size="small"
              :loading="enqueueing === sub.id"
              :disabled="!sub.result_video_url"
              @click="handleEnqueue(sub)"
            >
              <svg v-if="enqueueing !== sub.id" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:4px"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
              加入队列
            </el-button>

            <el-button
              v-if="canRollback(sub)"
              size="small"
              plain
              :loading="rollbacking === sub.id"
              @click="handleRollback(sub)"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:4px"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
              撤回
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else class="vtd-error">
      <p>任务不存在或无权访问</p>
      <el-button @click="router.back()">返回</el-button>
    </div>

    <!-- 发布对话框 -->
    <PublishVideoDialog
      v-model="publishDialogVisible"
      :video-url="publishingSubTask?.result_video_url"
      :account="account"
      :sub-task="publishingSubTask"
      @success="onPublishSuccess"
    />

    <!-- Sticky Bottom Nav Bar -->
    <div class="vtd-nav-bar">
      <!-- 左侧占位，保持中间按钮真正居中 -->
      <div class="vtd-nav-spacer"></div>

      <button
        class="vtd-nav-btn"
        :disabled="!hasPrevBlogger || navLoading"
        @click="goToPrevBlogger"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/><polyline points="8 18 2 12 8 6"/></svg>
        上一个博主
      </button>
      <button
        class="vtd-nav-btn"
        :disabled="!hasPrevVideo || navLoading"
        @click="goToPrevVideo"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
        上一个视频
      </button>
      <div class="vtd-nav-pos" v-if="navInfo && navInfo.total > 0">
        {{ navInfo.position + 1 }} / {{ navInfo.total }}
      </div>
      <button
        class="vtd-nav-btn vtd-nav-btn-right"
        :disabled="!hasNextVideo || navLoading"
        @click="goToNextVideo"
      >
        下一个视频
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
      </button>
      <button
        class="vtd-nav-btn vtd-nav-btn-right"
        :disabled="!hasNextBlogger || navLoading"
        @click="goToNextBlogger"
      >
        下一个博主
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/><polyline points="16 18 22 12 16 6"/></svg>
      </button>

      <!-- 选择进度统计，靠右 -->
      <div v-if="selectionStats" class="vtd-nav-stats">
        <span class="vtd-nav-stats-done">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
          已选 {{ selectionStats.selected }}
        </span>
        <span class="vtd-nav-stats-sep">/</span>
        <span class="vtd-nav-stats-pending">未选 {{ selectionStats.unselected }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchVideoTask,
  fetchVideoTaskState,
  fetchTaskNavigation,
  patchSubTaskStatus,
  rollbackSubTaskStatus,
  saveSubTaskNote,
  enqueueSubTask,
} from '../api/video_tasks.js'
import { fetchAccount } from '../api/accounts.js'
import PublishVideoDialog from '../components/PublishVideoDialog.vue'

const STATUS_LABELS = {
  pending: '待处理',
  generating: '生成中',
  scoring: 'AI审核中',
  reviewing: '待决策',
  pending_publish: '待发布',
  publishing: '发布中',
  publish_failed: '发布失败',
  published: '已发布',
  abandoned: '已废弃',
}

// Timeline steps in order
const TIMELINE_STEPS = [
  { key: 'pending',         label: '任务创建',   desc: '任务已建立，等待上传' },
  { key: 'generating',      label: '视频生成中', desc: '正在 AI 生成视频' },
  { key: 'scoring',         label: 'AI审核中',   desc: '正在进行 AI 智能评分' },
  { key: 'pending_publish', label: '待发布',     desc: 'AI 评分通过，请前往账号详情页发布' },
  { key: 'publishing',      label: '发布中',     desc: '视频正在上传到平台' },
  { key: 'published',       label: '已发布',     desc: '视频已成功发布' },
]

const STATUS_ORDER = ['pending', 'generating', 'scoring', 'pending_publish', 'publishing', 'published']

const CRITICAL_CHECKS = [
  { key: 'temporal_consistency', label: '时序一致性', desc: '是否存在明显跨帧跳变' },
  { key: 'character_integrity', label: '人物结构完整性', desc: '是否存在严重人物结构错误' },
  { key: 'audio_sync', label: '声画同步', desc: '是否存在严重声画不同步' },
]

const DIMENSIONS = [
  { key: 'audio_visual', label: '声画与听觉', weight: 20, desc: 'BGM、节奏卡点、人声自然度、口型同步' },
  { key: 'character_realism', label: '人物与全身拟真', weight: 30, desc: '面部、身体结构、动作自然度、反AI感' },
  { key: 'performance_narrative', label: '表演与叙事', weight: 15, desc: '情绪表达、行为逻辑、Hook与收束' },
  { key: 'editing_transition', label: '剪辑与转场', weight: 12, desc: '转场动机、节奏、结构' },
  { key: 'camera_composition', label: '镜头与构图', weight: 12, desc: '景别、运镜、构图、稳定' },
  { key: 'visual_environment', label: '画面与环境', weight: 11, desc: '光影色调、曝光肤色、背景与风格统一' },
]

const SCORE_LABELS = ['Fail', 'Terrible', 'Bad', 'Normal', 'Good', 'Awesome']

const route = useRoute()
const router = useRouter()
const task = ref(null)
const account = ref(null)
const loading = ref(false)
const selecting = ref(null)
const rollbacking = ref(null)
const promptExpanded = ref(false)

// 手动备注：{ [subId]: draftText }
const manualNotes = ref({})
// 关键穿帮检测：{ [subId]: { temporal_consistency: bool, ... } }
const criticalChecks = ref({})
// 多维度打分：{ [subId]: { audio_visual: 3, ... } }
const dimensionScores = ref({})
// AI评分理由展开状态：{ [subId]: boolean }
const aiReasonExpanded = ref({})
// 保存中状态：{ [subId]: boolean }
const savingNote = ref({})

// 加入队列
const enqueueing = ref(null)

// 发布对话框（保留，备用）
const publishDialogVisible = ref(false)
const publishingSubTask = ref(null)

// 导航数据
const navInfo = ref(null)   // VideoTaskNavRead from /navigation endpoint
const navLoading = ref(false)

let refreshInterval = null

const accountName = computed(() => task.value?.account_name || '未知账号')
const templateTitle = computed(() => task.value?.template_title || '未知模板')

const hasPrevVideo = computed(() => !!navInfo.value?.prev_task)
const hasNextVideo = computed(() => !!navInfo.value?.next_task)
const hasPrevBlogger = computed(() => !!navInfo.value?.prev_blogger_task)
const hasNextBlogger = computed(() => !!navInfo.value?.next_blogger_task)

// 当前账号任务选择进度统计
const selectionStats = computed(() => {
  const nav = navInfo.value
  if (!nav || !nav.total) return null
  const selected = nav.selected_count
  const unselected = nav.total - selected
  return { selected, unselected, total: nav.total }
})

const timeline = computed(() => {
  if (!task.value) return []
  const currentIdx = STATUS_ORDER.indexOf(task.value.status)
  return TIMELINE_STEPS.map((step, i) => {
    const stepIdx = STATUS_ORDER.indexOf(step.key)
    const done = stepIdx < currentIdx
    const current = stepIdx === currentIdx
    return {
      ...step,
      done,
      current,
      active: done || current,
      desc: current ? step.desc : (done ? '已完成' : step.desc),
    }
  })
})

function canRollback(sub) {
  return ['generating', 'pending_publish'].includes(sub.status)
}

function getAiScoreClass(score) {
  if (score >= 80) return 'vtd-ai-high'
  if (score >= 60) return 'vtd-ai-medium'
  return 'vtd-ai-low'
}

function hasAiScores(sub) {
  return (
    sub.ai_score !== null && sub.ai_score !== undefined ||
    sub.round1_score !== null && sub.round1_score !== undefined ||
    sub.round2_score !== null && sub.round2_score !== undefined ||
    !!sub.round1_reason ||
    !!sub.round2_reason
  )
}

function hasReviewingScores() {
  if (!task.value?.sub_tasks) return false
  return task.value.sub_tasks.some(
    sub => (
      ['reviewing', 'pending_publish', 'published', 'abandoned'].includes(sub.status) &&
      (
        sub.ai_score !== null && sub.ai_score !== undefined ||
        sub.round1_score !== null && sub.round1_score !== undefined ||
        sub.round2_score !== null && sub.round2_score !== undefined
      )
    )
  )
}

function reviewingSubTasks() {
  if (!task.value?.sub_tasks) return []
  return task.value.sub_tasks.filter(
    sub => ['reviewing', 'pending_publish', 'published', 'abandoned'].includes(sub.status)
  ).filter(sub =>
    sub.ai_score !== null && sub.ai_score !== undefined ||
    sub.round1_score !== null && sub.round1_score !== undefined ||
    sub.round2_score !== null && sub.round2_score !== undefined
  )
}

function shouldAutoRefresh() {
  if (!task.value) return false
  // Auto-refresh if any sub-task is in 'scoring' or 'generating' status or parent task is 'scoring' or 'generating'
  return ['generating', 'scoring'].includes(task.value.status) ||
         (task.value.sub_tasks && task.value.sub_tasks.some(sub => ['generating', 'scoring'].includes(sub.status)))
}

async function loadTask(polling = false) {
  if (!polling) {
    loading.value = true
  }
  try {
    if (polling && task.value) {
      const stateData = await fetchVideoTaskState(route.params.id)
      task.value.status = stateData.status
      if (stateData.sub_tasks && task.value.sub_tasks) {
        stateData.sub_tasks.forEach(newState => {
          const sub = task.value.sub_tasks.find(s => s.id === newState.id)
          if (sub) {
            Object.assign(sub, newState)
          }
        })
      }
    } else {
      task.value = await fetchVideoTask(route.params.id)
      // 初始化 draft 状态（首次加载时同步数据库已有值）
      if (task.value?.sub_tasks) {
        task.value.sub_tasks.forEach(sub => {
          if (manualNotes.value[sub.id] === undefined) {
            manualNotes.value[sub.id] = sub.manual_note ?? ''
          }
          if (criticalChecks.value[sub.id] === undefined) {
            criticalChecks.value[sub.id] = {
              temporal_consistency: sub.temporal_consistency ?? null,
              character_integrity: sub.character_integrity ?? null,
              audio_sync: sub.audio_sync ?? null,
            }
          }
          if (dimensionScores.value[sub.id] === undefined) {
            dimensionScores.value[sub.id] = sub.dimension_scores ? { ...sub.dimension_scores } : {}
          }
        })
      }
    }
  } catch (e) {
    if (!polling) {
      task.value = null
    }
  } finally {
    if (!polling) {
      loading.value = false
    }
  }
}

async function loadAccount() {
  if (!task.value?.account_id) return
  try {
    account.value = await fetchAccount(task.value.account_id)
  } catch {
    // 加载失败不阻断页面，发布对话框会显示无平台可选
  }
}

function startAutoRefresh() {
  stopAutoRefresh() // Clear any existing interval
  refreshInterval = setInterval(async () => {
    if (shouldAutoRefresh()) {
      await loadTask(true)
    } else {
      stopAutoRefresh()
    }
  }, 3000) // Refresh every 3 seconds
}

function stopAutoRefresh() {
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
}

function toggleAiReason(subId) {
  aiReasonExpanded.value[subId] = !aiReasonExpanded.value[subId]
}

function getWeightedScoreClass(score) {
  if (score >= 80) return 'vtd-ws-high'
  if (score >= 60) return 'vtd-ws-medium'
  return 'vtd-ws-low'
}

async function handleSaveNote(sub) {
  if (savingNote.value[sub.id]) return
  savingNote.value[sub.id] = true
  try {
    const checks = criticalChecks.value[sub.id] || {}
    const dims = dimensionScores.value[sub.id] || {}
    const payload = {
      manual_note: manualNotes.value[sub.id] || null,
      temporal_consistency: checks.temporal_consistency ?? null,
      character_integrity: checks.character_integrity ?? null,
      audio_sync: checks.audio_sync ?? null,
      dimension_scores: Object.keys(dims).length > 0 ? dims : null,
    }
    const updated = await saveSubTaskNote(sub.id, payload)
    sub.manual_score = updated.manual_score
    sub.manual_note = updated.manual_note
    sub.temporal_consistency = updated.temporal_consistency
    sub.character_integrity = updated.character_integrity
    sub.audio_sync = updated.audio_sync
    sub.critical_fail = updated.critical_fail
    sub.dimension_scores = updated.dimension_scores
    sub.weighted_total_score = updated.weighted_total_score
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    savingNote.value[sub.id] = false
  }
}

async function setCriticalCheck(sub, key, value) {
  if (!criticalChecks.value[sub.id]) criticalChecks.value[sub.id] = {}
  criticalChecks.value[sub.id][key] = value
  await handleSaveNote(sub)
}

async function setDimensionScore(sub, key, value) {
  if (!dimensionScores.value[sub.id]) dimensionScores.value[sub.id] = {}
  dimensionScores.value[sub.id][key] = value
  await handleSaveNote(sub)
}

async function handleEnqueue(sub) {
  if (enqueueing.value) return
  enqueueing.value = sub.id
  try {
    await enqueueSubTask(sub.id)
    ElMessage.success('已加入发布队列，系统将自动发布')
    await loadTask()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加入队列失败')
  } finally {
    enqueueing.value = null
  }
}

function openPublishDialog(sub) {
  publishingSubTask.value = sub
  publishDialogVisible.value = true
}

function onPublishSuccess() {
  publishDialogVisible.value = false
  loadTask()
}

async function handleSelect(sub) {
  await ElMessageBox.confirm(
    `确认选择子任务 #${sub.sub_index} 的视频作为发布版本？另外两个子任务将被废弃。`,
    '选择发布版本',
    { confirmButtonText: '确认选择', cancelButtonText: '取消', type: 'warning' }
  )
  selecting.value = sub.id
  try {
    await patchSubTaskStatus(sub.id, { status: 'pending_publish', selected: true })
    ElMessage.success('已选定发布版本')
    // 本地更新状态，不刷新页面避免滚动位置丢失
    sub.status = 'pending_publish'
    sub.selected = true
    for (const sibling of task.value.sub_tasks) {
      if (sibling.id !== sub.id && sibling.status !== 'published' && sibling.status !== 'abandoned') {
        sibling.status = 'abandoned'
      }
    }
    task.value.status = 'pending_publish'
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    selecting.value = null
  }
}

async function handleRollback(sub) {
  rollbacking.value = sub.id
  try {
    await rollbackSubTaskStatus(sub.id)
    ElMessage.success('已撤回')
    await loadTask()
    if (shouldAutoRefresh()) {
      startAutoRefresh()
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '撤回失败')
  } finally {
    rollbacking.value = null
  }
}

async function loadNavigationData() {
  if (!task.value) return
  navLoading.value = true
  try {
    navInfo.value = await fetchTaskNavigation(task.value.id)
  } catch (e) {
    if (!e?.isDuplicateRequest) console.error('[Nav] 加载导航信息失败', e)
  } finally {
    navLoading.value = false
  }
}

function goToPrevVideo() {
  const t = navInfo.value?.prev_task
  if (!t) return
  router.push(`/dashboard/video-tasks/${t.id}`)
}

function goToNextVideo() {
  const t = navInfo.value?.next_task
  if (!t) return
  router.push(`/dashboard/video-tasks/${t.id}`)
}

function goToPrevBlogger() {
  const t = navInfo.value?.prev_blogger_task
  if (!t) return
  router.push(`/dashboard/video-tasks/${t.id}`)
}

function goToNextBlogger() {
  const t = navInfo.value?.next_blogger_task
  if (!t) return
  router.push(`/dashboard/video-tasks/${t.id}`)
}

// 路由参数变化时重新加载（同一组件切换任务）
watch(() => route.params.id, async (newId, oldId) => {
  if (newId && newId !== oldId) {
    stopAutoRefresh()
    task.value = null
    account.value = null
    manualNotes.value = {}
    criticalChecks.value = {}
    dimensionScores.value = {}
    navInfo.value = null
    await loadTask()
    await loadAccount()
    await loadNavigationData()
    if (shouldAutoRefresh()) startAutoRefresh()
  }
})

onMounted(async () => {
  await loadTask()
  await loadAccount()
  await loadNavigationData()
  if (shouldAutoRefresh()) {
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.vtd-page {
  padding: 28px 32px 80px;
  min-height: 100%;
  background: #f8fafc;
}

.vtd-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.vtd-back-btn {
  display: flex; align-items: center; gap: 4px;
  font-size: 14px; color: #6366f1; background: none; border: none;
  cursor: pointer; padding: 6px 10px; border-radius: 6px;
  font-weight: 500; transition: background 0.15s; white-space: nowrap;
}
.vtd-back-btn:hover { background: #eef2ff; }

.vtd-header-info { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.vtd-info-item { font-size: 14px; color: #475569; display: flex; align-items: center; }

.vtd-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.vtd-tag-chip {
  --vtd-tag-color: #6366f1;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--vtd-tag-color) 12%, white);
  border: 1px solid color-mix(in srgb, var(--vtd-tag-color) 22%, white);
  color: color-mix(in srgb, var(--vtd-tag-color) 78%, #111827);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.vtd-tag-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--vtd-tag-color);
  flex: 0 0 auto;
}

.vtd-template { color: #6366f1; font-weight: 500; }
.vtd-template-link { cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
.vtd-template-link:hover { color: #4f46e5; }

.vtd-sep { color: #cbd5e1; font-size: 14px; }

.vtd-loading { height: 300px; }

.vtd-body { display: flex; flex-direction: column; gap: 20px; }

/* Top row: timeline + prompt side by side */
.vtd-top-row {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  align-items: start;
}

.vtd-original-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 18px;
}

.vtd-original-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.vtd-original-link {
  border: none;
  background: transparent;
  color: #6366f1;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.vtd-original-grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 18px;
  align-items: start;
}

.vtd-original-player {
  width: 100%;
}

.vtd-original-video,
.vtd-original-placeholder {
  width: 100%;
  aspect-ratio: 9 / 16;
  border-radius: 12px;
  background: #0f172a;
  object-fit: cover;
}

.vtd-original-placeholder {
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
  color: #94a3b8;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.vtd-original-meta {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vtd-original-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.5;
}

.vtd-original-info {
  font-size: 14px;
  color: #475569;
  line-height: 1.6;
}

.vtd-original-source {
  width: fit-content;
  color: #4f46e5;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.vtd-original-source:hover {
  text-decoration: underline;
}

/* Timeline card */
.vtd-timeline-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 18px;
}

.vtd-section-label {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 16px;
}

.vtd-timeline { display: flex; flex-direction: column; }

.vtd-timeline-item {
  display: flex;
  gap: 12px;
  position: relative;
}

.vtd-tl-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 20px;
}

.vtd-tl-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e2e8f0;
  border: 2px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  z-index: 1;
  transition: all 0.2s;
}

.vtd-timeline-item.done .vtd-tl-dot {
  background: #6366f1;
  border-color: #6366f1;
}

.vtd-timeline-item.current .vtd-tl-dot {
  background: #fff;
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.2);
}

.vtd-tl-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6366f1;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.7; }
}

.vtd-tl-line {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: #e2e8f0;
  margin: 2px 0;
}

.vtd-timeline-item.done .vtd-tl-line,
.vtd-timeline-item.current .vtd-tl-line {
  background: #c7d2fe;
}

.vtd-tl-content {
  padding-bottom: 20px;
  flex: 1;
}

.vtd-timeline-item:last-child .vtd-tl-content { padding-bottom: 0; }

.vtd-tl-title {
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  line-height: 20px;
  transition: color 0.2s;
}

.vtd-timeline-item.done .vtd-tl-title { color: #475569; }
.vtd-timeline-item.current .vtd-tl-title { color: #6366f1; font-weight: 700; }

.vtd-tl-desc {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
  line-height: 1.4;
}
.vtd-timeline-item.current .vtd-tl-desc { color: #6366f1; opacity: 0.8; }

.vtd-tl-scores {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.vtd-tl-score-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 11px;
}

.vtd-tl-score-item.vtd-tl-score-selected {
  border-color: #6366f1;
  background: #eef2ff;
}

.vtd-tl-score-item.vtd-tl-score-abandoned {
  border-color: #fecaca;
  background: #fff1f2;
}

.vtd-tl-score-index {
  font-weight: 600;
  color: #64748b;
}

.vtd-tl-score-value {
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.vtd-tl-score-value.vtd-ai-high { background: #dcfce7; color: #15803d; }
.vtd-tl-score-value.vtd-ai-medium { background: #fef3c7; color: #d97706; }
.vtd-tl-score-value.vtd-ai-low { background: #fee2e2; color: #b91c1c; }

.vtd-tl-score-rounds {
  font-size: 10px;
  color: #94a3b8;
  margin-left: 2px;
}

/* Prompt card */
.vtd-prompt-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 20px;
}

.vtd-prompt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
  margin-bottom: 10px;
}
.vtd-prompt-header:hover svg { stroke: #6366f1; }

.vtd-prompt-text {
  font-size: 13px;
  color: #334155;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow: hidden;
  transition: max-height 0.3s ease;
}

.vtd-prompt-text.collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.vtd-prompt-expand {
  margin-top: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #6366f1;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}
.vtd-prompt-expand:hover { color: #4f46e5; }

/* Sub-task grid */
.vtd-subtasks {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 900px) {
  .vtd-subtasks { grid-template-columns: 1fr; }
  .vtd-top-row { grid-template-columns: 1fr; }
  .vtd-original-grid { grid-template-columns: 1fr; }
}

.vtd-sub-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.vtd-sub-card.vtd-sub-selected {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.12);
}

.vtd-sub-card.vtd-sub-abandoned { opacity: 0.55; }

.vtd-sub-header {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; border-bottom: 1px solid #f1f5f9;
}

.vtd-sub-index {
  font-size: 14px; font-weight: 700; color: #1e293b;
  background: #f1f5f9; border-radius: 6px; padding: 2px 8px;
}

.vtd-selected-badge {
  margin-left: auto;
  display: flex; align-items: center; gap: 3px;
  font-size: 11px; font-weight: 600; color: #6366f1;
  background: #eef2ff; padding: 2px 8px; border-radius: 20px;
}

.vtd-ai-score {
  display: flex; align-items: center; gap: 3px;
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 20px;
}

.vtd-ai-high {
  background: #dcfce7; color: #15803d;
}

.vtd-ai-medium {
  background: #fef3c7; color: #d97706;
}

.vtd-ai-low {
  background: #fee2e2; color: #b91c1c;
}

.vtd-ai-details {
  padding: 12px 16px;
  border-top: 1px solid #f1f5f9;
  background: #fafbfc;
}

.vtd-ai-details-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}

.vtd-ai-details-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.vtd-ai-scores {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.vtd-ai-score-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 60px;
}

.vtd-ai-score-item.vtd-ai-final {
  margin-left: auto;
  padding-left: 12px;
  border-left: 2px solid #e2e8f0;
}

.vtd-ai-round {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}

.vtd-ai-score-value {
  font-size: 16px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 12px;
  min-width: 50px;
  text-align: center;
}

.vtd-ai-reason {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #cbd5e1;
}

.vtd-ai-reason-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.vtd-ai-reason-text {
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.vtd-sub-video-wrap {
  width: 100%; aspect-ratio: 9/16; background: #0f172a;
  overflow: hidden; display: flex; align-items: center; justify-content: center;
}

.vtd-sub-video { width: 100%; height: 100%; object-fit: contain; }

.vtd-sub-video-placeholder {
  display: flex; flex-direction: column; align-items: center;
  gap: 10px; color: #64748b; font-size: 13px;
}

.vtd-sub-actions {
  padding: 12px 16px; display: flex; gap: 8px;
  flex-wrap: wrap; border-top: 1px solid #f1f5f9; min-height: 52px; align-items: center;
}

.vtd-scoring-error {
  padding: 10px 16px;
  margin: 0 16px 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.vtd-scoring-error svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.vtd-error-text {
  font-size: 13px;
  color: #b91c1c;
  line-height: 1.5;
}

.vtd-error {
  display: flex; flex-direction: column; align-items: center;
  padding: 80px 0; gap: 16px; color: #94a3b8;
}

/* Status badges */
.vtd-status-badge {
  font-size: 11px; font-weight: 600; padding: 2px 9px;
  border-radius: 20px; white-space: nowrap;
}
.vtd-status-pending         { background: #f1f5f9; color: #64748b; }
.vtd-status-generating      { background: #eff6ff; color: #3b82f6; }
.vtd-status-scoring         { background: #f0fdf4; color: #059669; }
.vtd-status-reviewing       { background: #fef9c3; color: #854d0e; }
.vtd-status-pending_publish { background: #fef3c7; color: #d97706; }
.vtd-status-publishing      { background: #ede9fe; color: #7c3aed; }
.vtd-status-publish_failed  { background: #fee2e2; color: #b91c1c; }
.vtd-status-published       { background: #dcfce7; color: #15803d; }
.vtd-status-abandoned       { background: #fee2e2; color: #b91c1c; }

/* 手动备注区域 */
.vtd-note-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.vtd-note-score-col {
  flex: 0 0 90px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vtd-note-reason-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vtd-note-col-label {
  font-size: 11px;
  font-weight: 600;
  color: #6366f1;
  letter-spacing: 0.02em;
}

.vtd-note-score-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
}

.vtd-note-score-input {
  width: 64px;
  padding: 6px 8px;
  border: 1px solid #c7d2fe;
  border-radius: 6px;
  font-size: 13px;
  color: #1e293b;
  background: #fff;
  outline: none;
  -moz-appearance: textfield;
  transition: border-color 0.15s;
}

.vtd-note-score-input::-webkit-outer-spin-button,
.vtd-note-score-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.vtd-note-score-input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
}

.vtd-note-score-unit {
  font-size: 12px;
  color: #94a3b8;
}

.vtd-manual-note {
  margin: 14px 0 0;
  padding: 14px;
  background: #f8faff;
  border: 1px solid #e0e7ff;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vtd-manual-note-label {
  display: flex;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
  color: #4f46e5;
  letter-spacing: 0.02em;
}

.vtd-note-textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #c7d2fe;
  border-radius: 9px;
  background: #fff;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #1e293b;
  resize: vertical;
  outline: none;
  font-family: inherit;
  transition: border-color 0.15s;
}

.vtd-note-textarea:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
}

.vtd-note-textarea::placeholder {
  color: #a5b4fc;
}

/* Critical checks section */
.vtd-critical-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vtd-critical-title,
.vtd-dimension-title {
  font-size: 12px;
  font-weight: 700;
  color: #374151;
  letter-spacing: 0.02em;
}

.vtd-critical-checks {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.vtd-critical-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  transition: all 0.15s;
}

.vtd-critical-item.vtd-critical-pass {
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.vtd-critical-item.vtd-critical-fail {
  background: #fef2f2;
  border-color: #fecaca;
}

.vtd-critical-label {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  min-width: 100px;
}

.vtd-critical-desc {
  font-size: 12px;
  color: #64748b;
  flex: 1;
}

.vtd-critical-btns {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.vtd-ck-btn {
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.vtd-ck-pass.active {
  background: #10b981;
  color: #fff;
  border-color: #10b981;
}

.vtd-ck-fail.active {
  background: #ef4444;
  color: #fff;
  border-color: #ef4444;
}

.vtd-ck-btn:hover:not(.active) {
  border-color: #94a3b8;
}

.vtd-critical-verdict {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: 8px;
}

.vtd-verdict-fail {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.vtd-verdict-pass {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #bbf7d0;
}

/* Dimension scoring */
.vtd-dimension-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;
}

.vtd-dimension-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.vtd-dim-item {
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.vtd-dim-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.vtd-dim-name {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
}

.vtd-dim-weight {
  font-size: 10px;
  font-weight: 600;
  color: #6366f1;
  background: #eef2ff;
  padding: 2px 6px;
  border-radius: 4px;
}

.vtd-dim-desc {
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 8px;
}

.vtd-dim-scores-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
}

.vtd-dim-score-btn {
  --btn-color: #94a3b8;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: 5px 0;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
}

.vtd-dim-score-btn.vtd-score-0 { --btn-color: #dc2626; }
.vtd-dim-score-btn.vtd-score-1 { --btn-color: #f97316; }
.vtd-dim-score-btn.vtd-score-2 { --btn-color: #eab308; }
.vtd-dim-score-btn.vtd-score-3 { --btn-color: #84cc16; }
.vtd-dim-score-btn.vtd-score-4 { --btn-color: #22c55e; }
.vtd-dim-score-btn.vtd-score-5 { --btn-color: #7c3aed; }

.vtd-dim-btn-num {
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
}

.vtd-dim-btn-label {
  font-size: 9px;
  font-weight: 600;
  line-height: 1;
  opacity: 0.85;
}

.vtd-dim-score-btn:hover:not(.active) {
  border-color: #94a3b8;
  color: #1e293b;
}

.vtd-dim-score-btn.active {
  background: var(--btn-color);
  color: #fff;
  border-color: var(--btn-color);
}

.vtd-dim-score-labels-placeholder {
  /* removed, labels now inside buttons */
  font-size: 9px;
  color: #94a3b8;
}

.vtd-weighted-total {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.vtd-weighted-value {
  font-size: 22px;
  font-weight: 800;
}

.vtd-ws-high { color: #10b981; }
.vtd-ws-medium { color: #eab308; }
.vtd-ws-low { color: #ef4444; }

.vtd-weighted-max {
  font-size: 13px;
  color: #94a3b8;
  font-weight: 500;
}

.vtd-autosave-indicator {
  font-size: 11px;
  color: #94a3b8;
  text-align: right;
  font-style: italic;
}

/* Sticky bottom nav bar */
.vtd-nav-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(8px);
  border-top: 1px solid #e2e8f0;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.06);
}

/* 占位元素，和右侧统计等宽，让中间按钮真正居中 */
.vtd-nav-spacer {
  flex: 1;
}

.vtd-nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.vtd-nav-btn:hover:not(:disabled) {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #4f46e5;
}

.vtd-nav-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.vtd-nav-btn-right {
  flex-direction: row-reverse;
}

.vtd-nav-pos {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  padding: 0 12px;
  min-width: 60px;
  text-align: center;
}

.vtd-nav-stats {
  flex: 1;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}

.vtd-nav-stats-done {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #10b981;
}

.vtd-nav-stats-sep {
  color: #cbd5e1;
}

.vtd-nav-stats-pending {
  color: #f59e0b;
}
</style>
