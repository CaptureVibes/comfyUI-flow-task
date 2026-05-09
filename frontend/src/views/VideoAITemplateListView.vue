<template>
  <div class="vai-page">
    <!-- Header -->
    <div class="vai-header">
      <h1 class="vai-title">AI模板</h1>
      <div class="vai-header-actions">
        <el-dropdown trigger="click" :disabled="batchPrimaryLoading" @command="handleBatchCommand">
          <el-button class="vai-batch-btn" :loading="batchPrimaryLoading">
            <svg v-if="!batchPrimaryLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M4 7h16"/><path d="M4 12h16"/><path d="M4 17h16"/></svg>
            一键操作
            <svg v-if="!batchPrimaryLoading" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-left:6px"><polyline points="6 9 12 15 18 9"/></svg>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="pause">
                <span class="vai-menu-item vai-menu-pause">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                  一键暂停
                </span>
              </el-dropdown-item>
              <el-dropdown-item command="retry">
                <span class="vai-menu-item vai-menu-retry">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
                  一键重试
                </span>
              </el-dropdown-item>
              <el-dropdown-item command="restart" divided>
                <span class="vai-menu-item vai-menu-restart">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
                  一键重跑
                </span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button class="vai-config-btn" @click="openConfig">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="margin-right:6px"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          流程配置
        </el-button>
        <el-button type="primary" class="vai-add-btn" @click="$router.push('/dashboard/video-ai-templates/new')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          新建模板
        </el-button>
      </div>
    </div>

    <!-- Stats row -->
    <div class="vai-stats">
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'pending' }" style="--stat-color: #64748b; --stat-bg: #f1f5f9;" @click="toggleFilter('pending')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">排队中</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.pending || 0 }}</div>
        <div class="vai-stat-sub">pending</div>
      </div>
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'imagegen' }" style="--stat-color: #8b5cf6; --stat-bg: #ede9fe;" @click="toggleFilter('imagegen')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">阶段1 抽帧上传</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.imagegen || 0 }}</div>
        <div class="vai-stat-sub">imagegen</div>
      </div>
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'outfit_selecting' }" style="--stat-color: #ec4899; --stat-bg: #fce7f3;" @click="toggleFilter('outfit_selecting')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">阶段2 穿搭识别</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ec4899" stroke-width="2"><path d="M20.38 3.46L16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.57a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.57a2 2 0 0 0-1.34-2.23z"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.outfit_selecting || 0 }}</div>
        <div class="vai-stat-sub">outfit_selecting</div>
      </div>
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'outfit_detailing' }" style="--stat-color: #a855f7; --stat-bg: #faf5ff;" @click="toggleFilter('outfit_detailing')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">阶段3 单品理解</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a855f7" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.outfit_detailing || 0 }}</div>
        <div class="vai-stat-sub">outfit_detailing</div>
      </div>
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'understanding' }" style="--stat-color: #6366f1; --stat-bg: #eef2ff;" @click="toggleFilter('understanding')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">阶段4-5 视频理解</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.understanding || 0 }}</div>
        <div class="vai-stat-sub">intent + understanding</div>
      </div>
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'product_imagegen' }" style="--stat-color: #f97316; --stat-bg: #fff7ed;" @click="toggleFilter('product_imagegen')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">阶段6 单品生图</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f97316" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.product_imagegen || 0 }}</div>
        <div class="vai-stat-sub">product_imagegen</div>
      </div>
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'outfit_regen' }" style="--stat-color: #06b6d4; --stat-bg: #ecfeff;" @click="toggleFilter('outfit_regen')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">阶段7 造型重生</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" stroke-width="2"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.outfit_regen || 0 }}</div>
        <div class="vai-stat-sub">outfit_regen</div>
      </div>
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'paused' }" style="--stat-color: #475569; --stat-bg: #f1f5f9;" @click="toggleFilter('paused')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">暂停</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="#475569"><rect x="7" y="5" width="3.5" height="14" rx="1"/><rect x="13.5" y="5" width="3.5" height="14" rx="1"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.paused || 0 }}</div>
        <div class="vai-stat-sub">paused</div>
      </div>
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'success' }" style="--stat-color: #10b981; --stat-bg: #dcfce7;" @click="toggleFilter('success')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">成功</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.success || 0 }}</div>
        <div class="vai-stat-sub">success</div>
      </div>
      <div class="vai-stat-card" :class="{ 'vai-stat-active': activeFilter === 'fail' }" style="--stat-color: #ef4444; --stat-bg: #fee2e2;" @click="toggleFilter('fail')">
        <div class="vai-stat-top">
          <span class="vai-stat-label">失败</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.fail || 0 }}</div>
        <div class="vai-stat-sub">fail</div>
      </div>
    </div>

    <!-- Card grid -->
    <div v-loading="loading" class="vai-grid">
      <div v-for="item in items" :key="item.id" class="vt-card" @click="goToDetail(item)">
        <!-- Header with status -->
        <div class="vt-header">
          <el-tag
            size="small"
            :type="statusType(item.process_status)"
            class="vt-status-tag"
            :style="statusStyle(item.process_status)"
          >
            {{ statusLabel(item.process_status) }}
          </el-tag>
          <div class="vt-actions" @click.stop>
            <!-- fail: retry button -->
            <button
              v-if="item.process_status === 'fail'"
              class="vt-action-btn vt-action-retry"
              :disabled="!!actioning"
              @click="handleStart(item)"
            >
              <svg v-if="actioning !== item.id + '-start'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
              <svg v-else class="vt-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
              重试
            </button>
            <!-- paused: resume + restart -->
            <template v-if="canResume(item)">
              <button
                class="vt-action-btn vt-action-resume"
                :disabled="!!actioning"
                @click="handleResume(item)"
              >
                <svg v-if="actioning !== item.id + '-resume'" width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                <svg v-else class="vt-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
                继续
              </button>
              <button
                class="vt-action-btn vt-action-restart"
                :disabled="!!actioning"
                @click.stop="handleRestart(item)"
              >
                <svg v-if="actioning !== item.id + '-restart'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
                <svg v-else class="vt-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
                重跑
              </button>
            </template>
            <!-- understanding-only: pause -->
            <button
              v-if="canPause(item)"
              class="vt-action-btn vt-action-pause"
              :disabled="!!actioning"
              @click="handlePause(item)"
            >
              <svg v-if="actioning !== item.id + '-pause'" width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
              <svg v-else class="vt-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
              暂停
            </button>
          </div>
        </div>

        <!-- Video preview -->
        <div v-if="item.video_source" class="vt-video-section" @click.stop="openPlayer(item.video_source)">
          <div v-if="item.video_source.thumbnail_url" class="vt-thumb">
            <img :src="item.video_source.thumbnail_url" class="vt-thumb-img" />
            <div class="vt-thumb-overlay">
              <div class="vt-play-btn">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="white"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              </div>
            </div>
          </div>
          <div v-else class="vt-thumb-placeholder">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M10 9l5 3-5 3V9z"/></svg>
          </div>
          <div v-if="item.video_source.platform" class="vt-platform-badge">
            {{ platformLabel(item.video_source.platform) }}
          </div>
          <span v-if="isAdmin() && item.owner_username" class="vt-owner-badge">{{ item.owner_username }}</span>
        </div>

        <!-- Content -->
        <div class="vt-content">
          <div class="vt-title">{{ item.title }}</div>
          <div v-if="item.description" class="vt-desc">{{ item.description }}</div>
          <div v-if="item.tags && item.tags.length > 0" class="vt-tags">
            <span
              v-for="tag in item.tags"
              :key="tag.id"
              class="vt-tag-chip"
              :style="tag.color ? { '--vt-tag-color': tag.color } : {}"
            >
              <span class="vt-tag-dot"></span>
              {{ tag.name }}
            </span>
          </div>

          <!-- Error message -->
          <div v-if="item.process_error" class="vt-error">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>{{ item.process_error }}</span>
          </div>

          <!-- Video source stats -->
          <div class="vt-source-stats">
            <span v-if="item.video_source && item.video_source.view_count != null" class="vt-stat-item">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              {{ formatViewCount(item.video_source.view_count) }}
            </span>
            <span class="vt-stat-item">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
              {{ item.generated_video_count || 0 }} 个视频
            </span>
            <span v-if="item.last_published_at" class="vt-stat-item">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              {{ formatDate(item.last_published_at) }}
            </span>
          </div>

          <!-- Meta info -->
          <div class="vt-meta">
            <div class="vt-meta-info">
              <span class="vt-date">{{ formatDate(item.updated_at) }}</span>
              <span v-if="item.video_source" class="vt-video-info">
                @{{ item.video_source.blogger_name || '未知' }}
              </span>
            </div>
            <div class="vt-footer-actions">
              <button
                class="vc-btn vc-btn-del"
                :class="{ loading: deleting === item.id }"
                @click.stop="handleDelete(item)"
              >删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty -->
    <el-empty v-if="!loading && items.length === 0" description="暂无模板，点击「新建模板」开始" :image-size="80" />

    <!-- Pipeline Config Dialog -->
    <div v-if="showConfig" class="vt-dialog-overlay" @click.self="showConfig = false">
      <div class="vt-dialog-content" :class="{ 'vt-cta-mode': configCtaMode }" style="width: 760px;">
        <div class="vt-dialog-header">
          <div class="vt-cfg-header-left">
            <div class="vt-cta-toggle" :class="{ 'is-cta': configCtaMode }">
              <button
                type="button"
                class="vt-cta-toggle-btn"
                :class="{ active: !configCtaMode }"
                @click="configCtaMode = false"
              >无 CTA</button>
              <button
                type="button"
                class="vt-cta-toggle-btn"
                :class="{ active: configCtaMode }"
                @click="configCtaMode = true"
              >有 CTA</button>
            </div>
            <h2 class="vt-dialog-title">AI 处理流程配置</h2>
          </div>
          <button class="vt-dialog-close" @click="showConfig = false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>

        <div v-loading="configLoading" class="vt-dialog-body cfg-body">
          <div class="cfg-hint-bar">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            API Key 和 Base URL 由管理员在<router-link to="/dashboard/settings" @click="showConfig=false">系统设置</router-link>中配置，此处为你的个人流程参数。
          </div>

          <div class="vt-tabs">
            <button
              v-for="tab in [
                { key: 'step_imagegen', label: '阶段1 抽帧上传' },
                { key: 'step_outfit_select', label: '阶段2 穿搭识别' },
                { key: 'step_outfit_detail', label: '阶段3 单品理解' },
                { key: 'step_intent', label: '阶段4 意图识别' },
                { key: 'step_understand', label: '阶段5 视频理解' },
                { key: 'step_product_gen', label: '阶段6 单品生图' },
                { key: 'step_outfit_regen', label: '阶段7 造型重生' }
              ]"
              :key="tab.key"
              class="vt-tab-btn"
              :class="{ 'vt-tab-active': configTab === tab.key }"
              @click="configTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>

          <div class="vt-tab-content">
            <!-- 阶段1：抽帧上传（无需配置，仅说明） -->
            <div v-if="configTab === 'step_imagegen'">
              <div class="cfg-step-desc">
                对视频（超过 15s 只取前 15s）每隔 <strong>1 秒</strong>抽一帧，并发上传到 CDN。抽帧图将落库保存，供后续识别穿搭使用。此步骤无需配置。
              </div>
            </div>

            <!-- 阶段2：穿搭识别 -->
            <div v-if="configTab === 'step_outfit_select'">
              <div class="cfg-step-desc">
                将所有抽帧图发给 Gemini，识别视频中出现的 Unique 穿搭，每套穿搭选出最能代表该穿搭的一帧。必须输出 JSON（使用 json_schema 约束），结果落库保存。
              </div>
              <div class="vt-form">
                <div class="vt-form-item">
                  <label class="vt-label">识别模型</label>
                  <input type="text" v-model="cfg.outfit_select_model" class="vt-input" placeholder="gemini-2.5-flash-preview-05-20（留空使用默认）" />
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">识别提示词 (Prompt)</label>
                  <textarea v-model="cfg[promptKey('outfit_select_prompt')]" class="vt-textarea" rows="5" placeholder="以下是从视频中1秒一帧抽取的图片，请识别其中的独特穿搭（outfit）。不同镜头角度的同一套穿搭算同一个，只选出一张最能代表该穿搭的图。请以JSON格式输出 representative_frame_index（从0开始）和 frame_indices 列表。"></textarea>
                  <div class="cfg-field-hint">留空使用内置默认提示词。输出必须为 JSON，系统已自动约束 json_schema。</div>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">温度 (Temperature)：{{ Number(cfg.outfit_select_temperature).toFixed(1) }}</label>
                  <input type="range" v-model.number="cfg.outfit_select_temperature" min="0" max="2" step="0.1" class="vt-range" />
                </div>
              </div>
            </div>

            <!-- 阶段3：单品理解 -->
            <div v-if="configTab === 'step_outfit_detail'">
              <div class="cfg-step-desc">
                对每一个 Unique 穿搭图，让 Gemini 输出整体造型风格描述和所有穿搭单品的名称、描述。输出为 JSON 格式（含 outfit_style 和 solo_products 数组）。
              </div>
              <div class="vt-form">
                <div class="vt-form-item">
                  <label class="vt-label">理解模型</label>
                  <input type="text" v-model="cfg.outfit_detail_model" class="vt-input" placeholder="gemini-2.5-flash-preview-05-20（留空使用默认）" />
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">理解提示词 (Prompt)</label>
                  <textarea v-model="cfg[promptKey('outfit_detail_prompt')]" class="vt-textarea" rows="5" placeholder="请分析这张穿搭图，输出整体造型风格描述和图中所有穿搭单品的名称及描述。以JSON格式返回，outfit_style为整体风格，solo_products为单品数组，每项含name和description。"></textarea>
                  <div class="cfg-field-hint">留空使用内置默认提示词。输出 JSON 格式：{ outfit_style: string, solo_products: [{name, description}] }</div>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">温度 (Temperature)：{{ Number(cfg.outfit_detail_temperature).toFixed(1) }}</label>
                  <input type="range" v-model.number="cfg.outfit_detail_temperature" min="0" max="2" step="0.1" class="vt-range" />
                </div>
              </div>
            </div>

            <!-- 阶段4：意图识别 -->
            <div v-if="configTab === 'step_intent'">
              <div class="cfg-step-desc">
                让 Gemini 直接基于视频判断核心创作意图。必须返回结构化 JSON（含 content_intent 等字段，已自动约束 json_schema），content_intent 必须是
                <strong>beauty_show / knowledge / persona_story / trend_meme</strong> 之一，否则自动重试最多 3 次。
              </div>
              <div class="vt-form">
                <div class="vt-form-item">
                  <label class="vt-label">意图识别模型</label>
                  <input type="text" v-model="cfg.intent_classify_model" class="vt-input" placeholder="gemini-2.5-flash-preview-05-20（留空使用默认）" />
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">意图识别提示词 (Prompt)</label>
                  <textarea v-model="cfg[promptKey('intent_classify_prompt')]" class="vt-textarea" rows="6" placeholder="请分析这段视频，判断视频的核心创作意图..."></textarea>
                  <div class="cfg-field-hint">留空使用内置默认提示词。content_intent 由 json_schema 强约束。</div>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">温度 (Temperature)：{{ Number(cfg.intent_classify_temperature).toFixed(1) }}</label>
                  <input type="range" v-model.number="cfg.intent_classify_temperature" min="0" max="2" step="0.1" class="vt-range" />
                </div>
              </div>
            </div>

            <!-- 阶段5：视频理解（按 content_intent 分支，4 个 prompt 共用模型/温度） -->
            <div v-if="configTab === 'step_understand'">
              <div class="cfg-step-desc">
                根据上一步输出的 <code>content_intent</code> 选择对应分支提示词，结合视频生成一段最终用于后续视频生成的提示词文本（落库到 prompt_description）。
              </div>
              <div class="vt-form">
                <div class="vt-form-item">
                  <label class="vt-label">视频理解模型</label>
                  <input type="text" v-model="cfg.understand_model" class="vt-input" placeholder="gemini-2.5-flash-preview-05-20（留空使用默认）" />
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">温度 (Temperature)：{{ Number(cfg.understand_temperature).toFixed(1) }}</label>
                  <input type="range" v-model.number="cfg.understand_temperature" min="0" max="2" step="0.1" class="vt-range" />
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">分支：beauty_show（穿搭/美感）</label>
                  <textarea v-model="cfg[promptKey('understand_prompt_beauty_show')]" class="vt-textarea" rows="4" placeholder="留空使用内置默认。支持 {intent_json} 占位符。"></textarea>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">分支：knowledge（知识/讲解）</label>
                  <textarea v-model="cfg[promptKey('understand_prompt_knowledge')]" class="vt-textarea" rows="4" placeholder="留空使用内置默认。支持 {intent_json} 占位符。"></textarea>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">分支：persona_story（人物/故事）</label>
                  <textarea v-model="cfg[promptKey('understand_prompt_persona_story')]" class="vt-textarea" rows="4" placeholder="留空使用内置默认。支持 {intent_json} 占位符。"></textarea>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">分支：trend_meme（潮流/梗）</label>
                  <textarea v-model="cfg[promptKey('understand_prompt_trend_meme')]" class="vt-textarea" rows="4" placeholder="留空使用内置默认。支持 {intent_json} 占位符。"></textarea>
                </div>
                <div class="cfg-field-hint">支持的占位符：<code>{intent_json}</code>（注入完整意图识别 JSON）。留空使用内置默认提示词。</div>
              </div>
            </div>

            <!-- 阶段6：单品生图 -->
            <div v-if="configTab === 'step_product_gen'">
              <div class="cfg-step-desc">
                针对每个单品，以其描述为提示词 + 造型图为参考，生成该单品的独立展示图。所有单品并发生成。
              </div>
              <div class="vt-form">
                <div class="vt-form-item">
                  <label class="vt-label">单品生图模型</label>
                  <input type="text" v-model="cfg.product_imagegen_model" class="vt-input" placeholder="gemini-2.5-flash-preview-05-20（留空使用默认）" />
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">单品生图提示词 (Prompt)</label>
                  <textarea v-model="cfg[promptKey('product_imagegen_prompt')]" class="vt-textarea" rows="4" placeholder="根据这张穿搭参考图，生成图中【{name}】单品的独立展示图。描述：{description}。保持原图风格，白色或简洁背景，突出单品细节。"></textarea>
                  <div class="cfg-field-hint">支持变量 {name} 和 {description}，留空使用内置默认提示词。</div>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">单品图尺寸 (Size)</label>
                  <div class="vt-select-wrapper" style="width: 220px">
                    <select v-model="cfg.product_imagegen_size" class="vt-select">
                      <option value="1:1">1:1（方形，推荐）</option>
                      <option value="9:16">9:16（竖屏）</option>
                      <option value="3:4">3:4</option>
                      <option value="4:3">4:3</option>
                      <option value="16:9">16:9（横屏）</option>
                    </select>
                    <div class="vt-select-arrow">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                  </div>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">单品图质量 (Quality)</label>
                  <div class="vt-radio-group">
                    <label class="vt-radio-label"><input type="radio" value="0.5K" v-model="cfg.product_imagegen_quality" class="vt-radio-input" /><span class="vt-radio-circle"></span>0.5K</label>
                    <label class="vt-radio-label"><input type="radio" value="1K" v-model="cfg.product_imagegen_quality" class="vt-radio-input" /><span class="vt-radio-circle"></span>1K</label>
                    <label class="vt-radio-label"><input type="radio" value="2K" v-model="cfg.product_imagegen_quality" class="vt-radio-input" /><span class="vt-radio-circle"></span>2K（推荐）</label>
                    <label class="vt-radio-label"><input type="radio" value="4K" v-model="cfg.product_imagegen_quality" class="vt-radio-input" /><span class="vt-radio-circle"></span>4K</label>
                  </div>
                </div>
              </div>
            </div>

            <!-- 阶段7：新造型图生成 -->
            <div v-if="configTab === 'step_outfit_regen'">
              <div class="cfg-step-desc">
                将每个穿搭的所有单品图 + outfit_style 作为提示词，生成新的整体造型图。新造型图将作为最终结果进入后续步骤。
              </div>
              <div class="vt-form">
                <div class="vt-form-item">
                  <label class="vt-label">造型重生模型</label>
                  <input type="text" v-model="cfg.outfit_regen_model" class="vt-input" placeholder="gemini-2.5-flash-preview-05-20（留空使用默认）" />
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">造型重生提示词 (Prompt)</label>
                  <textarea v-model="cfg[promptKey('outfit_regen_prompt')]" class="vt-textarea" rows="4" placeholder="根据以下单品图片，生成一张完整穿搭造型图。整体风格：{outfit_style}。保持服装风格一致，人物比例自然，背景简洁时尚。"></textarea>
                  <div class="cfg-field-hint">支持变量 {outfit_style}，留空使用内置默认提示词。所有单品图将作为参考图一起传入。</div>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">造型图尺寸 (Size)</label>
                  <div class="vt-select-wrapper" style="width: 220px">
                    <select v-model="cfg.outfit_regen_size" class="vt-select">
                      <option value="9:16">9:16（竖屏，推荐）</option>
                      <option value="1:1">1:1（方形）</option>
                      <option value="3:4">3:4</option>
                      <option value="4:3">4:3</option>
                      <option value="16:9">16:9（横屏）</option>
                    </select>
                    <div class="vt-select-arrow">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                  </div>
                </div>
                <div class="vt-form-item">
                  <label class="vt-label">造型图质量 (Quality)</label>
                  <div class="vt-radio-group">
                    <label class="vt-radio-label"><input type="radio" value="0.5K" v-model="cfg.outfit_regen_quality" class="vt-radio-input" /><span class="vt-radio-circle"></span>0.5K</label>
                    <label class="vt-radio-label"><input type="radio" value="1K" v-model="cfg.outfit_regen_quality" class="vt-radio-input" /><span class="vt-radio-circle"></span>1K</label>
                    <label class="vt-radio-label"><input type="radio" value="2K" v-model="cfg.outfit_regen_quality" class="vt-radio-input" /><span class="vt-radio-circle"></span>2K（推荐）</label>
                    <label class="vt-radio-label"><input type="radio" value="4K" v-model="cfg.outfit_regen_quality" class="vt-radio-input" /><span class="vt-radio-circle"></span>4K</label>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>

        <div class="vt-dialog-footer">
          <button class="vt-btn vt-btn-cancel" @click="showConfig = false">取消</button>
          <button class="vt-btn vt-btn-primary" :class="{ 'is-loading': configSaving }" :disabled="hasJsonError" @click="saveConfig">
            <svg v-if="configSaving" class="vt-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
            保存配置
          </button>
        </div>
      </div>
    </div>

    <!-- Footer pagination -->
    <div v-if="total > 0" class="vai-footer">
      <div class="vai-pagination-left">
        <span class="vai-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
        <select v-model="pageSize" @change="handleSizeChange(pageSize)" class="vai-simple-select">
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="500">500</option>
        </select>
      </div>
      <div class="vai-pagination">
        <button class="pg-btn" :disabled="page <= 1" @click="goPage(page - 1)">← 上一页</button>
        <!-- Page number buttons -->
        <template v-for="p in visiblePages" :key="p">
          <span v-if="p === '...'" class="pg-ellipsis">…</span>
          <button v-else class="pg-btn pg-num" :class="{ active: p === page }" @click="goPage(p)">{{ p }}</button>
        </template>
        <button class="pg-btn" :disabled="endIdx >= total" @click="goPage(page + 1)">下一页 →</button>
        <!-- Jump to page -->
        <span class="pg-jump-wrap">
          跳至
          <input
            v-model.number="jumpPage"
            class="pg-jump-input"
            type="number"
            :min="1"
            :max="totalPages"
            @keyup.enter="doJump"
          />
          页
          <button class="pg-btn pg-jump-go" @click="doJump">GO</button>
        </span>
      </div>
    </div>

    <!-- ── Video player dialog ── -->
    <el-dialog
      v-model="playerVisible"
      :title="playerItem?.video_title || '视频播放'"
      width="800px"
      align-center
      destroy-on-close
    >
      <div class="player-wrap">
        <video
          v-if="playerItem?.local_video_url || playerItem?.video_url"
          :src="playerItem.local_video_url || playerItem.video_url"
          controls
          autoplay
          class="player-video"
        />
        <div v-else class="player-nourl">
          <el-empty description="暂无可播放地址" :image-size="80" />
          <el-link :href="playerItem?.source_url" target="_blank" type="primary">前往原始链接观看</el-link>
        </div>
      </div>
      <div v-if="playerItem" class="player-meta">
        <span>@{{ playerItem.blogger_name || '-' }}</span>
        <el-divider direction="vertical" />
        <span>{{ platformLabel(playerItem.platform) }}</span>
        <el-divider direction="vertical" />
        <span v-if="playerItem.view_count != null">{{ formatCount(playerItem.view_count) }} 次播放</span>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onActivated, onMounted, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { openInNewTab } from '../utils/nav'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchVideoAITemplates,
  fetchTemplateStats,
  startVideoAITemplate,
  pauseVideoAITemplate,
  restartVideoAITemplate,
  resumeVideoAITemplate,
  deleteVideoAITemplate,
  batchPauseTemplates,
  batchRetryTemplates,
  batchRestartTemplates,
} from '../api/video_ai_templates'
import { fetchPipelineSettings, updatePipelineSettings } from '../api/settings'
import { isDuplicateRequestError } from '../api/http'
import { useAuth } from '../composables/useAuth'

