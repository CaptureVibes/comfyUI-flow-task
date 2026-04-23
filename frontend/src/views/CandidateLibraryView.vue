<template>
  <div class="cl-page">
    <!-- 页头 -->
    <div class="cl-header">
      <h1 class="cl-title">候选库</h1>
      <div class="cl-header-actions">
        <button class="cl-btn cl-btn-config" @click="openConfigDialog" title="候选库配置">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          搜索配置
        </button>
        <button class="cl-btn cl-btn-schedule" :class="{ active: scheduleEnabled }" @click="openScheduleDialog">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          {{ scheduleEnabled ? '定时抓取中' : '定时抓取' }}
        </button>
        <button class="cl-btn cl-btn-primary" @click="openSearchDialog">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          搜索候选视频
        </button>
      </div>
    </div>

    <!-- 主体：左侧目录树 + 右侧内容 -->
    <div class="cl-body">
      <!-- 左侧目录树 -->
      <div class="cl-tree-panel" :class="{ collapsed: treePanelCollapsed }">
        <div class="cl-tree-header">
          <span v-if="!treePanelCollapsed" class="cl-tree-title">关键词目录</span>
          <button class="cl-tree-toggle" :title="treePanelCollapsed ? '展开目录' : '收起目录'" @click="treePanelCollapsed = !treePanelCollapsed">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <polyline v-if="treePanelCollapsed" points="9 18 15 12 9 6"/>
              <polyline v-else points="15 18 9 12 15 6"/>
            </svg>
          </button>
        </div>
        <div v-show="!treePanelCollapsed" class="cl-tree-search">
          <svg class="cl-tree-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            v-model="treeSearchQuery"
            class="cl-tree-search-input"
            placeholder="搜索关键词..."
            @input="onTreeSearch"
          />
          <button v-if="treeSearchQuery" class="cl-tree-search-clear" @click="treeSearchQuery = ''">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div v-show="!treePanelCollapsed" class="cl-tree-content">
          <!-- 全部 -->
          <div
            v-show="!treeSearchQuery"
            class="cl-tree-item cl-tree-all"
            :class="{ active: !filterKeywordId }"
            @click="filterKeywordId = ''; page = 1; loadVideos()"
          >全部关键词</div>
          <!-- Topics -->
          <template v-for="topic in filteredTree" :key="topic.id">
            <div class="cl-tree-topic">
              <div
                class="cl-tree-item cl-tree-topic-label"
                :class="{ expanded: expandedTopics[topic.id] }"
                @click="toggleTopic(topic.id)"
              >
                <svg class="cl-tree-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                <span v-html="highlightMatch(topic.name)"></span>
              </div>
              <div v-show="expandedTopics[topic.id]" class="cl-tree-children">
                <template v-for="mk in topic.motherKeywords" :key="mk.id">
                  <div class="cl-tree-mk">
                    <div
                      class="cl-tree-item cl-tree-mk-label"
                      :class="{ expanded: expandedMks[mk.id] }"
                      @click="toggleMk(mk.id)"
                    >
                      <svg class="cl-tree-arrow" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                      <span v-html="highlightMatch(mk.name)"></span>
                    </div>
                    <div v-show="expandedMks[mk.id]" class="cl-tree-children">
                      <div
                        v-for="kw in mk.keywords"
                        :key="kw.id"
                        class="cl-tree-item cl-tree-kw-label"
                        :class="{ active: filterKeywordId === kw.id }"
                        @click="filterKeywordId = kw.id; page = 1; loadVideos()"
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/></svg>
                        <span v-html="highlightMatch(kw.keyword)"></span>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </template>
          <div v-if="treeSearchQuery && filteredTree.length === 0" class="cl-tree-empty">无匹配结果</div>
        </div>
      </div>

      <!-- 右侧内容 -->
      <div class="cl-main">
        <!-- Tab 切换 -->
        <div class="cl-tabs">
          <button
            v-for="tab in TABS"
            :key="tab.key"
            class="cl-tab"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key; page = 1; filterStatus = ''; selectedIds = new Set(); loadVideos(); loadTabCounts()"
          >
            {{ tab.label }}
            <span v-if="tabCounts[tab.key]" class="cl-tab-count">{{ tabCounts[tab.key] }}</span>
          </button>
        </div>

        <!-- 当前筛选面包屑 -->
        <div v-if="filterKeywordId" class="cl-breadcrumb">
          <span class="cl-breadcrumb-text">{{ currentFilterPath }}</span>
          <button class="cl-breadcrumb-clear" @click="filterKeywordId = ''; page = 1; loadVideos()">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            清除筛选
          </button>
        </div>

        <!-- 状态筛选（仅候选库 tab 显示） -->
        <div v-if="isCandidateTab" class="cl-status-filter">
          <button
            v-for="s in STATUS_FILTERS"
            :key="s.value"
            class="cl-status-chip"
            :class="{ active: filterStatus === s.value }"
            :style="filterStatus === s.value ? { color: s.color, borderColor: s.color, background: s.bg } : {}"
            @click="filterStatus = filterStatus === s.value ? '' : s.value; page = 1; loadVideos()"
          >{{ s.label }}</button>
        </div>

        <!-- 批量操作栏（仅候选库 tab 显示） -->
        <div v-if="isCandidateTab" class="cl-batch-bar">
          <label class="cl-check-all">
            <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" />
            全选
          </label>
          <template v-if="selectedIds.size > 0">
            <span class="cl-selected-count">已选 {{ selectedIds.size }} 个</span>
            <button class="cl-btn cl-btn-ai" @click="handleBatchAIReview">
              AI审核
            </button>
            <button class="cl-btn cl-btn-import" :disabled="batchImporting" @click="handleBatchImport">
              <span v-if="batchImporting" class="btn-spin"></span>
              导入到库
            </button>
            <button class="cl-btn cl-btn-deselect" @click="selectedIds = new Set()">取消选择</button>
          </template>
          <div class="cl-batch-bar-spacer"></div>
          <button class="cl-btn cl-btn-review-all" :disabled="pendingCount === 0" @click="handleBulkAIReviewAll">
            全量AI审核 ({{ pendingCount }})
          </button>
          <button class="cl-btn cl-btn-import-all" :disabled="importingAll || importableCount === 0" @click="handleImportAll">
            <span v-if="importingAll" class="btn-spin"></span>
            一键导入全部 ({{ importableCount }})
          </button>
        </div>

        <!-- 视频列表 -->
        <div v-loading="loading" class="cl-grid">
          <div
            v-for="video in videos"
            :key="video.id"
            class="cl-card"
            :class="{ selected: selectedIds.has(video.id) }"
            @click="isCandidateTab && toggleSelect(video.id)"
          >
            <!-- 复选框（仅候选库 tab） -->
            <label v-if="isCandidateTab" class="cl-card-checkbox" @click.stop>
              <input type="checkbox" :checked="selectedIds.has(video.id)" @change="toggleSelect(video.id)" />
            </label>
            <div class="cl-card-cover">
              <img v-if="video.cdn_cover_url || video.cover_url" :src="video.cdn_cover_url || video.cover_url" class="cl-cover-img" />
              <div v-else class="cl-cover-placeholder">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              </div>
              <!-- AI 状态徽章（仅候选库 tab） -->
              <div
                v-if="isCandidateTab"
                class="cl-status-badge"
                :class="{ 'cl-status-badge--error': video.status === 'ai_failed' && video.ai_error }"
                :style="{ color: statusBadge(video.status).color, background: statusBadge(video.status).bg }"
              >
                {{ statusBadge(video.status).label }}
                <span v-if="video.status === 'ai_failed' && video.ai_error" class="cl-error-tooltip">{{ video.ai_error }}</span>
              </div>
              <a v-if="video.video_url" :href="video.video_url" target="_blank" class="cl-card-link" title="在 TikTok 打开" @click.stop>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>
            <div class="cl-card-info">
              <div class="cl-card-blogger">
                <span class="cl-blogger-name">@{{ video.blogger_unique_id }}</span>
                <span v-if="video.blogger_follower_count" class="cl-follower-count">
                  {{ formatCount(video.blogger_follower_count) }} 粉丝
                </span>
              </div>
              <div v-if="video.video_title" class="cl-card-title" :title="video.video_title">{{ video.video_title }}</div>
              <div class="cl-card-meta">
                <span v-if="video.duration">{{ video.duration }}s</span>
                <span v-if="video.play_count">▶ {{ formatCount(video.play_count) }}</span>
                <span v-if="video.like_count">♥ {{ formatCount(video.like_count) }}</span>
              </div>
              <div class="cl-card-keyword">{{ video.keyword_text }}</div>
            </div>
            <button class="cl-card-del" title="删除" @click.stop="handleDelete(video)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>

        <el-empty v-if="!loading && videos.length === 0" description="暂无候选视频，点击「搜索候选视频」开始" :image-size="80" />

        <!-- 分页 -->
        <div v-if="total > 0" class="cl-footer">
          <div class="cl-pagination-left">
            <span class="cl-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
            <select v-model="pageSize" @change="handleSizeChange(pageSize)" class="cl-size-select">
              <option :value="20">20</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
              <option :value="200">200</option>
            </select>
          </div>
          <div class="cl-pagination">
            <button class="pg-btn" :disabled="page <= 1" @click="goPage(page - 1)">← 上一页</button>
            <template v-for="p in visiblePages" :key="p">
              <span v-if="p === '...'" class="pg-ellipsis">…</span>
              <button v-else class="pg-btn pg-num" :class="{ active: p === page }" @click="goPage(p)">{{ p }}</button>
            </template>
            <button class="pg-btn" :disabled="endIdx >= total" @click="goPage(page + 1)">下一页 →</button>
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
      </div>
    </div>

    <!-- 配置对话框 -->
    <el-dialog v-model="showConfigDialog" title="候选库搜索配置" width="580px" align-center destroy-on-close @open="loadConfig">
      <div v-loading="loadingConfig" class="config-form">
        <div class="cf-row">
          <label class="cf-label">最多收集博主数</label>
          <el-input-number v-model="configForm.candidate_max_bloggers" :min="1" :max="200" />
          <span class="cf-hint">初始搜索阶段最多收集多少个唯一博主（默认 20）</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">独享门槛（视频数）</label>
          <el-input-number v-model="configForm.candidate_exclusive_threshold" :min="1" :max="500" />
          <span class="cf-hint">博主符合条件视频数 ≥ 此值则为独享，否则共享（默认 10）</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">每博主最大搜索视频数</label>
          <el-input-number v-model="configForm.candidate_max_videos_per_blogger" :min="10" :max="500" />
          <span class="cf-hint">精搜时最多获取多少条视频（默认 100）</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">视频时长过滤上限（秒）</label>
          <el-input-number v-model="configForm.candidate_max_duration_seconds" :min="1" :max="600" />
          <span class="cf-hint">超过此时长的视频将被过滤（默认 30s）</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">限流重试等待（秒）</label>
          <el-input-number v-model="configForm.candidate_retry_delay_seconds" :min="1" :max="60" />
          <span class="cf-hint">遇到 RapidAPI 429 限流时等待秒数后重试（默认 5s）</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">最低播放量（万）</label>
          <el-input-number v-model="minPlayCountWan" :min="0" :max="10000" :step="1" :precision="1" />
          <span class="cf-hint">播放量低于此值的视频将被过滤（0 = 不限制，单位：万）</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">发布日期限制</label>
          <el-date-picker
            v-model="configForm.candidate_publish_after_date"
            type="date"
            placeholder="不限制"
            value-format="YYYY-MM-DD"
            clearable
            style="width: 100%;"
          />
          <span class="cf-hint">只保留该日期之后发布的视频（留空 = 不限制）</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">共享模板保留数量</label>
          <el-input-number v-model="configForm.candidate_shared_top_n" :min="1" :max="1000" />
          <span class="cf-hint">共享结果按播放量从高到低只保留前 N 条（默认 50）</span>
        </div>
        <div class="cf-row">
          <label class="cf-label">关键词间隔（min）</label>
          <el-input-number v-model="configForm.candidate_search_interval_minutes" :min="0" :max="1440" />
          <span class="cf-hint">每处理完一个关键词后等待的时间，0 = 不间隔</span>
        </div>

        <div class="cf-divider"></div>
        <h4 class="cf-section-title">AI 审核配置</h4>

        <div class="cf-row">
          <label class="cf-label">审核模型</label>
          <el-input v-model="configForm.candidate_ai_review_model" placeholder="gemini-3.1-pro-preview" />
        </div>
        <div class="cf-row">
          <label class="cf-label">审核提示词</label>
          <el-input
            v-model="configForm.candidate_ai_review_prompt"
            type="textarea"
            :rows="5"
            placeholder="请输入审核提示词，系统会自动在末尾追加 JSON 输出要求..."
          />
          <span class="cf-hint">AI 将根据此提示词判断视频是否通过审核（输出 pass: true/false）。提示词中可使用 <code>{keyword}</code> 占位符，审核时将自动替换为该视频对应的关键词。</span>
        </div>
      </div>
      <template #footer>
        <button class="dlg-btn-cancel" @click="showConfigDialog = false">取消</button>
        <button class="dlg-btn-primary" :disabled="savingConfig" @click="handleSaveConfig">
          <span v-if="savingConfig" class="btn-spin"></span>
          保存配置
        </button>
      </template>
    </el-dialog>

    <!-- 搜索对话框 -->
    <el-dialog v-model="showSearchDialog" title="搜索候选视频" width="480px" align-center destroy-on-close>
      <div class="search-form">
        <div class="sf-row">
          <label class="sf-label">搜索方式</label>
          <div class="sf-radio-group">
            <label class="sf-radio">
              <input v-model="searchMode" type="radio" value="keyword" />
              从关键词库选择
            </label>
            <label class="sf-radio">
              <input v-model="searchMode" type="radio" value="manual" />
              手动输入关键词
            </label>
          </div>
        </div>

        <div v-if="searchMode === 'keyword'" class="sf-row">
          <label class="sf-label">选择关键词</label>
          <select v-model="searchKeywordId" class="cl-select">
            <option value="">请选择关键词...</option>
            <option v-for="kw in allKeywords" :key="kw.id" :value="kw.id">
              {{ kw.mother_keyword }} / {{ kw.keyword }}
            </option>
          </select>
          <div v-if="searchKeywordId" class="sf-preview">
            将搜索：<strong>{{ selectedKeywordText }}</strong>
          </div>
        </div>

        <div v-else class="sf-row">
          <label class="sf-label">关键词</label>
          <input v-model="searchManualKeyword" class="sf-input" placeholder="请输入关键词..." />
        </div>

        <div class="sf-tip">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          搜索将在后台运行，完成后刷新页面查看结果。搜索参数可在「设置 → 候选库配置」中调整。
        </div>
      </div>
      <template #footer>
        <button class="dlg-btn-cancel" @click="showSearchDialog = false">取消</button>
        <button class="dlg-btn-primary" :disabled="!canSearch || searching" @click="handleSearch">
          <span v-if="searching" class="btn-spin"></span>
          开始搜索
        </button>
      </template>
    </el-dialog>

    <!-- 定时抓取配置 dialog -->
    <el-dialog v-model="showScheduleDialog" title="定时抓取配置" width="520px" align-center destroy-on-close>
      <div class="config-form">
        <div class="cf-row">
          <label class="cf-label">
            <el-switch v-model="scheduleForm.candidate_schedule_enabled" size="small" style="margin-right: 8px;" />
            启用定时抓取
          </label>
          <span class="cf-hint">启用后将按 Cron 表达式自动对已有关键词重新搜索入库</span>
        </div>
        <template v-if="scheduleForm.candidate_schedule_enabled">
          <div class="cf-row">
            <label class="cf-label">快捷选择</label>
            <div class="cl-cron-presets">
              <button
                v-for="p in CRON_PRESETS"
                :key="p.cron"
                type="button"
                class="cl-preset-btn"
                :class="{ active: scheduleForm.candidate_schedule_cron === p.cron }"
                @click="scheduleForm.candidate_schedule_cron = p.cron"
              >{{ p.label }}</button>
            </div>
          </div>
          <div class="cf-row">
            <label class="cf-label">Cron 表达式</label>
            <el-input v-model="scheduleForm.candidate_schedule_cron" placeholder="0 10 * * *" style="font-family:monospace" />
            <span class="cf-hint">格式：分 时 日 月 周（北京时间）。例：每天10点 = 0 10 * * *</span>
          </div>
          <div v-if="schedulePreview" class="sf-tip">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            {{ schedulePreview }}
          </div>
        </template>
      </div>
      <template #footer>
        <button class="dlg-btn-cancel" @click="showScheduleDialog = false">取消</button>
        <button class="dlg-btn-primary" :disabled="savingSchedule" @click="handleSaveSchedule">
          <span v-if="savingSchedule" class="btn-spin"></span>
          保存
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchCandidateVideos, triggerCandidateSearch, deleteCandidateVideo, batchAIReview, batchImportCandidates, bulkAIReviewAll } from '../api/candidates'
import { fetchAllKeywords } from '../api/topics'
import { fetchCandidateConfig, updateCandidateConfig } from '../api/settings'

