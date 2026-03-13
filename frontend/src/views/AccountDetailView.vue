<template>
  <div v-loading="loading" class="ad-page">
    <!-- Back -->
    <div class="ad-back" @click="$router.push('/dashboard/accounts')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      返回账号列表
    </div>

    <template v-if="account">
      <!-- Hero card -->
      <div class="ad-hero">
        <div class="ad-hero-media">
          <button
            type="button"
            class="ad-media-card ad-media-avatar"
            :class="{ 'is-clickable': !!account.avatar_url }"
            @click="openMediaPreview(account.avatar_url, `${account.account_name}头像`)"
          >
            <img v-if="account.avatar_url" :src="account.avatar_url" class="ad-avatar-img" />
            <div v-else class="ad-avatar-placeholder">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            </div>
            <span class="ad-media-label">头像</span>
          </button>
          <button
            type="button"
            class="ad-media-card ad-media-photo"
            :class="{ 'is-clickable': !!account.photo_url }"
            @click="openMediaPreview(account.photo_url, `${account.account_name}照片`)"
          >
            <img v-if="account.photo_url" :src="account.photo_url" class="ad-photo-img" />
            <div v-else class="ad-photo-placeholder">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.7"><path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14l-5.5-5.5a2 2 0 0 0-2.828 0L4 21V5z"/><circle cx="15" cy="9" r="2"/></svg>
              <span>暂无照片</span>
            </div>
            <span class="ad-media-label">照片</span>
          </button>
        </div>

        <div class="ad-hero-info">
          <div class="ad-hero-name">{{ account.account_name }}</div>
          <div v-if="account.style_description" class="ad-hero-style">{{ account.style_description }}</div>
          <div class="ad-hero-meta">
            <span class="ad-hero-stat"><strong>{{ tabCounts.published }}</strong> 已发布</span>
            <span class="ad-hero-stat"><strong>{{ tabCounts.queued }}</strong> 发布队列</span>
            <span class="ad-hero-stat"><strong>{{ tabCounts.pending_publish }}</strong> 待发布</span>
            <span v-if="tabCounts.publish_failed" class="ad-hero-stat ad-hero-stat-fail">
              <strong>{{ tabCounts.publish_failed }}</strong> 发布失败
            </span>
            <span class="ad-hero-stat ad-hero-stat-link" @click="router.push('/dashboard/daily-tasks')">
              <strong>{{ tabCounts.pending + tabCounts.generating }}</strong> 生成任务
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
            </span>
          </div>
          <div class="ad-hero-platforms">
            <span v-for="binding in (account.social_bindings || [])" :key="binding.platform"
              class="ad-platform-badge" :class="`ad-platform-${binding.platform}`">
              {{ platformLabel(binding.platform) }}
            </span>
            <span v-if="!account.social_bindings?.length" class="ad-no-platform">未绑定平台</span>
          </div>

          <!-- Bound TikTok bloggers -->
          <div v-if="account.tiktok_bloggers?.length" class="ad-hero-bloggers">
            <span class="ad-bloggers-label">关联博主</span>
            <div
              v-for="blogger in account.tiktok_bloggers"
              :key="blogger.id"
              class="ad-blogger-chip"
              :title="blogger.blogger_name + (blogger.blogger_handle ? ' @' + blogger.blogger_handle : '')"
            >
              <img v-if="blogger.avatar_url" :src="blogger.avatar_url" class="ad-blogger-avatar" />
              <div v-else class="ad-blogger-avatar ad-blogger-avatar-ph">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
              </div>
              <span class="ad-blogger-name">{{ blogger.blogger_name }}</span>
            </div>
          </div>
        </div>

        <div class="ad-hero-actions">
          <button class="ad-gen-btn" @click="$router.push(`/dashboard/accounts/${account.id}/generate`)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            生成视频
          </button>
          <button class="ad-schedule-btn" :class="{ active: account.publish_enabled }" @click="openScheduleDialog">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            {{ account.publish_enabled ? '定时发布中' : '定时发布' }}
          </button>
          <button class="ad-ai-btn" @click="openAIDialog">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 12h8"/><path d="M12 8v8"/></svg>
            {{ aiDialogButtonText }}
          </button>
          <button class="ad-edit-btn" @click="$router.push(`/dashboard/accounts/${account.id}/edit`)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            编辑账号
          </button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="ad-tabs-bar">
        <button
          v-for="tab in TABS"
          :key="tab.key"
          class="ad-tab"
          :class="{ active: activeTab === tab.key, 'ad-tab-fail': tab.key === 'publish_failed', 'ad-tab-queue': tab.key === 'queued' }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span v-if="tabCounts[tab.key]" class="ad-tab-count" :class="{ 'ad-tab-count-fail': tab.key === 'publish_failed', 'ad-tab-count-queue': tab.key === 'queued' }">{{ tabCounts[tab.key] }}</span>
        </button>
        <button class="ad-refresh-btn" :disabled="tasksLoading" @click="loadTasks">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" :class="{ spinning: tasksLoading }"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
          刷新
        </button>
      </div>

      <!-- Queue tab hint -->
      <div v-if="activeTab === 'queued'" class="ad-queue-hint">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        拖拽视频卡片可调整发布顺序，队列按得分从高到低排列
      </div>

      <!-- Video grid -->
      <div v-if="tasksLoading" class="ad-grid-loading" v-loading="true"></div>

      <div v-else-if="!filteredSubTasks.length" class="ad-grid-empty">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#c7d2fe" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
        <span>{{ emptyText }}</span>
      </div>

      <div
        v-else
        class="ad-video-grid"
        :class="{ 'ad-grid-draggable': activeTab === 'queued' }"
        @dragover.prevent
        @drop="onDrop($event)"
      >
        <div
          v-for="(item, index) in filteredSubTasks"
          :key="item.sub.id"
          class="ad-video-card"
          :class="{ 'ad-card-selected': item.sub.selected, 'ad-card-dragging': draggingId === item.sub.id }"
          :draggable="activeTab === 'queued'"
          @dragstart="onDragStart($event, item.sub.id, index)"
          @dragend="onDragEnd"
          @dragover.prevent="onDragOver($event, index)"
        >
          <!-- Drag handle (queue tab only) -->
          <div v-if="activeTab === 'queued'" class="ad-drag-handle">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="9" cy="7" r="1" fill="#94a3b8"/><circle cx="15" cy="7" r="1" fill="#94a3b8"/><circle cx="9" cy="12" r="1" fill="#94a3b8"/><circle cx="15" cy="12" r="1" fill="#94a3b8"/><circle cx="9" cy="17" r="1" fill="#94a3b8"/><circle cx="15" cy="17" r="1" fill="#94a3b8"/></svg>
            <span class="ad-queue-rank">#{{ index + 1 }}</span>
          </div>

          <!-- Thumbnail / video -->
          <div class="ad-card-thumb" @click="router.push(`/dashboard/video-tasks/${item.task.id}`)">
            <video
              v-if="item.sub.result_video_url"
              :src="item.sub.result_video_url"
              class="ad-card-video"
              preload="metadata"
              muted
              loop
              @mouseenter="e => e.target.play()"
              @mouseleave="e => { e.target.pause(); e.target.currentTime = 0 }"
            />
            <div v-else class="ad-card-placeholder">
              <svg v-if="item.sub.status === 'generating'" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
              <svg v-else width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="1.5" stroke-linecap="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>
            </div>

            <!-- Status overlay -->
            <div class="ad-card-status-badge" :class="`ad-status-${item.sub.status}`">
              {{ STATUS_LABELS[item.sub.status] }}
            </div>

            <!-- Selected checkmark -->
            <div v-if="item.sub.selected" class="ad-card-check">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>
            </div>

            <!-- AI Score badge -->
            <div v-if="item.sub.ai_score != null" class="ad-card-score-badge" :class="scoreClass(item.sub.ai_score)">
              {{ item.sub.ai_score }}分
            </div>
          </div>

          <!-- Card content -->
          <div class="ad-card-body">
            <div class="ad-card-meta">
              <span class="ad-card-date">{{ item.task.target_date }}</span>
              <span class="ad-card-index">#{{ item.sub.sub_index }}</span>
            </div>
            <div class="ad-card-template">{{ item.task.template_title || '未知模板' }}</div>
            <div class="ad-card-prompt">{{ item.task.prompt }}</div>

            <!-- AI Scoring details -->
            <div v-if="item.sub.ai_score != null || item.sub.round1_score != null" class="ad-score-detail">
              <div class="ad-score-row">
                <span class="ad-score-label">AI综合分</span>
                <span class="ad-score-val" :class="scoreClass(item.sub.ai_score)">{{ item.sub.ai_score ?? '-' }}</span>
              </div>
              <div v-if="item.sub.round1_score != null" class="ad-score-row">
                <span class="ad-score-label">第一轮</span>
                <span class="ad-score-val">{{ item.sub.round1_score }}</span>
                <span v-if="item.sub.round1_reason" class="ad-score-reason" :title="item.sub.round1_reason">{{ item.sub.round1_reason }}</span>
              </div>
              <div v-if="item.sub.round2_score != null" class="ad-score-row">
                <span class="ad-score-label">第二轮</span>
                <span class="ad-score-val">{{ item.sub.round2_score }}</span>
                <span v-if="item.sub.round2_reason" class="ad-score-reason" :title="item.sub.round2_reason">{{ item.sub.round2_reason }}</span>
              </div>
            </div>

            <!-- Scoring error message -->
            <div v-if="item.sub.scoring_error" class="ad-card-error">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>{{ item.sub.scoring_error }}</span>
            </div>

            <!-- Channel status (published tab) -->
            <div v-if="activeTab === 'published' && publicationsMap[item.sub.id]?.channels_status?.length" class="ad-channel-status">
              <div
                v-for="ch in publicationsMap[item.sub.id].channels_status"
                :key="ch.upload_id || ch.channel_id"
                class="ad-ch-item"
                :class="`ad-ch-${ch.status}`"
              >
                <span class="ad-ch-platform">{{ platformLabel(ch.platform) }}</span>
                <span class="ad-ch-status-label">{{ ch.status === 'completed' ? '成功' : ch.status === 'failed' ? '失败' : ch.status }}</span>
                <a v-if="ch.platform_video_url" :href="ch.platform_video_url" target="_blank" class="ad-ch-link" @click.stop>查看</a>
                <span v-if="ch.error_message && ch.status === 'failed'" class="ad-ch-error" :title="ch.error_message">{{ ch.error_message }}</span>
              </div>
            </div>

            <!-- Action buttons -->
            <div class="ad-card-actions">
              <!-- 待发布：入队按钮 -->
              <el-button
                v-if="item.sub.status === 'pending_publish' && item.sub.selected"
                type="success"
                size="small"
                :loading="enqueuing === item.sub.id"
                @click="handleEnqueue(item.sub)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px"><path d="M3 17l9-9 9 9M12 8v13"/></svg>
                加入队列
              </el-button>

              <!-- 发布队列：出队按钮 -->
              <el-button
                v-if="item.sub.status === 'queued'"
                size="small"
                plain
                :loading="dequeuing === item.sub.id"
                @click="handleDequeue(item.sub)"
              >移出队列</el-button>

              <!-- 发布队列：直接发布按钮 -->
              <el-button
                v-if="item.sub.status === 'queued'"
                type="primary"
                size="small"
                @click="openPublishDialog(item.task, item.sub)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="margin-right: 4px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                发布
              </el-button>

              <!-- 发布失败：重试发布 -->
              <el-button
                v-if="item.sub.status === 'publish_failed' && item.sub.selected"
                type="primary"
                size="small"
                :loading="retrying === item.sub.id"
                @click="handleRetryPublish(item.task, item.sub)"
              >重试发布</el-button>

              <!-- 待发布：删除 -->
              <el-button
                v-if="item.sub.status === 'pending_publish'"
                type="danger"
                size="small"
                plain
                :loading="deleting === item.sub.id"
                @click="handleDeleteSubTask(item.task, item.sub)"
              >删除</el-button>

              <!-- generating：撤回 -->
              <el-button
                v-if="canRollback(item.sub)"
                size="small"
                plain
                :loading="rollbacking === item.sub.id"
                @click="handleRollback(item.task, item.sub)"
              >撤回</el-button>

              <button class="ad-card-detail-btn" @click="router.push(`/dashboard/video-tasks/${item.task.id}`)">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 发布对话框 -->
    <PublishVideoDialog
      v-model="publishDialogVisible"
      :video-url="publishVideoUrl"
      :account="account"
      :sub-task="publishSubTask"
      @success="handlePublishSuccess"
    />

    <!-- 定时发布配置 dialog -->
    <el-dialog v-model="showScheduleDialog" title="定时发布配置" width="520px">
      <el-form :model="scheduleForm" label-width="120px" label-position="left">
        <el-form-item label="启用定时发布">
          <el-switch v-model="scheduleForm.publish_enabled" />
        </el-form-item>
        <template v-if="scheduleForm.publish_enabled">
          <el-form-item label="快捷规则">
            <div class="ad-schedule-presets">
              <button
                v-for="p in CRON_PRESETS"
                :key="p.cron"
                type="button"
                class="ad-preset-btn"
                :class="{ active: scheduleForm.publish_cron === p.cron }"
                @click="scheduleForm.publish_cron = p.cron"
              >{{ p.label }}</button>
            </div>
          </el-form-item>
          <el-form-item label="Cron 表达式">
            <el-input v-model="scheduleForm.publish_cron" placeholder="0 10 * * *" style="font-family:monospace" />
            <div class="ad-schedule-hint">格式：分 时 日 月 周（北京时间）。例：每天10点 = 0 10 * * *</div>
          </el-form-item>
          <el-form-item label="随机延迟">
            <el-input-number v-model="scheduleForm.publish_window_minutes" :min="0" :max="720" :step="15" style="width:130px" />
            <span class="ad-schedule-unit">分钟（到点后随机延迟，0 = 精确时间）</span>
          </el-form-item>
          <el-form-item label="每次发布数量">
            <el-input-number v-model="scheduleForm.publish_count" :min="1" :max="20" style="width:100px" />
            <span class="ad-schedule-unit">个视频（按队列顺序）</span>
          </el-form-item>
          <el-form-item label="规则预览">
            <div class="ad-schedule-preview">{{ schedulePreview }}</div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showScheduleDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingSchedule" @click="handleSaveSchedule">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showAIDialog"
      width="min(94vw, 1100px)"
      top="4vh"
      append-to-body
      class="ad-ai-dialog"
      destroy-on-close
    >
      <template #header>
        <div class="ad-ai-header">
          <div>
            <div class="ad-ai-title">AI 博主生成候选</div>
            <div class="ad-ai-subtitle">{{ aiStatusLabel(aiState?.status || account?.ai_generation_status || 'idle') }}</div>
          </div>
          <el-button size="small" :loading="aiStateLoading" @click="loadAIState">刷新状态</el-button>
        </div>
      </template>

      <div v-loading="aiStateLoading" class="ad-ai-body">
        <div v-if="aiState?.error_message" class="ad-ai-error">{{ aiState.error_message }}</div>

        <div class="ad-ai-summary">
          <div class="ad-ai-summary-item">
            <span>标签视频总数</span>
            <strong>{{ aiState?.all_video_count ?? 0 }}</strong>
          </div>
          <div class="ad-ai-summary-item">
            <span>分析样本数</span>
            <strong>{{ aiState?.analysis_sample_size ?? 0 }}</strong>
          </div>
          <div class="ad-ai-summary-item">
            <span>照片候选数</span>
            <strong>{{ aiState?.photo_candidates?.length ?? 0 }}</strong>
          </div>
          <div class="ad-ai-summary-item">
            <span>生成名称</span>
            <strong>{{ aiState?.generated_name || '未生成' }}</strong>
          </div>
        </div>

        <div class="ad-ai-section">
          <div class="ad-ai-section-head">
            <h3>视频分析样本</h3>
            <span>{{ aiState?.analysis_items?.length || 0 }} 条</span>
          </div>
          <div v-if="!aiState?.analysis_items?.length" class="ad-ai-empty">暂无分析结果</div>
          <div v-else class="ad-ai-analysis-list">
            <div v-for="item in aiState.analysis_items" :key="`${item.video_source_id}-${item.video_url}`" class="ad-ai-analysis-card">
              <video :src="item.video_url" class="ad-ai-video" controls preload="metadata" />
              <div class="ad-ai-analysis-meta">
                <span class="ad-ai-status-pill" :class="`is-${item.status}`">{{ aiCandidateStatusLabel(item.status) }}</span>
                <span class="ad-ai-video-id">视频 {{ item.video_source_id.slice(0, 8) }}</span>
              </div>
              <div class="ad-ai-text">{{ item.description || item.error_message || '处理中...' }}</div>
            </div>
          </div>
        </div>

        <div class="ad-ai-section">
          <div class="ad-ai-section-head">
            <h3>照片候选</h3>
            <span>{{ aiState?.photo_candidates?.length || 0 }} 个</span>
          </div>
          <div v-if="!aiState?.photo_candidates?.length" class="ad-ai-empty">暂无照片候选</div>
          <div v-else class="ad-ai-photo-groups">
            <div
              v-for="group in groupedPhotoCandidates"
              :key="`group-${group.source_group_index}`"
              class="ad-ai-photo-group"
            >
              <div class="ad-ai-source-wrap">
                <div class="ad-ai-source-label">来源视频 {{ group.source_group_index }}</div>
                <video :src="group.video_url" class="ad-ai-video ad-ai-source-video" controls preload="metadata" />
              </div>
              <div class="ad-ai-analysis-meta">
                <span class="ad-ai-video-id">视频 {{ group.video_source_id.slice(0, 8) }}</span>
              </div>
              <div class="ad-ai-text">{{ group.analysis_description || group.error_message || '处理中...' }}</div>

              <div class="ad-ai-photo-grid">
                <div
                  v-for="candidate in group.candidates"
                  :key="candidate.candidate_id"
                  class="ad-ai-photo-card"
                  :class="{ 'is-selected': aiState.selected_photo_candidate_id === candidate.candidate_id }"
                >
                  <button
                    v-if="candidate.generated_photo_url"
                    type="button"
                    class="ad-ai-photo-preview"
                    @click="openMediaPreview(candidate.generated_photo_url, `照片候选 ${candidate.candidate_number}`)"
                  >
                    <img :src="candidate.generated_photo_url" class="ad-ai-photo-img" />
                  </button>
                  <div v-else class="ad-ai-photo-placeholder">{{ aiCandidateStatusLabel(candidate.status) }}</div>
                  <div class="ad-ai-analysis-meta">
                    <span class="ad-ai-status-pill" :class="`is-${candidate.status}`">{{ aiCandidateStatusLabel(candidate.status) }}</span>
                    <span class="ad-ai-video-id">候选 {{ candidate.candidate_number }}</span>
                  </div>
                  <el-button
                    v-if="candidate.status === 'completed'"
                    type="primary"
                    size="small"
                    :loading="selectingCandidateId === candidate.candidate_id"
                    :disabled="aiState.status !== 'awaiting_photo_selection'"
                    @click="handleSelectCandidate(candidate)"
                  >
                    {{ aiState.selected_photo_candidate_id === candidate.candidate_id ? '已选用' : '选用此照片' }}
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog
      v-model="previewVisible"
      width="min(92vw, 1080px)"
      top="5vh"
      append-to-body
      class="ad-preview-dialog"
    >
      <img v-if="previewImage.url" :src="previewImage.url" :alt="previewImage.title" class="ad-preview-image" />
      <template #header>
        <div class="ad-preview-title">{{ previewImage.title }}</div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchAccount, fetchAIGenerationStatus, selectAIPhotoCandidate, updateScheduledPublish } from '../api/accounts'