const { isAdmin } = useAuth()

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const deleting = ref(null)
const actioning = ref(null)
const batchResuming = ref(false)
const batchPausing = ref(false)
const batchRestarting = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(Number(route.query.page) || 1)
const pageSize = ref(Number(route.query.page_size) || 20)
const jumpPage = ref(page.value)
const activeFilter = ref(route.query.status || null)
const templateStats = ref({})

const playerVisible = ref(false)
const playerItem = ref(null)
const batchPrimaryLoading = computed(() => batchPausing.value || batchResuming.value || batchRestarting.value)

// Config dialog state
const showConfig = ref(false)
const configTab = ref('step_imagegen')
const configLoading = ref(false)
const configSaving = ref(false)
// 「无CTA」/「有CTA」切换；textarea 根据该值动态绑定到 *_cta 或非 cta 字段
const configCtaMode = ref(false)
function promptKey(name) {
  return configCtaMode.value ? `${name}_cta` : name
}

const cfg = reactive({
  // 阶段2：穿搭识别
  outfit_select_model: 'gemini-2.5-flash-preview-05-20',
  outfit_select_prompt: '',
  outfit_select_temperature: 0.3,
  // 阶段3：单品理解
  outfit_detail_model: 'gemini-2.5-flash-preview-05-20',
  outfit_detail_prompt: '',
  outfit_detail_temperature: 0.3,
  // 阶段4：意图识别（JSON）
  intent_classify_model: 'gemini-2.5-flash-preview-05-20',
  intent_classify_prompt: '',
  intent_classify_temperature: 0.3,
  // 阶段5：视频理解（按 content_intent 分支，共用 model/temperature）
  understand_model: '',
  understand_temperature: 0.3,
  understand_prompt_beauty_show: '',
  understand_prompt_knowledge: '',
  understand_prompt_persona_story: '',
  understand_prompt_trend_meme: '',
  // 阶段6：单品生图
  product_imagegen_model: 'gemini-2.5-flash-preview-05-20',
  product_imagegen_prompt: '',
  product_imagegen_size: '1:1',
  product_imagegen_quality: '2K',
  // 阶段8：新造型图生成
  outfit_regen_model: 'gemini-2.5-flash-preview-05-20',
  outfit_regen_prompt: '',
  outfit_regen_size: '9:16',
  outfit_regen_quality: '2K',
  // 「有CTA」9 套提示词（与同名无 _cta 字段对应；textarea 通过 promptKey 动态绑定）
  outfit_select_prompt_cta: '',
  outfit_detail_prompt_cta: '',
  intent_classify_prompt_cta: '',
  understand_prompt_beauty_show_cta: '',
  understand_prompt_knowledge_cta: '',
  understand_prompt_persona_story_cta: '',
  understand_prompt_trend_meme_cta: '',
  product_imagegen_prompt_cta: '',
  outfit_regen_prompt_cta: '',
})