// tab.key 格式: "candidate_shared" | "shared" | "candidate_exclusive" | "exclusive"
// candidate_ 前缀表示候选库（未导入），无前缀表示已导入库
const TABS = [
  { key: 'candidate_shared',    label: '候选共享库' },
  { key: 'shared',              label: '共享库' },
  { key: 'candidate_exclusive', label: '候选独享库' },
  { key: 'exclusive',           label: '独享库' },
]

// 从 tab key 解析出 template_type 和 imported 参数
function parseTabKey(key) {
  if (key.startsWith('candidate_')) {
    return { template_type: key.replace('candidate_', ''), imported: false }
  }
  return { template_type: key, imported: true }
}

const activeTab = ref('candidate_shared')
const loading = ref(false)
const videos = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterKeywordId = ref('')
const filterStatus = ref('')
const allKeywords = ref([])

// 目录树面板折叠
const treePanelCollapsed = ref(false)

// 目录树展开状态
const expandedTopics = reactive({})
const expandedMks = reactive({})

// 将扁平关键词列表构建为 Topic → MotherKeyword → Keyword 树
const keywordTree = computed(() => {
  const topicMap = new Map()
  for (const kw of allKeywords.value) {
    if (!topicMap.has(kw.topic_id)) {
      topicMap.set(kw.topic_id, { id: kw.topic_id, name: kw.topic_name, mkMap: new Map() })
    }
    const topic = topicMap.get(kw.topic_id)
    if (!topic.mkMap.has(kw.mother_keyword_id)) {
      topic.mkMap.set(kw.mother_keyword_id, { id: kw.mother_keyword_id, name: kw.mother_keyword, keywords: [] })
    }
    topic.mkMap.get(kw.mother_keyword_id).keywords.push({ id: kw.id, keyword: kw.keyword })
  }
  return Array.from(topicMap.values()).map(t => ({
    id: t.id,
    name: t.name,
    motherKeywords: Array.from(t.mkMap.values()),
  }))
})

