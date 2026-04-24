<template>
  <div class="al-page">
    <div class="al-header">
      <h1 class="al-title">AI博主</h1>
      <div class="al-header-actions">
        <el-button class="al-config-btn" @click="openAISettings">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          AI博主配置
        </el-button>
        <el-button class="al-config-btn" @click="handleBulkGenerateAIAccounts" :loading="bulkGenerating">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M12 5v14"/><path d="M5 12h14"/><path d="M4 4h16v16H4z" opacity=".2"/></svg>
          一键生成AI博主
        </el-button>
        <el-button class="al-restart-btn" @click="openBulkContinueDialog" :loading="bulkRestarting" :disabled="items.length === 0">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
          {{ selectedMap.size > 0 ? `一键继续 (${selectedMap.size})` : '一键继续' }}
        </el-button>
        <el-button class="al-gen-btn" :loading="bulkVideoGenerating" :disabled="total === 0" @click="handleBulkVideoGenerate">
          <svg v-if="!bulkVideoGenerating" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          {{ bulkVideoGenerating ? `${bulkVideoGenProgress.current}/${bulkVideoGenProgress.total}` : selectedMap.size > 0 ? `一键生成 (${selectedMap.size})` : '一键生成' }}
        </el-button>
        <el-button class="al-schedule-btn" :disabled="total === 0" @click="openBulkScheduleDialog">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="margin-right:6px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          {{ selectedMap.size > 0 ? `一键定时 (${selectedMap.size})` : '一键定时' }}
        </el-button>
        <el-button class="al-supplement-btn" :disabled="total === 0" @click="openSupplementDialog">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
          {{ selectedMap.size > 0 ? `补充模板 (${selectedMap.size})` : '补充模板' }}
        </el-button>
        <el-button class="al-namehandle-btn" :loading="bulkNameHandleLoading" :disabled="total === 0" @click="confirmBulkNameHandle">
          <svg v-if="!bulkNameHandleLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
          {{ selectedMap.size > 0 ? `生成Handle (${selectedMap.size})` : '生成Handle' }}
        </el-button>
        <el-button class="al-hashtag-btn" :loading="hashtagSearchLoading" :disabled="total === 0" @click="openHashtagSearchDialog">
          <svg v-if="!hashtagSearchLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>
          {{ selectedMap.size > 0 ? `标签搜索 (${selectedMap.size})` : '标签搜索' }}
        </el-button>
        <el-button class="al-tasks-btn" :loading="downloading" @click="handleDownload">
          <svg v-if="!downloading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          {{ downloading ? '下载中...' : selectedMap.size > 0 ? `下载 (${selectedMap.size})` : '下载视频' }}
        </el-button>
        <el-button class="al-tasks-btn" :loading="exporting" @click="handleExportVideoUrls">
          <svg v-if="!exporting" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          {{ exporting ? '导出中...' : selectedMap.size > 0 ? `一键导出 (${selectedMap.size})` : '一键导出' }}
        </el-button>
        <el-button type="primary" class="al-add-btn" @click="$router.push('/dashboard/accounts/new')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          新建账号
        </el-button>
      </div>
    </div>

    <!-- AI博主配置弹窗 -->
    <el-dialog
      v-model="showAISettingsDialog"
      title="AI博主配置"
      width="700px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-loading="aiSettingsLoading" class="ai-cfg-body">

        <!-- 阶段一：视频理解 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">阶段一：视频理解</span>
            <span class="ai-cfg-desc">从标签关联的全部视频里随机抽样，生成理解结果并用于名称生成</span>
          </div>
          <el-form-item label="分析样本数">
            <el-input-number v-model="aiSettingsForm.ai_account_analysis_sample_size" :min="1" :max="50" style="width: 160px" />
          </el-form-item>
          <el-form-item label="视频分析提示词">
            <el-input v-model="aiSettingsForm.ai_account_video_prompt" type="textarea" :rows="4" placeholder="请输入视频分析提示词..." />
          </el-form-item>
          <el-form-item label="视频理解模型">
            <el-input v-model="aiSettingsForm.ai_account_video_model" placeholder="e.g. gemini-3.1-pro-preview" />
          </el-form-item>
        </div>

        <!-- 阶段二：名称生成 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">阶段二：名称生成</span>
            <span class="ai-cfg-desc">基于视频描述，调用 Gemini 生成博主名称</span>
          </div>
          <el-form-item label="名称生成提示词">
            <el-input v-model="aiSettingsForm.ai_account_name_prompt" type="textarea" :rows="4" placeholder="请输入名称生成提示词..." />
          </el-form-item>
          <el-form-item label="名称生成模型">
            <el-input v-model="aiSettingsForm.ai_account_name_model" placeholder="e.g. gemini-3.1-pro-preview" />
          </el-form-item>
        </div>

        <!-- 阶段三：照片候选生成 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">阶段三：照片候选生成</span>
            <span class="ai-cfg-desc">随机选择最多 3 个不同视频，每个视频并发生成 3 张照片候选，用户后续手动选择一张进入头像生成</span>
          </div>
          <el-form-item label="照片生成提示词">
            <el-input v-model="aiSettingsForm.ai_account_photo_image_prompt" type="textarea" :rows="3" placeholder="Nano2 生图提示词前缀，将与视频描述拼接后调用生图..." />
          </el-form-item>
        </div>

        <!-- 阶段四：头像生成 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">阶段四：头像生成</span>
            <span class="ai-cfg-desc">基于人工选中的照片候选和视频描述生成博主头像</span>
          </div>
          <el-form-item label="头像生成提示词">
            <el-input v-model="aiSettingsForm.ai_account_avatar_prompt" type="textarea" :rows="4" placeholder="请输入头像生成提示词..." />
          </el-form-item>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">
            <el-form-item label="头像生成模型">
              <el-input v-model="aiSettingsForm.ai_account_avatar_model" placeholder="e.g. nano2" />
            </el-form-item>
            <el-form-item label="头像尺寸">
              <el-select v-model="aiSettingsForm.ai_account_avatar_size" style="width:100%">
                <el-option label="1:1 (正方形)" value="1:1" />
                <el-option label="9:16 (竖版)" value="9:16" />
                <el-option label="16:9 (横版)" value="16:9" />
                <el-option label="3:4" value="3:4" />
              </el-select>
            </el-form-item>
            <el-form-item label="头像质量">
              <el-select v-model="aiSettingsForm.ai_account_avatar_quality" style="width:100%">
                <el-option label="1K" value="1K" />
                <el-option label="2K" value="2K" />
                <el-option label="4K" value="4K" />
              </el-select>
            </el-form-item>
          </div>
        </div>

        <!-- 批量生成名称/Handle/签名 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">批量生成：独享号 &amp; 人设号 Prompt</span>
            <span class="ai-cfg-desc">
              基于绑定的 TikTok 博主信息生成，可用占位符：
              <code style="background:#f3f4f6;padding:1px 4px;border-radius:3px">{blogger_name}</code>
              <code style="background:#f3f4f6;padding:1px 4px;border-radius:3px">{blogger_handle}</code>
              <code style="background:#f3f4f6;padding:1px 4px;border-radius:3px">{blogger_signature}</code>
            </span>
          </div>
          <el-form-item label="独享号/人设号 Prompt">
            <el-input v-model="aiSettingsForm.ai_account_exclusive_name_prompt" type="textarea" :rows="4" placeholder="例：参考博主 {blogger_name}（@{blogger_handle}）的简介「{blogger_signature}」，为新账号生成一个创意名称、handle 和个人签名..." />
          </el-form-item>
        </div>

        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">批量生成：共享号 Prompt</span>
            <span class="ai-cfg-desc">
              基于绑定的标签关键词生成，可用占位符：
              <code style="background:#f3f4f6;padding:1px 4px;border-radius:3px">{keyword}</code>
            </span>
          </div>
          <el-form-item label="共享号 Prompt">
            <el-input v-model="aiSettingsForm.ai_account_shared_name_prompt" type="textarea" :rows="4" placeholder="例：根据关键词「{keyword}」，为一个共享账号生成博主名称、handle 和签名..." />
          </el-form-item>
        </div>

        <!-- 标签搜索配置 -->
        <div class="ai-cfg-section">
          <div class="ai-cfg-section-header">
            <span class="ai-cfg-tag">标签搜索（Hashtag Search）</span>
            <span class="ai-cfg-desc">根据账号绑定的 TikTok 博主，抓取热门视频的 HashTag，经 AI 过滤后返回推荐标签列表</span>
          </div>
          <el-form-item label="抓取视频数量">
            <el-input-number v-model="aiSettingsForm.hashtag_search_top_n" :min="10" :max="500" :step="10" style="width: 160px" />
            <span style="margin-left:8px;color:#6b7280;font-size:13px">条（按播放量排序取前 N 个视频）</span>
          </el-form-item>
          <el-form-item label="过滤模型">
            <el-input v-model="aiSettingsForm.hashtag_filter_model" placeholder="e.g. gemini-3.1-pro-preview" />
          </el-form-item>
          <el-form-item label="AI 过滤提示词">
            <el-input
              v-model="aiSettingsForm.hashtag_filter_prompt"
              type="textarea"
              :rows="5"
              placeholder="例：以下是从 TikTok 视频中提取的 HashTag 列表，请过滤掉无意义、过于通用（如 fyp、viral）或与目标内容无关的标签，保留能精准描述内容品类、场景、风格的标签..."
            />
            <div style="margin-top:4px;color:#9ca3af;font-size:12px">留空则跳过 AI 过滤，直接返回全量去重 HashTag。系统会在提示词末尾自动拼接 JSON 格式化指令。</div>
          </el-form-item>
        </div>

      </div>
      <template #footer>
        <el-button @click="showAISettingsDialog = false">取消</el-button>
        <el-button type="primary" :loading="aiSettingsSaving" @click="saveAISettings">保存配置</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showBulkContinueDialog"
      title="一键继续 AI 生成"
      width="520px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="al-bulk-resume-body">
        <div class="al-bulk-resume-hint">
          选择从哪个阶段开始继续。
          <template v-if="selectedMap.size > 0">
            <b>操作范围：已选 {{ selectedMap.size }} 个账号</b>。
          </template>
          <template v-else>
            该操作会对当前账号下所有未完成、且不处于"待选照片"的 AI 博主统一生效。
          </template>
        </div>
        <el-form-item label="继续阶段">
          <el-select v-model="bulkResumeStage" style="width: 100%">
            <el-option label="按当前数据库阶段断点续跑" value="current" />
            <el-option label="从视频理解开始" value="video_analyzing" />
            <el-option label="从名称生成开始" value="name_generating" />
            <el-option label="从照片生成开始" value="photo_generating" />
            <el-option label="从头像生成开始" value="avatar_generating" />
          </el-select>
        </el-form-item>
        <div class="al-bulk-resume-desc">
          <template v-if="bulkResumeStage === 'photo_generating'">
            会清空已有照片候选、已选照片和头像，并重新生成照片与头像。
          </template>
          <template v-else-if="bulkResumeStage === 'avatar_generating'">
            会保留照片候选和已选照片，只重新生成头像。
          </template>
          <template v-else-if="bulkResumeStage === 'name_generating'">
            会保留照片、视频理解结果和头像，只重新生成名称。
          </template>
          <template v-else-if="bulkResumeStage === 'video_analyzing'">
            会从视频理解开始重跑整个 AI 博主流程。
          </template>
          <template v-else>
            会按照数据库里当前记录的阶段断点续跑。
          </template>
        </div>
      </div>
      <template #footer>
        <el-button @click="showBulkContinueDialog = false">取消</el-button>
        <el-button type="primary" :loading="bulkRestarting" @click="handleBulkContinueAIGeneration">确认继续</el-button>
      </template>
    </el-dialog>

    <!-- 批量定时发布配置 dialog -->
    <el-dialog
      v-model="showBulkScheduleDialog"
      title="批量定时发布配置"
      width="520px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="al-bulk-resume-hint" style="margin-bottom:16px">
        以下设置将强制启用并覆盖全部 <strong>{{ total }}</strong> 个账号的定时发布配置。
      </div>
      <el-form :model="bulkScheduleForm" label-width="120px" label-position="left">
        <el-form-item label="快捷规则">
          <div class="al-schedule-presets">
            <button
              v-for="p in CRON_PRESETS"
              :key="p.cron"
              type="button"
              class="al-preset-btn"
              :class="{ active: bulkScheduleForm.publish_cron === p.cron }"
              @click="bulkScheduleForm.publish_cron = p.cron"
            >{{ p.label }}</button>
          </div>
        </el-form-item>
        <el-form-item label="Cron 表达式">
          <el-input v-model="bulkScheduleForm.publish_cron" placeholder="0 10 * * *" style="font-family:monospace" />
          <div class="al-schedule-hint">格式：分 时 日 月 周（北京时间）。例：每天10点 = 0 10 * * *</div>
        </el-form-item>
        <el-form-item label="随机延迟">
          <el-input-number v-model="bulkScheduleForm.publish_window_minutes" :min="0" :max="720" :step="15" style="width:130px" />
          <span class="al-schedule-unit">分钟（0 = 精确时间）</span>
        </el-form-item>
        <el-form-item label="每次发布数量">
          <el-input-number v-model="bulkScheduleForm.publish_count" :min="1" :max="20" style="width:100px" />
          <span class="al-schedule-unit">个视频</span>
        </el-form-item>
        <el-form-item label="规则预览">
          <div class="al-schedule-preview">{{ bulkSchedulePreview }}</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBulkScheduleDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingBulkSchedule" @click="handleBulkSchedule">{{ selectedMap.size > 0 ? `应用到已选 ${selectedMap.size} 个账号` : '应用到全部账号' }}</el-button>
      </template>
    </el-dialog>

    <!-- 一键生成配置 dialog -->
    <el-dialog
      v-model="showBulkGenDialog"
      title="一键生成"
      width="480px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="al-supplement-body">
        <!-- 操作范围提示 -->
        <div class="al-supplement-scope">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span v-if="selectedMap.size > 0">将为已选 <b>{{ selectedMap.size }}</b> 个账号创建生成任务</span>
          <span v-else>将为全部 <b>{{ total }}</b> 个账号创建生成任务</span>
        </div>
        <!-- 模式选择 -->
        <div class="al-supplement-types">
          <button
            class="al-supplement-type-card"
            :class="{ active: bulkGenForm.mode === 'unused' }"
            @click="bulkGenForm.mode = 'unused'"
          >
            <div class="al-supplement-type-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>
            </div>
            <div class="al-supplement-type-name">未用过的</div>
            <div class="al-supplement-type-desc">选择从未使用的模板，按顺序取前 N 个</div>
          </button>
          <button
            class="al-supplement-type-card"
            :class="{ active: bulkGenForm.mode === 'used' }"
            @click="bulkGenForm.mode = 'used'"
          >
            <div class="al-supplement-type-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            </div>
            <div class="al-supplement-type-name">用过的</div>
            <div class="al-supplement-type-desc">从已使用过的模板中随机抽取 N 个</div>
          </button>
        </div>
        <!-- 数量配置 -->
        <div class="al-supplement-config">
          <div class="al-supplement-config-label">每账号最多使用模板数（0 = 不限制）</div>
          <div class="al-supplement-config-row">
            <button class="al-supplement-minus" @click="bulkGenForm.limit = Math.max(0, bulkGenForm.limit - 1)">−</button>
            <span class="al-supplement-num">{{ bulkGenForm.limit }}</span>
            <button class="al-supplement-plus" @click="bulkGenForm.limit = Math.min(99, bulkGenForm.limit + 1)">+</button>
            <span class="al-supplement-num-hint">个</span>
          </div>
        </div>
        <!-- 子任务数量配置 -->
        <div class="al-supplement-config">
          <div class="al-supplement-config-label">每个任务生成子任务数</div>
          <div class="al-supplement-config-row">
            <button class="al-supplement-minus" @click="bulkGenForm.subtaskCount = Math.max(1, bulkGenForm.subtaskCount - 1)">−</button>
            <span class="al-supplement-num">{{ bulkGenForm.subtaskCount }}</span>
            <button class="al-supplement-plus" @click="bulkGenForm.subtaskCount = Math.min(20, bulkGenForm.subtaskCount + 1)">+</button>
            <span class="al-supplement-num-hint">个</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showBulkGenDialog = false">取消</el-button>
        <el-button type="primary" :loading="bulkVideoGenerating" @click="startBulkVideoGenerate">开始生成</el-button>
      </template>
    </el-dialog>

    <!-- 补充模板弹窗 -->
    <el-dialog
      v-model="showSupplementDialog"
      title="补充模板"
      width="480px"
      :close-on-click-modal="false"
    >
      <div class="al-supplement-body">
        <!-- 操作范围提示 -->
        <div class="al-supplement-scope">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span v-if="selectedMap.size > 0">将为已选 <b>{{ selectedMap.size }}</b> 个账号补充模板</span>
          <span v-else>将为全部 <b>{{ total }}</b> 个账号补充模板</span>
        </div>
        <!-- 类型选择 -->
        <div class="al-supplement-types">
          <button
            class="al-supplement-type-card"
            :class="{ active: supplementForm.templateType === 'shared' }"
            @click="supplementForm.templateType = 'shared'"
          >
            <div class="al-supplement-type-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
            </div>
            <div class="al-supplement-type-name">补充共享</div>
            <div class="al-supplement-type-desc">以标签名搜索视频</div>
          </button>
          <button
            class="al-supplement-type-card"
            :class="{ active: supplementForm.templateType === 'exclusive' }"
            @click="supplementForm.templateType = 'exclusive'"
          >
            <div class="al-supplement-type-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </div>
            <div class="al-supplement-type-name">补充人设</div>
            <div class="al-supplement-type-desc">搜索绑定博主的视频</div>
          </button>
        </div>
        <!-- 数量配置 -->
        <div class="al-supplement-config">
          <div class="al-supplement-config-label">每账号最多新增视频数</div>
          <div class="al-supplement-config-row">
            <button class="al-supplement-minus" @click="supplementForm.maxNewVideos = Math.max(1, supplementForm.maxNewVideos - 1)">−</button>
            <span class="al-supplement-num">{{ supplementForm.maxNewVideos }}</span>
            <button class="al-supplement-plus" @click="supplementForm.maxNewVideos = Math.min(50, supplementForm.maxNewVideos + 1)">+</button>
            <span class="al-supplement-num-hint">条</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showSupplementDialog = false">取消</el-button>
        <el-button type="primary" :loading="supplementing" @click="handleSupplement">开始补充</el-button>
      </template>
    </el-dialog>

    <!-- 标签搜索确认弹窗 -->
    <el-dialog
      v-model="showHashtagSearchDialog"
      title="标签搜索"
      width="480px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="al-supplement-body">
        <div class="al-supplement-scope">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span v-if="selectedMap.size > 0">将为已选 <b>{{ selectedMap.size }}</b> 个账号搜索并绑定 HashTag</span>
          <span v-else>将为全部 <b>{{ total }}</b> 个账号搜索并绑定 HashTag</span>
        </div>
        <div style="color:#6b7280;font-size:13px;line-height:1.6">
          任务会在后台执行：抓取每个账号绑定博主的热门视频 → 提取 HashTag → AI 过滤 → 自动写入账号。<br>
          抓取数量、AI 过滤提示词可在「AI博主配置」中设置。
        </div>
        <div class="al-hashtag-bind-bar">
          <span class="al-hashtag-bind-label">绑定方式：</span>
          <el-radio-group v-model="hashtagBindMode" size="small">
            <el-radio-button value="replace">覆盖原有标签</el-radio-button>
            <el-radio-button value="merge">追加合并</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <template #footer>
        <el-button @click="showHashtagSearchDialog = false">取消</el-button>
        <el-button type="primary" :loading="hashtagSearchLoading" @click="startHashtagSearch">开始搜索并绑定</el-button>
      </template>
    </el-dialog>

    <!-- Flag 过滤栏 -->
    <div class="al-filter-bar">
      <!-- 账号名搜索框 -->
      <div class="al-search-box">
        <svg class="al-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input
          v-model="searchQuery"
          class="al-search-input"
          placeholder="搜索账号名称..."
          @input="onSearchInput"
        />
        <button v-if="searchQuery" class="al-search-clear" @click="clearSearch">✕</button>
      </div>
      <div class="al-filter-flags">
        <button
          class="al-flag-filter-btn"
          :class="{ active: filterFlagId === null }"
          @click="handleFilterFlag(null)"
        >全部</button>
        <template v-for="flag in visibleFilterFlags" :key="flag.id">
          <button
            class="al-flag-filter-btn"
            :class="{ active: filterFlagId === flag.id, 'is-pinned': flag.is_pinned }"
            :style="filterFlagId === flag.id && flag.color ? { background: flag.color, borderColor: flag.color, color: '#fff' } : flag.color ? { borderColor: flag.color, color: flag.color } : {}"
            @click="handleFilterFlag(flag.id)"
          >
            <svg v-if="flag.is_pinned" width="10" height="10" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0"><path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5v6h2v-6h5v-2l-2-2z"/></svg>
            <span class="al-flag-dot" v-else :style="flag.color ? { background: flag.color } : {}"></span>
            {{ flag.name }}
          </button>
        </template>
        <button v-if="hasMoreFlags" class="al-flag-expand-btn" @click="flagBarExpanded = !flagBarExpanded">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <polyline v-if="flagBarExpanded" points="18 15 12 9 6 15"/>
            <polyline v-else points="6 9 12 15 18 9"/>
          </svg>
          {{ flagBarExpanded ? '收起' : `展开全部 (${allFlags.length})` }}
        </button>
        <button class="al-flag-manage-btn" @click="openFlagManager">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          管理标识
        </button>
      </div>

      <!-- 字段筛选行 -->
      <div class="al-col-filters">
        <select class="al-col-filter-select" v-model="filterGender" @change="onFilterChange">
          <option value="">性别 · 全部</option>
          <option value="female">女</option>
          <option value="male">男</option>
          <option value="unisex">中性</option>
        </select>
        <select class="al-col-filter-select" v-model="filterAccountType" @change="onFilterChange">
          <option value="">类型 · 全部</option>
          <option value="exclusive">独享号</option>
          <option value="shared">共享号</option>
          <option value="persona">人设号</option>
        </select>
        <select class="al-col-filter-select" v-model="filterFaceMode" @change="onFilterChange">
          <option value="">面孔 · 全部</option>
          <option value="face">人脸</option>
          <option value="no_face">非人脸</option>
        </select>
        <select class="al-col-filter-select" v-model="filterPlatformBindingStatus" @change="onFilterChange">
          <option value="">平台绑定 · 全部</option>
          <option value="bound">已绑定</option>
          <option value="confirmed">已确认</option>
          <option value="reserved">已预留</option>
          <option value="unbound">未绑定</option>
        </select>
        <button v-if="hasActiveColFilters" class="al-col-filter-clear" @click="clearColFilters">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          清除筛选
        </button>
      </div>

      <!-- 多选批量操作栏 -->
      <transition name="bulk-bar">
        <div v-if="selectedIds.size > 0" class="al-bulk-bar">
          <span class="al-bulk-count">已选 {{ selectedIds.size }} 个</span>
          <button class="al-bulk-action-btn is-bind" @click="openBulkFlagDialog('bind')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
            批量绑定标识
          </button>
          <button class="al-bulk-action-btn is-unbind" @click="openBulkFlagDialog('unbind')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            批量移除标识
          </button>
          <button class="al-bulk-clear-btn" @click="clearSelection">取消选择</button>
        </div>
      </transition>
    </div>

    <!-- Table list -->
    <div v-loading="loading" class="al-table-wrap">
      <div class="al-table-scroll">
      <table class="al-table">
        <thead>
          <tr>
            <th class="al-th al-th-check">
              <input
                type="checkbox"
                class="al-checkbox"
                :checked="allSelected"
                :indeterminate="someSelected"
                @change="e => toggleSelectAll(e.target.checked)"
              />
            </th>
            <th class="al-th al-th-media">头像 / 照片</th>
            <th class="al-th al-th-name">账号名称</th>
            <th class="al-th al-th-platform">平台绑定</th>
            <th class="al-th al-th-stat al-th-sortable" @click="toggleSort('followers_count')">
              <span class="al-th-label">粉丝数</span>
              <span class="al-sort-icon"><SortIcon field="followers_count" :sort-by="sortBy" :sort-order="sortOrder" /></span>
            </th>
            <th class="al-th al-th-stat al-th-sortable" @click="toggleSort('total_views')">
              <span class="al-th-label">总 Views</span>
              <span class="al-sort-icon"><SortIcon field="total_views" :sort-by="sortBy" :sort-order="sortOrder" /></span>
            </th>
            <th class="al-th al-th-stat al-th-sortable" @click="toggleSort('avg_views')">
              <span class="al-th-label">均 Views</span>
              <span class="al-sort-icon"><SortIcon field="avg_views" :sort-by="sortBy" :sort-order="sortOrder" /></span>
            </th>
            <th class="al-th al-th-stat al-th-sortable" @click="toggleSort('avg_like_rate')">
              <span class="al-th-label">点赞率</span>
              <span class="al-sort-icon"><SortIcon field="avg_like_rate" :sort-by="sortBy" :sort-order="sortOrder" /></span>
            </th>
            <th class="al-th al-th-date al-th-sortable" @click="toggleSort('latest_video_published_at')">
              <span class="al-th-label">最新发布</span>
              <span class="al-sort-icon"><SortIcon field="latest_video_published_at" :sort-by="sortBy" :sort-order="sortOrder" /></span>
            </th>
            <th class="al-th al-th-flags">标识</th>
            <th class="al-th al-th-tags">标签 / 博主</th>
            <th class="al-th al-th-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in items"
            :key="item.id"
            class="al-tr"
            :class="{ 'is-selected': selectedIds.has(item.id) }"
            @click="goToDetail(item)"
          >
            <!-- 多选 -->
            <td class="al-td al-td-check" @click.stop>
              <input
                type="checkbox"
                class="al-checkbox"
                :checked="selectedIds.has(item.id)"
                @change="() => toggleSelectItem(item.id)"
              />
            </td>

            <!-- 头像/照片 -->
            <td class="al-td al-td-media" @click.stop>
              <div class="al-media-cell">
                <div class="al-photo-wrap" @click="previewMedia(item, 'photo')">
                  <img v-if="item.photo_url" :src="item.photo_url" class="al-photo-img" />
                  <div v-else class="al-photo-ph">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.7"><path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14l-5.5-5.5a2 2 0 0 0-2.828 0L4 21V5z"/><circle cx="15" cy="9" r="2"/></svg>
                  </div>
                </div>
                <div class="al-avatar-wrap" @click="previewMedia(item, 'avatar')">
                  <img v-if="item.avatar_url" :src="item.avatar_url" class="al-avatar-img" />
                  <div v-else class="al-avatar-ph">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                  </div>
                </div>
                <span v-if="item.pending_publish_count" class="al-pending-badge" :title="`队列中 ${item.pending_publish_count} 条`">{{ item.pending_publish_count }}</span>
              </div>
            </td>

            <!-- 账号名称 -->
            <td class="al-td al-td-name">
              <div class="al-name-main">{{ item.account_name }}</div>
              <div v-if="item.account_handle || item.account_signature" class="al-name-handle">
                <span v-if="item.account_handle" class="al-handle">@{{ item.account_handle }}</span>
                <span v-if="item.account_signature" class="al-signature">{{ item.account_signature }}</span>
              </div>
              <div class="al-name-meta">
                <span class="ac-type-badge" :class="`ac-type-${item.account_type || 'exclusive'}`">
                  {{ item.account_type === 'persona' ? '人设号' : item.account_type === 'exclusive' ? '独享号' : '共享号' }}
                </span>
                <span
                  class="ac-type-badge ac-face-badge"
                  :class="item.face_mode === 'no_face' ? 'ac-face-no' : 'ac-face-yes'"
                  style="cursor:pointer"
                  @click.stop="toggleFaceMode(item)"
                >
                  {{ item.face_mode === 'no_face' ? '非人脸' : '人脸' }}
                </span>
                <span
                  class="ac-type-badge"
                  :class="`ac-gender-${item.gender || 'female'}`"
                  style="cursor:pointer"
                  @click.stop="cycleGender(item)"
                >
                  {{ { male: '男', female: '女', unisex: '中性' }[item.gender || 'female'] }}
                </span>
                <span v-if="item.ai_generation_status && item.ai_generation_status !== 'idle'" class="ac-ai-status" :class="`is-${item.ai_generation_status}`">
                  {{ aiGenerationStatusLabel(item.ai_generation_status) }}
                </span>
              </div>
              <div v-if="item.style_description" class="al-style-desc">{{ item.style_description }}</div>
            </td>

            <!-- 平台绑定 -->
            <td class="al-td al-td-platform">
              <div v-if="item.channel_reservations?.length" class="al-bindings">
                <template v-for="reservation in boundChannelReservations(item)" :key="`bound-${reservation.id}`">
                  <span
                    class="ac-tag"
                    :class="[`ac-tag-${reservation.platform}`, reservation.channel_status === 'disabled' ? 'ac-tag-disabled' : '']"
                    :title="reservation.channel_status === 'disabled' ? reservationBoundLabel(reservation) + '（已禁用）' : reservationBoundLabel(reservation)"
                  >
                    <svg v-if="reservation.channel_status === 'disabled'" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:2px;flex-shrink:0"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    {{ reservationBoundLabel(reservation) }}
                  </span>
                </template>
                <span
                  v-for="reservation in unboundChannelReservations(item)"
                  :key="`reservation-${reservation.id}`"
                  class="ac-tag ac-tag-reserved"
                  :title="reservationDisplayLabel(reservation)"
                >{{ reservationDisplayLabel(reservation) }}</span>
              </div>
              <span v-else class="al-no-binding">未绑定</span>
            </td>

            <!-- 粉丝数 -->
            <td class="al-td al-td-stat">{{ formatCount(snapshotValue(item, 'followers_count')) }}</td>

            <!-- 总 Views -->
            <td class="al-td al-td-stat">{{ formatCount(snapshotValue(item, 'total_views')) }}</td>

            <!-- 均 Views -->
            <td class="al-td al-td-stat">{{ formatCount(snapshotValue(item, 'avg_views')) }}</td>

            <!-- 点赞率 -->
            <td class="al-td al-td-stat">{{ formatPercent(snapshotValue(item, 'avg_like_rate')) }}</td>

            <!-- 最新发布 -->
            <td class="al-td al-td-date">{{ formatSnapshotDate(snapshotValue(item, 'latest_video_published_at')) }}</td>

            <!-- 标识 -->
            <td class="al-td al-td-flags">
              <div v-if="item.bound_flags?.length" class="al-flags-wrap">
                <span v-for="flag in item.bound_flags" :key="flag.id" class="ac-flag-chip" :style="flag.color ? { background: flag.color + '22', borderColor: flag.color + '66', color: flag.color } : {}">
                  <span class="ac-flag-dot" :style="flag.color ? { background: flag.color } : {}"></span>
                  {{ flag.name }}
                </span>
              </div>
              <span v-else class="al-no-binding">—</span>
            </td>

            <!-- 标签 / 博主 -->
            <td class="al-td al-td-tags">
              <div v-if="item.bound_tags?.length" class="al-tags-wrap">
                <span v-for="tag in item.bound_tags" :key="tag.id" class="ac-tag-chip">
                  <span class="ac-tag-dot" :style="tag.color ? { background: tag.color } : {}"></span>
                  {{ tag.name }}
                </span>
              </div>
              <div v-if="item.tiktok_bloggers?.length" class="al-bloggers-wrap">
                <span
                  v-for="blogger in item.tiktok_bloggers"
                  :key="blogger.id"
                  class="ac-blogger-chip"
                  :title="blogger.blogger_name + (blogger.blogger_handle ? ' @' + blogger.blogger_handle : '')"
                >
                  <img v-if="blogger.avatar_url" :src="blogger.avatar_url" class="ac-blogger-avatar" />
                  <div v-else class="ac-blogger-avatar ac-blogger-avatar-ph">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                  </div>
                  <span class="ac-blogger-name">{{ blogger.blogger_name }}</span>
                </span>
              </div>
              <!-- Hashtags -->
              <div v-if="item.hashtags?.length" class="al-hashtags-wrap">
                <span v-for="tag in item.hashtags.slice(0, 5)" :key="tag" class="al-hashtag-chip">#{{ tag }}</span>
                <span v-if="item.hashtags.length > 5" class="al-hashtag-chip al-hashtag-more">+{{ item.hashtags.length - 5 }}</span>
              </div>
              <span v-if="!item.bound_tags?.length && !item.tiktok_bloggers?.length && !item.hashtags?.length" class="al-no-binding">—</span>
            </td>

            <!-- 操作 -->
            <td class="al-td al-td-actions" @click.stop>
              <div class="al-row-actions">
                <button class="ac-btn ac-btn-stats" @click="$router.push({ name: 'publication-stats', query: { account_id: item.id } })">统计</button>
                <button class="ac-btn ac-btn-sync" :class="{ loading: syncingId === item.id }" @click="handleSyncAccount(item)">{{ syncingId === item.id ? '同步中' : '同步' }}</button>
                <button class="ac-btn ac-btn-edit" @click="$router.push(`/dashboard/accounts/${item.id}/edit`)">编辑</button>
                <button class="ac-btn ac-btn-del" :class="{ loading: deleting === item.id }" @click="handleDelete(item)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      </div><!-- end al-table-scroll -->
    </div>

    <!-- Flag 管理弹窗 -->
    <el-dialog
      v-model="showFlagManagerDialog"
      title="管理标识"
      width="520px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="fm-body">
        <!-- 新建 / 编辑表单 -->
        <div class="fm-form">
          <div class="fm-form-title">{{ editingFlag ? '编辑标识' : '新建标识' }}</div>
          <div class="fm-form-row">
            <input
              v-model="flagForm.name"
              class="fm-input"
              placeholder="标识名称"
              maxlength="100"
              @keyup.enter="saveFlagForm"
            />
            <div class="fm-color-picker">
              <div
                class="fm-color-preview"
                :style="{ background: flagForm.color || '#e2e8f0' }"
                :title="flagForm.color"
              ></div>
              <div class="fm-color-swatches">
                <button
                  v-for="c in FLAG_COLORS"
                  :key="c"
                  class="fm-swatch"
                  :class="{ active: flagForm.color === c }"
                  :style="{ background: c }"
                  @click="flagForm.color = c"
                ></button>
              </div>
            </div>
          </div>
          <label class="fm-pin-toggle">
            <input type="checkbox" v-model="flagForm.is_pinned" class="fm-pin-checkbox" />
            <span class="fm-pin-label">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5v6h2v-6h5v-2l-2-2z"/></svg>
              设为快捷标签（固定显示在过滤栏最前面）
            </span>
          </label>
          <div class="fm-form-actions">
            <button v-if="editingFlag" class="fm-cancel-btn" @click="cancelEditFlag">取消</button>
            <button class="fm-save-btn" :disabled="flagSaving" @click="saveFlagForm">
              {{ flagSaving ? '保存中…' : editingFlag ? '更新' : '创建' }}
            </button>
          </div>
        </div>

        <!-- 已有标识列表 -->
        <div class="fm-list">
          <div v-if="pinnedFlags.length > 0" class="fm-group">
            <div class="fm-group-label">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5v6h2v-6h5v-2l-2-2z"/></svg>
              快捷标签
            </div>
            <div v-for="flag in pinnedFlags" :key="flag.id" class="fm-item is-pinned">
              <span class="fm-item-dot" :style="flag.color ? { background: flag.color } : {}"></span>
              <span class="fm-item-name">{{ flag.name }}</span>
              <div class="fm-item-actions">
                <button class="fm-edit-btn" @click="startEditFlag(flag)">编辑</button>
                <button class="fm-del-btn" :class="{ loading: flagDeletingId === flag.id }" @click="handleDeleteFlag(flag)">删除</button>
              </div>
            </div>
          </div>
          <div v-if="unpinnedFlags.length > 0" class="fm-group">
            <div class="fm-group-label">全部标识（{{ unpinnedFlags.length }}）</div>
            <div v-for="flag in unpinnedFlags" :key="flag.id" class="fm-item">
              <span class="fm-item-dot" :style="flag.color ? { background: flag.color } : {}"></span>
              <span class="fm-item-name">{{ flag.name }}</span>
              <div class="fm-item-actions">
                <button class="fm-edit-btn" @click="startEditFlag(flag)">编辑</button>
                <button class="fm-del-btn" :class="{ loading: flagDeletingId === flag.id }" @click="handleDeleteFlag(flag)">删除</button>
              </div>
            </div>
          </div>
          <div v-if="allFlags.length === 0" class="fm-empty">暂无标识</div>
        </div>
      </div>
    </el-dialog>

    <!-- 批量绑定/移除标识弹窗 -->
    <el-dialog
      v-model="showBulkFlagDialog"
      :title="bulkFlagMode === 'bind' ? `批量绑定标识（已选 ${selectedIds.size} 个账号）` : `批量移除标识（已选 ${selectedIds.size} 个账号）`"
      width="460px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="bfd-body">
        <div class="bfd-hint">{{ bulkFlagMode === 'bind' ? '选择要绑定到选中账号的标识：' : '选择要从选中账号移除的标识：' }}</div>
        <div class="bfd-flags">
          <label
            v-for="flag in allFlags"
            :key="flag.id"
            class="bfd-flag-item"
            :class="{ selected: bulkFlagSelectedIds.includes(flag.id) }"
          >
            <input type="checkbox" :value="flag.id" v-model="bulkFlagSelectedIds" class="bfd-checkbox" />
            <span class="bfd-flag-dot" :style="flag.color ? { background: flag.color } : {}"></span>
            <span class="bfd-flag-name">{{ flag.name }}</span>
          </label>
        </div>
        <div v-if="allFlags.length === 0" class="bfd-empty">暂无标识，请先在「管理标识」中创建</div>
      </div>
      <template #footer>
        <el-button @click="showBulkFlagDialog = false">取消</el-button>
        <el-button
          :type="bulkFlagMode === 'bind' ? 'primary' : 'danger'"
          :loading="bulkFlagSaving"
          @click="handleBulkFlagSubmit"
        >
          {{ bulkFlagMode === 'bind' ? '确认绑定' : '确认移除' }}
        </el-button>
      </template>
    </el-dialog>

    <el-empty v-if="!loading && items.length === 0" description="暂无账号，点击「新建账号」开始" :image-size="80" />

    <el-dialog
      v-model="previewVisible"
      width="min(92vw, 960px)"
      top="5vh"
      append-to-body
      class="ac-preview-dialog"
    >
      <img v-if="previewImage.url" :src="previewImage.url" :alt="previewImage.title" class="ac-preview-image" />
      <template #header>
        <div class="ac-preview-title">{{ previewImage.title }}</div>
      </template>
    </el-dialog>

    <!-- Footer pagination -->
    <div v-if="total > 0" class="al-footer">
      <div class="al-pagination-left">
        <span class="al-count-text">显示 {{ startIdx }}-{{ endIdx }} 共 {{ total }} 条</span>
        <select v-model="pageSize" @change="handleSizeChange(pageSize)" class="al-simple-select">
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="500">500</option>
        </select>
      </div>
      <div class="al-pagination">
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
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bulkGenerateAIAccounts, bulkResumeAIAccountGeneration, fetchAccounts, deleteAccount, updateScheduledPublish, supplementTemplates, bulkGenerateVideoTasks, patchAccount, bulkGenerateNameHandle, bulkSearchHashtags, exportVideoUrls } from '../api/accounts'
import { fetchFlags, createFlag, updateFlag, deleteFlag, bulkBindFlags, bulkUnbindFlags } from '../api/flags'
import { syncAccountSnapshots } from '../api/video_publications'
import { isDuplicateRequestError } from '../api/http'
import { fetchPipelineSettings, updatePipelineSettings } from '../api/settings'
import { downloadLatestPublishedVideos } from '../api/video_tasks'