import { fetchAccountVideoTasks, patchSubTaskStatus, rollbackSubTaskStatus, deleteSubTask, enqueueSubTask, dequeueSubTask } from '../api/video_tasks'
import { fetchSubTaskPublications } from '../api/video_publications'
import http from '../api/http'

import PublishVideoDialog from '../components/PublishVideoDialog.vue'

const route = useRoute()
const router = useRouter()

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }

const STATUS_LABELS = {
  pending: '待处理',
  generating: '生成中',
  scoring: 'AI打分',
  pending_publish: '待发布',
  queued: '队列中',
  publishing: '发布中',
  publish_failed: '发布失败',
  published: '已发布',
  abandoned: '已废弃',
}

const TABS = [
  { key: 'pending_publish', label: '待发布' },
  { key: 'queued',          label: '发布队列' },
  { key: 'publishing',      label: '发布中' },
  { key: 'publish_failed',  label: '发布失败' },
  { key: 'published',       label: '已发布' },
]

const EMPTY_TEXTS = {
  pending_publish: '暂无待发布的视频',
  queued:          '发布队列为空，在「待发布」tab 中将视频加入队列',
  publishing:      '暂无发布中的视频',
  publish_failed:  '暂无发布失败的视频',
  published:       '暂无已发布的视频',
}