// 当前筛选路径面包屑
const currentFilterPath = computed(() => {
  if (!filterKeywordId.value) return ''
  const kw = allKeywords.value.find(k => k.id === filterKeywordId.value)
  if (!kw) return ''
  return `${kw.topic_name} / ${kw.mother_keyword} / ${kw.keyword}`
})

// 目录树搜索
const treeSearchQuery = ref('')

// 根据搜索词过滤树：匹配关键词/母题词/主题词名称，自动展开匹配路径
const filteredTree = computed(() => {
  const q = treeSearchQuery.value.trim().toLowerCase()
  if (!q) return keywordTree.value

  const result = []
  for (const topic of keywordTree.value) {
    const topicMatch = topic.name.toLowerCase().includes(q)
    const filteredMks = []
    for (const mk of topic.motherKeywords) {
      const mkMatch = mk.name.toLowerCase().includes(q)
      const filteredKws = mk.keywords.filter(kw => kw.keyword.toLowerCase().includes(q))
      // 包含：主题词匹配（显示全部）、母题词匹配（显示该母题词全部关键词）、或有匹配的关键词
      if (topicMatch || mkMatch || filteredKws.length > 0) {
        filteredMks.push({
          ...mk,
          keywords: (topicMatch || mkMatch) ? mk.keywords : filteredKws,
        })
      }
    }
    if (filteredMks.length > 0) {
      result.push({ ...topic, motherKeywords: filteredMks })
    }
  }
  return result
})