const route = useRoute()
const router = useRouter()

const PLATFORM_LABELS = { youtube: 'YouTube', tiktok: 'TikTok', instagram: 'Instagram' }

// ── Sort icon component ───────────────────────────────────────────────────────
const SortIcon = defineComponent({
  props: { field: String, sortBy: String, sortOrder: String },
  setup(props) {
    return () => {
      const active = props.sortBy === props.field
      const desc = props.sortOrder === 'desc'
      const color = active ? '#6366f1' : '#cbd5e1'
      return h('svg', { width: 10, height: 12, viewBox: '0 0 10 12', fill: 'none', style: 'flex-shrink:0' }, [
        h('path', { d: 'M5 1L2 4h6L5 1z', fill: active && !desc ? '#6366f1' : color }),
        h('path', { d: 'M5 11L2 8h6L5 11z', fill: active && desc ? '#6366f1' : color }),
      ])
    }
  },
})

// ── Sort state ────────────────────────────────────────────────────────────────
const sortBy = ref(null)
const sortOrder = ref('desc')

function toggleSort(field) {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = field
    sortOrder.value = 'desc'
  }
  page.value = 1
  loadData()
}

// ── Column filters ────────────────────────────────────────────────────────────
const filterGender = ref('')
const filterAccountType = ref('')
const filterFaceMode = ref('')
const filterPlatformBindingStatus = ref('')