const loading = ref(false)
const account = ref(null)
const tasks = ref([])
const tasksLoading = ref(false)
const activeTab = ref('pending_publish')
const rollbacking = ref(null)
const retrying = ref(null)
const deleting = ref(null)
const enqueuing = ref(null)
const dequeuing = ref(null)
const previewVisible = ref(false)
const previewImage = ref({ url: '', title: '' })
const showAIDialog = ref(false)
const aiStateLoading = ref(false)
const aiState = ref(null)
const selectingCandidateId = ref(null)
let aiPollTimer = null

// 拖拽状态
const draggingId = ref(null)
const draggingIndex = ref(null)
const dragOverIndex = ref(null)

// 发布对话框
const publishDialogVisible = ref(false)
const publishVideoUrl = ref('')
const publishSubTask = ref(null)

// 已发布 tab 的渠道状态缓存（以 sub_id 为键）
const publicationsMap = ref({})

// Flatten all sub-tasks with parent task reference
const allSubTasks = computed(() => {
  const result = []
  for (const task of tasks.value) {
    for (const sub of (task.sub_tasks || [])) {
      if (sub.status !== 'abandoned') {
        result.push({ task, sub })
      }
    }
  }
  return result
})

const filteredSubTasks = computed(() => {
  const items = allSubTasks.value.filter(item => item.sub.status === activeTab.value)
  // 待发布按分数从高到低排序
  if (activeTab.value === 'pending_publish') {
    return [...items].sort((a, b) => {
      const aScore = a.sub.ai_score ?? -1
      const bScore = b.sub.ai_score ?? -1
      return bScore - aScore
    })
  }
  // 发布队列只按 queue_order 手动排序
  if (activeTab.value === 'queued') {
    return [...items].sort((a, b) => {
      const aOrder = a.sub.queue_order ?? 99999
      const bOrder = b.sub.queue_order ?? 99999
      return aOrder - bOrder
    })
  }
  return items
})