function onTreeSearch() {
  const q = treeSearchQuery.value.trim().toLowerCase()
  if (!q) return
  // 自动展开所有匹配路径
  for (const topic of filteredTree.value) {
    expandedTopics[topic.id] = true
    for (const mk of topic.motherKeywords) {
      expandedMks[mk.id] = true
    }
  }
}

function highlightMatch(text) {
  const q = treeSearchQuery.value.trim()
  if (!q) return text
  const idx = text.toLowerCase().indexOf(q.toLowerCase())
  if (idx === -1) return text
  const before = text.slice(0, idx)
  const match = text.slice(idx, idx + q.length)
  const after = text.slice(idx + q.length)
  return `${before}<mark class="cl-tree-hl">${match}</mark>${after}`
}

function toggleTopic(id) {
  expandedTopics[id] = !expandedTopics[id]
}
function toggleMk(id) {
  expandedMks[id] = !expandedMks[id]
}
const tabCounts = ref({ candidate_shared: 0, shared: 0, candidate_exclusive: 0, exclusive: 0 })

// 多选状态
const selectedIds = ref(new Set())

const batchImporting = ref(false)
const importingAll = ref(false)
const pendingCount = ref(0)   // 全量AI审核按钮数量（仅 pending）
const importableCount = ref(0) // 一键导入按钮数量（排除 ai_failed/import_failed/imported）

// 当前 tab 是否是候选库（支持 AI 审核 + 导入操作）
const isCandidateTab = computed(() => activeTab.value.startsWith('candidate_'))

function toggleSelect(id) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value) // trigger reactivity
}

function toggleSelectAll() {
  if (selectedIds.value.size === videos.value.length) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(videos.value.map(v => v.id))
  }
}

const allSelected = computed(() =>
  videos.value.length > 0 && selectedIds.value.size === videos.value.length
)

// AI 状态筛选项
const STATUS_FILTERS = [
  { value: 'pending',       label: '待审核',   color: '#64748b', bg: '#f1f5f9' },
  { value: 'ai_reviewing',  label: 'AI审核中',  color: '#2563eb', bg: '#eff6ff' },
  { value: 'ai_failed',     label: 'AI拒绝',   color: '#dc2626', bg: '#fef2f2' },
  { value: 'import_failed', label: '导入失败',  color: '#d97706', bg: '#fffbeb' },
]

// AI 状态徽章
const STATUS_MAP = {
  pending:       { label: '待审核',  color: '#64748b', bg: '#f1f5f9' },
  ai_reviewing:  { label: 'AI审核中', color: '#2563eb', bg: '#eff6ff' },
  ai_passed:     { label: 'AI通过',  color: '#16a34a', bg: '#f0fdf4' },
  ai_failed:     { label: 'AI拒绝',  color: '#dc2626', bg: '#fef2f2' },
  importing:     { label: '导入中',  color: '#7c3aed', bg: '#f5f3ff' },
  imported:      { label: '已导入',  color: '#0891b2', bg: '#ecfeff' },
  import_failed: { label: '导入失败', color: '#d97706', bg: '#fffbeb' },
}
function statusBadge(status) {
  return STATUS_MAP[status] || STATUS_MAP.pending
}
const jumpPage = ref(1)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const startIdx = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const endIdx = computed(() => Math.min(page.value * pageSize.value, total.value))

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

function goPage(p) {
  const target = Math.max(1, Math.min(p, totalPages.value))
  if (target === page.value) return
  page.value = target
  jumpPage.value = target
  loadVideos()
}

function handleSizeChange(val) {
  pageSize.value = val
  page.value = 1
  jumpPage.value = 1
  loadVideos()
  loadTabCounts()
}

function doJump() {
  const p = parseInt(jumpPage.value)
  if (!isNaN(p)) goPage(p)
}

// 配置对话框
const showConfigDialog = ref(false)
const loadingConfig = ref(false)
const savingConfig = ref(false)
const configForm = ref({
  candidate_max_bloggers: 20,
  candidate_exclusive_threshold: 10,
  candidate_max_videos_per_blogger: 100,
  candidate_max_duration_seconds: 30,
  candidate_retry_delay_seconds: 5,
  candidate_min_play_count: 0,
  candidate_publish_after_date: null,
  candidate_shared_top_n: 50,
  candidate_search_interval_minutes: 0,

  candidate_ai_review_model: 'gemini-3.1-pro-preview',
  candidate_ai_review_prompt: '',
})

// 搜索对话框
const showSearchDialog = ref(false)
const searching = ref(false)
const searchMode = ref('keyword')
const searchKeywordId = ref('')
const searchManualKeyword = ref('')