const hasActiveColFilters = computed(() =>
  filterGender.value || filterAccountType.value || filterFaceMode.value || filterPlatformBindingStatus.value
)

function onFilterChange() {
  page.value = 1
  loadData()
}

function clearColFilters() {
  filterGender.value = ''
  filterAccountType.value = ''
  filterFaceMode.value = ''
  filterPlatformBindingStatus.value = ''
  page.value = 1
  loadData()
}

const loading = ref(false)
const deleting = ref(null)

// 下载视频
const downloading = ref(false)

async function handleDownload() {
  if (downloading.value) return
  downloading.value = true
  try {
    const ids = selectedMap.value.size > 0 ? [...selectedMap.value.keys()] : null
    const blob = await downloadLatestPublishedVideos(ids)
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = 'videos_latest.zip'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(blobUrl), 10000)
    ElMessage.success('打包完成，已开始下载')
  } catch (e) {
    let errText = ''
    if (e?.response?.data instanceof Blob) {
      errText = await e.response.data.text().catch(() => '')
    } else if (typeof e?.response?.data === 'string') {
      errText = e.response.data
    }
    const detail = errText ? (JSON.parse(errText).detail || errText) : (e?.message || '')
    ElMessage.error(detail.includes('没有已发布') ? '暂无已发布的视频' : '下载失败，请稍后重试')
  } finally {
    downloading.value = false
  }
}
const exporting = ref(false)