const hasJsonError = computed(() => false)

async function openConfig() {
  showConfig.value = true
  configTab.value = 'step_imagegen'
  configLoading.value = true
  try {
    const data = await fetchPipelineSettings()
    Object.assign(cfg, {
      outfit_select_model: data.outfit_select_model || 'gemini-2.5-flash-preview-05-20',
      outfit_select_prompt: data.outfit_select_prompt || '',
      outfit_select_temperature: data.outfit_select_temperature ?? 0.3,
      outfit_detail_model: data.outfit_detail_model || 'gemini-2.5-flash-preview-05-20',
      outfit_detail_prompt: data.outfit_detail_prompt || '',
      outfit_detail_temperature: data.outfit_detail_temperature ?? 0.3,
      intent_classify_model: data.intent_classify_model || 'gemini-2.5-flash-preview-05-20',
      intent_classify_prompt: data.intent_classify_prompt || '',
      intent_classify_temperature: data.intent_classify_temperature ?? 0.3,
      understand_model: data.understand_model || '',
      understand_temperature: data.understand_temperature ?? 0.3,
      understand_prompt_beauty_show: data.understand_prompt_beauty_show || '',
      understand_prompt_knowledge: data.understand_prompt_knowledge || '',
      understand_prompt_persona_story: data.understand_prompt_persona_story || '',
      understand_prompt_trend_meme: data.understand_prompt_trend_meme || '',
      product_imagegen_model: data.product_imagegen_model || 'gemini-2.5-flash-preview-05-20',
      product_imagegen_prompt: data.product_imagegen_prompt || '',
      product_imagegen_size: data.product_imagegen_size || '1:1',
      product_imagegen_quality: data.product_imagegen_quality || '2K',
      outfit_regen_model: data.outfit_regen_model || 'gemini-2.5-flash-preview-05-20',
      outfit_regen_prompt: data.outfit_regen_prompt || '',
      outfit_regen_size: data.outfit_regen_size || '9:16',
      outfit_regen_quality: data.outfit_regen_quality || '2K',
      // 「有CTA」9 套
      outfit_select_prompt_cta: data.outfit_select_prompt_cta || '',
      outfit_detail_prompt_cta: data.outfit_detail_prompt_cta || '',
      intent_classify_prompt_cta: data.intent_classify_prompt_cta || '',
      understand_prompt_beauty_show_cta: data.understand_prompt_beauty_show_cta || '',
      understand_prompt_knowledge_cta: data.understand_prompt_knowledge_cta || '',
      understand_prompt_persona_story_cta: data.understand_prompt_persona_story_cta || '',
      understand_prompt_trend_meme_cta: data.understand_prompt_trend_meme_cta || '',
      product_imagegen_prompt_cta: data.product_imagegen_prompt_cta || '',
      outfit_regen_prompt_cta: data.outfit_regen_prompt_cta || '',
    })
    configCtaMode.value = false   // 默认显示「无CTA」
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载配置失败')
  } finally {
    configLoading.value = false
  }
}