const minPlayCountWan = computed({
  get: () => configForm.value.candidate_min_play_count / 10000,
  set: (v) => { configForm.value.candidate_min_play_count = Math.round(v * 10000) },
})

const selectedKeywordText = computed(() => {
  const kw = allKeywords.value.find(k => k.id === searchKeywordId.value)
  return kw ? kw.keyword : ''
})

const canSearch = computed(() => {
  if (searchMode.value === 'keyword') return !!searchKeywordId.value
  return searchManualKeyword.value.trim().length > 0
})

onMounted(async () => {
  await Promise.all([loadVideos(), loadKeywords(), loadTabCounts()])
  // 加载定时抓取状态（用于按钮样式）
  try {
    const cfg = await fetchCandidateConfig()
    scheduleEnabled.value = cfg.candidate_schedule_enabled ?? false
  } catch { /* 静默 */ }
})

async function loadKeywords() {
  try {
    allKeywords.value = await fetchAllKeywords()
  } catch {
    // 静默失败，下拉为空时用户可手动输入
  }
}

async function loadVideos() {
  loading.value = true
  selectedIds.value = new Set()
  try {
    const { template_type, imported } = parseTabKey(activeTab.value)
    const params = {
      template_type,
      imported,
      page: page.value,
      page_size: pageSize.value,
    }
    if (filterKeywordId.value) params.keyword_id = filterKeywordId.value
    if (isCandidateTab.value && filterStatus.value) params.status = filterStatus.value
    const res = await fetchCandidateVideos(params)
    videos.value = res.items
    total.value = res.total
  } catch {
    ElMessage.warning('请稍后再试')
  } finally {
    loading.value = false
  }
}

async function loadTabCounts() {
  try {
    const [cs, s, ce, e] = await Promise.all([
      fetchCandidateVideos({ template_type: 'shared',    imported: false, page: 1, page_size: 1 }),
      fetchCandidateVideos({ template_type: 'shared',    imported: true,  page: 1, page_size: 1 }),
      fetchCandidateVideos({ template_type: 'exclusive', imported: false, page: 1, page_size: 1 }),
      fetchCandidateVideos({ template_type: 'exclusive', imported: true,  page: 1, page_size: 1 }),
    ])
    tabCounts.value = {
      candidate_shared: cs.total,
      shared: s.total,
      candidate_exclusive: ce.total,
      exclusive: e.total,
    }
  } catch (e) { console.error('loadTabCounts error', e) }

  if (!isCandidateTab.value) return
  try {
    const { template_type } = parseTabKey(activeTab.value)
    const [pending, importable] = await Promise.all([
      fetchCandidateVideos({ template_type, imported: false, status: 'pending', page: 1, page_size: 1 }),
      fetchCandidateVideos({ template_type, imported: false, page: 1, page_size: 1 }),
    ])
    pendingCount.value = pending.total
    importableCount.value = importable.total
  } catch (e) { console.error('loadButtonCounts error', e) }
}

async function loadConfig() {
  loadingConfig.value = true
  try {
    const data = await fetchCandidateConfig()
    configForm.value = { ...data }
  } catch {
    ElMessage.error('加载配置失败')
  } finally {
    loadingConfig.value = false
  }
}

async function openConfigDialog() {
  showConfigDialog.value = true
}

async function handleSaveConfig() {
  savingConfig.value = true
  try {
    await updateCandidateConfig(configForm.value)
    ElMessage.success('配置已保存')
    showConfigDialog.value = false
  } catch {
    ElMessage.error('保存配置失败')
  } finally {
    savingConfig.value = false
  }
}

function openSearchDialog() {
  searchMode.value = 'keyword'
  searchKeywordId.value = ''
  searchManualKeyword.value = ''
  showSearchDialog.value = true
}

async function handleSearch() {
  searching.value = true
  try {
    const keywordText = searchMode.value === 'keyword'
      ? selectedKeywordText.value
      : searchManualKeyword.value.trim()
    const keywordId = searchMode.value === 'keyword' ? searchKeywordId.value : null

    await triggerCandidateSearch({
      keyword_text: keywordText,
      keyword_id: keywordId || null,
    })
    ElMessage.success('搜索任务已启动，完成后刷新查看结果')
    showSearchDialog.value = false
  } catch {
    ElMessage.error('触发搜索失败，请稍后重试')
  } finally {
    searching.value = false
  }
}