async function handleExportVideoUrls() {
  if (exporting.value) return
  exporting.value = true
  try {
    const ids = selectedMap.value.size > 0 ? [...selectedMap.value.keys()] : null
    const blob = await exportVideoUrls(ids)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'ai_blogger_videos.xlsx'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 10000)
    ElMessage.success('导出成功')
  } catch (e) {
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

const syncingId = ref(null)

async function handleSyncAccount(item) {
  if (syncingId.value) return
  syncingId.value = item.id
  try {
    const r = await syncAccountSnapshots(item.id)
    ElMessage.success(r?.message || '同步任务已提交')
    await loadData()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '同步失败')
  } finally {
    syncingId.value = null
  }
}

const bulkGenerating = ref(false)
const bulkRestarting = ref(false)
const showBulkContinueDialog = ref(false)
const bulkResumeStage = ref('current')
const items = ref([])
const previewVisible = ref(false)
const previewImage = ref({ url: '', title: '' })
const total = ref(0)
const page = ref(Number(route.query.page) || 1)
const pageSize = ref(20)

// ── 多选（跨页）────────────────────────────────────────────────────────────────
// Map<id, account对象> 跨页保留完整 account 信息
const selectedMap = ref(new Map())
const selectedIds = computed(() => new Set(selectedMap.value.keys()))

// ── Flag 相关 ─────────────────────────────────────────────────────────────────
const allFlags = ref([])
const filterFlagId = ref(null)
const searchQuery = ref('')
let _searchTimer = null
const flagBarExpanded = ref(false)
const FLAG_BAR_LIMIT = 20

const pinnedFlags = computed(() => allFlags.value.filter(f => f.is_pinned))
const unpinnedFlags = computed(() => allFlags.value.filter(f => !f.is_pinned))
// 过滤栏显示：快捷标签全显，其余按展开状态截断
const visibleFilterFlags = computed(() => {
  const pinned = pinnedFlags.value
  const unpinned = unpinnedFlags.value
  if (flagBarExpanded.value) return [...pinned, ...unpinned]
  const remain = FLAG_BAR_LIMIT - pinned.length
  return [...pinned, ...unpinned.slice(0, Math.max(0, remain))]
})
const hasMoreFlags = computed(() =>
  allFlags.value.length > FLAG_BAR_LIMIT ||
  (pinnedFlags.value.length < FLAG_BAR_LIMIT && unpinnedFlags.value.length > FLAG_BAR_LIMIT - pinnedFlags.value.length)
)

// Flag 管理弹窗
const showFlagManagerDialog = ref(false)
const flagForm = ref({ name: '', color: '#6366f1', is_pinned: false })
const editingFlag = ref(null)
const flagSaving = ref(false)
const flagDeletingId = ref(null)

const FLAG_COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#ef4444', '#f97316',
  '#eab308', '#22c55e', '#10b981', '#06b6d4', '#3b82f6',
  '#64748b', '#0f172a',
]

async function loadFlags() {
  try {
    allFlags.value = await fetchFlags()
  } catch { /* silent */ }
}

function openFlagManager() {
  flagForm.value = { name: '', color: '#6366f1', is_pinned: false }
  editingFlag.value = null
  showFlagManagerDialog.value = true
}

function startEditFlag(flag) {
  editingFlag.value = flag
  flagForm.value = { name: flag.name, color: flag.color || '#6366f1', is_pinned: !!flag.is_pinned }
}

function cancelEditFlag() {
  editingFlag.value = null
  flagForm.value = { name: '', color: '#6366f1', is_pinned: false }
}

async function saveFlagForm() {
  if (!flagForm.value.name.trim()) {
    ElMessage.warning('请输入标识名称')
    return
  }
  flagSaving.value = true
  try {
    if (editingFlag.value) {
      const updated = await updateFlag(editingFlag.value.id, {
        name: flagForm.value.name.trim(),
        color: flagForm.value.color || null,
        is_pinned: flagForm.value.is_pinned,
      })
      const idx = allFlags.value.findIndex(f => f.id === updated.id)
      if (idx >= 0) allFlags.value[idx] = updated
      // 重新排序：pinned 在前
      allFlags.value.sort((a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0) || new Date(a.created_at) - new Date(b.created_at))
      cancelEditFlag()
      ElMessage.success('已更新')
    } else {
      const created = await createFlag({
        name: flagForm.value.name.trim(),
        color: flagForm.value.color || null,
        is_pinned: flagForm.value.is_pinned,
      })
      allFlags.value.push(created)
      allFlags.value.sort((a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0) || new Date(a.created_at) - new Date(b.created_at))
      flagForm.value = { name: '', color: '#6366f1', is_pinned: false }
      ElMessage.success('已创建')
    }
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  } finally {
    flagSaving.value = false
  }
}

