<template>
  <div class="vai-page">
    <!-- Header -->
    <div class="vai-header">
      <h1 class="vai-title">视频AI模板</h1>
      <div class="vai-header-actions">
        <el-button class="vai-retry-btn" :loading="batchResuming" @click="handleBatchResume">
          <svg v-if="!batchResuming" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" style="margin-right:6px"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.5"/></svg>
          一键重试
        </el-button>
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
      <div class="vai-stat-card">
        <div class="vai-stat-top">
          <span class="vai-stat-label">排队中</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.pending || 0 }}</div>
        <div class="vai-stat-sub">pending</div>
      </div>
      <div class="vai-stat-card">
        <div class="vai-stat-top">
          <span class="vai-stat-label">理解视频</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.understanding || 0 }}</div>
        <div class="vai-stat-sub">understanding</div>
      </div>
      <div class="vai-stat-card">
        <div class="vai-stat-top">
          <span class="vai-stat-label">图片生成</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.imagegen || 0 }}</div>
        <div class="vai-stat-sub">imagegen</div>
      </div>
      <div class="vai-stat-card">
        <div class="vai-stat-top">
          <span class="vai-stat-label">拆分图片</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ec4899" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.splitting || 0 }}</div>
        <div class="vai-stat-sub">splitting</div>
      </div>
      <div class="vai-stat-card">
        <div class="vai-stat-top">
          <span class="vai-stat-label">消除人脸</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/><line x1="17" y1="3" x2="21" y2="7"/><line x1="21" y1="3" x2="17" y2="7"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.face_removing || 0 }}</div>
        <div class="vai-stat-sub">face_removing</div>
      </div>
      <div class="vai-stat-card">
        <div class="vai-stat-top">
          <span class="vai-stat-label">成功</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        </div>
        <div class="vai-stat-value">{{ templateStats.success || 0 }}</div>
        <div class="vai-stat-sub">success</div>
      </div>
      <div class="vai-stat-card">
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

          <!-- Error message -->
          <div v-if="item.process_error" class="vt-error">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>{{ item.process_error }}</span>
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
    <el-dialog
      v-model="showConfig"
      title="AI 处理流程配置"
      width="760px"
      :close-on-click-modal="false"
    >
      <div v-loading="configLoading" class="cfg-body">
        <div class="cfg-hint-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          API Key 和 Base URL 由管理员在<router-link to="/dashboard/settings" @click="showConfig=false">系统设置</router-link>中配置，此处为你的个人流程参数。
        </div>

        <el-tabs v-model="configTab" type="border-card" class="cfg-tabs">
          <!-- Step 1 -->
          <el-tab-pane label="步骤一：视频理解" name="step1">
            <div class="cfg-step-desc">AI 理解视频全局内容，输出整体文字描述。此结果将作为背景信息展示在模板详情中。</div>
            <el-form label-position="top" class="cfg-form">
              <el-form-item label="模型名称">
                <el-input v-model="cfg.understand_model" placeholder="gemini-3.1-pro-preview（留空使用默认）" />
              </el-form-item>
              <el-form-item label="提示词 (Prompt)">
                <el-input v-model="cfg.understand_prompt" type="textarea" :rows="4"
                  placeholder="请描述这个视频的内容，包括场景、人物、服装风格等。" />
              </el-form-item>
              <el-form-item :label="`温度 (Temperature)：${cfg.understand_temperature.toFixed(1)}`">
                <el-slider v-model="cfg.understand_temperature" :min="0" :max="2" :step="0.1" />
              </el-form-item>
              <el-form-item label="输出格式">
                <el-radio-group v-model="cfg.understand_output_format">
                  <el-radio value="text">纯文本</el-radio>
                  <el-radio value="json">JSON</el-radio>
                  <el-radio value="markdown">Markdown</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-if="cfg.understand_output_format === 'json'" label="JSON 格式定义">
                <el-input
                  v-model="cfg.understand_json_schema"
                  type="textarea"
                  :rows="5"
                  placeholder='{\n  "overall_style": "...",\n  "color_palette": ["..."],\n  "theme": "..."\n}'
                  class="cfg-code-input"
                  :class="{ 'cfg-json-invalid': jsonErrors.understand }"
                  @input="validateJsonField('understand', cfg.understand_json_schema)"
                />
                <div v-if="jsonErrors.understand" class="cfg-json-error-msg">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                  {{ jsonErrors.understand }}
                </div>
                <div v-else-if="cfg.understand_json_schema.trim()" class="cfg-json-ok-msg">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                  JSON 格式正确
                </div>
                <div class="cfg-field-hint">此 JSON 格式将追加到提示词末尾，要求模型严格按格式输出。</div>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- Step 2 -->
          <el-tab-pane label="步骤二：抽帧生图" name="step2">
            <div class="cfg-step-desc">
              对视频（超过 15s 只取前 15s）每隔 1.5s 抽一帧，共 10 帧，将所有帧一口气传给模型，生成一张造型图，结果自动填入模板的「造型图」区域。
            </div>
            <el-form label-position="top" class="cfg-form">
              <el-form-item label="生图模型">
                <el-input v-model="cfg.imagegen_model" placeholder="gemini-3.1-flash-image-preview（留空使用默认）" />
              </el-form-item>
              <el-form-item label="生图提示词 (Prompt)">
                <el-input
                  v-model="cfg.imagegen_prompt"
                  type="textarea"
                  :rows="5"
                  placeholder="根据参考图生成同款风格图片，保持人物姿态、服装和场景风格一致"
                />
                <div class="cfg-field-hint">所有抽取的帧截图将一起发给模型，此提示词指导生成最终造型图。</div>
              </el-form-item>
              <el-form-item label="图片尺寸 (Size)">
                <el-select v-model="cfg.imagegen_size" style="width: 220px">
                  <el-option label="9:16（竖屏）" value="9:16" />
                  <el-option label="1:1（方形）" value="1:1" />
                  <el-option label="3:4" value="3:4" />
                  <el-option label="4:3" value="4:3" />
                  <el-option label="16:9（横屏）" value="16:9" />
                  <el-option label="4:1（超宽）" value="4:1" />
                  <el-option label="8:1（全景宽）" value="8:1" />
                </el-select>
              </el-form-item>
              <el-form-item label="图片质量 (Quality)">
                <el-radio-group v-model="cfg.imagegen_quality">
                  <el-radio value="0.5K">0.5K（快速）</el-radio>
                  <el-radio value="1K">1K</el-radio>
                  <el-radio value="2K">2K（推荐）</el-radio>
                  <el-radio value="4K">4K（高质量）</el-radio>
                </el-radio-group>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- Step 3 -->
          <el-tab-pane label="步骤三：拆分图片" name="step3">
            <div class="cfg-step-desc">
              调用 Segment API 对生图结果进行人物分割，将每个分割区域的图片上传 CDN，结果自动填入模板的「造型图」区域。
            </div>
            <el-form label-position="top" class="cfg-form">
              <el-form-item label="Segment API 地址">
                <el-input v-model="cfg.splitting_api_url" placeholder="http://34.21.127.95:8080（留空使用默认）" />
                <div class="cfg-field-hint">例如：http://34.21.127.95:8080，实际请求会追加 /api/segment-models</div>
              </el-form-item>
            </el-form>
          </el-tab-pane>

          <!-- Step 4 -->
          <el-tab-pane label="步骤四：去脸" name="step4">
            <div class="cfg-step-desc">
              对每张拆分后的图片调用去脸 API，去除人物头部，处理后的图片 URL 替换原造型图。
            </div>
            <el-form label-position="top" class="cfg-form">
              <el-form-item label="去脸 API 地址">
                <el-input v-model="cfg.face_removing_api_url" placeholder="http://34.86.216.234:8001（留空使用默认）" />
                <div class="cfg-field-hint">实际请求会追加 /api/v1/style-outfits/processBodyShape</div>
              </el-form-item>
              <el-form-item label="scoreThresh（人脸检测阈值）">
                <el-input-number v-model="cfg.face_removing_score_thresh" :min="0" :max="1" :step="0.05" :precision="2" style="width:160px" />
                <div class="cfg-field-hint">0~1，越高越严格，默认 0.3</div>
              </el-form-item>
              <el-form-item label="marginScale（边距缩放）">
                <el-input-number v-model="cfg.face_removing_margin_scale" :min="0" :max="2" :step="0.05" :precision="2" style="width:160px" />
                <div class="cfg-field-hint">裁切头部时的边距缩放比例，默认 0.2</div>
              </el-form-item>
              <el-form-item label="headTopRatio（头顶比例）">
                <el-input-number v-model="cfg.face_removing_head_top_ratio" :min="0" :max="2" :step="0.05" :precision="2" style="width:160px" />
                <div class="cfg-field-hint">头顶额外保留比例，默认 0.7</div>
              </el-form-item>
            </el-form>
          </el-tab-pane>

        </el-tabs>
      </div>

      <template #footer>
        <el-button @click="showConfig = false">取消</el-button>
        <el-button type="primary" :loading="configSaving" :disabled="hasJsonError" @click="saveConfig">保存配置</el-button>
      </template>
    </el-dialog>

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
        <button class="pg-btn" :disabled="endIdx >= total" @click="goPage(page + 1)">下一页 →</button>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchVideoAITemplates,
  fetchTemplateStats,
  startVideoAITemplate,
  pauseVideoAITemplate,
  restartVideoAITemplate,
  resumeVideoAITemplate,
  deleteVideoAITemplate,
} from '../api/video_ai_templates'
import { fetchPipelineSettings, updatePipelineSettings } from '../api/settings'
import { isDuplicateRequestError } from '../api/http'
import { useAuth } from '../composables/useAuth'