async function handleDelete(video) {
  try {
    await ElMessageBox.confirm(
      `确定删除这条候选视频？`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteCandidateVideo(video.id)
    ElMessage.success('已删除')
    await Promise.all([loadVideos(), loadTabCounts()])
  } catch { /* cancelled */ }
}

async function handleBatchAIReview() {
  if (selectedIds.value.size === 0) return
  try {
    const ids = Array.from(selectedIds.value)
    await batchAIReview(ids)
    ElMessage.success(`AI 审核已在后台启动，共 ${ids.length} 条视频，请稍后刷新查看结果`)
    selectedIds.value = new Set()
    // 立即刷新一次（状态会变为 ai_reviewing）
    await loadVideos()
  } catch {
    ElMessage.error('启动 AI 审核失败，请稍后重试')
  }
}

async function handleBatchImport() {
  if (selectedIds.value.size === 0) return
  batchImporting.value = true
  try {
    const ids = Array.from(selectedIds.value)
    const res = await batchImportCandidates(ids)
    ElMessage.success(res.message || `导入已启动，共 ${ids.length} 条视频，后台处理中`)
    selectedIds.value = new Set()
    await Promise.all([loadVideos(), loadTabCounts()])
  } catch {
    ElMessage.error('导入失败，请稍后重试')
  } finally {
    batchImporting.value = false
  }
}

async function handleImportAll() {
  if (total.value === 0) return
  try {
    await ElMessageBox.confirm(
      `确定将当前候选库全部 ${total.value} 条视频（ai_passed 状态）导入到库？`,
      '一键导入',
      { confirmButtonText: '确认导入', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  importingAll.value = true
  try {
    // 逐页收集所有 ai_passed 的 id（直接用 status 参数过滤，跳过 ai_failed）
    const { template_type } = parseTabKey(activeTab.value)
    let allIds = []
    let p = 1
    const PAGE = 100
    while (true) {
      const res = await fetchCandidateVideos({ template_type, imported: false, page: p, page_size: PAGE })
      const skip = ['ai_failed', 'import_failed', 'imported']
      allIds = allIds.concat(res.items.filter(v => !skip.includes(v.status)).map(v => v.id))
      if (res.items.length < PAGE) break
      p++
    }
    if (allIds.length === 0) {
      ElMessage.warning('没有状态为 AI通过 的视频可以导入')
      return
    }
    const res = await batchImportCandidates(allIds)
    ElMessage.success(res.message || `导入已启动，共 ${allIds.length} 条视频，后台处理中`)
    selectedIds.value = new Set()
    await Promise.all([loadVideos(), loadTabCounts()])
  } catch {
    ElMessage.error('一键导入失败，请稍后重试')
  } finally {
    importingAll.value = false
  }
}

async function handleBulkAIReviewAll() {
  if (total.value === 0) return
  const { template_type } = parseTabKey(activeTab.value)
  try {
    await ElMessageBox.confirm(
      `确定将当前候选库全部 ${pendingCount.value} 条待审核视频加入AI审核队列？`,
      '全量AI审核',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'info' }
    )
  } catch { return }

  try {
    const res = await bulkAIReviewAll(template_type)
    ElMessage.success(res.message || '已加入AI审核队列，后台处理中')
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  }
}

// ── 定时抓取 ──────────────────────────────────────────────────────────────────

const CRON_PRESETS = [
  { label: '每天8点',    cron: '0 8 * * *' },
  { label: '每天10点',   cron: '0 10 * * *' },
  { label: '每天20点',   cron: '0 20 * * *' },
  { label: '每12小时',   cron: '0 */12 * * *' },
  { label: '隔天10点',   cron: '0 10 */2 * *' },
  { label: '每周一10点', cron: '0 10 * * 1' },
]

const showScheduleDialog = ref(false)
const savingSchedule = ref(false)
const scheduleEnabled = ref(false)
const scheduleForm = ref({
  candidate_schedule_enabled: false,
  candidate_schedule_cron: '',
})

const schedulePreview = computed(() => {
  const cron = scheduleForm.value.candidate_schedule_cron?.trim()
  if (!cron) return '请输入 Cron 表达式'
  const preset = CRON_PRESETS.find(p => p.cron === cron)
  return preset ? `将在 ${preset.label} 自动抓取（北京时间）` : `Cron: ${cron}（北京时间）`
})

async function openScheduleDialog() {
  showScheduleDialog.value = true
  try {
    const data = await fetchCandidateConfig()
    scheduleForm.value = {
      candidate_schedule_enabled: data.candidate_schedule_enabled ?? false,
      candidate_schedule_cron: data.candidate_schedule_cron ?? '',
    }
  } catch {
    ElMessage.error('加载定时配置失败')
  }
}

async function handleSaveSchedule() {
  savingSchedule.value = true
  try {
    // 先加载完整配置，合并定时字段后保存
    const full = await fetchCandidateConfig()
    const merged = {
      ...full,
      candidate_schedule_enabled: scheduleForm.value.candidate_schedule_enabled,
      candidate_schedule_cron: scheduleForm.value.candidate_schedule_cron || null,
    }
    await updateCandidateConfig(merged)
    scheduleEnabled.value = merged.candidate_schedule_enabled
    showScheduleDialog.value = false
    ElMessage.success(merged.candidate_schedule_enabled ? '定时抓取已启用' : '定时抓取已关闭')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingSchedule.value = false
  }
}

function formatCount(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}
</script>

<style scoped>
.cl-page { padding: 28px 32px; max-width: 1600px; }

.cl-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;
}
.cl-title { font-size: 22px; font-weight: 700; color: #1e293b; margin: 0; }
.cl-header-actions { display: flex; gap: 10px; }

.cl-btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 18px; border-radius: 8px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .15s; }
.cl-btn-primary { background: #6366f1; color: #fff; }
.cl-btn-primary:hover { background: #4f46e5; }
.cl-btn-config { background: #f1f5f9; color: #475569; }
.cl-btn-config:hover { background: #e2e8f0; }
.cl-btn-schedule { background: #f1f5f9; color: #475569; }
.cl-btn-schedule:hover { background: #e2e8f0; }
.cl-btn-schedule.active { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }

/* Body layout: tree + main */
.cl-body { display: flex; gap: 20px; }

/* Tree panel */
.cl-tree-panel {
  width: 240px; min-width: 240px; background: #fff; border: 1px solid #e2e8f0;
  border-radius: 10px; overflow: hidden; align-self: flex-start; position: sticky; top: 20px;
  transition: width .2s, min-width .2s;
}
.cl-tree-panel.collapsed { width: 44px; min-width: 44px; }
.cl-tree-header {
  padding: 10px 12px; border-bottom: 1px solid #e2e8f0; background: #f8fafc;
  display: flex; align-items: center; justify-content: space-between; gap: 6px;
}
.cl-tree-panel.collapsed .cl-tree-header { justify-content: center; border-bottom: none; }
.cl-tree-title { font-size: 13px; font-weight: 700; color: #374151; }
.cl-tree-toggle {
  border: none; background: transparent; color: #94a3b8; cursor: pointer;
  padding: 2px; display: flex; align-items: center; border-radius: 4px; transition: all .12s;
}
.cl-tree-toggle:hover { color: #6366f1; background: #eef2ff; }
.cl-tree-search {
  display: flex; align-items: center; gap: 6px; padding: 8px 10px; border-bottom: 1px solid #e2e8f0;
  position: relative;
}
.cl-tree-search-icon { flex-shrink: 0; }
.cl-tree-search-input {
  flex: 1; border: none; outline: none; font-size: 12px; color: #374151;
  background: transparent; min-width: 0;
}
.cl-tree-search-input::placeholder { color: #cbd5e1; }
.cl-tree-search-clear {
  flex-shrink: 0; border: none; background: transparent; color: #94a3b8;
  cursor: pointer; padding: 2px; display: flex; align-items: center;
}
.cl-tree-search-clear:hover { color: #475569; }
.cl-tree-content { padding: 6px 0; max-height: calc(100vh - 250px); overflow-y: auto; }
.cl-tree-empty { padding: 16px 14px; font-size: 12px; color: #94a3b8; text-align: center; }
:deep(.cl-tree-hl) { background: #fef08a; color: #92400e; border-radius: 2px; padding: 0 1px; }

.cl-tree-item {
  display: flex; align-items: center; gap: 6px; padding: 6px 14px; font-size: 13px;
  color: #475569; cursor: pointer; transition: all .12s; user-select: none;
}
.cl-tree-item:hover { background: #f1f5f9; }
.cl-tree-item.active { background: #eef2ff; color: #6366f1; font-weight: 600; }

.cl-tree-all { font-weight: 600; border-bottom: 1px solid #f1f5f9; margin-bottom: 2px; }

.cl-tree-arrow {
  transition: transform .15s; flex-shrink: 0;
}
.cl-tree-item.expanded .cl-tree-arrow { transform: rotate(90deg); }

.cl-tree-topic-label { padding-left: 10px; font-weight: 600; color: #374151; }
.cl-tree-mk-label { padding-left: 26px; font-weight: 500; color: #475569; }
.cl-tree-kw-label { padding-left: 44px; font-weight: 400; color: #64748b; font-size: 12px; }
.cl-tree-children { /* animated via v-show */ }

/* Main content area */
.cl-main { flex: 1; min-width: 0; }

/* Breadcrumb */
.cl-breadcrumb {
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
  padding: 6px 12px; background: #f5f3ff; border-radius: 6px; font-size: 12px; color: #6366f1;
}
.cl-breadcrumb-text { font-weight: 500; }
.cl-breadcrumb-clear {
  display: inline-flex; align-items: center; gap: 4px; border: none; background: transparent;
  color: #94a3b8; font-size: 11px; cursor: pointer; padding: 2px 6px; border-radius: 4px;
  transition: all .12s; margin-left: auto;
}
.cl-breadcrumb-clear:hover { background: #e0e7ff; color: #6366f1; }

/* Config form */
.config-form { display: flex; flex-direction: column; gap: 14px; padding: 0 4px; }
.cf-row { display: flex; flex-direction: column; gap: 4px; }
.cf-label { font-size: 13px; font-weight: 600; color: #374151; }
.cf-hint { font-size: 12px; color: #94a3b8; }
.cf-divider { border-top: 1px solid #e2e8f0; margin: 4px 0; }
.cf-section-title { font-size: 14px; font-weight: 700; color: #374151; margin: 0 0 4px; }

/* Cron presets */
.cl-cron-presets { display: flex; flex-wrap: wrap; gap: 6px; }
.cl-preset-btn {
  padding: 5px 12px; border: 1px solid #d1d5db; border-radius: 6px; background: #fff;
  color: #374151; font-size: 12px; cursor: pointer; transition: all .15s;
}
.cl-preset-btn:hover { border-color: #6366f1; color: #6366f1; }
.cl-preset-btn.active { background: #6366f1; color: #fff; border-color: #6366f1; }

/* Tabs */
.cl-tabs { display: flex; gap: 4px; border-bottom: 1px solid #e2e8f0; margin-bottom: 16px; }
.cl-tab {
  padding: 10px 20px; border: none; background: transparent; color: #64748b;
  font-size: 14px; cursor: pointer; border-bottom: 2px solid transparent;
  transition: all .15s; display: inline-flex; align-items: center; gap: 6px;
}
.cl-tab:hover { color: #6366f1; }
.cl-tab.active { color: #6366f1; font-weight: 700; border-bottom-color: #6366f1; }
.cl-tab-count {
  background: #6366f1; color: #fff; padding: 1px 7px; border-radius: 10px;
  font-size: 11px; font-weight: 600;
}
.cl-tab.active .cl-tab-count { background: #4f46e5; }

/* Filters — select kept for search dialog */
.cl-select {
  padding: 7px 12px; border: 1px solid #d1d5db; border-radius: 8px;
  font-size: 13px; color: #374151; outline: none; background: #fff;
  cursor: pointer; min-width: 220px;
}
.cl-select:focus { border-color: #6366f1; }

/* Grid */
.cl-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px; min-height: 120px;
}

.cl-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  overflow: hidden; transition: all .15s; position: relative;
}
.cl-card:hover { border-color: #6366f1; box-shadow: 0 2px 12px rgba(99,102,241,.1); }

.cl-card-cover { position: relative; aspect-ratio: 9/16; background: #f8fafc; overflow: hidden; }
.cl-cover-img { width: 100%; height: 100%; object-fit: cover; }
.cl-cover-placeholder {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
}
.cl-card-badge {
  position: absolute; top: 8px; left: 8px; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 700;
}
.badge-shared { background: rgba(34,197,94,.15); color: #16a34a; }
.badge-exclusive { background: rgba(245,158,11,.15); color: #d97706; }

.cl-card-link {
  position: absolute; bottom: 8px; right: 8px; width: 28px; height: 28px;
  background: rgba(0,0,0,.5); border-radius: 6px; display: flex; align-items: center;
  justify-content: center; color: #fff; text-decoration: none; transition: background .15s;
}
.cl-card-link:hover { background: rgba(0,0,0,.75); }

.cl-card-info { padding: 10px 12px; }
.cl-card-blogger { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
.cl-blogger-name { font-size: 13px; font-weight: 600; color: #1e293b; }
.cl-follower-count { font-size: 11px; color: #64748b; }
.cl-card-title {
  font-size: 12px; color: #475569; margin-bottom: 6px;
  overflow: hidden; text-overflow: ellipsis; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical; line-height: 1.4;
}
.cl-card-meta { display: flex; gap: 8px; font-size: 11px; color: #94a3b8; margin-bottom: 4px; }
.cl-card-keyword {
  font-size: 11px; color: #6366f1; background: #eef2ff; padding: 2px 7px; border-radius: 4px;
  display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.cl-card-del {
  position: absolute; top: 8px; right: 8px; width: 26px; height: 26px;
  border-radius: 6px; border: none; background: rgba(255,255,255,.9);
  color: #94a3b8; cursor: pointer; display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: all .15s;
}
.cl-card:hover .cl-card-del { opacity: 1; }
.cl-card-del:hover { background: #fef2f2; color: #ef4444; }

/* Card checkbox */
.cl-card-checkbox {
  position: absolute; top: 8px; left: 8px; z-index: 2; cursor: pointer;
  width: 20px; height: 20px; display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity .15s;
}
.cl-card:hover .cl-card-checkbox,
.cl-card.selected .cl-card-checkbox { opacity: 1; }
.cl-card-checkbox input[type="checkbox"] { width: 15px; height: 15px; cursor: pointer; }
.cl-card.selected { border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99,102,241,.2); }

/* AI status badge */
.cl-status-badge {
  position: absolute; bottom: 8px; left: 8px; padding: 2px 7px; border-radius: 4px;
  font-size: 10px; font-weight: 700; pointer-events: none;
}
.cl-status-badge--error { pointer-events: auto; cursor: default; }
.cl-error-tooltip {
  display: none;
  position: absolute; bottom: calc(100% + 6px); left: 0;
  min-width: 180px; max-width: 260px;
  background: #1e293b; color: #f1f5f9;
  font-size: 10px; font-weight: 400; line-height: 1.4;
  padding: 5px 8px; border-radius: 5px;
  white-space: pre-wrap; word-break: break-all;
  box-shadow: 0 4px 12px rgba(0,0,0,.25);
  z-index: 10;
}
.cl-status-badge--error:hover .cl-error-tooltip { display: block; }

/* Status filter chips */
.cl-status-filter {
  display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px;
}
.cl-status-chip {
  padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 500;
  border: 1px solid #e2e8f0; background: #fff; color: #64748b;
  cursor: pointer; transition: all .15s;
}
.cl-status-chip:hover { border-color: #94a3b8; color: #334155; }
.cl-status-chip.active { font-weight: 700; }

/* Batch bar */
.cl-batch-bar {
  display: flex; align-items: center; gap: 10px; margin-bottom: 12px;
  padding: 8px 12px; background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 8px; min-height: 40px;
}
.cl-check-all {
  display: flex; align-items: center; gap: 6px; font-size: 13px; color: #475569;
  cursor: pointer; user-select: none;
}
.cl-check-all input { cursor: pointer; }
.cl-selected-count { font-size: 13px; color: #6366f1; font-weight: 600; margin-left: 4px; }
.cl-btn-ai { background: #4f46e5; color: #fff; }
.cl-btn-ai:hover:not(:disabled) { background: #4338ca; }
.cl-btn-ai:disabled { opacity: .5; cursor: not-allowed; }
.cl-btn-import { background: #059669; color: #fff; }
.cl-btn-import:hover:not(:disabled) { background: #047857; }
.cl-btn-import:disabled { opacity: .5; cursor: not-allowed; }
.cl-btn-deselect { background: #f1f5f9; color: #475569; }
.cl-btn-deselect:hover { background: #e2e8f0; }
.cl-batch-bar-spacer { flex: 1; }
.cl-btn-review-all { background: #7c3aed; color: #fff; }
.cl-btn-review-all:hover:not(:disabled) { background: #6d28d9; }
.cl-btn-review-all:disabled { opacity: .5; cursor: not-allowed; }
.cl-btn-import-all { background: #0f766e; color: #fff; }
.cl-btn-import-all:hover:not(:disabled) { background: #0d9488; }
.cl-btn-import-all:disabled { opacity: .5; cursor: not-allowed; }

/* Spinner */
.btn-spin {
  width: 12px; height: 12px; border: 2px solid rgba(255,255,255,.4);
  border-top-color: #fff; border-radius: 50%; animation: spin .6s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Footer */
.cl-footer {
  display: flex; align-items: center; justify-content: space-between; margin-top: 20px;
  padding: 16px 0 8px; border-top: 1px solid #f1f5f9; flex-wrap: wrap; gap: 12px;
}
.cl-pagination-left { display: flex; align-items: center; gap: 12px; }
.cl-count-text { font-size: 13px; color: #94a3b8; }
.cl-size-select {
  border: none; background: transparent; color: #94a3b8; font-size: 13px;
  font-weight: 500; cursor: pointer; outline: none; padding: 0 4px;
}
.cl-size-select:hover { color: #64748b; }
.cl-pagination { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.pg-btn {
  font-size: 13px; font-weight: 500; padding: 7px 14px; border-radius: 9px;
  border: 1px solid #e2e8f0; background: #fff; color: #475569; cursor: pointer; transition: all .15s;
}
.pg-btn:hover:not(:disabled) { border-color: #6366f1; color: #6366f1; background: #eef2ff; }
.pg-btn:disabled { opacity: .4; cursor: not-allowed; }
.pg-num { min-width: 36px; padding: 7px 10px; text-align: center; }
.pg-num.active { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; border-color: transparent; font-weight: 700; }
.pg-ellipsis { font-size: 13px; color: #94a3b8; padding: 0 4px; user-select: none; }
.pg-jump-wrap { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #94a3b8; margin-left: 4px; }
.pg-jump-input {
  width: 52px; height: 34px; border: 1px solid #e2e8f0; border-radius: 8px;
  text-align: center; font-size: 13px; color: #334155; outline: none; padding: 0 6px;
}
.pg-jump-input:focus { border-color: #6366f1; }
.pg-jump-input::-webkit-inner-spin-button, .pg-jump-input::-webkit-outer-spin-button { -webkit-appearance: none; }
.pg-jump-go { padding: 7px 12px; }

/* Search dialog */
.search-form { display: flex; flex-direction: column; gap: 16px; padding: 0 4px; }
.sf-row {}
.sf-label { display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 6px; }
.sf-radio-group { display: flex; gap: 16px; }
.sf-radio { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #374151; cursor: pointer; }
.sf-input {
  width: 100%; padding: 9px 12px; border: 1px solid #d1d5db; border-radius: 8px;
  font-size: 14px; outline: none; transition: border .15s; box-sizing: border-box;
}
.sf-input:focus { border-color: #6366f1; }
.sf-preview { margin-top: 6px; font-size: 12px; color: #6366f1; }
.sf-tip {
  display: flex; align-items: flex-start; gap: 6px; padding: 10px 12px;
  background: #f5f3ff; border-radius: 8px; font-size: 12px; color: #6b7280; line-height: 1.5;
}

/* Dialog buttons */
.dlg-btn-cancel { padding: 8px 18px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; color: #374151; font-size: 13px; cursor: pointer; }
.dlg-btn-cancel:hover { background: #f9fafb; }
.dlg-btn-primary { padding: 8px 18px; border: none; border-radius: 8px; background: #6366f1; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.dlg-btn-primary:hover { background: #4f46e5; }
.dlg-btn-primary:disabled { opacity: .5; cursor: not-allowed; }

.btn-spin {
  width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.3);
  border-top-color: #fff; border-radius: 50%; animation: spin .6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
