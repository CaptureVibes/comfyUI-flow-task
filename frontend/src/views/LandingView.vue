<template>
  <div class="story-landing">
    <canvas ref="bgCanvas" class="bg-canvas"></canvas>

    <!-- Nav -->
    <nav class="clean-nav gsap-nav">
      <div class="brand">
        <svg width="24" height="24" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" style="vertical-align:-5px;margin-right:7px;border-radius:6px">
          <defs>
            <linearGradient id="nav-bg" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#6366f1"/>
              <stop offset="100%" stop-color="#4f46e5"/>
            </linearGradient>
          </defs>
          <rect width="48" height="48" rx="12" fill="url(#nav-bg)"/>
          <path d="M 9 24 Q 9 9 24 9" stroke="white" stroke-width="2" stroke-linecap="round" opacity="0.3" fill="none"/>
          <path d="M 6 24 Q 6 6 24 6" stroke="white" stroke-width="1.5" stroke-linecap="round" opacity="0.15" fill="none"/>
          <circle cx="29" cy="29" r="2.2" fill="white" opacity="0.9"/>
          <circle cx="36.5" cy="29" r="2.2" fill="white" opacity="0.9"/>
          <circle cx="44" cy="29" r="2.2" fill="white" opacity="0.45"/>
          <circle cx="29" cy="36.5" r="2.2" fill="white" opacity="0.9"/>
          <circle cx="36.5" cy="36.5" r="2.2" fill="#10b981"/>
          <circle cx="44" cy="36.5" r="2.2" fill="white" opacity="0.45"/>
          <circle cx="29" cy="44" r="2.2" fill="white" opacity="0.45"/>
          <circle cx="36.5" cy="44" r="2.2" fill="white" opacity="0.45"/>
          <circle cx="44" cy="44" r="2.2" fill="white" opacity="0.25"/>
          <text x="7" y="31" font-family="'SF Pro Display','Inter',system-ui,sans-serif" font-size="24" font-weight="900" fill="white" letter-spacing="-1">E</text>
        </svg>
        EchoMatrix
      </div>
      <button class="primary-btn" @click="enterDashboard">登录控制台</button>
    </nav>

    <!-- Hero -->
    <main class="hero-story-section">
      <div class="story-container">
        <div class="intro-side gsap-intro">
          <div class="hero-badge">
            <span class="badge-dot"></span>
            自动化视频矩阵平台
          </div>
          <h1 class="hero-title">
            从剪辑噩梦到<br/>
            <span class="hero-emphasize">一键万条视频矩阵</span>
          </h1>
          <p class="hero-subtitle">
            告别对齐时间线、导出崩溃和重复劳动。<br>
            一条指令，EchoMatrix 在云端全自动生成、审阅并分发数千条高质量短视频。
          </p>
          <div class="hero-actions">
            <button class="primary-btn hero-btn" @click="enterDashboard">立刻开启自动化</button>
            <span class="hero-hint">已有 2,400+ 创作者在使用</span>
          </div>
        </div>

        <!-- Hero Right: Dashboard Preview -->
        <div class="animation-side gsap-intro">
          <div class="dashboard-preview">
            <!-- Window chrome -->
            <div class="win-bar">
              <span class="win-dot r"></span>
              <span class="win-dot y"></span>
              <span class="win-dot g"></span>
              <span class="win-title">EchoMatrix — 控制台</span>
            </div>

            <!-- Sidebar + content -->
            <div class="win-body">
              <div class="win-sidebar">
                <div
                  v-for="tab in previewTabs" :key="tab.id"
                  class="sb-item" :class="{ 'sb-active': activeTab === tab.id }"
                  @click="activeTab = tab.id"
                >
                  <span v-html="tab.icon"></span>
                  {{ tab.label }}
                </div>
              </div>

              <div class="win-main">
                <!-- Tab: 任务 -->
                <template v-if="activeTab === 'tasks'">
                  <div class="stat-row">
                    <div class="mini-stat">
                      <div class="mini-num" ref="statVideos">0</div>
                      <div class="mini-label">已生成视频</div>
                    </div>
                    <div class="mini-stat">
                      <div class="mini-num green" ref="statAccounts">0</div>
                      <div class="mini-label">活跃账号</div>
                    </div>
                    <div class="mini-stat">
                      <div class="mini-num purple" ref="statViews">0</div>
                      <div class="mini-label">累计播放</div>
                    </div>
                  </div>
                  <div class="task-list">
                    <div class="task-item" v-for="(task, i) in tasks" :key="i">
                      <div class="task-icon">
                        <svg v-if="task.status==='done'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                        <div v-else-if="task.status==='running'" class="spin-dot"></div>
                        <div v-else class="idle-dot"></div>
                      </div>
                      <div class="task-info">
                        <div class="task-name">{{ task.name }}</div>
                        <div class="task-progress-bar"><div class="task-progress-fill" :style="{ width: task.progress + '%', background: task.color }"></div></div>
                      </div>
                      <div class="task-count" :style="{ color: task.color }">{{ task.count }}</div>
                    </div>
                  </div>
                  <div class="live-feed">
                    <div class="feed-header"><span class="live-badge">● LIVE</span>实时生成日志</div>
                    <div class="feed-log">
                      <div class="log-line" v-for="(log, i) in logs" :key="i">
                        <span class="log-time">{{ log.time }}</span>
                        <span :class="'log-msg log-' + log.type">{{ log.msg }}</span>
                      </div>
                    </div>
                  </div>
                </template>

                <!-- Tab: 视频库 -->
                <template v-else-if="activeTab === 'videos'">
                  <div class="tab-section-title">最近解析视频</div>
                  <div class="video-grid-preview">
                    <div class="vp-card" v-for="v in videoItems" :key="v.id">
                      <div class="vp-thumb" :style="{ background: v.color }">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" opacity="0.8"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                      </div>
                      <div class="vp-info">
                        <div class="vp-name">{{ v.name }}</div>
                        <div class="vp-meta">{{ v.views }} 播放 · {{ v.score }}</div>
                      </div>
                      <div class="vp-badge" :class="v.pass ? 'pass' : 'fail'">{{ v.pass ? '✓' : '✗' }}</div>
                    </div>
                  </div>
                  <div class="live-feed" style="margin-top:auto">
                    <div class="feed-header"><span class="live-badge">● AI 审核中</span>自动打分</div>
                    <div class="feed-log">
                      <div class="log-line" v-for="(log, i) in logs.slice(0,3)" :key="i">
                        <span class="log-time">{{ log.time }}</span>
                        <span :class="'log-msg log-' + log.type">{{ log.msg }}</span>
                      </div>
                    </div>
                  </div>
                </template>

                <!-- Tab: 数据 -->
                <template v-else-if="activeTab === 'stats'">
                  <div class="tab-section-title">7日播放趋势</div>
                  <div class="mini-chart">
                    <div class="chart-bars-row">
                      <div v-for="(b, i) in chartBars" :key="i" class="chart-bar-wrap">
                        <div class="chart-bar-fill" :style="{ height: b.h + '%', background: b.color }"></div>
                        <div class="chart-bar-label">{{ b.label }}</div>
                      </div>
                    </div>
                  </div>
                  <div class="mini-stats-grid">
                    <div class="ms-item" v-for="s in miniStats" :key="s.label">
                      <div class="ms-val" :style="{ color: s.color }">{{ s.val }}</div>
                      <div class="ms-label">{{ s.label }}</div>
                    </div>
                  </div>
                </template>

                <!-- Tab: AI博主 -->
                <template v-else-if="activeTab === 'bloggers'">
                  <div class="tab-section-title">博主矩阵概览</div>
                  <div class="blogger-list-preview">
                    <div class="blg-item" v-for="b in bloggerItems" :key="b.name">
                      <div class="blg-avatar" :style="{ background: b.color }">{{ b.initial }}</div>
                      <div class="blg-info">
                        <div class="blg-name">{{ b.name }}</div>
                        <div class="blg-fans">{{ b.fans }} 粉丝</div>
                      </div>
                      <div class="blg-bar-wrap">
                        <div class="blg-bar"><div class="blg-bar-fill" :style="{ width: b.pct + '%', background: b.color }"></div></div>
                        <span class="blg-pct">{{ b.pct }}%</span>
                      </div>
                    </div>
                  </div>
                  <div class="blg-summary">
                    <div class="blg-sum-item"><span class="blg-sum-val">6</span><span class="blg-sum-key">活跃博主</span></div>
                    <div class="blg-sum-item"><span class="blg-sum-val green">+2,840</span><span class="blg-sum-key">今日新增粉丝</span></div>
                    <div class="blg-sum-item"><span class="blg-sum-val purple">86K</span><span class="blg-sum-key">总粉丝数</span></div>
                  </div>
                </template>

                <!-- Tab: AI模板 -->
                <template v-else-if="activeTab === 'templates'">
                  <div class="tab-section-title">已激活模板</div>
                  <div class="tpl-list-preview">
                    <div class="tpl-item" v-for="t in templateItems" :key="t.name">
                      <div class="tpl-color-bar" :style="{ background: t.color }"></div>
                      <div class="tpl-info">
                        <div class="tpl-name">{{ t.name }}</div>
                        <div class="tpl-meta">已生成 {{ t.count }} 条 · {{ t.model }}</div>
                      </div>
                      <div class="tpl-status" :class="t.active ? 'active' : 'idle'">
                        {{ t.active ? '运行中' : '待机' }}
                      </div>
                    </div>
                  </div>
                  <div class="tpl-pipeline">
                    <div class="tpl-step-row">
                      <div class="tpl-step" v-for="(s, i) in pipelineSteps" :key="i" :style="{ borderColor: s.color }">
                        <div class="tpl-step-dot" :style="{ background: s.color }"></div>
                        <span>{{ s.name }}</span>
                      </div>
                    </div>
                    <div class="tpl-pipe-label">AI 生产流水线</div>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Features -->
    <section class="features-section">
      <div class="section-header gsap-row">
        <div class="section-eyebrow">核心功能</div>
        <h2 class="section-title">从生产到分发，全链路自动化</h2>
      </div>

      <!-- Feature 1: AI Review -->
      <div class="feature-row row-left gsap-row">
        <div class="feature-text">
          <div class="feature-tag">AI 内容审核</div>
          <h3>多模态视觉打分，摒弃垃圾内容</h3>
          <p>EchoMatrix 内建视觉感知模型，像最严苛的剪辑主编一样逐帧过滤低画质、无网感或表情穿模的废片。只把极具爆款潜质的作品推入分发矩阵，捍卫账号质量。</p>
        </div>
        <div class="feature-visual">
          <div class="visual-card">
            <svg class="feat-svg" viewBox="0 0 380 260" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="380" height="260" fill="#f8fafc" rx="14"/>
              <!-- Header -->
              <rect width="380" height="44" fill="white" rx="14"/>
              <rect y="30" width="380" height="14" fill="white"/>
              <text x="20" y="28" font-size="11" font-weight="800" fill="#64748b" font-family="monospace" letter-spacing="1">AI CONTENT REVIEW</text>
              <rect x="320" y="12" width="46" height="20" rx="10" fill="#d1fae5"/>
              <text x="329" y="26" font-size="10" fill="#059669" font-weight="700" font-family="sans-serif">LIVE ●</text>

              <!-- Video thumbnails row -->
              <g class="rc1 review-card">
                <rect x="20" y="58" width="92" height="68" rx="8" fill="#dbeafe" stroke="#93c5fd" stroke-width="1.5"/>
                <rect x="28" y="64" width="76" height="44" rx="4" fill="#60a5fa"/>
                <polygon points="52,80 52,96 68,88" fill="white" opacity="0.9"/>
                <rect x="28" y="112" width="50" height="8" rx="4" fill="#bfdbfe"/>
                <rect x="28" y="116" width="30" height="4" rx="2" fill="none"/>
                <rect x="28" y="124" width="42" height="16" rx="8" fill="#10b981" class="pass-badge"/>
                <text x="35" y="136" font-size="9" fill="white" font-weight="800" font-family="sans-serif">✓ PASS</text>
              </g>

              <g class="rc2 review-card">
                <rect x="128" y="58" width="92" height="68" rx="8" fill="#fee2e2" stroke="#fca5a5" stroke-width="1.5"/>
                <rect x="136" y="64" width="76" height="44" rx="4" fill="#f87171"/>
                <line x1="143" y1="71" x2="205" y2="101" stroke="#ef4444" stroke-width="3" stroke-linecap="round"/>
                <line x1="205" y1="71" x2="143" y2="101" stroke="#ef4444" stroke-width="3" stroke-linecap="round"/>
                <rect x="136" y="124" width="58" height="16" rx="8" fill="#ef4444" class="fail-badge"/>
                <text x="142" y="136" font-size="9" fill="white" font-weight="800" font-family="sans-serif">✗ REJECT</text>
              </g>

              <g class="rc3 review-card">
                <rect x="236" y="58" width="92" height="68" rx="8" fill="#dbeafe" stroke="#93c5fd" stroke-width="1.5"/>
                <rect x="244" y="64" width="76" height="44" rx="4" fill="#60a5fa"/>
                <polygon points="268,80 268,96 284,88" fill="white" opacity="0.9"/>
                <rect x="244" y="124" width="50" height="16" rx="8" fill="#10b981" class="pass-badge2"/>
                <text x="251" y="136" font-size="9" fill="white" font-weight="800" font-family="sans-serif">✓ PASS</text>
              </g>

              <!-- Score section -->
              <rect x="20" y="148" width="340" height="96" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1"/>
              <text x="32" y="168" font-size="10" fill="#64748b" font-weight="700" font-family="sans-serif">综合评分</text>

              <text x="32" y="190" font-size="10" fill="#94a3b8" font-family="sans-serif">画质</text>
              <rect x="72" y="182" width="220" height="7" rx="3.5" fill="#f1f5f9"/>
              <rect x="72" y="182" width="198" height="7" rx="3.5" fill="#10b981" class="sb1"/>
              <text x="298" y="190" font-size="10" fill="#10b981" font-weight="700" font-family="sans-serif">90%</text>

              <text x="32" y="212" font-size="10" fill="#94a3b8" font-family="sans-serif">爆款率</text>
              <rect x="72" y="204" width="220" height="7" rx="3.5" fill="#f1f5f9"/>
              <rect x="72" y="204" width="176" height="7" rx="3.5" fill="#6366f1" class="sb2"/>
              <text x="298" y="212" font-size="10" fill="#6366f1" font-weight="700" font-family="sans-serif">80%</text>

              <text x="32" y="234" font-size="10" fill="#94a3b8" font-family="sans-serif">互动率</text>
              <rect x="72" y="226" width="220" height="7" rx="3.5" fill="#f1f5f9"/>
              <rect x="72" y="226" width="154" height="7" rx="3.5" fill="#f59e0b" class="sb3"/>
              <text x="298" y="234" font-size="10" fill="#f59e0b" font-weight="700" font-family="sans-serif">70%</text>
            </svg>
          </div>
        </div>
      </div>

      <!-- Feature 2: Distribution -->
      <div class="feature-row row-right gsap-row">
        <div class="feature-text">
          <div class="feature-tag">矩阵分发</div>
          <h3>多路账号全网同步铺量</h3>
          <p>不用再费力切换数百个账户。对接中控枢纽，按照精确的计划表进行毫秒级铺量。系统后台实时监听各路推送反馈，全天候 24/7 等待指令运行，彻底解放你的双手。</p>
        </div>
        <div class="feature-visual">
          <div class="visual-card">
            <svg class="feat-svg" viewBox="0 0 380 260" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="380" height="260" fill="#f8fafc" rx="14"/>
              <!-- Center -->
              <circle cx="190" cy="128" r="36" fill="#eef2ff" stroke="#c7d2fe" stroke-width="2"/>
              <circle cx="190" cy="128" r="25" fill="#6366f1"/>
              <text x="177" y="124" font-size="9" fill="white" font-weight="700" font-family="sans-serif">Echo</text>
              <text x="174" y="136" font-size="9" fill="white" font-weight="700" font-family="sans-serif">Matrix</text>
              <circle cx="190" cy="128" r="36" fill="none" stroke="#6366f1" stroke-width="1.5" class="pulse-ring r1"/>
              <circle cx="190" cy="128" r="36" fill="none" stroke="#6366f1" stroke-width="1" class="pulse-ring r2"/>

              <!-- Lines -->
              <line x1="190" y1="128" x2="65" y2="42" stroke="#c7d2fe" stroke-width="1.5" stroke-dasharray="5 3"/>
              <line x1="190" y1="128" x2="315" y2="42" stroke="#c7d2fe" stroke-width="1.5" stroke-dasharray="5 3"/>
              <line x1="190" y1="128" x2="40" y2="155" stroke="#c7d2fe" stroke-width="1.5" stroke-dasharray="5 3"/>
              <line x1="190" y1="128" x2="340" y2="155" stroke="#c7d2fe" stroke-width="1.5" stroke-dasharray="5 3"/>
              <line x1="190" y1="128" x2="90" y2="222" stroke="#c7d2fe" stroke-width="1.5" stroke-dasharray="5 3"/>
              <line x1="190" y1="128" x2="290" y2="222" stroke="#c7d2fe" stroke-width="1.5" stroke-dasharray="5 3"/>

              <!-- Nodes -->
              <g class="target-node tn1"><circle cx="65" cy="42" r="22" fill="#fff7ed" stroke="#fed7aa" stroke-width="1.5"/><text x="51" y="38" font-size="8.5" fill="#c2410c" font-weight="700" font-family="sans-serif">TikTok</text><text x="52" y="50" font-size="8.5" fill="#c2410c" font-family="sans-serif">@acc01</text></g>
              <g class="target-node tn2"><circle cx="315" cy="42" r="22" fill="#fff7ed" stroke="#fed7aa" stroke-width="1.5"/><text x="301" y="38" font-size="8.5" fill="#c2410c" font-weight="700" font-family="sans-serif">TikTok</text><text x="302" y="50" font-size="8.5" fill="#c2410c" font-family="sans-serif">@acc02</text></g>
              <g class="target-node tn3"><circle cx="40" cy="155" r="22" fill="#f0fdf4" stroke="#bbf7d0" stroke-width="1.5"/><text x="26" y="151" font-size="8.5" fill="#15803d" font-weight="700" font-family="sans-serif">TikTok</text><text x="27" y="163" font-size="8.5" fill="#15803d" font-family="sans-serif">@acc03</text></g>
              <g class="target-node tn4"><circle cx="340" cy="155" r="22" fill="#f0fdf4" stroke="#bbf7d0" stroke-width="1.5"/><text x="326" y="151" font-size="8.5" fill="#15803d" font-weight="700" font-family="sans-serif">TikTok</text><text x="327" y="163" font-size="8.5" fill="#15803d" font-family="sans-serif">@acc04</text></g>
              <g class="target-node tn5"><circle cx="90" cy="222" r="22" fill="#fdf4ff" stroke="#e9d5ff" stroke-width="1.5"/><text x="76" y="218" font-size="8.5" fill="#7e22ce" font-weight="700" font-family="sans-serif">TikTok</text><text x="77" y="230" font-size="8.5" fill="#7e22ce" font-family="sans-serif">@acc05</text></g>
              <g class="target-node tn6"><circle cx="290" cy="222" r="22" fill="#fdf4ff" stroke="#e9d5ff" stroke-width="1.5"/><text x="276" y="218" font-size="8.5" fill="#7e22ce" font-weight="700" font-family="sans-serif">TikTok</text><text x="277" y="230" font-size="8.5" fill="#7e22ce" font-family="sans-serif">@acc06</text></g>

              <!-- Packets -->
              <circle class="packet p-t1" r="4.5" fill="#6366f1" opacity="0"/>
              <circle class="packet p-t2" r="4.5" fill="#6366f1" opacity="0"/>
              <circle class="packet p-t3" r="4.5" fill="#10b981" opacity="0"/>
              <circle class="packet p-t4" r="4.5" fill="#10b981" opacity="0"/>
              <circle class="packet p-t5" r="4.5" fill="#8b5cf6" opacity="0"/>
              <circle class="packet p-t6" r="4.5" fill="#8b5cf6" opacity="0"/>
            </svg>
          </div>
        </div>
      </div>

      <!-- Feature 3: Analytics -->
      <div class="feature-row row-left gsap-row">
        <div class="feature-text">
          <div class="feature-tag">数据分析</div>
          <h3>全链路追踪，洞察爆款规律</h3>
          <p>每条视频的播放量、点赞、粉丝增长全部实时汇总。AI 自动分析爆款规律，持续优化下一批内容策略，让每次投放都比上一次更精准。</p>
        </div>
        <div class="feature-visual">
          <div class="visual-card">
            <svg class="feat-svg analytics-svg" viewBox="0 0 380 260" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="380" height="260" fill="#f8fafc" rx="14"/>
              <!-- Stat cards -->
              <g class="stat-card sc1"><rect x="14" y="14" width="106" height="56" rx="9" fill="white" stroke="#e2e8f0" stroke-width="1.5"/><text x="24" y="34" font-size="10" fill="#94a3b8" font-family="sans-serif">总播放量</text><text x="24" y="56" font-size="19" fill="#0f172a" font-weight="900" font-family="sans-serif">2.4M</text><text x="86" y="56" font-size="10" fill="#10b981" font-weight="700" font-family="sans-serif">↑12%</text></g>
              <g class="stat-card sc2"><rect x="136" y="14" width="106" height="56" rx="9" fill="white" stroke="#e2e8f0" stroke-width="1.5"/><text x="146" y="34" font-size="10" fill="#94a3b8" font-family="sans-serif">总粉丝数</text><text x="146" y="56" font-size="19" fill="#0f172a" font-weight="900" font-family="sans-serif">86K</text><text x="202" y="56" font-size="10" fill="#10b981" font-weight="700" font-family="sans-serif">↑8%</text></g>
              <g class="stat-card sc3"><rect x="258" y="14" width="106" height="56" rx="9" fill="white" stroke="#e2e8f0" stroke-width="1.5"/><text x="268" y="34" font-size="10" fill="#94a3b8" font-family="sans-serif">在线视频</text><text x="268" y="56" font-size="19" fill="#6366f1" font-weight="900" font-family="sans-serif">10K</text><text x="321" y="56" font-size="10" fill="#10b981" font-weight="700" font-family="sans-serif">+243</text></g>

              <!-- Chart -->
              <rect x="14" y="84" width="352" height="160" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
              <text x="26" y="103" font-size="10" fill="#64748b" font-weight="700" font-family="sans-serif">7日播放趋势</text>
              <!-- Grid -->
              <line x1="26" y1="118" x2="358" y2="118" stroke="#f1f5f9" stroke-width="1"/>
              <line x1="26" y1="133" x2="358" y2="133" stroke="#f1f5f9" stroke-width="1"/>
              <line x1="26" y1="148" x2="358" y2="148" stroke="#f1f5f9" stroke-width="1"/>
              <line x1="26" y1="163" x2="358" y2="163" stroke="#f1f5f9" stroke-width="1"/>
              <line x1="26" y1="178" x2="358" y2="178" stroke="#f1f5f9" stroke-width="1"/>
              <line x1="26" y1="193" x2="358" y2="193" stroke="#f1f5f9" stroke-width="1"/>
              <line x1="26" y1="210" x2="358" y2="210" stroke="#f1f5f9" stroke-width="1"/>
              <!-- Bars -->
              <rect x="38" y="172" width="30" height="38" rx="3" fill="#c7d2fe" class="cb1"/>
              <rect x="88" y="158" width="30" height="52" rx="3" fill="#a5b4fc" class="cb2"/>
              <rect x="138" y="148" width="30" height="62" rx="3" fill="#818cf8" class="cb3"/>
              <rect x="188" y="138" width="30" height="72" rx="3" fill="#6366f1" class="cb4"/>
              <rect x="238" y="124" width="30" height="86" rx="3" fill="#4f46e5" class="cb5"/>
              <rect x="288" y="114" width="30" height="96" rx="3" fill="#4338ca" class="cb6"/>
              <rect x="338" y="104" width="14" height="106" rx="3" fill="#3730a3" class="cb7"/>
              <!-- Trend line -->
              <polyline points="53,177 103,163 153,153 203,143 253,129 303,119 345,109" stroke="#f59e0b" stroke-width="2.5" fill="none" class="trend-line" stroke-dasharray="500" stroke-dashoffset="500"/>
              <!-- X labels -->
              <text x="40" y="226" font-size="9" fill="#94a3b8" font-family="sans-serif">周一</text>
              <text x="90" y="226" font-size="9" fill="#94a3b8" font-family="sans-serif">周二</text>
              <text x="140" y="226" font-size="9" fill="#94a3b8" font-family="sans-serif">周三</text>
              <text x="190" y="226" font-size="9" fill="#94a3b8" font-family="sans-serif">周四</text>
              <text x="240" y="226" font-size="9" fill="#94a3b8" font-family="sans-serif">周五</text>
              <text x="290" y="226" font-size="9" fill="#94a3b8" font-family="sans-serif">周六</text>
              <text x="332" y="226" font-size="9" fill="#6366f1" font-weight="700" font-family="sans-serif">周日</text>
            </svg>
          </div>
        </div>
      </div>

      <!-- Feature 4: AI Template -->
      <div class="feature-row row-right gsap-row">
        <div class="feature-text">
          <div class="feature-tag">AI 模板引擎</div>
          <h3>一次配置，无限复用的内容工厂</h3>
          <p>通过可视化模板编辑器定义你的内容风格：字幕样式、BGM 节奏、转场效果、画面滤镜。每次生成都严格遵循模板，保持账号风格高度一致，强化品牌辨识度。</p>
        </div>
        <div class="feature-visual">
          <div class="visual-card">
            <svg class="feat-svg template-svg" viewBox="0 0 380 260" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="380" height="260" fill="#f8fafc" rx="14"/>
              <!-- Template card -->
              <rect x="14" y="14" width="352" height="44" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
              <rect x="26" y="24" width="24" height="24" rx="6" fill="#6366f1"/>
              <text x="31" y="41" font-size="14" fill="white">T</text>
              <text x="60" y="34" font-size="11" fill="#0f172a" font-weight="700" font-family="sans-serif">美妆穿搭·爆款模板 v3</text>
              <text x="60" y="48" font-size="10" fill="#94a3b8" font-family="sans-serif">已应用 4,231 次</text>
              <rect x="310" y="22" width="44" height="20" rx="10" fill="#dbeafe"/>
              <text x="318" y="36" font-size="9" fill="#1d4ed8" font-weight="700" font-family="sans-serif">激活中</text>

              <!-- Step pipeline -->
              <g class="tpl-step ts1">
                <rect x="14" y="70" width="80" height="70" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
                <rect x="14" y="70" width="80" height="8" rx="10" fill="#6366f1"/>
                <rect x="14" y="74" width="80" height="4" fill="#6366f1"/>
                <text x="30" y="100" font-size="10" fill="#64748b" font-weight="700" font-family="sans-serif">视频解析</text>
                <text x="22" y="116" font-size="9" fill="#94a3b8" font-family="sans-serif">提取人物动作</text>
                <text x="22" y="128" font-size="9" fill="#94a3b8" font-family="sans-serif">识别服装特征</text>
              </g>
              <text x="101" y="109" font-size="16" fill="#c7d2fe" font-weight="300">→</text>
              <g class="tpl-step ts2">
                <rect x="114" y="70" width="80" height="70" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
                <rect x="114" y="70" width="80" height="8" rx="10" fill="#8b5cf6"/>
                <rect x="114" y="74" width="80" height="4" fill="#8b5cf6"/>
                <text x="126" y="100" font-size="10" fill="#64748b" font-weight="700" font-family="sans-serif">AI 生成</text>
                <text x="122" y="116" font-size="9" fill="#94a3b8" font-family="sans-serif">重写脚本文案</text>
                <text x="122" y="128" font-size="9" fill="#94a3b8" font-family="sans-serif">匹配音乐节奏</text>
              </g>
              <text x="201" y="109" font-size="16" fill="#c7d2fe" font-weight="300">→</text>
              <g class="tpl-step ts3">
                <rect x="214" y="70" width="80" height="70" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
                <rect x="214" y="70" width="80" height="8" rx="10" fill="#f59e0b"/>
                <rect x="214" y="74" width="80" height="4" fill="#f59e0b"/>
                <text x="224" y="100" font-size="10" fill="#64748b" font-weight="700" font-family="sans-serif">视频合成</text>
                <text x="222" y="116" font-size="9" fill="#94a3b8" font-family="sans-serif">字幕渲染叠加</text>
                <text x="222" y="128" font-size="9" fill="#94a3b8" font-family="sans-serif">转场特效合成</text>
              </g>
              <text x="301" y="109" font-size="16" fill="#c7d2fe" font-weight="300">→</text>
              <g class="tpl-step ts4">
                <rect x="314" y="70" width="52" height="70" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
                <rect x="314" y="70" width="52" height="8" rx="10" fill="#10b981"/>
                <rect x="314" y="74" width="52" height="4" fill="#10b981"/>
                <text x="322" y="100" font-size="10" fill="#64748b" font-weight="700" font-family="sans-serif">发布</text>
                <text x="318" y="116" font-size="9" fill="#94a3b8" font-family="sans-serif">自动</text>
                <text x="318" y="128" font-size="9" fill="#94a3b8" font-family="sans-serif">上传</text>
              </g>

              <!-- Output preview -->
              <rect x="14" y="154" width="352" height="90" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
              <text x="26" y="173" font-size="10" fill="#64748b" font-weight="700" font-family="sans-serif">最近输出</text>
              <g class="tpl-output to1">
                <rect x="26" y="180" width="48" height="52" rx="6" fill="#dbeafe"/>
                <rect x="26" y="180" width="48" height="32" rx="6" fill="#60a5fa"/>
                <polygon points="38,190 38,204 52,197" fill="white" opacity="0.9"/>
                <text x="30" y="244" font-size="9" fill="#64748b" font-family="sans-serif">v_001.mp4</text>
              </g>
              <g class="tpl-output to2">
                <rect x="84" y="180" width="48" height="52" rx="6" fill="#dbeafe"/>
                <rect x="84" y="180" width="48" height="32" rx="6" fill="#818cf8"/>
                <polygon points="96,190 96,204 110,197" fill="white" opacity="0.9"/>
                <text x="88" y="244" font-size="9" fill="#64748b" font-family="sans-serif">v_002.mp4</text>
              </g>
              <g class="tpl-output to3">
                <rect x="142" y="180" width="48" height="52" rx="6" fill="#dbeafe"/>
                <rect x="142" y="180" width="48" height="32" rx="6" fill="#34d399"/>
                <polygon points="154,190 154,204 168,197" fill="white" opacity="0.9"/>
                <text x="146" y="244" font-size="9" fill="#64748b" font-family="sans-serif">v_003.mp4</text>
              </g>
              <text x="202" y="210" font-size="22" fill="#c7d2fe">···</text>
              <text x="260" y="210" font-size="13" fill="#0f172a" font-weight="800" font-family="sans-serif">× 4,231</text>
              <text x="260" y="226" font-size="10" fill="#94a3b8" font-family="sans-serif">条视频已生成</text>
            </svg>
          </div>
        </div>
      </div>

      <!-- Feature 5: Scheduler -->
      <div class="feature-row row-left gsap-row">
        <div class="feature-text">
          <div class="feature-tag">智能调度</div>
          <h3>精准排期，黄金时段自动铺量</h3>
          <p>内置流量预测模型，自动识别目标受众的活跃时间窗口。支持设定发布频率、时段偏好、地区定向，让每条视频都在最佳时机触达最精准的用户。</p>
        </div>
        <div class="feature-visual">
          <div class="visual-card">
            <svg class="feat-svg sched-svg" viewBox="0 0 380 260" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="380" height="260" fill="#f8fafc" rx="14"/>
              <!-- Calendar header -->
              <rect x="14" y="14" width="352" height="40" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
              <text x="26" y="39" font-size="13" fill="#0f172a" font-weight="800" font-family="sans-serif">四月 2025</text>
              <rect x="316" y="22" width="20" height="20" rx="5" fill="#f1f5f9"/>
              <text x="322" y="36" font-size="12" fill="#64748b">‹</text>
              <rect x="340" y="22" width="20" height="20" rx="5" fill="#f1f5f9"/>
              <text x="346" y="36" font-size="12" fill="#64748b">›</text>

              <!-- Day headers -->
              <text x="22" y="72" font-size="9" fill="#94a3b8" font-family="sans-serif">一</text>
              <text x="72" y="72" font-size="9" fill="#94a3b8" font-family="sans-serif">二</text>
              <text x="122" y="72" font-size="9" fill="#94a3b8" font-family="sans-serif">三</text>
              <text x="172" y="72" font-size="9" fill="#94a3b8" font-family="sans-serif">四</text>
              <text x="222" y="72" font-size="9" fill="#94a3b8" font-family="sans-serif">五</text>
              <text x="271" y="72" font-size="9" fill="#6366f1" font-weight="700" font-family="sans-serif">六</text>
              <text x="321" y="72" font-size="9" fill="#6366f1" font-weight="700" font-family="sans-serif">日</text>

              <!-- Calendar grid with scheduled events -->
              <!-- Row 1 -->
              <rect x="14" y="78" width="44" height="38" rx="6" fill="white" stroke="#e2e8f0" stroke-width="1"/><text x="30" y="100" font-size="11" fill="#0f172a" font-family="sans-serif">1</text>
              <rect x="64" y="78" width="44" height="38" rx="6" fill="white" stroke="#e2e8f0" stroke-width="1"/><text x="80" y="100" font-size="11" fill="#0f172a" font-family="sans-serif">2</text>
              <rect x="114" y="78" width="44" height="38" rx="6" fill="white" stroke="#e2e8f0" stroke-width="1"/><text x="130" y="100" font-size="11" fill="#0f172a" font-family="sans-serif">3</text>
              <rect x="164" y="78" width="44" height="38" rx="6" fill="#eef2ff" stroke="#c7d2fe" stroke-width="1.5"/><text x="180" y="94" font-size="11" fill="#4338ca" font-family="sans-serif">4</text><text x="170" y="108" font-size="8" fill="#6366f1" font-family="sans-serif">× 80条</text>
              <rect x="214" y="78" width="44" height="38" rx="6" fill="white" stroke="#e2e8f0" stroke-width="1"/><text x="230" y="100" font-size="11" fill="#0f172a" font-family="sans-serif">5</text>
              <rect x="264" y="78" width="44" height="38" rx="6" fill="#fef3c7" stroke="#fde68a" stroke-width="1.5"/><text x="278" y="94" font-size="11" fill="#d97706" font-family="sans-serif">6</text><text x="268" y="108" font-size="8" fill="#d97706" font-family="sans-serif">× 240条</text>
              <rect x="314" y="78" width="44" height="38" rx="6" fill="#fef3c7" stroke="#fde68a" stroke-width="1.5"/><text x="328" y="94" font-size="11" fill="#d97706" font-family="sans-serif">7</text><text x="318" y="108" font-size="8" fill="#d97706" font-family="sans-serif">× 320条</text>

              <!-- Row 2 -->
              <rect x="14" y="122" width="44" height="38" rx="6" fill="white" stroke="#e2e8f0" stroke-width="1"/><text x="30" y="144" font-size="11" fill="#0f172a" font-family="sans-serif">8</text>
              <rect x="64" y="122" width="44" height="38" rx="6" fill="white" stroke="#e2e8f0" stroke-width="1"/><text x="80" y="144" font-size="11" fill="#0f172a" font-family="sans-serif">9</text>
              <rect x="114" y="122" width="44" height="38" rx="6" fill="#eef2ff" stroke="#c7d2fe" stroke-width="1.5"/><text x="128" y="138" font-size="11" fill="#4338ca" font-family="sans-serif">10</text><text x="118" y="152" font-size="8" fill="#6366f1" font-family="sans-serif">× 120条</text>
              <rect x="164" y="122" width="44" height="38" rx="6" fill="white" stroke="#e2e8f0" stroke-width="1"/><text x="178" y="144" font-size="11" fill="#0f172a" font-family="sans-serif">11</text>
              <rect x="214" y="122" width="44" height="38" rx="6" fill="#eef2ff" stroke="#c7d2fe" stroke-width="1.5"/><text x="228" y="138" font-size="11" fill="#4338ca" font-family="sans-serif">12</text><text x="218" y="152" font-size="8" fill="#6366f1" font-family="sans-serif">× 90条</text>
              <rect x="264" y="122" width="44" height="38" rx="6" fill="#fef3c7" stroke="#fde68a" stroke-width="1.5"/><text x="276" y="138" font-size="11" fill="#d97706" font-family="sans-serif">13</text><text x="268" y="152" font-size="8" fill="#d97706" font-family="sans-serif">× 280条</text>
              <rect x="314" y="122" width="44" height="38" rx="6" fill="#fef3c7" stroke="#fde68a" stroke-width="1.5"/><text x="326" y="138" font-size="11" fill="#d97706" font-family="sans-serif">14</text><text x="318" y="152" font-size="8" fill="#d97706" font-family="sans-serif">× 300条</text>

              <!-- Today highlight -->
              <rect x="14" y="168" width="44" height="38" rx="6" fill="#6366f1"/>
              <text x="30" y="190" font-size="11" fill="white" font-weight="700" font-family="sans-serif">15</text>
              <text x="18" y="200" font-size="8" fill="#c7d2fe" font-family="sans-serif">今日</text>

              <!-- Legend -->
              <rect x="14" y="220" width="352" height="28" rx="8" fill="white" stroke="#e2e8f0" stroke-width="1"/>
              <rect x="26" y="230" width="10" height="10" rx="2" fill="#eef2ff" stroke="#c7d2fe" stroke-width="1"/>
              <text x="40" y="239" font-size="9" fill="#64748b" font-family="sans-serif">工作日铺量</text>
              <rect x="126" y="230" width="10" height="10" rx="2" fill="#fef3c7" stroke="#fde68a" stroke-width="1"/>
              <text x="140" y="239" font-size="9" fill="#64748b" font-family="sans-serif">周末爆量</text>
              <rect x="220" y="230" width="10" height="10" rx="2" fill="#6366f1"/>
              <text x="234" y="239" font-size="9" fill="#64748b" font-family="sans-serif">今日</text>
            </svg>
          </div>
        </div>
      </div>

      <!-- Feature 6: Blogger Tracking -->
      <div class="feature-row row-right gsap-row">
        <div class="feature-text">
          <div class="feature-tag">博主追踪</div>
          <h3>竞品监控，把握行业热点动向</h3>
          <p>一键订阅竞品博主主页，自动抓取其最新视频并解析爆款结构。结合你自己的数据，让 AI 生成差异化策略建议，帮你持续保持内容领先优势。</p>
        </div>
        <div class="feature-visual">
          <div class="visual-card">
            <svg class="feat-svg blogger-svg" viewBox="0 0 380 260" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect width="380" height="260" fill="#f8fafc" rx="14"/>
              <!-- Header -->
              <rect x="14" y="14" width="352" height="40" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
              <text x="26" y="39" font-size="12" fill="#0f172a" font-weight="800" font-family="sans-serif">博主追踪雷达</text>
              <rect x="320" y="22" width="34" height="20" rx="10" fill="#d1fae5"/>
              <text x="326" y="36" font-size="9" fill="#059669" font-weight="700" font-family="sans-serif">+ 订阅</text>

              <!-- Blogger cards -->
              <g class="blogger-card bc1">
                <rect x="14" y="64" width="168" height="82" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
                <circle cx="38" cy="88" r="16" fill="#fde68a"/>
                <text x="30" y="94" font-size="14" font-family="sans-serif">👗</text>
                <text x="60" y="83" font-size="11" fill="#0f172a" font-weight="700" font-family="sans-serif">@fashion_kol</text>
                <text x="60" y="96" font-size="9" fill="#94a3b8" font-family="sans-serif">1.2M 粉丝</text>
                <rect x="26" y="108" width="68" height="6" rx="3" fill="#f1f5f9"/>
                <rect x="26" y="108" width="52" height="6" rx="3" fill="#f59e0b" class="bk-bar bb1"/>
                <text x="100" y="115" font-size="9" fill="#f59e0b" font-weight="700" font-family="sans-serif">76%热度</text>
                <rect x="26" y="120" width="68" height="6" rx="3" fill="#f1f5f9"/>
                <rect x="26" y="120" width="60" height="6" rx="3" fill="#10b981" class="bk-bar bb2"/>
                <text x="100" y="127" font-size="9" fill="#10b981" font-weight="700" font-family="sans-serif">88%互动</text>
              </g>

              <g class="blogger-card bc2">
                <rect x="198" y="64" width="168" height="82" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
                <circle cx="222" cy="88" r="16" fill="#dbeafe"/>
                <text x="214" y="94" font-size="14" font-family="sans-serif">💄</text>
                <text x="244" y="83" font-size="11" fill="#0f172a" font-weight="700" font-family="sans-serif">@beauty_star</text>
                <text x="244" y="96" font-size="9" fill="#94a3b8" font-family="sans-serif">890K 粉丝</text>
                <rect x="210" y="108" width="68" height="6" rx="3" fill="#f1f5f9"/>
                <rect x="210" y="108" width="56" height="6" rx="3" fill="#6366f1" class="bk-bar bb3"/>
                <text x="284" y="115" font-size="9" fill="#6366f1" font-weight="700" font-family="sans-serif">82%热度</text>
                <rect x="210" y="120" width="68" height="6" rx="3" fill="#f1f5f9"/>
                <rect x="210" y="120" width="46" height="6" rx="3" fill="#10b981" class="bk-bar bb4"/>
                <text x="284" y="127" font-size="9" fill="#10b981" font-weight="700" font-family="sans-serif">68%互动</text>
              </g>

              <!-- AI insight card -->
              <rect x="14" y="158" width="352" height="88" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1.5"/>
              <rect x="14" y="158" width="352" height="6" rx="10" fill="linear-gradient(90deg,#6366f1,#8b5cf6)"/>
              <rect x="14" y="158" width="352" height="6" rx="10" fill="#6366f1"/>
              <text x="26" y="180" font-size="10" fill="#6366f1" font-weight="800" font-family="sans-serif">✦ AI 策略建议</text>
              <rect x="26" y="188" width="328" height="1" fill="#f1f5f9"/>
              <text x="26" y="204" font-size="10" fill="#475569" font-family="sans-serif">• @fashion_kol 近期"穿搭开箱"系列互动率高达 92%，建议跟进同类型内容</text>
              <text x="26" y="220" font-size="10" fill="#475569" font-family="sans-serif">• 周六晚 20:00-22:00 发布窗口竞争度低，流量红利明显，优先排期</text>
              <text x="26" y="236" font-size="10" fill="#475569" font-family="sans-serif">• 检测到新兴话题 #outfit_of_the_day 热度上升 340%，立即生成相关视频</text>
            </svg>
          </div>
        </div>
      </div>

    </section>

    <!-- CTA section -->
    <section class="cta-section gsap-row">
      <div class="cta-inner">
        <h2 class="cta-title">准备好告别重复劳动了吗？</h2>
        <p class="cta-sub">加入 2,400+ 创作者，用 EchoMatrix 构建你的内容帝国</p>
        <button class="primary-btn cta-btn" @click="enterDashboard">免费开始使用</button>
      </div>
    </section>

    <footer class="clean-footer">
      <p>EchoMatrix 控制台 © 2025</p>
    </footer>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