async function handleDeleteFlag(flag) {
  try {
    await ElMessageBox.confirm(`确定删除标识「${flag.name}」？`, '删除确认', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
  } catch { return }
  flagDeletingId.value = flag.id
  try {
    await deleteFlag(flag.id)
    allFlags.value = allFlags.value.filter(f => f.id !== flag.id)
    if (filterFlagId.value === flag.id) {
      filterFlagId.value = null
      loadData()
    }
    ElMessage.success('已删除')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    flagDeletingId.value = null
  }
}

// 批量绑定 flag 弹窗
const showBulkFlagDialog = ref(false)
const bulkFlagMode = ref('bind') // 'bind' | 'unbind'
const bulkFlagSelectedIds = ref([])
const bulkFlagSaving = ref(false)

// 批量生成名称/Handle/签名
const bulkNameHandleLoading = ref(false)

async function confirmBulkNameHandle() {
  if (bulkNameHandleLoading.value) return
  bulkNameHandleLoading.value = true
  try {
    const ids = selectedMap.value.size > 0 ? [...selectedMap.value.keys()] : null
    const result = await bulkGenerateNameHandle(ids)
    ElMessage.success(`已入队 ${result.queued_count} 个账号，生成完成后请刷新列表查看`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  } finally {
    bulkNameHandleLoading.value = false
  }
}

// 标签搜索
const showHashtagSearchDialog = ref(false)
const hashtagSearchLoading = ref(false)
const hashtagBindMode = ref('replace')

function openHashtagSearchDialog() {
  showHashtagSearchDialog.value = true
}

async function startHashtagSearch() {
  if (hashtagSearchLoading.value) return
  hashtagSearchLoading.value = true
  try {
    const ids = selectedMap.value.size > 0 ? [...selectedMap.value.keys()] : null
    await bulkSearchHashtags(ids, hashtagBindMode.value)
    ElMessage.success('标签搜索任务已入队，完成后将自动绑定到账号，请稍后刷新查看')
    showHashtagSearchDialog.value = false
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '操作失败，请检查 Apify Token 和博主绑定配置')
  } finally {
    hashtagSearchLoading.value = false
  }
}

function openBulkFlagDialog(mode) {
  if (selectedIds.value.size === 0) {
    ElMessage.warning('请先勾选账号')
    return
  }
  bulkFlagMode.value = mode
  bulkFlagSelectedIds.value = []
  showBulkFlagDialog.value = true
}

async function handleBulkFlagSubmit() {
  if (bulkFlagSelectedIds.value.length === 0) {
    ElMessage.warning('请选择至少一个标识')
    return
  }
  bulkFlagSaving.value = true
  try {
    const accountIds = [...selectedIds.value]
    if (bulkFlagMode.value === 'bind') {
      await bulkBindFlags(accountIds, bulkFlagSelectedIds.value)
      ElMessage.success(`已为 ${accountIds.length} 个账号绑定标识`)
    } else {
      await bulkUnbindFlags(accountIds, bulkFlagSelectedIds.value)
      ElMessage.success(`已从 ${accountIds.length} 个账号移除标识`)
    }
    showBulkFlagDialog.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '操作失败')
  } finally {
    bulkFlagSaving.value = false
  }
}

// 多选（跨页保留）
function toggleSelectAll(checked) {
  const next = new Map(selectedMap.value)
  if (checked) {
    items.value.forEach(i => next.set(i.id, i))
  } else {
    // 只取消当前页的选中
    items.value.forEach(i => next.delete(i.id))
  }
  selectedMap.value = next
}

function toggleSelectItem(id) {
  const next = new Map(selectedMap.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    const item = items.value.find(i => i.id === id)
    if (item) next.set(id, item)
  }
  selectedMap.value = next
}

function clearSelection() {
  selectedMap.value = new Map()
}

const allSelected = computed(() =>
  items.value.length > 0 && items.value.every(i => selectedIds.value.has(i.id))
)
const someSelected = computed(() =>
  items.value.some(i => selectedIds.value.has(i.id)) && !allSelected.value
)

function syncUrl() {
  const query = {}
  if (page.value > 1) query.page = String(page.value)
  if (filterFlagId.value) query.flag_id = filterFlagId.value
  router.replace({ query })
}

function handleFilterFlag(flagId) {
  filterFlagId.value = flagId
  page.value = 1
  jumpPage.value = 1
  syncUrl()
  loadData()
}

function onSearchInput() {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(() => {
    page.value = 1
    jumpPage.value = 1
    loadData()
  }, 300)
}

function clearSearch() {
  searchQuery.value = ''
  page.value = 1
  jumpPage.value = 1
  loadData()
}

// AI 博主配置弹窗
const showAISettingsDialog = ref(false)
const aiSettingsLoading = ref(false)
const aiSettingsSaving = ref(false)
const aiSettingsForm = ref({
  _pipeline: null,
  ai_account_analysis_sample_size: 10,
  ai_account_video_prompt: '',
  ai_account_video_model: 'gemini-3.1-pro-preview',
  ai_account_name_prompt: '',
  ai_account_name_model: 'gemini-3.1-pro-preview',
  ai_account_avatar_prompt: '',
  ai_account_avatar_model: 'gemini-3.1-flash-image-preview',
  ai_account_avatar_size: '1:1',
  ai_account_avatar_quality: '1K',
  ai_account_photo_image_prompt: '',
  ai_account_exclusive_name_prompt: '',
  ai_account_shared_name_prompt: '',
  hashtag_search_top_n: 100,
  hashtag_filter_model: 'gemini-3.1-pro-preview',
  hashtag_filter_prompt: '',
})

async function openAISettings() {
  showAISettingsDialog.value = true
  aiSettingsLoading.value = true
  try {
    const data = await fetchPipelineSettings()
    aiSettingsForm.value._pipeline = data
    aiSettingsForm.value.ai_account_analysis_sample_size = data.ai_account_analysis_sample_size ?? 10
    aiSettingsForm.value.ai_account_video_prompt = data.ai_account_video_prompt || ''
    aiSettingsForm.value.ai_account_video_model = data.ai_account_video_model || 'gemini-3.1-pro-preview'
    aiSettingsForm.value.ai_account_name_prompt = data.ai_account_name_prompt || ''
    aiSettingsForm.value.ai_account_name_model = data.ai_account_name_model || 'gemini-3.1-pro-preview'
    aiSettingsForm.value.ai_account_avatar_prompt = data.ai_account_avatar_prompt || ''
    aiSettingsForm.value.ai_account_avatar_model = data.ai_account_avatar_model || 'gemini-3.1-flash-image-preview'
    aiSettingsForm.value.ai_account_avatar_size = data.ai_account_avatar_size || '1:1'
    aiSettingsForm.value.ai_account_avatar_quality = data.ai_account_avatar_quality || '1K'
    aiSettingsForm.value.ai_account_photo_image_prompt = data.ai_account_photo_image_prompt || ''
    aiSettingsForm.value.ai_account_exclusive_name_prompt = data.ai_account_exclusive_name_prompt || ''
    aiSettingsForm.value.ai_account_shared_name_prompt = data.ai_account_shared_name_prompt || ''
    aiSettingsForm.value.hashtag_search_top_n = data.hashtag_search_top_n ?? 100
    aiSettingsForm.value.hashtag_filter_model = data.hashtag_filter_model || 'gemini-3.1-pro-preview'
    aiSettingsForm.value.hashtag_filter_prompt = data.hashtag_filter_prompt || ''
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '加载配置失败')
  } finally {
    aiSettingsLoading.value = false
  }
}

async function saveAISettings() {
  if (aiSettingsSaving.value) return
  aiSettingsSaving.value = true
  try {
    const base = aiSettingsForm.value._pipeline || {}
    const payload = {
      ...base,
      ai_account_analysis_sample_size: aiSettingsForm.value.ai_account_analysis_sample_size,
      ai_account_video_prompt: aiSettingsForm.value.ai_account_video_prompt,
      ai_account_video_model: aiSettingsForm.value.ai_account_video_model,
      ai_account_name_prompt: aiSettingsForm.value.ai_account_name_prompt,
      ai_account_name_model: aiSettingsForm.value.ai_account_name_model,
      ai_account_avatar_prompt: aiSettingsForm.value.ai_account_avatar_prompt,
      ai_account_avatar_model: aiSettingsForm.value.ai_account_avatar_model,
      ai_account_avatar_size: aiSettingsForm.value.ai_account_avatar_size,
      ai_account_avatar_quality: aiSettingsForm.value.ai_account_avatar_quality,
      ai_account_photo_image_prompt: aiSettingsForm.value.ai_account_photo_image_prompt,
      ai_account_exclusive_name_prompt: aiSettingsForm.value.ai_account_exclusive_name_prompt,
      ai_account_shared_name_prompt: aiSettingsForm.value.ai_account_shared_name_prompt,
      hashtag_search_top_n: aiSettingsForm.value.hashtag_search_top_n,
      hashtag_filter_model: aiSettingsForm.value.hashtag_filter_model,
      hashtag_filter_prompt: aiSettingsForm.value.hashtag_filter_prompt,
    }
    await updatePipelineSettings(payload)
    ElMessage.success('配置已保存')
    showAISettingsDialog.value = false
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '保存失败')
  } finally {
    aiSettingsSaving.value = false
  }
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const startIdx = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const endIdx = computed(() => Math.min(page.value * pageSize.value, total.value))
const jumpPage = ref(page.value)

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