async function saveConfig() {
  if (hasJsonError.value) {
    ElMessage.error('请修正 JSON 格式错误后再保存')
    return
  }
  configSaving.value = true
  try {
    await updatePipelineSettings({
      understand_model: cfg.understand_model,
      understand_temperature: cfg.understand_temperature,
      understand_prompt_beauty_show: cfg.understand_prompt_beauty_show,
      understand_prompt_knowledge: cfg.understand_prompt_knowledge,
      understand_prompt_persona_story: cfg.understand_prompt_persona_story,
      understand_prompt_trend_meme: cfg.understand_prompt_trend_meme,
      intent_classify_model: cfg.intent_classify_model,
      intent_classify_prompt: cfg.intent_classify_prompt,
      intent_classify_temperature: cfg.intent_classify_temperature,
      outfit_select_model: cfg.outfit_select_model,
      outfit_select_prompt: cfg.outfit_select_prompt,
      outfit_select_temperature: cfg.outfit_select_temperature,
      outfit_detail_model: cfg.outfit_detail_model,
      outfit_detail_prompt: cfg.outfit_detail_prompt,
      outfit_detail_temperature: cfg.outfit_detail_temperature,
      product_imagegen_model: cfg.product_imagegen_model,
      product_imagegen_prompt: cfg.product_imagegen_prompt,
      product_imagegen_size: cfg.product_imagegen_size,
      product_imagegen_quality: cfg.product_imagegen_quality,
      outfit_regen_model: cfg.outfit_regen_model,
      outfit_regen_prompt: cfg.outfit_regen_prompt,
      outfit_regen_size: cfg.outfit_regen_size,
      outfit_regen_quality: cfg.outfit_regen_quality,
      // 「有CTA」9 套
      outfit_select_prompt_cta: cfg.outfit_select_prompt_cta,
      outfit_detail_prompt_cta: cfg.outfit_detail_prompt_cta,
      intent_classify_prompt_cta: cfg.intent_classify_prompt_cta,
      understand_prompt_beauty_show_cta: cfg.understand_prompt_beauty_show_cta,
      understand_prompt_knowledge_cta: cfg.understand_prompt_knowledge_cta,
      understand_prompt_persona_story_cta: cfg.understand_prompt_persona_story_cta,
      understand_prompt_trend_meme_cta: cfg.understand_prompt_trend_meme_cta,
      product_imagegen_prompt_cta: cfg.product_imagegen_prompt_cta,
      outfit_regen_prompt_cta: cfg.outfit_regen_prompt_cta,
    })
    ElMessage.success('配置已保存')
    showConfig.value = false
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    configSaving.value = false
  }
}