const tabCounts = computed(() => {
  const counts = { pending_publish: 0, queued: 0, publishing: 0, publish_failed: 0, published: 0, generating: 0, pending: 0, all: 0 }
  for (const { sub } of allSubTasks.value) {
    if (counts[sub.status] !== undefined) counts[sub.status]++
    counts.all++
  }
  return counts
})

const emptyText = computed(() => EMPTY_TEXTS[activeTab.value] || '暂无内容')

function platformLabel(p) { return PLATFORM_LABELS[p] || p }

function canRollback(sub) {
  return sub.status === 'generating'
}

function scoreClass(score) {
  if (score == null) return ''
  if (score >= 80) return 'score-high'
  if (score >= 60) return 'score-mid'
  return 'score-low'
}

function openMediaPreview(url, title) {
  if (!url) return
  previewImage.value = { url, title }
  previewVisible.value = true
}

const aiDialogButtonText = computed(() => {
  const status = aiState.value?.status || account.value?.ai_generation_status || 'idle'
  return status === 'awaiting_photo_selection' ? '选择照片候选' : '查看 AI 候选'
})

const groupedPhotoCandidates = computed(() => {
  const groups = new Map()
  for (const candidate of aiState.value?.photo_candidates || []) {
    const key = candidate.source_group_index || candidate.video_source_id
    if (!groups.has(key)) {
      groups.set(key, {
        source_group_index: candidate.source_group_index || 1,
        video_source_id: candidate.video_source_id,
        video_url: candidate.video_url,
        analysis_description: candidate.analysis_description,
        error_message: candidate.error_message,
        candidates: [],
      })
    }
    const group = groups.get(key)
    if (!group.analysis_description && candidate.analysis_description) group.analysis_description = candidate.analysis_description
    if (!group.error_message && candidate.error_message) group.error_message = candidate.error_message
    group.candidates.push(candidate)
  }
  return Array.from(groups.values())
    .sort((a, b) => a.source_group_index - b.source_group_index)
    .map(group => ({
      ...group,
      candidates: [...group.candidates].sort((a, b) => (a.candidate_number || 0) - (b.candidate_number || 0)),
    }))
})