function platformLabel(p) { return PLATFORM_LABELS[p] || p }
function bindingDisplayLabel(binding) {
  const platform = platformLabel(binding.platform)
  const channelName = binding.channel_name?.trim()
  const channelId = binding.channel_id?.trim()
  return channelName ? `${platform} · ${channelName}` : channelId ? `${platform} · ${channelId}` : platform
}
function boundChannelReservations(item) {
  return (item.channel_reservations || []).filter(r => r?.status === 'bound')
}
function unboundChannelReservations(item) {
  return (item.channel_reservations || []).filter(r => r?.platform && r?.status !== 'bound')
}
function reservationBoundLabel(reservation) {
  const platform = platformLabel(reservation.platform)
  const channelName = reservation.channel_name?.trim()
  const channelId = reservation.channel_id?.trim()
  return channelName ? `${platform} · ${channelName}` : channelId ? `${platform} · ${channelId}` : platform
}
function reservationDisplayLabel(reservation) {
  const platform = platformLabel(reservation.platform)
  const statusMap = { reserved: '已占位', confirmed: '已确认', bound: '已绑定' }
  return `${platform} · ${statusMap[reservation.status] || reservation.status || '已占位'}`
}
function snapshotValue(item, key) {
  return item?.performance_snapshot?.[key]
}
function aiGenerationStatusLabel(status) {
  const map = {
    pending: '排队中',
    video_analyzing: '分析视频',
    name_generating: '生成名称',
    photo_generating: '生成照片候选',
    awaiting_photo_selection: '待选照片',
    avatar_generating: '生成头像',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

function formatCount(value) {
  if (value == null || value === '') return '-'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(Math.round(n))
}

function formatPercent(value) {
  if (value == null || value === '') return '-'
  const n = Number(value)
  if (Number.isNaN(n)) return String(value)
  return `${n.toFixed(1)}%`
}

function formatSnapshotDate(value) {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

function previewMedia(item, type) {
  const isAvatar = type === 'avatar'
  const url = isAvatar ? item.avatar_url : item.photo_url
  if (!url) return
  previewImage.value = {
    url,
    title: `${item.account_name}${isAvatar ? '头像' : '照片'}`
  }
  previewVisible.value = true
}

function goToDetail(item) {
  router.push(`/dashboard/accounts/${item.id}`)
}

async function loadData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterFlagId.value) params.flag_id = filterFlagId.value
    if (searchQuery.value.trim()) params.search = searchQuery.value.trim()
    if (sortBy.value) { params.sort_by = sortBy.value; params.sort_order = sortOrder.value }
    if (filterGender.value) params.gender = filterGender.value
    if (filterAccountType.value) params.account_type = filterAccountType.value
    if (filterFaceMode.value) params.face_mode = filterFaceMode.value
    if (filterPlatformBindingStatus.value) params.platform_binding_status = filterPlatformBindingStatus.value
    const data = await fetchAccounts(params)
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

function openBulkContinueDialog() {
  if (bulkRestarting.value) return
  showBulkContinueDialog.value = true
}

async function handleBulkContinueAIGeneration() {
  if (bulkRestarting.value) return

  bulkRestarting.value = true
  try {
    const ids = selectedMap.value.size > 0 ? [...selectedMap.value.keys()] : null
    const result = await bulkResumeAIAccountGeneration(bulkResumeStage.value, ids)
    if (result.status === 'no_accounts') {
      ElMessage.info(
        bulkResumeStage.value === 'current'
          ? '没有可继续的 AI 博主任务'
          : '没有找到可从该阶段重跑的 AI 博主'
      )
      return
    }
    ElMessage.success(`已继续 ${result.resumed_count || 0} 个任务，跳过 ${result.skipped_count || 0} 个`)
    showBulkContinueDialog.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '一键继续失败')
  } finally {
    bulkRestarting.value = false
  }
}

async function handleBulkGenerateAIAccounts() {
  if (bulkGenerating.value) return

  try {
    await ElMessageBox.confirm(
      '将根据"已有关联视频、但尚未绑定任何 AI 博主账号"的标签批量创建账号，并统一进入后端队列排队生成。确定继续？',
      '确认生成',
      { confirmButtonText: '开始生成', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  bulkGenerating.value = true
  try {
    const result = await bulkGenerateAIAccounts()
    if (result.status === 'no_tags') {
      ElMessage.info('没有可生成的标签，所有有视频的标签都已绑定 AI 博主')
      return
    }
    ElMessage.success(`已创建并入队 ${result.created_count || 0} 个 AI 博主`)
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '一键生成失败')
  } finally {
    bulkGenerating.value = false
  }
}

async function handleDelete(item) {
  try {
    await ElMessageBox.confirm(
      `确定删除账号「${item.account_name}」？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning', customClass: 'premium-delete-dialog' }
    )
  } catch { return }

  deleting.value = item.id
  try {
    await deleteAccount(item.id)
    ElMessage.success('已删除')
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = null
  }
}

async function toggleFaceMode(item) {
  const newMode = item.face_mode === 'no_face' ? 'face' : 'no_face'
  try {
    await patchAccount(item.id, { face_mode: newMode })
    item.face_mode = newMode
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '切换失败')
  }
}

const GENDER_CYCLE = ['male', 'female', 'unisex']
async function cycleGender(item) {
  const current = item.gender || 'female'
  const next = GENDER_CYCLE[(GENDER_CYCLE.indexOf(current) + 1) % GENDER_CYCLE.length]
  try {
    await patchAccount(item.id, { gender: next })
    item.gender = next
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '切换失败')
  }
}

// ── 一键生成 ────────────────────────────────────────────────────────────────

const bulkVideoGenerating = ref(false)
const bulkVideoGenProgress = ref({ current: 0, total: 0 })
const showBulkGenDialog = ref(false)
const bulkGenForm = ref({ mode: 'unused', limit: 0, subtaskCount: 3 })


function handleBulkVideoGenerate() {
  if (bulkVideoGenerating.value) return
  bulkGenForm.value = { mode: 'unused', limit: 0, subtaskCount: 3 }
  showBulkGenDialog.value = true
}

async function startBulkVideoGenerate() {
  const { mode, limit } = bulkGenForm.value
  showBulkGenDialog.value = false
  bulkVideoGenerating.value = true

  try {
    const isSelection = selectedMap.value.size > 0
    let accountIds = []

    if (isSelection) {
      accountIds = [...selectedMap.value.values()].map(a => a.id)
    } else {
      const data = await fetchAccounts({ page: 1, page_size: 9999 })
      accountIds = (data.items || []).map(a => a.id)
    }

    if (accountIds.length === 0) {
      ElMessage.info('没有可操作的账号')
      return
    }

    const result = await bulkGenerateVideoTasks(accountIds, mode, limit, bulkGenForm.value.subtaskCount)
    const skipMsg = result.skipped_accounts > 0 ? `，${result.skipped_accounts} 个账号无可用模板` : ''
    ElMessage.success(result.message || `后台已启动，预计创建 ${result.planned || 0} 个生成任务${skipMsg}`)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '一键生成失败')
  } finally {
    bulkVideoGenerating.value = false
  }
}

// ── 一键定时 ────────────────────────────────────────────────────────────────

const CRON_PRESETS = [
  { label: '每天8点',    cron: '0 8 * * *' },
  { label: '每天10点',   cron: '0 10 * * *' },
  { label: '每天12点',   cron: '0 12 * * *' },
  { label: '每天20点',   cron: '0 20 * * *' },
  { label: '隔天10点',   cron: '0 10 */2 * *' },
  { label: '每周一10点', cron: '0 10 * * 1' },
]

const showBulkScheduleDialog = ref(false)
const savingBulkSchedule = ref(false)
const bulkScheduleForm = ref({
  publish_cron: '',
  publish_window_minutes: 0,
  publish_count: 1,
})

const bulkSchedulePreview = computed(() => {
  const cron = bulkScheduleForm.value.publish_cron?.trim()
  if (!cron) return '请先选择快捷规则或输入 Cron 表达式'
  const preset = CRON_PRESETS.find(p => p.cron === cron)
  const label = preset ? preset.label : `Cron: ${cron}`
  const win = bulkScheduleForm.value.publish_window_minutes
  const count = bulkScheduleForm.value.publish_count
  const winStr = win > 0 ? `，到点后随机延迟最多 ${win} 分钟` : ''
  return `${label}${winStr}，每次发布 ${count} 个视频（按队列顺序）`
})

function openBulkScheduleDialog() {
  bulkScheduleForm.value = { publish_cron: '', publish_window_minutes: 0, publish_count: 1 }
  showBulkScheduleDialog.value = true
}

async function handleBulkSchedule() {
  if (savingBulkSchedule.value) return
  if (!bulkScheduleForm.value.publish_cron?.trim()) {
    ElMessage.warning('请先设置 Cron 表达式')
    return
  }

  savingBulkSchedule.value = true

  // 使用已选账号或拉取全部账号
  const isSelection = selectedMap.value.size > 0
  let allAccounts = []
  if (isSelection) {
    allAccounts = [...selectedMap.value.values()]
  } else {
    try {
      const data = await fetchAccounts({ page: 1, page_size: 9999 })
      allAccounts = data.items || []
    } catch {
      ElMessage.error('加载账号列表失败')
      savingBulkSchedule.value = false
      return
    }
  }

  const results = await Promise.allSettled(
    allAccounts.map(account =>
      updateScheduledPublish(account.id, {
        publish_enabled: true,
        publish_cron: bulkScheduleForm.value.publish_cron,
        publish_window_minutes: bulkScheduleForm.value.publish_window_minutes,
        publish_count: bulkScheduleForm.value.publish_count,
      })
    )
  )

  const successCount = results.filter(r => r.status === 'fulfilled').length
  const failCount = results.filter(r => r.status === 'rejected').length

  savingBulkSchedule.value = false
  showBulkScheduleDialog.value = false

  const failMsg = failCount > 0 ? `，${failCount} 个失败` : ''
  ElMessage.success(`已为 ${successCount} 个账号启用定时发布${failMsg}`)
  await loadData()
}

// ── 补充模板 ────────────────────────────────────────────────────────────────

const showSupplementDialog = ref(false)
const supplementing = ref(false)
const supplementForm = ref({ templateType: 'shared', maxNewVideos: 10 })

function openSupplementDialog() {
  supplementForm.value = { templateType: 'shared', maxNewVideos: 10 }
  showSupplementDialog.value = true
}

async function handleSupplement() {
  if (supplementing.value) return
  supplementing.value = true

  const isSelection = selectedMap.value.size > 0
  let accountIds = []
  if (isSelection) {
    accountIds = [...selectedMap.value.keys()]
  } else {
    try {
      const data = await fetchAccounts({ page: 1, page_size: 9999 })
      accountIds = (data.items || []).map(a => a.id)
    } catch {
      ElMessage.error('加载账号列表失败')
      supplementing.value = false
      return
    }
  }

  try {
    const result = await supplementTemplates(accountIds, supplementForm.value.templateType, supplementForm.value.maxNewVideos)
    showSupplementDialog.value = false
    ElMessage.success(result.message || `已为 ${accountIds.length} 个账号启动补充模板任务`)
  } catch (e) {
    ElMessage.error('启动补充模板失败')
  } finally {
    supplementing.value = false
  }
}

onMounted(() => {
  loadFlags()
  loadData()
})
</script>

<style scoped>
.al-page {
  padding: 28px 32px;
  min-height: 100%;
  animation: rise 0.3s ease;
}

.al-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
  flex-wrap: wrap;
  gap: 12px;
}

.al-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.al-more-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 14px;
  border: 1px solid #e2e8f0 !important;
  background: #f8fafc !important;
  color: #475569 !important;
  display: flex;
  align-items: center;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.al-more-btn:hover {
  background: #f1f5f9 !important;
  border-color: #cbd5e1 !important;
  color: #1e293b !important;
}

.al-title {
  font-size: 26px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.03em;
  margin: 0;
}

.al-bulk-resume-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.al-bulk-resume-hint {
  font-size: 13px;
  line-height: 1.7;
  color: #475569;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 14px;
}

.al-bulk-resume-desc {
  font-size: 13px;
  line-height: 1.7;
  color: #1e40af;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  padding: 12px 14px;
}

.al-add-btn {
  display: flex;
  align-items: center;
  font-weight: 600;
  height: 40px;
  border-radius: 10px;
  padding: 0 18px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
}

/* Table */
/* 外层容器：边框/圆角/阴影 */
.al-table-wrap {
  width: 100%;
  margin-bottom: 28px;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
  position: relative;
  overflow: hidden; /* 裁剪圆角 — sticky 列在此容器内仍可正常工作 */
}

/* 内层滚动容器：横向滚动，sticky 在这里生效 */
.al-table-scroll {
  width: 100%;
  overflow-x: auto;
  overflow-y: visible;
}

.al-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  min-width: 1440px;
  table-layout: fixed;
}

.al-th {
  padding: 11px 14px;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-align: left;
  background: #f8fafc;
  border-bottom: 1px solid #e8edf5;
  white-space: nowrap;
  user-select: none;
}

/* Sticky Header Cells */
.al-th.al-th-check,
.al-th.al-th-media,
.al-th.al-th-name {
  position: sticky;
  z-index: 30;
  background: #f8fafc;
}

.al-th:first-child { border-top-left-radius: 14px; }
.al-th:last-child  { border-top-right-radius: 14px; }

.al-th-check    { width: 44px; text-align: center; left: 0; border-right: 1px solid #e8edf5; }
.al-th-media    { width: 110px; left: 44px; border-right: 1px solid #e8edf5; }
.al-th-name     { width: 280px; left: 154px; box-shadow: 2px 0 5px -2px rgba(0,0,0,0.1); border-right: 1px solid #e8edf5; }
.al-th-platform { width: 180px; }
.al-th-stat     { width: 90px; text-align: right; }
.al-th-date     { width: 130px; }
.al-th-flags    { width: 160px; }
.al-th-tags     { width: 220px; }
.al-th-actions  { width: 160px; text-align: center; }

/* Sortable header */
.al-th-sortable {
  cursor: pointer;
}
.al-th-sortable:hover {
  background: #f1f5fb;
  color: #4f46e5;
}
.al-th-label {
  display: inline;
}
.al-sort-icon {
  display: inline-flex;
  align-items: center;
  margin-left: 4px;
  vertical-align: middle;
}

/* Column filter bar */
.al-col-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 6px 0 2px;
}
.al-col-filter-select {
  height: 28px;
  padding: 0 24px 0 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2394a3b8'/%3E%3C/svg%3E") no-repeat right 7px center;
  background-size: 10px 6px;
  font-size: 12px;
  color: #374151;
  appearance: none;
  cursor: pointer;
  transition: border-color 0.15s;
  outline: none;
}
.al-col-filter-select:hover {
  border-color: #a5b4fc;
}
.al-col-filter-select:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99,102,241,0.12);
}
.al-col-filter-clear {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  background: #fff;
  color: #ef4444;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.al-col-filter-clear:hover {
  background: #fee2e2;
}

.al-tr {
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid #f1f5f9;
}

.al-tr.is-selected {
  background: #eef2ff;
}

.al-tr:last-child { border-bottom: none; }

.al-tr:hover { background: #f8faff; }

.al-td {
  padding: 10px 14px;
  vertical-align: middle;
  font-size: 13px;
  color: #1e293b;
  background: #fff; /* Opaque background for sticky columns */
}

/* Sticky Data Cells */
.al-td.al-td-check,
.al-td.al-td-media,
.al-td.al-td-name {
  position: sticky;
  z-index: 20;
}

.al-td-check  { text-align: center; width: 44px; left: 0; border-right: 1px solid #f1f5f9; }
.al-td-media  { width: 110px; left: 44px; border-right: 1px solid #f1f5f9; }
.al-td-name   { width: 280px; left: 154px; box-shadow: 2px 0 5px -2px rgba(0,0,0,0.1); border-right: 1px solid #f1f5f9; }
.al-td-flags   { width: 160px; }
.al-td-actions { text-align: center; width: 160px; }

/* Name cell adjustments for fixed layout */
.al-name-main {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
}
.al-name-handle {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin-bottom: 4px;
  min-width: 0;
  width: 100%;
}
.al-handle {
  font-size: 12px;
  font-weight: 600;
  color: #6366f1;
}
.al-signature {
  font-size: 11px;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.al-tr:hover .al-td.al-td-check,
.al-tr:hover .al-td.al-td-media,
.al-tr:hover .al-td.al-td-name {
  background: #f8faff;
}

.al-tr.is-selected .al-td.al-td-check,
.al-tr.is-selected .al-td.al-td-media,
.al-tr.is-selected .al-td.al-td-name {
  background: #eef2ff;
}

.al-td-stat {
  text-align: right;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
}

.al-td-date {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

/* Media cell */
.al-media-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
}

.al-photo-wrap {
  width: 52px;
  height: 52px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  cursor: zoom-in;
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  display: flex;
  align-items: center;
  justify-content: center;
}

.al-photo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.al-photo-ph {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.al-avatar-wrap {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  cursor: zoom-in;
  background: #eef2ff;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,.1);
}

.al-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.al-avatar-ph {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.al-pending-badge {
  position: absolute;
  top: -4px;
  left: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(234, 88, 12, 0.96);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
  box-shadow: 0 2px 6px rgba(194, 65, 12, 0.3);
}

/* Name cell */
.al-name-main {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.al-name-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-wrap: wrap;
}

.al-style-desc {
  font-size: 11px;
  color: #64748b;
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  max-width: 200px;
}

/* Platform cell */
.al-bindings {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.al-no-binding {
  font-size: 12px;
  color: #94a3b8;
}

/* Tags / Flags cell */
.al-flags-wrap,
.al-tags-wrap,
.al-bloggers-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.ac-flag-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 11px;
  font-weight: 600;
  color: #334155;
  white-space: nowrap;
}

.ac-flag-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
  flex-shrink: 0;
}

/* Row actions */
.al-row-actions {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 5px;
  justify-content: center;
}

/* Shared chip / badge styles */
.al-hashtags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 3px;
}
.al-hashtag-chip {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 20px;
  background: #ede9fe;
  color: #6d28d9;
  white-space: nowrap;
}
.al-hashtag-chip.al-hashtag-more {
  background: #f3f4f6;
  color: #6b7280;
}

.ac-blogger-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  background: #f8faff;
  border: 1px solid #e0e7ff;
  border-radius: 20px;
  padding: 3px 8px 3px 3px;
  max-width: 140px;
}

.ac-blogger-avatar {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.ac-blogger-avatar-ph {
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ac-blogger-name {
  font-size: 11px;
  font-weight: 500;
  color: #4f46e5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 90px;
}

.ac-tag-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 11px;
  color: #334155;
  font-weight: 500;
  white-space: nowrap;
}

.ac-tag-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ac-tag {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
}

.ac-tag-youtube  { background: #fef2f2; color: #dc2626; }
.ac-tag-tiktok   { background: #f1f5f9; color: #0f172a; }
.ac-tag-instagram { background: #fef3c7; color: #92400e; }
.ac-tag-reserved { background: #ecfeff; color: #0e7490; border: 1px solid #a5f3fc; }
.ac-tag-disabled {
  background: #fff1f2 !important;
  color: #be123c !important;
  border: 1.5px solid #fda4af !important;
  text-decoration: line-through;
  opacity: 0.85;
}

/* Account type badge */
.ac-type-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 20px;
  letter-spacing: .02em;
  flex-shrink: 0;
  white-space: nowrap;
}

.ac-type-persona {
  background: #ede9fe;
  color: #6d28d9;
}

.ac-type-traffic,
.ac-type-shared {
  background: #dbeafe;
  color: #1d4ed8;
}

.ac-type-exclusive {
  background: #fef3c7;
  color: #d97706;
}

.ac-face-yes {
  background: #dcfce7;
  color: #15803d;
}

.ac-face-no {
  background: #fef3c7;
  color: #b45309;
}

.ac-gender-male {
  background: #dbeafe;
  color: #1d4ed8;
}

.ac-gender-female {
  background: #fce7f3;
  color: #be185d;
}

.ac-gender-unisex {
  background: #f3e8ff;
  color: #7c3aed;
}

.ac-ai-status {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  white-space: nowrap;
}

.ac-ai-status.is-pending,
.ac-ai-status.is-video_analyzing,
.ac-ai-status.is-name_generating,
.ac-ai-status.is-photo_generating,
.ac-ai-status.is-avatar_generating {
  background: #dbeafe;
  color: #1d4ed8;
}

.ac-ai-status.is-awaiting_photo_selection {
  background: #fef3c7;
  color: #b45309;
}

.ac-ai-status.is-failed {
  background: #fee2e2;
  color: #b91c1c;
}

.ac-ai-status.is-completed {
  background: #dcfce7;
  color: #15803d;
}

.ac-btn {
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 7px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ac-btn-stats {
  border-color: #bae6fd;
  color: #0369a1;
  background: #f0f9ff;
}

.ac-btn-stats:hover {
  border-color: #7dd3fc;
  color: #0284c7;
  background: #e0f2fe;
}

.ac-btn-edit:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.ac-btn-del {
  border-color: #fecaca;
  color: #dc2626;
  background: #fef2f2;
}

.ac-btn-del:hover {
  border-color: #fca5a5;
  color: #b91c1c;
  background: #fee2e2;
}

.ac-btn-sync {
  border-color: #fde68a;
  color: #92400e;
  background: #fffbeb;
}

.ac-btn-sync:hover {
  border-color: #fcd34d;
  color: #78350f;
  background: #fef3c7;
}

.ac-btn.loading {
  opacity: 0.5;
  pointer-events: none;
}

/* Footer */
.al-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0 8px;
  border-top: 1px solid #f1f5f9;
}

.al-pagination-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.al-count-text {
  font-size: 13px;
  color: #94a3b8;
}

.al-simple-select {
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  padding: 0 4px;
}

.al-simple-select:hover {
  color: #64748b;
}

.al-pagination {
  display: flex;
  gap: 8px;
}

.ac-preview-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.ac-preview-image {
  display: block;
  width: 100%;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 12px;
  background: #f8fafc;
}

.pg-btn {
  font-size: 13px;
  font-weight: 500;
  padding: 7px 14px;
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

.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.pg-num {
  min-width: 36px;
  padding: 7px 10px;
  text-align: center;
}

.pg-num.active {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border-color: transparent;
  font-weight: 700;
}

.pg-ellipsis {
  font-size: 13px;
  color: #94a3b8;
  padding: 0 4px;
  user-select: none;
}

.pg-jump-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #94a3b8;
  margin-left: 4px;
}

.pg-jump-input {
  width: 52px;
  height: 34px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  text-align: center;
  font-size: 13px;
  color: #334155;
  outline: none;
  padding: 0 6px;
}

.pg-jump-input:focus {
  border-color: #6366f1;
}

.pg-jump-go {
  padding: 7px 12px;
}

@keyframes rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

@media (max-width: 640px) {
  .al-page { padding: 16px; }
  .al-grid { grid-template-columns: 1fr 1fr; gap: 12px; }
}

/* 一键生成按钮 */
.al-gen-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(16,185,129,0.25) !important;
  background: rgba(16,185,129,0.07) !important;
  color: #059669 !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}
.al-gen-btn:hover:not(:disabled) {
  background: rgba(16,185,129,0.14) !important;
  border-color: rgba(16,185,129,0.45) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(16,185,129,0.18);
}
.al-gen-btn:active { transform: translateY(1px); }
.al-gen-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; box-shadow: none !important; }

/* 一键定时按钮 */
.al-schedule-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(59,130,246,0.25) !important;
  background: rgba(59,130,246,0.07) !important;
  color: #2563eb !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}
.al-schedule-btn:hover:not(:disabled) {
  background: rgba(59,130,246,0.14) !important;
  border-color: rgba(59,130,246,0.45) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(59,130,246,0.18);
}
.al-schedule-btn:active { transform: translateY(1px); }
.al-schedule-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; box-shadow: none !important; }

/* 批量定时发布弹窗内元素 */
.al-schedule-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.al-preset-btn {
  font-size: 13px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
}
.al-preset-btn:hover { border-color: #6366f1; color: #6366f1; background: #eef2ff; }
.al-preset-btn.active { border-color: #6366f1; background: #6366f1; color: #fff; font-weight: 600; }
.al-schedule-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 6px;
}
.al-schedule-unit {
  font-size: 13px;
  color: #64748b;
  margin-left: 10px;
}
.al-schedule-preview {
  font-size: 13px;
  color: #1e40af;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  padding: 10px 14px;
  line-height: 1.6;
}

.al-tasks-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(99,102,241,0.2) !important;
  background: rgba(99,102,241,0.05) !important;
  color: #4f46e5 !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}

.al-tasks-btn:hover {
  background: rgba(99,102,241,0.12) !important;
  border-color: rgba(99,102,241,0.4) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99,102,241,0.15);
}

.al-tasks-btn:active {
  transform: translateY(1px);
}

.al-config-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(139,92,246,0.2) !important;
  background: rgba(139,92,246,0.05) !important;
  color: #7c3aed !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}

.al-config-btn:hover {
  background: rgba(139,92,246,0.12) !important;
  border-color: rgba(139,92,246,0.4) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(139,92,246,0.15);
}

.al-config-btn:active {
  transform: translateY(1px);
}

.al-restart-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(245,158,11,0.2) !important;
  background: rgba(245,158,11,0.05) !important;
  color: #d97706 !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}

.al-restart-btn:hover {
  background: rgba(245,158,11,0.12) !important;
  border-color: rgba(245,158,11,0.4) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(245,158,11,0.15);
}

.al-restart-btn:active {
  transform: translateY(1px);
}

.al-restart-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
  box-shadow: none !important;
}

/* 补充模板按钮 */
.al-supplement-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(234,88,12,0.2) !important;
  background: rgba(234,88,12,0.06) !important;
  color: #c2410c !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}
.al-supplement-btn:hover:not(:disabled) {
  background: rgba(234,88,12,0.12) !important;
  border-color: rgba(234,88,12,0.4) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(234,88,12,0.16);
}
.al-supplement-btn:active { transform: translateY(1px); }
.al-supplement-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; box-shadow: none !important; }

.al-namehandle-btn {
  font-weight: 600;
  border-radius: 10px;
  height: 40px;
  padding: 0 16px;
  border: 1px solid rgba(124,58,237,0.2) !important;
  background: rgba(124,58,237,0.06) !important;
  color: #6d28d9 !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 6px;
}
.al-namehandle-btn:hover:not(:disabled) {
  background: rgba(124,58,237,0.12) !important;
  border-color: rgba(124,58,237,0.4) !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(124,58,237,0.16);
}
.al-namehandle-btn:active { transform: translateY(1px); }
.al-namehandle-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; box-shadow: none !important; }

/* 标签搜索按钮 */
.al-hashtag-btn {
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: 1.5px solid #7c3aed;
  background: #fff;
  color: #7c3aed;
  white-space: nowrap;
}
.al-hashtag-btn:hover:not(:disabled) {
  background: #7c3aed;
  color: #fff;
  box-shadow: 0 2px 8px rgba(124,58,237,0.18);
}
.al-hashtag-btn:active { transform: translateY(1px); }
.al-hashtag-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; box-shadow: none !important; }

/* 标签搜索弹窗 */
.al-hashtag-pre {
  padding: 4px 0 8px;
}
.al-hashtag-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
}
.al-hashtag-result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.al-hashtag-error {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ef4444;
  font-size: 14px;
  padding: 12px;
  background: #fef2f2;
  border-radius: 8px;
}
.al-hashtag-meta {
  font-size: 13px;
  color: #6b7280;
}
.al-hashtag-block {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}
.al-hashtag-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}
.al-hashtag-block-title {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.al-hashtag-copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #6366f1;
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 5px;
}
.al-hashtag-copy-btn:hover { background: #ede9fe; }
.al-hashtag-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 12px 14px;
  max-height: 180px;
  overflow-y: auto;
}
.al-hashtag-tags-raw {
  max-height: 130px;
}
.al-hashtag-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  background: #f3f4f6;
  color: #374151;
  cursor: pointer;
  transition: all 0.12s;
}
.al-hashtag-tag:hover { background: #e0e7ff; color: #4338ca; }
.al-hashtag-tag.is-filtered {
  background: #ede9fe;
  color: #6d28d9;
}
.al-hashtag-tag.is-filtered:hover { background: #ddd6fe; }
.al-hashtag-bind-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0 2px;
  border-top: 1px solid #f3f4f6;
  margin-top: 4px;
}
.al-hashtag-bind-label {
  font-size: 13px;
  color: #6b7280;
  white-space: nowrap;
}

/* 补充模板弹窗 */
.al-supplement-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.al-supplement-scope {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: #475569;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 14px;
  line-height: 1.5;
}
.al-supplement-scope svg { flex-shrink: 0; color: #6366f1; }
.al-supplement-scope b { color: #0f172a; font-weight: 700; }

.al-supplement-types {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.al-supplement-type-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 16px;
  border-radius: 12px;
  border: 2px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: center;
}
.al-supplement-type-card:hover:not(.is-disabled) {
  border-color: #6366f1;
  background: #eef2ff;
}
.al-supplement-type-card.active {
  border-color: #6366f1;
  background: #eef2ff;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.12);
}
.al-supplement-type-card.is-disabled {
  opacity: 0.45;
  cursor: not-allowed;
  background: #f1f5f9;
}

.al-supplement-type-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6366f1;
}
.al-supplement-type-card.active .al-supplement-type-icon {
  background: #6366f1;
  border-color: #6366f1;
  color: #fff;
}
.al-supplement-type-card.is-disabled .al-supplement-type-icon {
  color: #94a3b8;
}

.al-supplement-type-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}
.al-supplement-type-card.is-disabled .al-supplement-type-name {
  color: #94a3b8;
}

.al-supplement-type-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.4;
}
.al-supplement-type-card.is-disabled .al-supplement-type-desc {
  color: #94a3b8;
}

.al-supplement-config {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.al-supplement-config-label {
  font-size: 13px;
  color: #334155;
  font-weight: 500;
}
.al-supplement-config-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.al-supplement-minus,
.al-supplement-plus {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  line-height: 1;
}
.al-supplement-minus:hover,
.al-supplement-plus:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}
.al-supplement-num {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  min-width: 28px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.al-supplement-num-hint {
  font-size: 13px;
  color: #94a3b8;
}

/* AI 配置弹窗内容 */
.ai-cfg-body {
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 4px;
}

.ai-cfg-section {
  background: #f8fafc;
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 16px;
  border: 1px solid #e2e8f0;
}

.ai-cfg-section:last-child { margin-bottom: 0; }

.ai-cfg-section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.ai-cfg-tag {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  background: #e2e8f0;
  padding: 3px 10px;
  border-radius: 6px;
  white-space: nowrap;
}

.ai-cfg-desc {
  font-size: 12px;
  color: #94a3b8;
}

/* ── Flag 过滤栏 ──────────────────────────────────────────────────────────── */
.al-filter-bar {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.al-search-box {
  position: relative;
  display: flex;
  align-items: center;
  width: 260px;
}
.al-search-icon {
  position: absolute;
  left: 10px;
  color: #94a3b8;
  pointer-events: none;
  flex-shrink: 0;
}
.al-search-input {
  width: 100%;
  height: 34px;
  padding: 0 30px 0 32px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 13px;
  color: #1e293b;
  background: #f8fafc;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.al-search-input:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
  background: #fff;
}
.al-search-input::placeholder { color: #94a3b8; }
.al-search-clear {
  position: absolute;
  right: 8px;
  background: none;
  border: none;
  cursor: pointer;
  color: #94a3b8;
  font-size: 12px;
  padding: 2px 4px;
  line-height: 1;
}
.al-search-clear:hover { color: #475569; }

.al-filter-flags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.al-flag-filter-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.al-flag-filter-btn:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.al-flag-filter-btn.active {
  font-weight: 700;
}

.al-flag-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
  flex-shrink: 0;
}

.al-flag-filter-btn.is-pinned {
  font-weight: 600;
}

.al-flag-expand-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #f1f5f9;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.al-flag-expand-btn:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.al-flag-manage-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  padding: 5px 12px;
  border-radius: 20px;
  border: 1px dashed #cbd5e1;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
}

.al-flag-manage-btn:hover {
  border-color: #6366f1;
  color: #6366f1;
  background: #f8f9ff;
}

/* ── 多选 checkbox ─────────────────────────────────────────────────────────── */
.al-checkbox {
  width: 15px;
  height: 15px;
  cursor: pointer;
  accent-color: #6366f1;
}

/* ── 批量操作栏 ───────────────────────────────────────────────────────────── */
.al-bulk-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 10px;
}

.al-bulk-count {
  font-size: 13px;
  font-weight: 700;
  color: #4f46e5;
  margin-right: 4px;
}

.al-bulk-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 8px;
  border: 1px solid;
  cursor: pointer;
  transition: all 0.15s;
}

.al-bulk-action-btn.is-bind {
  border-color: #a5b4fc;
  background: #fff;
  color: #4f46e5;
}

.al-bulk-action-btn.is-bind:hover {
  background: #6366f1;
  color: #fff;
  border-color: #6366f1;
}

.al-bulk-action-btn.is-unbind {
  border-color: #fca5a5;
  background: #fff;
  color: #dc2626;
}

.al-bulk-action-btn.is-unbind:hover {
  background: #ef4444;
  color: #fff;
  border-color: #ef4444;
}

.al-bulk-action-btn.is-generate {
  border-color: #a78bfa;
  background: #fff;
  color: #7c3aed;
}

.al-bulk-action-btn.is-generate:hover {
  background: #7c3aed;
  color: #fff;
  border-color: #7c3aed;
}

.al-bulk-clear-btn {
  font-size: 12px;
  font-weight: 500;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #94a3b8;
  cursor: pointer;
  margin-left: auto;
  transition: all 0.15s;
}

.al-bulk-clear-btn:hover {
  color: #475569;
  border-color: #cbd5e1;
}

.bulk-bar-enter-active,
.bulk-bar-leave-active {
  transition: all 0.2s ease;
}

.bulk-bar-enter-from,
.bulk-bar-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ── Flag 管理弹窗 ─────────────────────────────────────────────────────────── */
.fm-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.fm-form {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fm-form-title {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.fm-form-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.fm-input {
  flex: 1;
  height: 36px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0 12px;
  font-size: 14px;
  color: #0f172a;
  outline: none;
  transition: border-color 0.15s;
}

.fm-input:focus {
  border-color: #6366f1;
}

.fm-color-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fm-color-preview {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,.15);
  flex-shrink: 0;
}

.fm-color-swatches {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  max-width: 180px;
}

.fm-swatch {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform 0.12s, border-color 0.12s;
  outline: none;
}

.fm-swatch:hover { transform: scale(1.2); }
.fm-swatch.active { border-color: #fff; box-shadow: 0 0 0 2px #6366f1; }

.fm-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.fm-cancel-btn {
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  cursor: pointer;
}

.fm-save-btn {
  font-size: 13px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  cursor: pointer;
  transition: opacity 0.15s;
}

.fm-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* 快捷标签开关 */
.fm-pin-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.fm-pin-checkbox {
  width: 14px;
  height: 14px;
  accent-color: #6366f1;
  cursor: pointer;
  flex-shrink: 0;
}

.fm-pin-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #475569;
}

.fm-list { display: flex; flex-direction: column; gap: 10px; }

/* 分组 */
.fm-group { display: flex; flex-direction: column; gap: 5px; }

.fm-group-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: .06em;
  margin-bottom: 2px;
}

.fm-item.is-pinned {
  border-color: #e0e7ff;
  background: #f5f3ff;
}

.fm-empty {
  font-size: 13px;
  color: #cbd5e1;
  text-align: center;
  padding: 12px;
}

.fm-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #f1f5f9;
  border-radius: 10px;
  background: #fff;
}

.fm-item-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #e2e8f0;
  flex-shrink: 0;
}

.fm-item-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

.fm-item-actions {
  display: flex;
  gap: 5px;
}

.fm-edit-btn,
.fm-del-btn {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  transition: all 0.12s;
}

.fm-edit-btn { color: #6366f1; border-color: #c7d2fe; background: #eef2ff; }
.fm-edit-btn:hover { background: #6366f1; color: #fff; }

.fm-del-btn { color: #dc2626; border-color: #fecaca; background: #fef2f2; }
.fm-del-btn:hover { background: #ef4444; color: #fff; border-color: #ef4444; }
.fm-del-btn.loading { opacity: 0.5; pointer-events: none; }

/* ── 批量标识弹窗 ──────────────────────────────────────────────────────────── */
.bfd-body { display: flex; flex-direction: column; gap: 14px; }

.bfd-hint {
  font-size: 13px;
  color: #475569;
}

.bfd-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.bfd-flag-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  transition: all 0.12s;
  user-select: none;
}

.bfd-flag-item:hover { border-color: #a5b4fc; background: #eef2ff; }

.bfd-flag-item.selected {
  border-color: #6366f1;
  background: #eef2ff;
  font-weight: 600;
}

.bfd-checkbox { display: none; }

.bfd-flag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
}

.bfd-flag-name { font-size: 13px; color: #334155; }

.bfd-empty {
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
  padding: 16px;
}
</style>