const startIdx = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const endIdx = computed(() => Math.min(page.value * pageSize.value, total.value))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const visiblePages = computed(() => {
  const n = totalPages.value
  const cur = page.value
  if (n <= 7) return Array.from({ length: n }, (_, i) => i + 1)
  const pages = []
  pages.push(1)
  if (cur > 3) pages.push('...')
  for (let p = Math.max(2, cur - 1); p <= Math.min(n - 1, cur + 1); p++) pages.push(p)
  if (cur < n - 2) pages.push('...')
  pages.push(n)
  return pages
})

function syncUrl() {
  const query = {}
  if (page.value > 1) query.page = String(page.value)
  if (pageSize.value !== 20) query.page_size = String(pageSize.value)
  if (activeFilter.value) query.status = activeFilter.value
  router.replace({ query })
}

function toggleFilter(status) {
  if (activeFilter.value === status) {
    activeFilter.value = null
  } else {
    activeFilter.value = status
  }
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
}

const STATUS_CONFIG = {
  pending: { label: '排队中', type: 'info' },
  imagegen: { label: '阶段1 抽帧上传', type: '', customColor: '#8b5cf6', bg: '#f5f3ff', border: '#ddd6fe' },
  outfit_selecting: { label: '阶段2 穿搭识别', type: '', customColor: '#ec4899', bg: '#fdf2f8', border: '#fbcfe8' },
  outfit_detailing: { label: '阶段3 单品理解', type: '', customColor: '#a855f7', bg: '#faf5ff', border: '#e9d5ff' },
  understanding: { label: '阶段4-5 视频理解', type: 'primary' },
  product_imagegen: { label: '阶段6 单品生图', type: '', customColor: '#f97316', bg: '#fff7ed', border: '#fed7aa' },
  outfit_regen: { label: '阶段7 造型重生', type: '', customColor: '#06b6d4', bg: '#ecfeff', border: '#a5f3fc' },
  splitting: { label: '拆分图片', type: '', customColor: '#ec4899', bg: '#fdf2f8', border: '#fbcfe8' }, // legacy
  face_removing: { label: '消除人脸', type: '', customColor: '#f59e0b', bg: '#fffbeb', border: '#fde68a' }, // legacy
  upscaling: { label: '图片超分', type: '', customColor: '#0ea5e9', bg: '#f0f9ff', border: '#bae6fd' }, // legacy
  paused: { label: '已暂停', type: 'info' },
  success: { label: '已完成', type: 'success' },
  fail: { label: '失败', type: 'danger' },
}