function aiStatusLabel(status) {
  const map = {
    idle: '未开始',
    pending: '排队中',
    video_analyzing: '分析视频中',
    name_generating: '生成名称中',
    photo_generating: '生成照片候选中',
    awaiting_photo_selection: '等待人工选择照片',
    avatar_generating: '生成头像中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

function aiCandidateStatusLabel(status) {
  const map = {
    pending: '等待中',
    running: '处理中',
    analyzing: '分析中',
    generating: '生图中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

function clearAIPollTimer() {
  clearTimeout(aiPollTimer)
  aiPollTimer = null
}

function scheduleAIPoll() {
  clearAIPollTimer()
  const running = ['pending', 'video_analyzing', 'name_generating', 'photo_generating', 'avatar_generating']
  if (!running.includes(aiState.value?.status)) return
  aiPollTimer = setTimeout(async () => {
    await loadAIState()
    scheduleAIPoll()
  }, 2500)
}

async function loadAIState() {
  aiStateLoading.value = true
  try {
    const data = await fetchAIGenerationStatus(route.params.id)
    aiState.value = data
    if (account.value) account.value.ai_generation_status = data.status
    if (data.generated_name && account.value) account.value.account_name = data.generated_name
    if (data.generated_photo_url && account.value) account.value.photo_url = data.generated_photo_url
    if (data.generated_avatar_url && account.value) account.value.avatar_url = data.generated_avatar_url
    if (['completed', 'failed', 'awaiting_photo_selection'].includes(data.status)) {
      clearAIPollTimer()
    }
    if (data.status === 'completed') {
      await loadAccount()
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载 AI 生成状态失败')
  } finally {
    aiStateLoading.value = false
  }
}

async function openAIDialog() {
  showAIDialog.value = true
  await loadAIState()
  scheduleAIPoll()
}

async function handleSelectCandidate(candidate) {
  if (selectingCandidateId.value) return
  selectingCandidateId.value = candidate.candidate_id
  try {
    const data = await selectAIPhotoCandidate(route.params.id, candidate.candidate_id)
    aiState.value = data
    if (data.generated_photo_url && account.value) account.value.photo_url = data.generated_photo_url
    ElMessage.success('已选中照片候选，正在继续生成头像')
    scheduleAIPoll()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '选择照片候选失败')
  } finally {
    selectingCandidateId.value = null
  }
}

// 打开发布对话框
function openPublishDialog(task, sub) {
  if (!sub.result_video_url) {
    ElMessage.warning('视频尚未生成完成')
    return
  }
  if (!account.value?.social_bindings?.length) {
    ElMessage.warning('该账号尚未绑定任何发布平台，请先在编辑页面绑定平台')
    return
  }
  publishVideoUrl.value = sub.result_video_url
  publishSubTask.value = { ...sub, task }
  publishDialogVisible.value = true
}

// 发布成功处理
async function handlePublishSuccess() {
  ElMessage.success('发布任务创建成功，正在后台处理...')
  await loadTasks()
}

// 重试发布（publish_failed → pending_publish）
async function handleRetryPublish(_task, sub) {
  retrying.value = sub.id
  try {
    await patchSubTaskStatus(sub.id, { status: 'pending_publish' })
    ElMessage.success('已重置为待发布')
    activeTab.value = 'pending_publish'
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '重置失败')
  } finally {
    retrying.value = null
  }
}

// 入队（pending_publish → queued）
async function handleEnqueue(sub) {
  enqueuing.value = sub.id
  try {
    await enqueueSubTask(sub.id)
    ElMessage.success('已加入发布队列')
    activeTab.value = 'queued'
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    enqueuing.value = null
  }
}

// 出队（queued → pending_publish）
async function handleDequeue(sub) {
  dequeuing.value = sub.id
  try {
    await dequeueSubTask(sub.id)
    ElMessage.success('已移出队列')
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    dequeuing.value = null
  }
}

// 加载已发布视频的渠道状态
async function loadPublishedPublications() {
  const publishedSubs = allSubTasks.value.filter(({ sub }) => sub.status === 'published')
  for (const { sub } of publishedSubs) {
    if (!publicationsMap.value[sub.id]) {
      try {
        const pubs = await fetchSubTaskPublications(sub.id)
        if (pubs.length) publicationsMap.value[sub.id] = pubs[0]
      } catch {
        // ignore
      }
    }
  }
}

watch(activeTab, (tab) => {
  if (tab === 'published') {
    loadPublishedPublications()
  }
})

watch(showAIDialog, (visible) => {
  if (!visible) clearAIPollTimer()
})

async function loadAccount() {
  loading.value = true
  try {
    account.value = await fetchAccount(route.params.id)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载失败')
    router.push('/dashboard/accounts')
  } finally {
    loading.value = false
  }
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    tasks.value = await fetchAccountVideoTasks(route.params.id)
    // 如果当前在已发布 tab，重新加载渠道状态
    if (activeTab.value === 'published') {
      publicationsMap.value = {}
      loadPublishedPublications()
    }
  } catch {
    ElMessage.error('加载任务失败')
  } finally {
    tasksLoading.value = false
  }
}

async function handleDeleteSubTask(_task, sub) {
  try {
    await ElMessageBox.confirm('确认删除该视频？此操作不可恢复。', '删除待发布视频', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }
  deleting.value = sub.id
  try {
    await deleteSubTask(sub.id)
    ElMessage.success('已删除')
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = null
  }
}

async function handleRollback(_task, sub) {
  rollbacking.value = sub.id
  try {
    await rollbackSubTaskStatus(sub.id)
    ElMessage.success('已撤回')
    await loadTasks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '撤回失败')
  } finally {
    rollbacking.value = null
  }
}

// ── 拖拽排序 (queue tab only) ──────────────────────────────────────────────────

function onDragStart(event, subId, index) {
  if (activeTab.value !== 'queued') return
  draggingId.value = subId
  draggingIndex.value = index
  event.dataTransfer.effectAllowed = 'move'
}

function onDragEnd() {
  draggingId.value = null
  draggingIndex.value = null
  dragOverIndex.value = null
}

function onDragOver(_event, index) {
  if (activeTab.value !== 'queued') return
  dragOverIndex.value = index
}

async function onDrop(_event) {
  if (activeTab.value !== 'queued') return
  if (draggingIndex.value === null || dragOverIndex.value === null) return
  if (draggingIndex.value === dragOverIndex.value) return

  // Reorder locally
  const items = [...filteredSubTasks.value]
  const [moved] = items.splice(draggingIndex.value, 1)
  items.splice(dragOverIndex.value, 0, moved)

  // Persist new order: PATCH queue_order for each item via sub-task status endpoint
  // We use a dedicated endpoint: PATCH /video-tasks/subtasks/{id}/queue-order
  // For now call the backend with the new order list
  try {
    const orderPayload = items.map((item, idx) => ({ id: item.sub.id, queue_order: idx + 1 }))
    await http.patch('/video-tasks/subtasks/queue-order', orderPayload)
    await loadTasks()
  } catch (e) {
    ElMessage.error('保存排序失败：' + (e?.response?.data?.detail || e.message))
  }
}

// ── 定时发布 dialog ────────────────────────────────────────────────────────────

const CRON_PRESETS = [
  { label: '每天8点',    cron: '0 8 * * *' },
  { label: '每天10点',   cron: '0 10 * * *' },
  { label: '每天12点',   cron: '0 12 * * *' },
  { label: '每天20点',   cron: '0 20 * * *' },
  { label: '隔天10点',   cron: '0 10 */2 * *' },
  { label: '每周一10点', cron: '0 10 * * 1' },
]

const showScheduleDialog = ref(false)
const savingSchedule = ref(false)
const scheduleForm = ref({
  publish_enabled: false,
  publish_cron: '',
  publish_window_minutes: 0,
  publish_count: 1,
})

const schedulePreview = computed(() => {
  const cron = scheduleForm.value.publish_cron?.trim()
  if (!cron) return '请输入 Cron 表达式'
  const preset = CRON_PRESETS.find(p => p.cron === cron)
  const label = preset ? `${preset.label}` : `Cron: ${cron}`
  const window = scheduleForm.value.publish_window_minutes
  const count = scheduleForm.value.publish_count
  const windowStr = window > 0 ? `，到点后随机延迟最多 ${window} 分钟` : ''
  return `${label}${windowStr}，每次发布 ${count} 个视频（按队列顺序）`
})

function openScheduleDialog() {
  scheduleForm.value = {
    publish_enabled: account.value?.publish_enabled ?? false,
    publish_cron: account.value?.publish_cron ?? '',
    publish_window_minutes: account.value?.publish_window_minutes ?? 0,
    publish_count: account.value?.publish_count ?? 1,
  }
  showScheduleDialog.value = true
}

async function handleSaveSchedule() {
  savingSchedule.value = true
  try {
    const updated = await updateScheduledPublish(account.value.id, {
      publish_enabled: scheduleForm.value.publish_enabled,
      publish_cron: scheduleForm.value.publish_cron || null,
      publish_window_minutes: scheduleForm.value.publish_window_minutes,
      publish_count: scheduleForm.value.publish_count,
    })
    account.value = updated
    showScheduleDialog.value = false
    ElMessage.success(scheduleForm.value.publish_enabled ? '定时发布已启用' : '定时发布已关闭')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    savingSchedule.value = false
  }
}

onMounted(async () => {
  await loadAccount()
  await loadTasks()
})

onUnmounted(() => {
  clearAIPollTimer()
})
</script>

<style scoped>
.ad-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
  background: #f8fafc;
}

/* Back */
.ad-back {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 13px; color: #6366f1; font-weight: 600;
  cursor: pointer; margin-bottom: 24px; transition: color 0.15s;
}
.ad-back:hover { color: #4338ca; }

/* Hero */
.ad-hero {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,.05);
  padding: 28px;
  display: flex; align-items: center; gap: 24px; flex-wrap: wrap;
  margin-bottom: 16px;
}

.ad-hero-media {
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
  gap: 14px;
}

.ad-media-card {
  position: relative;
  border: 0;
  padding: 0;
  background: transparent;
  overflow: hidden;
}

.ad-media-card.is-clickable {
  cursor: zoom-in;
}

.ad-media-avatar {
  width: 108px;
  height: 108px;
  border-radius: 28px;
}

.ad-media-photo {
  width: 164px;
  height: 108px;
  border-radius: 22px;
  background: linear-gradient(135deg, #eef2ff, #f8fafc);
  box-shadow: inset 0 0 0 1px #e2e8f0;
}

.ad-avatar-img {
  width: 100%; height: 100%; border-radius: 28px;
  object-fit: cover; border: 3px solid #e0e7ff;
  box-shadow: 0 2px 12px rgba(99,102,241,.15);
}

.ad-avatar-placeholder {
  width: 100%; height: 100%; border-radius: 28px;
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  display: flex; align-items: center; justify-content: center;
  border: 3px solid #e0e7ff;
}

.ad-photo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.ad-photo-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 12px;
  background: linear-gradient(135deg, #eef2ff, #f8fafc);
}

.ad-media-label {
  position: absolute;
  left: 10px;
  bottom: 10px;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(6px);
  padding: 4px 8px;
  border-radius: 999px;
}

.ad-hero-info { flex: 1; }

.ad-hero-name { font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.02em; margin-bottom: 4px; }
.ad-hero-style { font-size: 13px; color: #64748b; margin-bottom: 10px; line-height: 1.5; }

.ad-hero-meta { display: flex; gap: 20px; margin-bottom: 10px; flex-wrap: wrap; }
.ad-hero-stat { font-size: 13px; color: #64748b; }
.ad-hero-stat strong { color: #0f172a; font-weight: 700; margin-right: 3px; }
.ad-hero-stat-fail strong { color: #dc2626; }
.ad-hero-stat-link {
  cursor: pointer;
  color: #6366f1;
  display: flex;
  align-items: center;
  gap: 3px;
  transition: color 0.15s;
}
.ad-hero-stat-link:hover { color: #4f46e5; }
.ad-hero-stat-link strong { color: #6366f1; }

.ad-hero-platforms { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }

.ad-hero-bloggers {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.ad-bloggers-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  white-space: nowrap;
}

.ad-blogger-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  background: #f8faff;
  border: 1px solid #e0e7ff;
  border-radius: 20px;
  padding: 3px 10px 3px 3px;
  cursor: default;
}

.ad-blogger-avatar {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.ad-blogger-avatar-ph {
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ad-blogger-name {
  font-size: 12px;
  font-weight: 600;
  color: #4f46e5;
  white-space: nowrap;
}

.ad-platform-badge {
  font-size: 12px; font-weight: 700; padding: 3px 10px;
  border-radius: 20px; letter-spacing: .02em;
}
.ad-platform-youtube  { background: #fef2f2; color: #dc2626; }
.ad-platform-tiktok   { background: #f1f5f9; color: #0f172a; }
.ad-platform-instagram { background: #fef3c7; color: #92400e; }
.ad-no-platform { font-size: 13px; color: #94a3b8; }

.ad-hero-actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: stretch;
  justify-content: center;
  min-width: 130px;
}

.ad-gen-btn {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  width: 100%;
  font-size: 13px; font-weight: 700; padding: 9px 18px;
  border-radius: 10px; border: none; background: #6366f1; color: #fff;
  cursor: pointer; transition: all 0.15s;
  box-shadow: 0 2px 8px rgba(99,102,241,0.25);
}
.ad-gen-btn:hover { background: #4f46e5; transform: translateY(-1px); }

.ad-ai-btn {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  width: 100%;
  font-size: 13px; font-weight: 700; padding: 9px 18px;
  border-radius: 10px; border: 1px solid #fde68a;
  background: #fef3c7; color: #b45309; cursor: pointer; transition: all 0.15s;
}
.ad-ai-btn:hover { background: #fde68a; transform: translateY(-1px); }

.ad-edit-btn {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  width: 100%;
  font-size: 13px; font-weight: 600; padding: 9px 18px;
  border-radius: 10px; border: 1px solid #c7d2fe;
  background: #eef2ff; color: #4338ca; cursor: pointer; transition: all 0.15s;
}
.ad-edit-btn:hover { background: #e0e7ff; border-color: #6366f1; }

.ad-schedule-btn {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  width: 100%;
  font-size: 13px; font-weight: 600; padding: 9px 18px;
  border-radius: 10px; border: 1px solid #c7d2fe;
  background: #f5f3ff; color: #6366f1; cursor: pointer; transition: all 0.15s;
}
.ad-schedule-btn:hover { background: #ede9fe; border-color: #a5b4fc; }
.ad-schedule-btn.active {
  background: #6366f1; color: #fff; border-color: #6366f1;
  box-shadow: 0 2px 8px rgba(99,102,241,0.3);
}

/* Schedule dialog */
.ad-schedule-presets {
  display: flex; flex-wrap: wrap; gap: 6px;
}

.ad-preset-btn {
  padding: 4px 12px; border-radius: 20px; border: 1.5px solid #e2e8f0;
  background: #fff; color: #64748b; font-size: 12px; cursor: pointer;
  transition: all 0.15s; font-weight: 500;
}
.ad-preset-btn:hover { border-color: #a5b4fc; color: #6366f1; background: #f5f3ff; }
.ad-preset-btn.active { border-color: #6366f1; background: #6366f1; color: #fff; }

.ad-schedule-hint {
  font-size: 11px; color: #94a3b8; margin-top: 4px; line-height: 1.5;
}

.ad-schedule-unit {
  font-size: 12px; color: #94a3b8; margin-left: 8px;
}

.ad-schedule-preview {
  font-size: 13px; color: #374151; background: #f1f5f9;
  border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 14px;
  line-height: 1.5; width: 100%;
}

/* Tabs bar */
.ad-tabs-bar {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 12px;
  padding: 8px 12px;
  margin-bottom: 16px;
}

.ad-tab {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 500; color: #64748b;
  padding: 7px 14px; border: none; background: none;
  cursor: pointer; border-radius: 8px;
  transition: all 0.15s; white-space: nowrap;
}
.ad-tab:hover { color: #6366f1; background: #f5f3ff; }
.ad-tab.active { color: #6366f1; font-weight: 700; background: #eef2ff; }
.ad-tab-fail:hover { color: #dc2626; background: #fef2f2; }
.ad-tab-fail.active { color: #dc2626; background: #fef2f2; }
.ad-tab-queue:hover { color: #059669; background: #f0fdf4; }
.ad-tab-queue.active { color: #059669; background: #f0fdf4; }

.ad-tab-count {
  font-size: 11px; font-weight: 700;
  background: #6366f1; color: #fff;
  border-radius: 10px; padding: 1px 7px; min-width: 18px; text-align: center;
}
.ad-tab.active .ad-tab-count { background: #4f46e5; }
.ad-tab-count-fail { background: #dc2626; }
.ad-tab-fail.active .ad-tab-count { background: #dc2626; }
.ad-tab-count-queue { background: #059669; }
.ad-tab-queue.active .ad-tab-count { background: #047857; }

.ad-refresh-btn {
  margin-left: auto;
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; font-weight: 600; color: #64748b;
  background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 7px; padding: 5px 10px; cursor: pointer; transition: all 0.15s;
}
.ad-refresh-btn:hover:not(:disabled) { color: #6366f1; border-color: #c7d2fe; background: #eef2ff; }
.ad-refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Queue hint */
.ad-queue-hint {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #6366f1;
  background: #eef2ff; border: 1px solid #c7d2fe;
  border-radius: 8px; padding: 8px 14px; margin-bottom: 14px;
}

.spinning { animation: spin 0.8s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* Grid */
.ad-grid-loading { height: 200px; }

.ad-grid-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 12px; padding: 60px; color: #94a3b8; font-size: 13px;
  background: #fff; border: 1px solid #e8edf5; border-radius: 12px;
}

.ad-video-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.ad-grid-draggable {
  /* slight visual hint for draggable grid */
}

/* Video card */
.ad-video-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
}
.ad-video-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.07); }
.ad-video-card.ad-card-selected { border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99,102,241,0.15); }
.ad-video-card.ad-card-dragging { opacity: 0.5; border: 2px dashed #6366f1; }
.ad-grid-draggable .ad-video-card { cursor: grab; }
.ad-grid-draggable .ad-video-card:active { cursor: grabbing; }

/* Drag handle */
.ad-drag-handle {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px 0;
  color: #94a3b8; font-size: 11px;
}

.ad-queue-rank {
  font-size: 12px; font-weight: 700; color: #059669;
}

/* Thumbnail */
.ad-card-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 9/16;
  background: #0f172a;
  cursor: pointer;
  overflow: hidden;
}

.ad-card-video {
  width: 100%; height: 100%; object-fit: cover; display: block;
  transition: transform 0.3s;
}
.ad-card-thumb:hover .ad-card-video { transform: scale(1.03); }

.ad-card-placeholder {
  width: 100%; height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; color: #94a3b8; font-size: 11px;
  background: linear-gradient(135deg, #1e293b, #0f172a);
}

.ad-card-status-badge {
  position: absolute; bottom: 8px; left: 8px;
  font-size: 10px; font-weight: 700;
  padding: 3px 8px; border-radius: 6px;
  backdrop-filter: blur(6px);
}

.ad-card-check {
  position: absolute; top: 8px; right: 8px;
  width: 22px; height: 22px; border-radius: 50%;
  background: #6366f1; display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}

/* AI Score badge on thumb */
.ad-card-score-badge {
  position: absolute; top: 8px; left: 8px;
  font-size: 11px; font-weight: 800;
  padding: 3px 8px; border-radius: 6px;
  backdrop-filter: blur(6px);
}
.ad-card-score-badge.score-high { background: rgba(220,252,231,0.9); color: #15803d; }
.ad-card-score-badge.score-mid  { background: rgba(254,249,195,0.9); color: #854d0e; }
.ad-card-score-badge.score-low  { background: rgba(254,226,226,0.9); color: #b91c1c; }

/* Status colors */
.ad-status-pending         { background: rgba(241,245,249,0.85); color: #64748b; }
.ad-status-generating      { background: rgba(239,246,255,0.85); color: #3b82f6; }
.ad-status-reviewing       { background: rgba(254,249,195,0.9);  color: #854d0e; }
.ad-status-pending_publish { background: rgba(254,243,199,0.9);  color: #d97706; }
.ad-status-queued          { background: rgba(209,250,229,0.9);  color: #065f46; }
.ad-status-publishing      { background: rgba(237,233,254,0.9);  color: #7c3aed; }
.ad-status-publish_failed  { background: rgba(254,226,226,0.9);  color: #b91c1c; }
.ad-status-published       { background: rgba(220,252,231,0.9);  color: #15803d; }
.ad-status-abandoned       { background: rgba(254,226,226,0.9);  color: #b91c1c; }

/* Card body */
.ad-card-body { padding: 12px; }

.ad-card-meta {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 4px;
}

.ad-card-date { font-size: 11px; color: #94a3b8; }
.ad-card-index { font-size: 11px; font-weight: 700; color: #6366f1; background: #eef2ff; padding: 1px 6px; border-radius: 4px; }

.ad-card-template {
  font-size: 12px; font-weight: 600; color: #6366f1;
  margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.ad-card-prompt {
  font-size: 12px; color: #475569; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; margin-bottom: 10px;
}

/* AI Score detail */
.ad-score-detail {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ad-score-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.ad-score-label {
  color: #94a3b8;
  font-weight: 600;
  min-width: 48px;
}

.ad-score-val {
  font-weight: 800;
  color: #0f172a;
}
.ad-score-val.score-high { color: #15803d; }
.ad-score-val.score-mid  { color: #d97706; }
.ad-score-val.score-low  { color: #dc2626; }

.ad-score-reason {
  color: #64748b;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 140px;
}

.ad-card-actions {
  display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
}

.ad-card-error {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  margin-top: 10px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.4;
}

.ad-card-error svg {
  flex-shrink: 0;
  margin-top: 1px;
}

/* Channel status */
.ad-channel-status {
  margin-top: 8px;
  margin-bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.ad-ch-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px;
}

.ad-ch-platform {
  font-weight: 600; color: #475569; min-width: 52px;
}

.ad-ch-status-label { font-weight: 700; }
.ad-ch-completed .ad-ch-status-label { color: #15803d; }
.ad-ch-failed .ad-ch-status-label { color: #b91c1c; }

.ad-ch-link {
  color: #6366f1; text-decoration: none; font-size: 11px;
  padding: 1px 6px; background: #eef2ff; border-radius: 4px;
}
.ad-ch-link:hover { background: #e0e7ff; }

.ad-ch-error {
  color: #94a3b8; font-size: 11px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  max-width: 110px;
}

.ad-card-detail-btn {
  margin-left: auto;
  display: flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 6px;
  border: 1px solid #e2e8f0; background: #f8fafc;
  color: #94a3b8; cursor: pointer; transition: all 0.15s;
  flex-shrink: 0;
}
.ad-card-detail-btn:hover { border-color: #c7d2fe; background: #eef2ff; color: #6366f1; }

.ad-ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ad-ai-title {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.ad-ai-subtitle {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.ad-ai-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.ad-ai-error {
  padding: 12px 14px;
  border-radius: 10px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  font-size: 13px;
}

.ad-ai-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.ad-ai-summary-item {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

.ad-ai-summary-item strong {
  font-size: 16px;
  color: #0f172a;
}

.ad-ai-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ad-ai-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.ad-ai-section-head h3 {
  margin: 0;
  font-size: 15px;
  color: #0f172a;
}

.ad-ai-section-head span {
  font-size: 12px;
  color: #64748b;
}

.ad-ai-empty {
  padding: 18px;
  text-align: center;
  border-radius: 12px;
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
  color: #94a3b8;
  font-size: 13px;
}

.ad-ai-analysis-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.ad-ai-photo-groups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.ad-ai-photo-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
}

.ad-ai-analysis-card,
.ad-ai-photo-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
}

.ad-ai-photo-card.is-selected {
  border-color: #22c55e;
  box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.12);
}

.ad-ai-source-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ad-ai-source-label {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}

.ad-ai-video,
.ad-ai-photo-img {
  width: 100%;
  border-radius: 12px;
  background: #0f172a;
  object-fit: cover;
}

.ad-ai-video {
  aspect-ratio: 9 / 16;
  max-width: 168px;
  margin: 0 auto;
}

.ad-ai-source-video {
  border: 1px solid #e2e8f0;
}

.ad-ai-photo-preview {
  border: none;
  padding: 0;
  background: transparent;
  cursor: pointer;
}

.ad-ai-photo-img {
  aspect-ratio: 3 / 4;
}

.ad-ai-photo-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 3 / 4;
  border-radius: 12px;
  background: #f8fafc;
  color: #94a3b8;
  font-size: 13px;
  border: 1px dashed #cbd5e1;
}

.ad-ai-analysis-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ad-ai-status-pill {
  font-size: 11px;
  font-weight: 700;
  border-radius: 999px;
  padding: 3px 8px;
  background: #e2e8f0;
  color: #475569;
}

.ad-ai-status-pill.is-running,
.ad-ai-status-pill.is-analyzing,
.ad-ai-status-pill.is-generating {
  background: #dbeafe;
  color: #1d4ed8;
}

.ad-ai-status-pill.is-completed {
  background: #dcfce7;
  color: #15803d;
}

.ad-ai-status-pill.is-failed {
  background: #fee2e2;
  color: #b91c1c;
}

.ad-ai-video-id {
  font-size: 11px;
  color: #94a3b8;
}

.ad-ai-text {
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
  max-height: 132px;
  overflow: auto;
  white-space: pre-wrap;
}

.ad-ai-photo-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.ad-preview-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.ad-preview-image {
  display: block;
  width: 100%;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 12px;
  background: #f8fafc;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (max-width: 1100px) {
  .ad-video-grid { grid-template-columns: repeat(2, 1fr); }
  .ad-ai-photo-groups,
  .ad-ai-photo-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .ad-hero { flex-direction: column; text-align: center; }
  .ad-hero-media { width: 100%; justify-content: center; }
  .ad-hero-platforms { justify-content: center; }
  .ad-hero-meta { justify-content: center; }
  .ad-video-grid { grid-template-columns: repeat(2, 1fr); }
  .ad-ai-summary,
  .ad-ai-analysis-list,
  .ad-ai-photo-groups,
  .ad-ai-photo-grid { grid-template-columns: 1fr; }
  .ad-page { padding: 16px; }
}
</style>