const router = useRouter()
const bgCanvas = ref(null)
const feedLog = ref(null)
const statVideos = ref(null)
const statAccounts = ref(null)
const statViews = ref(null)

function enterDashboard() {
  const t = localStorage.getItem('task_manager_token')
  router.push(t ? '/dashboard' : '/login')
}

// --- Tab state ---
const activeTab = ref('tasks')
const previewTabs = [
  { id: 'tasks', label: '任务', icon: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>' },
  { id: 'videos', label: '视频库', icon: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>' },
  { id: 'stats', label: '数据', icon: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>' },
  { id: 'bloggers', label: 'AI博主', icon: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>' },
  { id: 'templates', label: 'AI模板', icon: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M3 9h6"/></svg>' },
]

// --- Video library tab data ---
const videoItems = [
  { id: 1, name: 'outfit_kol_0421.mp4', views: '12.4万', score: '得分 92', pass: true, color: '#60a5fa' },
  { id: 2, name: 'beauty_trend_0422.mp4', views: '3.1万', score: '得分 48', pass: false, color: '#f87171' },
  { id: 3, name: 'haul_video_0423.mp4', views: '8.9万', score: '得分 87', pass: true, color: '#34d399' },
  { id: 4, name: 'makeup_tips_0424.mp4', views: '15.2万', score: '得分 95', pass: true, color: '#a78bfa' },
]

// --- Stats tab data ---
const chartBars = [
  { h: 38, color: '#c7d2fe', label: '一' },
  { h: 52, color: '#a5b4fc', label: '二' },
  { h: 60, color: '#818cf8', label: '三' },
  { h: 70, color: '#6366f1', label: '四' },
  { h: 82, color: '#4f46e5', label: '五' },
  { h: 92, color: '#4338ca', label: '六' },
  { h: 100, color: '#3730a3', label: '日' },
]
const miniStats = [
  { val: '2.4M', label: '总播放', color: '#6366f1' },
  { val: '86K', label: '总粉丝', color: '#10b981' },
  { val: '↑12%', label: '本周增长', color: '#f59e0b' },
]

// --- Blogger tab data ---
const bloggerItems = [
  { name: '@fashion_kol_01', fans: '24K', pct: 88, color: '#6366f1', initial: 'F' },
  { name: '@beauty_star_02', fans: '19K', pct: 72, color: '#f59e0b', initial: 'B' },
  { name: '@outfit_daily_03', fans: '15K', pct: 61, color: '#10b981', initial: 'O' },
  { name: '@makeup_pro_04', fans: '12K', pct: 45, color: '#ec4899', initial: 'M' },
]

// --- Template tab data ---
const templateItems = [
  { name: '美妆穿搭·爆款模板', count: '4,231', model: 'Gemini Pro', active: true, color: '#6366f1' },
  { name: '电商带货·挂车模板', count: '2,180', model: 'GPT-4o', active: true, color: '#10b981' },
  { name: '知识科普·干货模板', count: '890', model: 'Claude 3', active: false, color: '#f59e0b' },
]
const pipelineSteps = [
  { name: '视频解析', color: '#6366f1' },
  { name: 'AI生成', color: '#8b5cf6' },
  { name: '合成渲染', color: '#f59e0b' },
  { name: '自动发布', color: '#10b981' },
]

// --- Tasks data (reactive for animation) ---
const tasks = reactive([
  { name: '美妆穿搭 · 批量生成', status: 'done', progress: 100, count: '2,400条', color: '#10b981' },
  { name: '电商带货 · 视频矩阵', status: 'running', progress: 67, count: '1,340/2,000', color: '#6366f1' },
  { name: '知识科普 · 多账号分发', status: 'running', progress: 38, count: '760/2,000', color: '#f59e0b' },
  { name: '游戏剪辑 · 高光合集', status: 'idle', progress: 0, count: '等待中', color: '#94a3b8' },
])

// --- Live logs ---
const logs = reactive([
  { time: '14:23:01', msg: '✓ video_0841.mp4 生成完毕', type: 'ok' },
  { time: '14:23:03', msg: '✓ video_0842.mp4 生成完毕', type: 'ok' },
  { time: '14:23:05', msg: '→ 上传至 @acc_023 成功', type: 'info' },
])

let logTimer = null
const logPool = [
  { msg: '✓ video_{n}.mp4 生成完毕', type: 'ok' },
  { msg: '→ 上传至 @acc_{a} 成功', type: 'info' },
  { msg: '✓ AI 审核通过 (得分 94)', type: 'ok' },
  { msg: '→ 分发至 6 个账号', type: 'info' },
  { msg: '✓ video_{n}.mp4 生成完毕', type: 'ok' },
  { msg: '⚡ 识别爆款特征，权重+12%', type: 'warn' },
]

let logIdx = 0, vidNum = 843, accNum = 24

function addLog() {
  const template = logPool[logIdx % logPool.length]
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`
  const msg = template.msg
    .replace('{n}', String(vidNum++).padStart(4, '0'))
    .replace('{a}', String(accNum++).padStart(3, '0'))
  logs.push({ time, msg, type: template.type })
  if (logs.length > 6) logs.shift()
  logIdx++
}

// ─── Ocean Canvas ───────────────────────────────────────────
let ctx, cw, ch, raf
let time = 0
let bigWaveTimer = 0
let bigWaveCooldown = 0
let bigWaveIntensity = 0

// Boat state
const boat = { x: 0.72, y: 0, angle: 0, bob: 0 }

function initCanvas() {
  const canvas = bgCanvas.value
  if (!canvas) return
  ctx = canvas.getContext('2d')

  const resize = () => {
    cw = canvas.width = window.innerWidth
    ch = canvas.height = window.innerHeight
    boat.x = cw * 0.72
  }
  window.addEventListener('resize', resize)
  resize()

  function getWaveY(x, t, big) {
    // Base gentle swell
    let y = ch * 0.62
      + Math.sin(x * 0.004 + t * 0.8) * 28
      + Math.sin(x * 0.009 + t * 1.3 + 1) * 14
      + Math.sin(x * 0.002 + t * 0.5 + 2) * 20
    // Big wave
    if (big > 0) {
      const waveX = cw * 0.3 + t * 80
      const dist = Math.abs(x - waveX)
      y -= big * 90 * Math.exp(-dist * dist / (cw * cw * 0.02))
    }
    return y
  }

  function drawSea(t, big) {
    // Background gradient sky
    const sky = ctx.createLinearGradient(0, 0, 0, ch)
    sky.addColorStop(0, '#f0f9ff')
    sky.addColorStop(0.5, '#e0f2fe')
    sky.addColorStop(1, '#bae6fd')
    ctx.fillStyle = sky
    ctx.fillRect(0, 0, cw, ch)

    // Far horizon haze
    const haze = ctx.createLinearGradient(0, ch * 0.45, 0, ch * 0.62)
    haze.addColorStop(0, 'rgba(186,230,253,0)')
    haze.addColorStop(1, 'rgba(186,230,253,0.5)')
    ctx.fillStyle = haze
    ctx.fillRect(0, ch * 0.45, cw, ch * 0.2)

    // Deep ocean layer
    ctx.beginPath()
    ctx.moveTo(0, ch)
    for (let x = 0; x <= cw; x += 10) {
      ctx.lineTo(x, getWaveY(x, t, big) + 40)
    }
    ctx.lineTo(cw, ch)
    ctx.fillStyle = '#0369a1'
    ctx.fill()

    // Mid ocean
    ctx.beginPath()
    ctx.moveTo(0, ch)
    for (let x = 0; x <= cw; x += 8) {
      ctx.lineTo(x, getWaveY(x, t, big) + 18)
    }
    ctx.lineTo(cw, ch)
    ctx.fillStyle = '#0284c7'
    ctx.fill()

    // Surface wave
    ctx.beginPath()
    ctx.moveTo(0, ch)
    for (let x = 0; x <= cw; x += 6) {
      ctx.lineTo(x, getWaveY(x, t, big))
    }
    ctx.lineTo(cw, ch)

    const surf = ctx.createLinearGradient(0, ch * 0.55, 0, ch)
    surf.addColorStop(0, '#38bdf8')
    surf.addColorStop(0.3, '#0ea5e9')
    surf.addColorStop(1, '#0369a1')
    ctx.fillStyle = surf
    ctx.fill()

    // Foam sparkles on crest
    ctx.strokeStyle = 'rgba(255,255,255,0.6)'
    ctx.lineWidth = 1.5
    for (let x = 20; x < cw; x += 60 + Math.sin(x + t * 2) * 20) {
      const wy = getWaveY(x, t, big)
      ctx.beginPath()
      ctx.moveTo(x, wy)
      ctx.bezierCurveTo(x + 8, wy - 4, x + 16, wy - 2, x + 20, wy + 1)
      ctx.stroke()
    }

    // Wave highlight shine
    ctx.beginPath()
    ctx.moveTo(0, ch)
    for (let x = 0; x <= cw; x += 6) {
      ctx.lineTo(x, getWaveY(x, t, big) - 3)
    }
    ctx.lineTo(cw, ch)
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'
    ctx.lineWidth = 2
    ctx.stroke()
  }

  function drawReef(t) {
    const rx = cw * 0.15
    const ry = ch * 0.6

    // Reef shadow
    ctx.beginPath()
    ctx.ellipse(rx, ry + 10, 55, 12, 0, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(0,0,0,0.1)'
    ctx.fill()

    // Main reef rock
    ctx.beginPath()
    ctx.moveTo(rx - 52, ry + 8)
    ctx.bezierCurveTo(rx - 55, ry - 20, rx - 30, ry - 55, rx, ry - 60)
    ctx.bezierCurveTo(rx + 30, ry - 55, rx + 55, ry - 20, rx + 52, ry + 8)
    ctx.closePath()
    const rg = ctx.createLinearGradient(rx, ry - 60, rx, ry + 8)
    rg.addColorStop(0, '#78716c')
    rg.addColorStop(0.5, '#57534e')
    rg.addColorStop(1, '#44403c')
    ctx.fillStyle = rg
    ctx.fill()

    // Rock texture details
    ctx.fillStyle = 'rgba(0,0,0,0.15)'
    ctx.beginPath(); ctx.ellipse(rx - 12, ry - 30, 8, 12, -0.3, 0, Math.PI * 2); ctx.fill()
    ctx.beginPath(); ctx.ellipse(rx + 18, ry - 20, 6, 10, 0.2, 0, Math.PI * 2); ctx.fill()

    // Highlight on rock
    ctx.beginPath()
    ctx.moveTo(rx - 15, ry - 55)
    ctx.bezierCurveTo(rx - 5, ry - 60, rx + 5, ry - 58, rx + 10, ry - 50)
    ctx.strokeStyle = 'rgba(255,255,255,0.3)'
    ctx.lineWidth = 2
    ctx.stroke()

    // Seaweed / algae
    ctx.strokeStyle = '#16a34a'
    ctx.lineWidth = 2.5
    for (let i = 0; i < 4; i++) {
      const sx = rx - 20 + i * 14
      ctx.beginPath()
      ctx.moveTo(sx, ry)
      ctx.bezierCurveTo(
        sx + Math.sin(t * 1.5 + i) * 6, ry - 12,
        sx + Math.sin(t * 1.5 + i + 1) * 8, ry - 22,
        sx + Math.sin(t * 1.5 + i + 2) * 5, ry - 30
      )
      ctx.stroke()
    }

    // Foam around reef base
    ctx.strokeStyle = 'rgba(255,255,255,0.5)'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.ellipse(rx, ry + 2, 60, 8, 0, Math.PI * 0.1, Math.PI * 0.9)
    ctx.stroke()
  }

  function drawBoat(t, big) {
    // Boat position follows wave
    const wx = boat.x
    const wy = getWaveY(wx, t, big)

    // Wave slope for tilt
    const wy1 = getWaveY(wx - 8, t, big)
    const wy2 = getWaveY(wx + 8, t, big)
    const slope = Math.atan2(wy2 - wy1, 16)

    // Bob offset
    boat.bob = Math.sin(t * 1.8) * 3 + big * 15

    const bx = wx
    const by = wy - 28 + boat.bob

    ctx.save()
    ctx.translate(bx, by)
    ctx.rotate(slope * 0.7)

    // Hull shadow
    ctx.beginPath()
    ctx.ellipse(0, 26, 36, 6, 0, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(0,0,0,0.12)'
    ctx.fill()

    // Hull
    ctx.beginPath()
    ctx.moveTo(-34, 14)
    ctx.bezierCurveTo(-36, 20, -30, 28, -20, 28)
    ctx.lineTo(20, 28)
    ctx.bezierCurveTo(30, 28, 36, 20, 34, 14)
    ctx.closePath()
    const hullGrad = ctx.createLinearGradient(0, 14, 0, 28)
    hullGrad.addColorStop(0, '#dc2626')
    hullGrad.addColorStop(1, '#991b1b')
    ctx.fillStyle = hullGrad
    ctx.fill()
    ctx.strokeStyle = '#7f1d1d'
    ctx.lineWidth = 1
    ctx.stroke()

    // Hull stripe
    ctx.beginPath()
    ctx.moveTo(-33, 17)
    ctx.bezierCurveTo(-28, 22, 28, 22, 33, 17)
    ctx.strokeStyle = 'rgba(255,255,255,0.3)'
    ctx.lineWidth = 1.5
    ctx.stroke()

    // Deck
    ctx.beginPath()
    ctx.moveTo(-32, 14)
    ctx.lineTo(32, 14)
    ctx.bezierCurveTo(34, 12, 34, 8, 30, 8)
    ctx.lineTo(-30, 8)
    ctx.bezierCurveTo(-34, 8, -34, 12, -32, 14)
    ctx.closePath()
    ctx.fillStyle = '#f5f0e8'
    ctx.fill()
    ctx.strokeStyle = '#d4c9b0'
    ctx.lineWidth = 1
    ctx.stroke()

    // Cabin
    ctx.beginPath()
    ctx.roundRect(-12, -4, 24, 14, 3)
    const cabinG = ctx.createLinearGradient(-12, -4, -12, 10)
    cabinG.addColorStop(0, '#ffffff')
    cabinG.addColorStop(1, '#e2e8f0')
    ctx.fillStyle = cabinG
    ctx.fill()
    ctx.strokeStyle = '#cbd5e1'
    ctx.lineWidth = 1
    ctx.stroke()

    // Cabin windows
    ctx.fillStyle = '#93c5fd'
    ctx.fillRect(-8, -1, 8, 6)
    ctx.fillRect(4, -1, 6, 6)
    ctx.strokeStyle = '#bfdbfe'
    ctx.lineWidth = 0.5
    ctx.strokeRect(-8, -1, 8, 6)
    ctx.strokeRect(4, -1, 6, 6)

    // Mast
    ctx.beginPath()
    ctx.moveTo(2, 8)
    ctx.lineTo(2, -44)
    ctx.strokeStyle = '#92400e'
    ctx.lineWidth = 2.5
    ctx.stroke()

    // Sail
    ctx.beginPath()
    ctx.moveTo(2, -42)
    ctx.bezierCurveTo(28, -36, 30, -18, 26, -4)
    ctx.lineTo(2, -4)
    ctx.closePath()
    const sailG = ctx.createLinearGradient(2, -42, 28, -4)
    sailG.addColorStop(0, '#f8fafc')
    sailG.addColorStop(1, '#e2e8f0')
    ctx.fillStyle = sailG
    ctx.fill()
    ctx.strokeStyle = '#cbd5e1'
    ctx.lineWidth = 1
    ctx.stroke()

    // Sail crease lines
    ctx.strokeStyle = 'rgba(0,0,0,0.06)'
    ctx.lineWidth = 0.8
    ctx.beginPath(); ctx.moveTo(2, -35); ctx.lineTo(22, -25); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(2, -24); ctx.lineTo(24, -14); ctx.stroke()

    // Flag at top
    ctx.beginPath()
    ctx.moveTo(2, -44)
    ctx.lineTo(14, -40)
    ctx.lineTo(2, -36)
    ctx.closePath()
    ctx.fillStyle = '#ef4444'
    ctx.fill()

    // Rigging lines
    ctx.strokeStyle = 'rgba(146,64,14,0.4)'
    ctx.lineWidth = 0.8
    ctx.beginPath(); ctx.moveTo(2, -44); ctx.lineTo(-28, 10); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(2, -44); ctx.lineTo(30, 10); ctx.stroke()

    ctx.restore()
  }

  function loop() {
    time += 0.016

    // Big wave trigger: every ~8-15s
    bigWaveTimer += 0.016
    if (bigWaveCooldown > 0) {
      bigWaveCooldown -= 0.016
      bigWaveIntensity = Math.sin((1 - bigWaveCooldown / 3.5) * Math.PI) * 0.9
    } else if (bigWaveTimer > 10 + Math.random() * 6) {
      bigWaveTimer = 0
      bigWaveCooldown = 3.5
    } else {
      bigWaveIntensity = 0
    }

    ctx.clearRect(0, 0, cw, ch)
    drawSea(time, bigWaveIntensity)
    drawReef(time)
    drawBoat(time, bigWaveIntensity)

    raf = requestAnimationFrame(loop)
  }
  loop()
}

// ─── Hero dashboard animation ──────────────────────────────
function initDashboardAnim() {
  // Count up stats
  const countUp = (el, target, suffix, duration = 1800) => {
    if (!el) return
    let start = null
    const step = (ts) => {
      if (!start) start = ts
      const p = Math.min((ts - start) / duration, 1)
      const ease = 1 - Math.pow(1 - p, 3)
      el.textContent = Math.floor(ease * target).toLocaleString() + suffix
      if (p < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }

  setTimeout(() => {
    countUp(statVideos.value, 10243, '条')
    countUp(statAccounts.value, 86, '个')
    countUp(statViews.value, 2.4, 'M')
  }, 800)

  // Task progress animation
  tasks.forEach((task, i) => {
    if (task.status !== 'idle') {
      const target = task.progress
      task.progress = 0
      setTimeout(() => {
        gsap.to(task, { progress: target, duration: 1.5 + i * 0.3, ease: 'power2.out' })
      }, 600 + i * 200)
    }
  })
}

// ─── Feature SVG Scroll Animations ─────────────────────────
function initFeatureAnimations() {
  // Review SVG
  gsap.set('.review-card', { opacity: 0, y: 18 })
  gsap.set(['.sb1', '.sb2', '.sb3'], { attr: { width: 0 } })
  gsap.set(['.pass-badge', '.pass-badge2', '.fail-badge'], { scaleX: 0, transformOrigin: 'left center' })

  ScrollTrigger.create({
    trigger: '.feat-svg',
    start: 'top 82%',
    onEnter: () => {
      gsap.to('.review-card', { opacity: 1, y: 0, stagger: 0.18, duration: 0.55, ease: 'power2.out' })
      gsap.to(['.pass-badge', '.pass-badge2'], { scaleX: 1, duration: 0.4, delay: 0.7, ease: 'back.out(2)' })
      gsap.to('.fail-badge', { scaleX: 1, duration: 0.4, delay: 0.9, ease: 'back.out(2)' })
      gsap.to('.sb1', { attr: { width: 198 }, duration: 1.1, delay: 1.0, ease: 'power2.out' })
      gsap.to('.sb2', { attr: { width: 176 }, duration: 1.1, delay: 1.1, ease: 'power2.out' })
      gsap.to('.sb3', { attr: { width: 154 }, duration: 1.1, delay: 1.2, ease: 'power2.out' })
    }
  })

  // Distribution packets
  gsap.set('.target-node', { opacity: 0, scale: 0, transformOrigin: 'center center' })

  ScrollTrigger.create({
    trigger: '.dist-svg',
    start: 'top 82%',
    onEnter: () => {
      gsap.to('.target-node', { opacity: 1, scale: 1, stagger: 0.12, duration: 0.5, ease: 'back.out(2)' })
      const paths = [
        { el: '.p-t1', x2: 65, y2: 42 }, { el: '.p-t2', x2: 315, y2: 42 },
        { el: '.p-t3', x2: 40, y2: 155 }, { el: '.p-t4', x2: 340, y2: 155 },
        { el: '.p-t5', x2: 90, y2: 222 }, { el: '.p-t6', x2: 290, y2: 222 },
      ]
      paths.forEach((p, i) => {
        const go = () => {
          gsap.set(p.el, { attr: { cx: 190, cy: 128 }, opacity: 1 })
          gsap.to(p.el, { attr: { cx: p.x2, cy: p.y2 }, duration: 1.1, delay: i * 0.1, ease: 'power1.inOut',
            onComplete: () => gsap.to(p.el, { opacity: 0, duration: 0.2, onComplete: go }) })
        }
        setTimeout(go, i * 180 + 700)
      })
      const pulse = () => {
        gsap.fromTo('.pulse-ring.r1', { attr: { r: 36 }, opacity: 0.6 }, { attr: { r: 58 }, opacity: 0, duration: 1.6, ease: 'power2.out', onComplete: pulse })
      }
      const pulse2 = () => {
        gsap.fromTo('.pulse-ring.r2', { attr: { r: 36 }, opacity: 0.4 }, { attr: { r: 76 }, opacity: 0, duration: 2.2, ease: 'power2.out', onComplete: pulse2 })
      }
      setTimeout(pulse, 200); setTimeout(pulse2, 700)
    }
  })

  // Analytics chart
  gsap.set('.stat-card', { opacity: 0, y: 12 })
  gsap.set(['.cb1','.cb2','.cb3','.cb4','.cb5','.cb6','.cb7'], { attr: { height: 0, y: 210 } })
  gsap.set('.trend-line', { strokeDashoffset: 500 })

  ScrollTrigger.create({
    trigger: '.analytics-svg',
    start: 'top 82%',
    onEnter: () => {
      gsap.to('.stat-card', { opacity: 1, y: 0, stagger: 0.12, duration: 0.5, ease: 'power2.out' })
      const bars = [
        { el: '.cb1', h: 38, y: 172 }, { el: '.cb2', h: 52, y: 158 }, { el: '.cb3', h: 62, y: 148 },
        { el: '.cb4', h: 72, y: 138 }, { el: '.cb5', h: 86, y: 124 }, { el: '.cb6', h: 96, y: 114 },
        { el: '.cb7', h: 106, y: 104 },
      ]
      bars.forEach((b, i) => gsap.to(b.el, { attr: { height: b.h, y: b.y }, duration: 0.7, delay: 0.3 + i * 0.07, ease: 'power2.out' }))
      gsap.to('.trend-line', { strokeDashoffset: 0, duration: 1.5, delay: 0.8, ease: 'power2.inOut' })
    }
  })

  // Template steps
  gsap.set('.tpl-step', { opacity: 0, x: -20 })
  gsap.set('.tpl-output', { opacity: 0, scale: 0.8, transformOrigin: 'center center' })
  ScrollTrigger.create({
    trigger: '.template-svg',
    start: 'top 82%',
    onEnter: () => {
      gsap.to('.tpl-step', { opacity: 1, x: 0, stagger: 0.15, duration: 0.5, ease: 'power2.out' })
      gsap.to('.tpl-output', { opacity: 1, scale: 1, stagger: 0.1, duration: 0.4, delay: 0.7, ease: 'back.out(1.5)' })
    }
  })

  // Blogger bars
  gsap.set('.blogger-card', { opacity: 0, y: 20 })
  gsap.set(['.bb1','.bb2','.bb3','.bb4'], { attr: { width: 0 } })
  ScrollTrigger.create({
    trigger: '.blogger-svg',
    start: 'top 82%',
    onEnter: () => {
      gsap.to('.blogger-card', { opacity: 1, y: 0, stagger: 0.2, duration: 0.55, ease: 'power2.out' })
      gsap.to('.bb1', { attr: { width: 52 }, duration: 0.9, delay: 0.5 })
      gsap.to('.bb2', { attr: { width: 60 }, duration: 0.9, delay: 0.6 })
      gsap.to('.bb3', { attr: { width: 56 }, duration: 0.9, delay: 0.7 })
      gsap.to('.bb4', { attr: { width: 46 }, duration: 0.9, delay: 0.8 })
    }
  })
}

onMounted(() => {
  initCanvas()
  initDashboardAnim()

  gsap.fromTo('.gsap-nav', { y: -20, opacity: 0 }, { y: 0, opacity: 1, duration: 1, ease: 'power2.out' })
  gsap.fromTo('.gsap-intro', { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 1.1, stagger: 0.25, ease: 'power3.out', delay: 0.3 })

  gsap.utils.toArray('.gsap-row').forEach(row => {
    gsap.fromTo(row, { y: 45, opacity: 0 }, {
      y: 0, opacity: 1, duration: 0.9, ease: 'power2.out',
      scrollTrigger: { trigger: row, start: 'top 85%', toggleActions: 'play none none reverse' }
    })
  })

  initFeatureAnimations()

  logTimer = setInterval(addLog, 1800)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  clearInterval(logTimer)
  ScrollTrigger.getAll().forEach(t => t.kill())
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

* { box-sizing: border-box; }

.story-landing {
  color: #0f172a;
  font-family: 'Inter', -apple-system, sans-serif;
  position: relative;
  overflow-x: hidden;
  background: transparent;
}

.bg-canvas {
  position: fixed;
  top: 0; left: 0;
  width: 100vw; height: 100vh;
  z-index: 0;
  pointer-events: none;
}

/* ── Nav ── */
.clean-nav {
  position: relative; z-index: 100;
  display: flex; justify-content: space-between; align-items: center;
  padding: 26px 6vw;
}
.brand {
  font-size: 20px; font-weight: 900; letter-spacing: -0.03em;
  color: #0f172a;
}
.primary-btn {
  background: #0f172a; border: none;
  padding: 11px 26px; border-radius: 8px;
  font-size: 14px; color: #fff; font-weight: 600;
  cursor: pointer; transition: all 0.25s ease;
  box-shadow: 0 4px 12px rgba(15,23,42,0.18);
}
.primary-btn:hover {
  background: #1d4ed8;
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(29,78,216,0.3);
}

/* ── Hero ── */
.hero-story-section {
  position: relative; z-index: 10;
  min-height: 92vh; display: flex; align-items: center;
  padding: 40px 6vw 60px;
}
.story-container {
  display: flex; justify-content: space-between; align-items: center;
  gap: 5vw; max-width: 1300px; margin: 0 auto; width: 100%;
}
.intro-side { flex: 1; max-width: 520px; }

.hero-badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 7px 16px; border-radius: 99px;
  background: rgba(255,255,255,0.85);
  border: 1px solid rgba(99,102,241,0.25);
  color: #4338ca; font-size: 13px; font-weight: 700;
  margin-bottom: 28px;
  backdrop-filter: blur(6px);
  box-shadow: 0 2px 8px rgba(99,102,241,0.1);
}
.badge-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #10b981;
  animation: pulse-dot 2s ease infinite;
}
@keyframes pulse-dot {
  0%,100% { box-shadow: 0 0 0 0 rgba(16,185,129,0.4); }
  50% { box-shadow: 0 0 0 4px rgba(16,185,129,0); }
}

.hero-title {
  font-size: clamp(36px, 4.2vw, 60px); font-weight: 900; line-height: 1.15;
  margin-bottom: 22px; letter-spacing: -0.04em; color: #0f172a;
}
.hero-emphasize {
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.hero-subtitle {
  font-size: clamp(15px, 1.3vw, 17px); line-height: 1.85;
  color: #334155; margin-bottom: 36px;
}
.hero-actions { display: flex; align-items: center; gap: 18px; }
.hero-btn { padding: 15px 34px; font-size: 15px; border-radius: 10px; }
.hero-hint { font-size: 13px; color: #64748b; font-weight: 500; }

/* ── Dashboard Preview ── */
.animation-side {
  flex: 1.1; display: flex; justify-content: flex-end;
}
.dashboard-preview {
  width: 100%; max-width: 520px;
  background: white;
  border-radius: 14px;
  border: 1px solid rgba(0,0,0,0.08);
  box-shadow:
    0 4px 6px rgba(0,0,0,0.04),
    0 20px 50px rgba(0,0,0,0.12),
    0 0 0 1px rgba(255,255,255,0.7) inset;
  overflow: hidden;
  transform: perspective(1200px) rotateY(-6deg) rotateX(2deg);
}
.win-bar {
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  padding: 10px 14px;
  display: flex; align-items: center; gap: 6px;
}
.win-dot {
  width: 11px; height: 11px; border-radius: 50%;
}
.win-dot.r { background: #ff5f57; }
.win-dot.y { background: #febc2e; }
.win-dot.g { background: #28c840; }
.win-title {
  margin-left: 8px; font-size: 11px; color: #94a3b8; font-weight: 600;
}

.win-body { display: flex; height: 340px; }

.win-sidebar {
  width: 100px;
  background: #f8fafc;
  border-right: 1px solid #e2e8f0;
  padding: 14px 8px;
  display: flex; flex-direction: column; gap: 4px;
}
.sb-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-radius: 7px;
  font-size: 12px; color: #64748b; cursor: pointer;
  font-weight: 500;
}
.sb-item:hover { background: #e2e8f0; }
.sb-active { background: #eef2ff; color: #4338ca; font-weight: 700; }

.win-main {
  flex: 1; padding: 14px; overflow: hidden;
  display: flex; flex-direction: column; gap: 10px;
}

.stat-row { display: flex; gap: 8px; }
.mini-stat {
  flex: 1; background: #f8fafc; border-radius: 8px;
  border: 1px solid #e2e8f0; padding: 8px 10px;
}
.mini-num {
  font-size: 17px; font-weight: 900; color: #0f172a;
  letter-spacing: -0.03em; line-height: 1.2;
}
.mini-num.green { color: #10b981; }
.mini-num.purple { color: #6366f1; }
.mini-label { font-size: 9px; color: #94a3b8; margin-top: 2px; }

.task-list { display: flex; flex-direction: column; gap: 5px; }
.task-item {
  display: flex; align-items: center; gap: 8px;
  background: #f8fafc; border-radius: 7px;
  border: 1px solid #e2e8f0; padding: 6px 8px;
}
.task-icon { width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.spin-dot {
  width: 10px; height: 10px; border-radius: 50%;
  border: 2px solid #e2e8f0; border-top-color: #6366f1;
  animation: spin 0.9s infinite linear;
}
.idle-dot { width: 8px; height: 8px; border-radius: 50%; background: #e2e8f0; }
@keyframes spin { to { transform: rotate(360deg); } }
.task-info { flex: 1; min-width: 0; }
.task-name { font-size: 10px; color: #475569; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 3px; }
.task-progress-bar { height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; }
.task-progress-fill { height: 100%; border-radius: 2px; transition: width 0.1s linear; }
.task-count { font-size: 9px; color: #64748b; font-weight: 600; white-space: nowrap; flex-shrink: 0; }

.live-feed {
  flex: 1; background: #0f172a; border-radius: 8px;
  overflow: hidden; display: flex; flex-direction: column; min-height: 0;
}
.feed-header {
  padding: 6px 10px; background: #1e293b;
  font-size: 10px; color: #94a3b8; font-weight: 700;
  display: flex; align-items: center; gap: 7px;
}
.live-badge { color: #10b981; animation: blink 2s ease infinite; }
@keyframes blink { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
.feed-log { flex: 1; padding: 6px 8px; overflow: hidden; display: flex; flex-direction: column; gap: 2px; }
.log-line { display: flex; gap: 8px; font-size: 9.5px; font-family: 'Courier New', monospace; }
.log-time { color: #475569; flex-shrink: 0; }
.log-ok { color: #34d399; }
.log-info { color: #60a5fa; }
.log-warn { color: #fbbf24; }

/* ── Tab shared ── */
.tab-section-title { font-size: 10px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }

/* ── Video tab ── */
.video-grid-preview { display: flex; flex-direction: column; gap: 5px; margin-bottom: 8px; }
.vp-card { display: flex; align-items: center; gap: 8px; background: #f8fafc; border-radius: 6px; padding: 5px 8px; border: 1px solid #f1f5f9; }
.vp-thumb { width: 36px; height: 26px; border-radius: 4px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.vp-info { flex: 1; min-width: 0; }
.vp-name { font-size: 10px; color: #334155; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.vp-meta { font-size: 9px; color: #94a3b8; margin-top: 1px; }
.vp-badge { width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 800; flex-shrink: 0; }
.vp-badge.pass { background: #d1fae5; color: #059669; }
.vp-badge.fail { background: #fee2e2; color: #dc2626; }

/* ── Stats tab ── */
.mini-chart { margin-bottom: 10px; }
.chart-bars-row { display: flex; align-items: flex-end; gap: 4px; height: 80px; padding-bottom: 18px; position: relative; }
.chart-bar-wrap { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }
.chart-bar-fill { width: 100%; border-radius: 3px 3px 0 0; transition: height 0.3s ease; }
.chart-bar-label { font-size: 9px; color: #94a3b8; margin-top: 4px; }
.mini-stats-grid { display: flex; gap: 6px; }
.ms-item { flex: 1; background: #f8fafc; border-radius: 8px; padding: 8px; border: 1px solid #f1f5f9; text-align: center; }
.ms-val { font-size: 14px; font-weight: 800; letter-spacing: -0.02em; }
.ms-label { font-size: 9px; color: #94a3b8; margin-top: 2px; }

/* ── Blogger tab ── */
.blogger-list-preview { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }
.blg-item { display: flex; align-items: center; gap: 8px; }
.blg-avatar { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; color: white; flex-shrink: 0; }
.blg-info { width: 110px; flex-shrink: 0; }
.blg-name { font-size: 10px; color: #334155; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.blg-fans { font-size: 9px; color: #94a3b8; }
.blg-bar-wrap { flex: 1; display: flex; align-items: center; gap: 5px; }
.blg-bar { flex: 1; height: 5px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
.blg-bar-fill { height: 100%; border-radius: 3px; }
.blg-pct { font-size: 9px; color: #64748b; font-weight: 700; width: 24px; text-align: right; }
.blg-summary { display: flex; gap: 6px; background: #f8fafc; border-radius: 8px; padding: 8px; border: 1px solid #f1f5f9; }
.blg-sum-item { flex: 1; text-align: center; }
.blg-sum-val { display: block; font-size: 13px; font-weight: 800; color: #0f172a; }
.blg-sum-val.green { color: #10b981; }
.blg-sum-val.purple { color: #6366f1; }
.blg-sum-key { font-size: 9px; color: #94a3b8; }

/* ── Template tab ── */
.tpl-list-preview { display: flex; flex-direction: column; gap: 5px; margin-bottom: 10px; }
.tpl-item { display: flex; align-items: center; gap: 8px; background: #f8fafc; border-radius: 6px; padding: 7px 8px; border: 1px solid #f1f5f9; }
.tpl-color-bar { width: 3px; height: 28px; border-radius: 2px; flex-shrink: 0; }
.tpl-info { flex: 1; min-width: 0; }
.tpl-name { font-size: 10px; color: #334155; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tpl-meta { font-size: 9px; color: #94a3b8; margin-top: 1px; }
.tpl-status { font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 99px; flex-shrink: 0; }
.tpl-status.active { background: #d1fae5; color: #059669; }
.tpl-status.idle { background: #f1f5f9; color: #94a3b8; }
.tpl-pipeline { background: #f8fafc; border-radius: 8px; padding: 8px 10px; border: 1px solid #f1f5f9; }
.tpl-step-row { display: flex; align-items: center; gap: 4px; margin-bottom: 5px; }
.tpl-step { display: flex; align-items: center; gap: 4px; font-size: 9px; color: #475569; font-weight: 600; padding: 3px 6px; border-radius: 4px; border: 1px solid; flex: 1; white-space: nowrap; }
.tpl-step-dot { width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.tpl-pipe-label { font-size: 9px; color: #94a3b8; text-align: center; }

/* ── Features ── */
.features-section { position: relative; z-index: 10; padding: 6vh 0 8vh; }

.section-header { text-align: center; margin-bottom: 6vh; padding: 0 4vw; }
.section-eyebrow {
  display: inline-block; padding: 5px 14px; border-radius: 99px;
  background: #eef2ff; border: 1px solid #c7d2fe;
  color: #4338ca; font-size: 12px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 14px;
}
.section-title {
  font-size: clamp(28px, 3vw, 40px); font-weight: 900;
  color: #0f172a; letter-spacing: -0.03em; line-height: 1.2;
}

.feature-row {
  display: flex; align-items: center; justify-content: center;
  gap: 6vw; max-width: 1200px; margin: 0 auto 9vh; padding: 0 5vw;
}
.row-left { flex-direction: row; }
.row-right { flex-direction: row-reverse; }

.feature-text { flex: 1; max-width: 420px; }
.feature-tag {
  display: inline-block; padding: 5px 13px; border-radius: 99px;
  background: #f0f4ff; border: 1px solid #dde5ff;
  color: #4338ca; font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 16px;
}
.feature-text h3 {
  font-size: clamp(22px, 2.2vw, 30px); font-weight: 800; color: #0f172a;
  margin-bottom: 16px; line-height: 1.35; letter-spacing: -0.025em;
}
.feature-text p { font-size: 15px; line-height: 1.88; color: #475569; }

.feature-visual { flex: 1.1; display: flex; justify-content: center; }
.visual-card {
  width: 100%; max-width: 430px;
  background: white; border-radius: 18px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 20px 50px -12px rgba(0,0,0,0.1), 0 4px 6px rgba(0,0,0,0.04);
  overflow: hidden;
}
.feat-svg { width: 100%; height: auto; display: block; }

/* ── CTA ── */
.cta-section {
  position: relative; z-index: 10;
  padding: 8vh 4vw;
  text-align: center;
}
.cta-inner {
  max-width: 640px; margin: 0 auto;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(99,102,241,0.2);
  border-radius: 24px;
  padding: 56px 48px;
  box-shadow: 0 25px 60px rgba(0,0,0,0.08);
}
.cta-title { font-size: clamp(26px, 3vw, 38px); font-weight: 900; letter-spacing: -0.03em; margin-bottom: 14px; color: #0f172a; }
.cta-sub { font-size: 16px; color: #64748b; margin-bottom: 32px; line-height: 1.6; }
.cta-btn { padding: 16px 44px; font-size: 16px; border-radius: 12px; }

.clean-footer {
  text-align: center; padding: 36px; color: #94a3b8;
  font-size: 13px; font-weight: 500;
  border-top: 1px solid rgba(0,0,0,0.06);
  position: relative; z-index: 10;
  background: rgba(255,255,255,0.5);
}

@media (max-width: 960px) {
  .story-container { flex-direction: column; gap: 50px; padding-top: 20px; }
  .intro-side { max-width: 100%; }
  .animation-side { justify-content: center; width: 100%; }
  .dashboard-preview { transform: none; max-width: 100%; }
  .feature-row { flex-direction: column !important; gap: 4vh; }
  .feature-text { max-width: 100%; }
  .visual-card { max-width: 100%; }
  .hero-actions { flex-wrap: wrap; }
}
</style>