function statusType(status) {
  return STATUS_CONFIG[status]?.type ?? 'info'
}

function statusStyle(status) {
  const config = STATUS_CONFIG[status]
  if (config && config.customColor) {
    return {
      backgroundColor: config.bg,
      color: config.customColor,
      borderColor: config.border
    }
  }
  return {}
}

function statusLabel(status) {
  return STATUS_CONFIG[status]?.label || status
}

function canStart(item) {
  return item.process_status === 'fail'
}

function canPause(item) {
  return ['pending', 'understanding', 'imagegen', 'outfit_selecting', 'outfit_detailing', 'product_imagegen', 'outfit_regen'].includes(item.process_status)
}

function canResume(item) {
  return item.process_status === 'paused'
}

function platformLabel(p) {
  const labels = { youtube: 'YouTube', tiktok: 'TikTok' }
  return labels[p] || (p || '其他')
}

function formatCount(n) {
  if (n == null) return '-'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function formatViewCount(n) {
  return formatCount(n)
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

async function handleBatchCommand(command) {
  if (command === 'pause') {
    await handleBatchPause()
  } else if (command === 'retry') {
    await handleBatchRetry()
  } else if (command === 'restart') {
    await handleBatchRestart()
  }
}

async function handleBatchPause() {
  try {
    await ElMessageBox.confirm(
      '将暂停所有排队中和运行中的模板；已完成、失败的模板不会受影响。确认继续？',
      '一键暂停',
      { confirmButtonText: '确认暂停', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  batchPausing.value = true
  try {
    await batchPauseTemplates()
    ElMessage.success('已触发批量暂停')
    await loadData()
    await loadStats()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '批量暂停失败')
  } finally {
    batchPausing.value = false
  }
}

async function handleBatchRetry() {
  batchResuming.value = true
  try {
    await batchRetryTemplates()
    ElMessage.success('已触发批量重试，失败/暂停模板将断点续跑')
    await loadData()
    await loadStats()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '批量重试失败')
  } finally {
    batchResuming.value = false
  }
}

async function handleBatchRestart() {
  try {
    await ElMessageBox.confirm(
      '将对所有模板从头重跑，已完成阶段和中间产物会被清空。确认继续？',
      '一键重跑',
      { confirmButtonText: '确认重跑', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  batchRestarting.value = true
  try {
    await batchRestartTemplates()
    ElMessage.success('已触发批量重跑，后台处理中…')
    await loadData()
    await loadStats()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '批量重跑失败')
  } finally {
    batchRestarting.value = false
  }
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (activeFilter.value) params.status = activeFilter.value
    const data = await fetchVideoAITemplates(params)
    items.value = data.items || []
    total.value = data.total || 0
  } catch (err) {
    if (isDuplicateRequestError(err)) return
    ElMessage.error(err?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function goPage(p) {
  const target = Math.max(1, Math.min(p, totalPages.value))
  if (target === page.value) return
  page.value = target
  jumpPage.value = target
  syncUrl()
  loadData()
}

function handleSizeChange(val) {
  pageSize.value = val
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
}

function doJump() {
  const p = parseInt(jumpPage.value)
  if (!isNaN(p)) goPage(p)
}

function openPlayer(item) {
  playerItem.value = item
  playerVisible.value = true
}

function goToDetail(item) {
  syncUrl()
  openInNewTab(`/dashboard/video-ai-templates/${item.id}/edit`)
}

function goToEdit(item) {
  syncUrl()
  openInNewTab(`/dashboard/video-ai-templates/${item.id}/edit`)
}

async function handleStart(item) {
  actioning.value = item.id + '-start'
  try {
    await startVideoAITemplate(item.id)
    ElMessage.success('已开始处理')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '启动失败')
  } finally {
    actioning.value = null
  }
}

async function handlePause(item) {
  actioning.value = item.id + '-pause'
  try {
    await pauseVideoAITemplate(item.id)
    ElMessage.success('已暂停')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '暂停失败')
  } finally {
    actioning.value = null
  }
}

async function handleResume(item) {
  actioning.value = item.id + '-resume'
  try {
    await resumeVideoAITemplate(item.id)
    ElMessage.success('已继续处理')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '继续失败')
  } finally {
    actioning.value = null
  }
}

async function handleRestart(item) {
  actioning.value = item.id + '-restart'
  try {
    await restartVideoAITemplate(item.id)
    ElMessage.success('已从头重新处理')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '重跑失败')
  } finally {
    actioning.value = null
  }
}

async function handleDelete(item) {
  try {
    await ElMessageBox.confirm(
      `确定删除模板「${item.title}」？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        customClass: 'premium-delete-dialog',
      }
    )
  } catch { return }

  deleting.value = item.id
  try {
    await deleteVideoAITemplate(item.id)
    ElMessage.success('已删除')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = null
  }
}

async function loadStats() {
  try {
    templateStats.value = await fetchTemplateStats()
  } catch { /* ignore */ }
}

onMounted(() => {
  loadData()
  loadStats()
})

onActivated(() => {
  const q = route.query
  page.value = Number(q.page) || 1
  pageSize.value = Number(q.page_size) || 20
  activeFilter.value = q.status || null
  jumpPage.value = page.value
  loadData()
  loadStats()
})
</script>

<style scoped>
/* Page layout */
.vai-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
}

.vai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}

.vai-title {
  font-size: 26px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.03em;
  margin: 0;
}

.vai-header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.vai-config-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  border: 1px solid #c7d2fe;
  color: #4338ca;
  background: #eef2ff;
}

.vai-config-btn:hover {
  background: #e0e7ff;
  border-color: #6366f1;
}

.vai-retry-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  border: 1px solid #fed7aa;
  color: #c2410c;
  background: #fff7ed;
}

.vai-retry-btn:hover {
  background: #ffedd5;
  border-color: #fb923c;
}

.vai-batch-btn {
  display: flex;
  align-items: center;
  font-weight: 700;
  height: 40px;
  border-radius: 10px;
  padding: 0 16px;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  background: #eff6ff;
}

.vai-batch-btn:hover,
.vai-batch-btn:focus {
  background: #dbeafe;
  border-color: #60a5fa;
  color: #1d4ed8;
}

.vai-menu-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 96px;
  font-weight: 700;
}

.vai-menu-pause {
  color: #d97706;
}

.vai-menu-retry {
  color: #2563eb;
}

.vai-menu-restart {
  color: #dc2626;
}

.vai-add-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
}

/* Config dialog */
.cfg-body {
  min-height: 320px;
}

.cfg-hint-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6366f1;
  background: #eef2ff;
  border-radius: 8px;
  padding: 8px 14px;
  margin-bottom: 14px;
}

.cfg-hint-bar a {
  color: #4f46e5;
  font-weight: 600;
  text-decoration: underline;
}

.cfg-tabs {
  border-radius: 10px;
  overflow: hidden;
}

.cfg-step-desc {
  font-size: 13px;
  color: #64748b;
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 20px;
  border-left: 3px solid #6366f1;
}

.cfg-form {
  padding-top: 4px;
}

.cfg-field-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  line-height: 1.4;
}

.cfg-field-hint code {
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: monospace;
  color: #6366f1;
}

.cfg-code-input :deep(textarea) {
  font-family: 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.cfg-json-invalid :deep(.el-textarea__inner) {
  border-color: #f56565 !important;
  box-shadow: 0 0 0 2px rgba(245, 101, 101, 0.15) !important;
}

.cfg-json-error-msg {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #dc2626;
  margin-top: 5px;
  font-family: 'Menlo', 'Consolas', monospace;
}

.cfg-json-ok-msg {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #16a34a;
  margin-top: 5px;
}

/* Step 3 job flow diagram */
.cfg-job-flow {
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  padding: 16px 20px;
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cfg-job-step {
  display: flex;
  align-items: center;
  gap: 12px;
}

.cfg-job-step-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #6366f1;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cfg-job-step-text {
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.cfg-job-step-text code {
  background: #e0e7ff;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: monospace;
  color: #4338ca;
  font-size: 11px;
}

.cfg-job-arrow {
  font-size: 16px;
  color: #94a3b8;
  padding-left: 8px;
  line-height: 1;
}

/* Stats row */
.vai-stats {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 14px;
  margin-bottom: 28px;
}

.vai-stat-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
  cursor: pointer;
  transition: all .2s;
}

.vai-stat-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.vai-stat-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: #94a3b8;
}

.vai-stat-value {
  font-size: 30px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
  margin-bottom: 5px;
  letter-spacing: -0.03em;
}

.vai-stat-sub {
  font-size: 11px;
  color: #94a3b8;
  font-family: monospace;
}

.vai-stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,.08);
}

.vai-stat-active {
  background: var(--stat-bg) !important;
  border-color: var(--stat-color) !important;
  box-shadow: 0 0 0 2px var(--stat-bg), 0 0 0 4px var(--stat-color) !important;
}

/* Card grid */
.vai-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 28px;
}

/* Template card */
.vt-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,.05);
  transition: box-shadow 0.2s, transform 0.2s;
  cursor: pointer;
  display: flex;
  flex-direction: column;
}

.vt-card:hover {
  box-shadow: 0 8px 24px rgba(0,0,0,.1);
  transform: translateY(-2px);
}

.vt-add {
  border: 2px dashed #c7d2fe;
  background: #fafbff;
  min-height: 300px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vt-add:hover {
  border-color: #6366f1;
  background: #eef2ff;
  transform: none;
  box-shadow: none;
}

.vt-add-inner {
  text-align: center;
}

.vt-add-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: #eef2ff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 12px;
  transition: background 0.2s;
}

.vt-add:hover .vt-add-icon {
  background: #c7d2fe;
}

.vt-add-title {
  font-size: 16px;
  font-weight: 700;
  color: #3730a3;
  margin-bottom: 4px;
}

.vt-add-sub {
  font-size: 13px;
  color: #818cf8;
}

/* Header */
.vt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid #f1f5f9;
}

.vt-status-tag {
  font-weight: 600;
  font-size: 11px;
}

.vt-actions {
  display: flex;
  gap: 5px;
}

.vt-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 9px;
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
  white-space: nowrap;
  line-height: 1.4;
}

.vt-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.vt-action-retry {
  background: #fef2f2;
  color: #dc2626;
  border-color: #fecaca;
}
.vt-action-retry:hover:not(:disabled) {
  background: #fee2e2;
  border-color: #f87171;
}

.vt-action-resume {
  background: #f0fdf4;
  color: #16a34a;
  border-color: #bbf7d0;
}
.vt-action-resume:hover:not(:disabled) {
  background: #dcfce7;
  border-color: #4ade80;
}

.vt-action-restart {
  background: #f8fafc;
  color: #475569;
  border-color: #e2e8f0;
}
.vt-action-restart:hover:not(:disabled) {
  background: #f1f5f9;
  border-color: #94a3b8;
}

.vt-action-pause {
  background: #fffbeb;
  color: #d97706;
  border-color: #fde68a;
}
.vt-action-pause:hover:not(:disabled) {
  background: #fef3c7;
  border-color: #fbbf24;
}

.vt-spin {
  animation: vt-spin 0.8s linear infinite;
}

@keyframes vt-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Video section */
.vt-video-section {
  position: relative;
  aspect-ratio: 16/9;
  overflow: hidden;
  background: #0f172a;
}

.vt-thumb {
  width: 100%;
  height: 100%;
  position: relative;
}

.vt-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.3s;
}

.vt-card:hover .vt-thumb-img {
  transform: scale(1.04);
}

.vt-thumb-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  pointer-events: none;
}

.vt-card:hover .vt-thumb-overlay {
  background: rgba(0,0,0,0.35);
}

.vt-play-btn {
  opacity: 0;
  transform: scale(0.8);
  transition: opacity 0.2s, transform 0.2s;
  background: rgba(255,255,255,0.15);
  border-radius: 50%;
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}

.vt-card:hover .vt-play-btn {
  opacity: 1;
  transform: scale(1);
}

.vt-thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
}

.vt-platform-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  backdrop-filter: blur(4px);
}

.vt-owner-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  background: #f3e8ff;
  color: #9333ea;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  letter-spacing: .03em;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Content */
.vt-content {
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.vt-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
}

.vt-desc {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}

.vt-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.vt-tag-chip {
  --vt-tag-color: #6366f1;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--vt-tag-color) 12%, white);
  border: 1px solid color-mix(in srgb, var(--vt-tag-color) 22%, white);
  color: color-mix(in srgb, var(--vt-tag-color) 78%, #111827);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.vt-tag-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--vt-tag-color);
  flex: 0 0 auto;
}

.vt-error {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: #fef2f2;
  border-radius: 8px;
  color: #dc2626;
  font-size: 12px;
  margin-bottom: 12px;
}

.vt-source-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 12px;
  color: #64748b;
}

.vt-stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.vt-meta {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #94a3b8;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.vt-video-info {
  font-weight: 500;
  color: #64748b;
}

.vt-owner {
  font-size: 11px;
  color: #9333ea;
  background: #f3e8ff;
  border-radius: 4px;
  padding: 1px 6px;
}

/* Footer */
.vai-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0 8px;
  border-top: 1px solid #f1f5f9;
}

.vai-pagination-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.vai-count-text {
  font-size: 13px;
  color: #94a3b8;
}

.vai-simple-select {
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  padding: 0 4px;
}

.vai-simple-select:hover {
  color: #64748b;
}

.vai-pagination {
  display: flex;
  gap: 8px;
}

.pg-btn {
  font-size: 13px;
  font-weight: 500;
  padding: 7px 16px;
  border-radius: 9px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
}

.pg-btn:hover:not(:disabled) {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.pg-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pg-num.active {
  background: #6366f1;
  color: #fff;
  border-color: #6366f1;
}

.pg-num {
  min-width: 36px;
  padding: 7px 10px;
}

.pg-ellipsis {
  display: inline-flex;
  align-items: center;
  padding: 7px 4px;
  color: #94a3b8;
  font-size: 14px;
}

.pg-jump-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #64748b;
  margin-left: 4px;
}

.pg-jump-input {
  width: 52px;
  padding: 6px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  text-align: center;
  outline: none;
  color: #475569;
}

.pg-jump-input:focus {
  border-color: #6366f1;
}

.pg-jump-go {
  padding: 7px 12px;
}

/* ── Player dialog ── */
.player-wrap {
  background: #000;
  border-radius: 10px;
  overflow: hidden;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.player-video {
  width: 100%;
  max-height: 460px;
  display: block;
}

.player-nourl {
  padding: 40px;
  text-align: center;
  background: #fff;
  width: 100%;
}

.player-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #64748b;
  margin-top: 14px;
  padding: 0 2px;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .vai-grid { grid-template-columns: 1fr; }
  .vai-header { flex-direction: column; gap: 12px; align-items: stretch; }
  .vai-header-actions { flex-wrap: wrap; }
  .vt-actions { flex-wrap: wrap; }
}

/* ── Custom Dialog ── */
.vt-dialog-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(4px);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: fadeIn 0.2s ease;
}

.vt-dialog-content {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.1), 0 0 0 1px rgba(0,0,0,0.05);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  animation: dialogSlideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
  transition: box-shadow 0.2s;
}

/* 有CTA 模式：弹窗整体淡淡的 amber 色调，与无CTA（默认白）区分 */
.vt-dialog-content.vt-cta-mode {
  box-shadow: 0 20px 40px rgba(0,0,0,0.1), 0 0 0 2px #fcd34d;
}
.vt-dialog-content.vt-cta-mode .vt-dialog-header {
  background: linear-gradient(180deg, #fffbeb 0%, #fff 100%);
  border-bottom-color: #fde68a;
}
.vt-dialog-content.vt-cta-mode .vt-dialog-body {
  background: #fffdf6;
}

.vt-dialog-header {
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #f1f5f9;
}

.vt-cfg-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.vt-cta-toggle {
  display: inline-flex;
  background: #f1f5f9;
  border-radius: 999px;
  padding: 3px;
  gap: 2px;
}

.vt-cta-toggle.is-cta {
  background: #fef3c7;
}

.vt-cta-toggle-btn {
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 700;
  padding: 5px 14px;
  border-radius: 999px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.18s;
}

.vt-cta-toggle-btn.active {
  background: #fff;
  color: #0f172a;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.vt-cta-toggle.is-cta .vt-cta-toggle-btn.active {
  background: #b45309;
  color: #fffbeb;
}

.vt-dialog-title {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
}

.vt-dialog-close {
  background: transparent;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.vt-dialog-close:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.vt-dialog-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

.vt-dialog-footer {
  padding: 16px 24px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  background: #fafbfc;
}

.vt-btn {
  height: 40px;
  padding: 0 18px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.vt-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.vt-btn-cancel {
  background: #fff;
  border-color: #e2e8f0;
  color: #475569;
}

.vt-btn-cancel:hover:not(:disabled) {
  border-color: #cbd5e1;
  background: #f8fafc;
  color: #0f172a;
}

.vt-btn-primary {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  box-shadow: 0 2px 4px rgba(99, 102, 241, 0.2);
}

.vt-btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.vt-btn-primary.is-loading {
  opacity: 0.8;
  cursor: wait;
}

/* ── Custom Tabs ── */
.vt-tabs {
  display: flex;
  gap: 4px;
  background: #f1f5f9;
  padding: 4px;
  border-radius: 10px;
  margin-bottom: 20px;
  overflow-x: auto;
}

.vt-tab-btn {
  flex: 1;
  background: transparent;
  border: none;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.vt-tab-btn:hover {
  color: #0f172a;
}

.vt-tab-active {
  background: #fff;
  color: #4f46e5;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

/* ── Custom Forms ── */
.vt-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.vt-form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.vt-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.vt-input, .vt-textarea, .vt-select {
  width: 100%;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 14px;
  color: #0f172a;
  transition: all 0.2s;
  outline: none;
  font-family: inherit;
}

.vt-input:focus, .vt-textarea:focus, .vt-select:focus {
  border-color: #818cf8;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.vt-input::placeholder, .vt-textarea::placeholder {
  color: #94a3b8;
}

.vt-textarea {
  resize: vertical;
  min-height: 80px;
  line-height: 1.5;
}

.vt-input-error {
  border-color: #f56565 !important;
  box-shadow: 0 0 0 3px rgba(245, 101, 101, 0.1) !important;
}

.vt-select-wrapper {
  position: relative;
}

.vt-select {
  -webkit-appearance: none;
  appearance: none;
  padding-right: 36px;
  cursor: pointer;
}

.vt-select-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  color: #64748b;
  display: flex;
  align-items: center;
}

.vt-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
}

.vt-radio-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #475569;
  cursor: pointer;
  user-select: none;
}

.vt-radio-input {
  display: none;
}

.vt-radio-circle {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 1.5px solid #cbd5e1;
  background: #fff;
  position: relative;
  transition: all 0.2s;
}

.vt-radio-input:checked + .vt-radio-circle {
  border-color: #6366f1;
}

.vt-radio-input:checked + .vt-radio-circle::after {
  content: '';
  position: absolute;
  inset: 4px;
  background: #6366f1;
  border-radius: 50%;
}

.vt-range {
  -webkit-appearance: none;
  width: 100%;
  height: 6px;
  background: #e2e8f0;
  border-radius: 4px;
  outline: none;
}

.vt-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #6366f1;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  transition: transform 0.1s;
}

.vt-range::-webkit-slider-thumb:hover {
  transform: scale(1.1);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes dialogSlideIn {
  from { opacity: 0; transform: translateY(10px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
</style>