const { isAdmin } = useAuth()

const router = useRouter()

const loading = ref(false)
const deleting = ref(null)
const actioning = ref(null)
const batchResuming = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const templateStats = ref({})

const playerVisible = ref(false)
const playerItem = ref(null)

// Config dialog state
const showConfig = ref(false)
const configTab = ref('step1')
const configLoading = ref(false)
const configSaving = ref(false)

const cfg = reactive({
  understand_model: '',
  understand_prompt: '',
  understand_temperature: 0.3,
  understand_output_format: 'text',
  understand_json_schema: '',
  imagegen_model: 'gemini-3.1-flash-image-preview',
  imagegen_prompt: '',
  imagegen_size: '9:16',
  imagegen_quality: '2K',
  splitting_api_url: '',
  face_removing_api_url: '',
  face_removing_score_thresh: 0.3,
  face_removing_margin_scale: 0.2,
  face_removing_head_top_ratio: 0.7,
})

// JSON validation errors for schema fields
const jsonErrors = reactive({ understand: '' })

function validateJsonField(field, value) {
  const v = (value || '').trim()
  if (!v) { jsonErrors[field] = ''; return }
  try {
    JSON.parse(v)
    jsonErrors[field] = ''
  } catch (e) {
    jsonErrors[field] = e.message
  }
}

const hasJsonError = computed(() =>
  cfg.understand_output_format === 'json' && !!jsonErrors.understand
)

async function openConfig() {
  showConfig.value = true
  configTab.value = 'step1'
  configLoading.value = true
  jsonErrors.understand = ''
  try {
    const data = await fetchPipelineSettings()
    Object.assign(cfg, {
      understand_model: data.understand_model || '',
      understand_prompt: data.understand_prompt || '',
      understand_temperature: data.understand_temperature ?? 0.3,
      understand_output_format: data.understand_output_format || 'text',
      understand_json_schema: data.understand_json_schema || '',
      imagegen_model: data.imagegen_model || 'gemini-3.1-flash-image-preview',
      imagegen_prompt: data.imagegen_prompt || '',
      imagegen_size: data.imagegen_size || '9:16',
      imagegen_quality: data.imagegen_quality || '2K',
      splitting_api_url: data.splitting_api_url || '',
      face_removing_api_url: data.face_removing_api_url || '',
      face_removing_score_thresh: data.face_removing_score_thresh ?? 0.3,
      face_removing_margin_scale: data.face_removing_margin_scale ?? 0.2,
      face_removing_head_top_ratio: data.face_removing_head_top_ratio ?? 0.7,
    })
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
      understand_prompt: cfg.understand_prompt,
      understand_temperature: cfg.understand_temperature,
      understand_output_format: cfg.understand_output_format,
      understand_json_schema: cfg.understand_json_schema,
      imagegen_model: cfg.imagegen_model,
      imagegen_prompt: cfg.imagegen_prompt,
      imagegen_size: cfg.imagegen_size,
      imagegen_quality: cfg.imagegen_quality,
      splitting_api_url: cfg.splitting_api_url,
      face_removing_api_url: cfg.face_removing_api_url,
      face_removing_score_thresh: cfg.face_removing_score_thresh,
      face_removing_margin_scale: cfg.face_removing_margin_scale,
      face_removing_head_top_ratio: cfg.face_removing_head_top_ratio,
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

const STATUS_CONFIG = {
  pending: { label: '排队中', type: 'info' },
  understanding: { label: '理解视频', type: 'primary' },
  imagegen: { label: '图片生成', type: '', customColor: '#8b5cf6', bg: '#f5f3ff', border: '#ddd6fe' }, // Purple
  splitting: { label: '拆分图片', type: '', customColor: '#ec4899', bg: '#fdf2f8', border: '#fbcfe8' }, // Pink
  face_removing: { label: '消除人脸', type: '', customColor: '#f59e0b', bg: '#fffbeb', border: '#fde68a' }, // Orange
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
  return ['pending', 'understanding'].includes(item.process_status)
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

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

async function handleBatchResume() {
  batchResuming.value = true
  try {
    // Fetch all pages to find non-success templates
    const allItems = []
    let p = 1
    const ps = 100
    while (true) {
      const data = await fetchVideoAITemplates({ page: p, page_size: ps })
      const batch = data.items || []
      allItems.push(...batch)
      if (allItems.length >= (data.total || 0) || batch.length < ps) break
      p++
    }
    const targets = allItems.filter(item => item.process_status !== 'success')
    if (!targets.length) {
      ElMessage.info('所有模板均已完成，无需重试')
      return
    }
    ElMessage.info(`开始重试 ${targets.length} 个任务…`)
    let successCount = 0
    let failCount = 0
    for (const item of targets) {
      try {
        await restartVideoAITemplate(item.id)
        successCount++
      } catch {
        failCount++
      }
    }
    ElMessage.success(`成功触发 ${successCount} 个任务重试${failCount > 0 ? `，${failCount} 个失败` : ''}`)
    await loadData()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '批量重试失败')
  } finally {
    batchResuming.value = false
  }
}

async function loadData() {
  loading.value = true
  try {
    const data = await fetchVideoAITemplates({ page: page.value, page_size: pageSize.value })
    items.value = data.items || []
    total.value = data.total || 0
    loadStats()
  } catch (err) {
    if (isDuplicateRequestError(err)) return
    ElMessage.error(err?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

function goPage(p) {
  page.value = p
  loadData()
}

function handleSizeChange(val) {
  pageSize.value = val
  page.value = 1
  loadData()
}

function openPlayer(item) {
  playerItem.value = item
  playerVisible.value = true
}

function goToDetail(item) {
  router.push(`/dashboard/video-ai-templates/${item.id}/edit`)
}

function goToEdit(item) {
  router.push(`/dashboard/video-ai-templates/${item.id}/edit`)
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
  grid-template-columns: repeat(7, 1fr);
  gap: 14px;
  margin-bottom: 28px;
}

.vai-stat-card {
  background: #fff;
  border: 1px solid #e8edf5;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
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

/* Card grid */
.vai-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
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
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
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
</style>
