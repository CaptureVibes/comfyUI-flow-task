<template>
  <div class="fb-page">
    <div class="fb-header">
      <h2>正式号回填（临时）</h2>
      <p class="fb-desc">
        从 4/1 开始把当前 prod 账号的「转正日期」重新随机分布，目标曲线 30 → N 单调递增、后期斜率更大。
        <strong>「生成方案」会先清空旧表再重跑。</strong>
        图表中 views / likes / LTV 的口径：当日数值 = 当日发布的正式视频的当前 metrics_snapshot 累计值之和；
        新数据由定时任务每日刷新覆盖。
      </p>
    </div>

    <div class="fb-controls">
      <div class="fb-field">
        <label>目标总数 N</label>
        <el-input-number v-model="form.targetTotal" :min="1" :max="10000" :step="1" />
      </div>
      <div class="fb-field">
        <label>起始日</label>
        <el-date-picker v-model="form.startDate" type="date" value-format="YYYY-MM-DD" />
      </div>
      <div class="fb-field">
        <label>截止日</label>
        <el-date-picker v-model="form.endDate" type="date" value-format="YYYY-MM-DD" />
      </div>
      <div class="fb-field">
        <label>随机种子（可选）</label>
        <el-input v-model.number="form.seed" placeholder="留空则真随机" style="width:140px" />
      </div>
      <div class="fb-actions">
        <el-button type="primary" :loading="generating" @click="onGenerate">生成方案</el-button>
        <el-button :loading="clearing" @click="onClear">清空</el-button>
        <el-button :loading="exporting" @click="onExport">导出 task_ids</el-button>
      </div>
    </div>

    <div v-if="summary" class="fb-stats">
      <div class="fb-stat"><strong>{{ summary.total_accounts }}</strong><span>正式号总数</span></div>
      <div class="fb-stat"><strong>{{ summary.total_videos }}</strong><span>正式视频总数</span></div>
      <div class="fb-stat">
        <strong>{{ summary.start_date || '-' }} → {{ summary.end_date || '-' }}</strong>
        <span>覆盖日期</span>
      </div>
      <div v-if="lastResult" class="fb-stat">
        <strong>{{ lastResult.actual_total }} / {{ lastResult.target_total }}</strong>
        <span>实际 / 目标</span>
      </div>
    </div>

    <template v-if="dailyCounts.length">
      <!-- 表 1 -->
      <div class="fb-chart-card">
        <h3 class="fb-chart-title">全部已发布视频新增总播放量（views） <span class="fb-tag">表1</span></h3>
        <LineChart
          :points="dailyCounts.map(p => ({ x: p.date, y: p.new_views }))"
          :height="260"
          stroke="#3b82f6"
          fill="rgba(59, 130, 246, 0.08)"
        />
      </div>

      <!-- 表 2 -->
      <div class="fb-chart-card">
        <h3 class="fb-chart-title">当日新增发布视频数 <span class="fb-tag">表2</span></h3>
        <LineChart
          :points="dailyCounts.map(p => ({ x: p.date, y: p.new_videos }))"
          :height="260"
          stroke="#10b981"
          fill="rgba(16, 185, 129, 0.08)"
        />
        <p class="fb-note">统计口径：当天新发布的视频数量，只计算发布日期落在当天的视频。</p>
      </div>

      <!-- 表 3 -->
      <div class="fb-chart-card">
        <h3 class="fb-chart-title">
          平均 LTV
          <span class="fb-subtle">（LTV：Lifetime Views，用来衡量单个视频生命周期内的总 Views。）</span>
          <span class="fb-tag">表3</span>
        </h3>
        <LineChart
          :points="ltvPoints"
          :height="260"
          stroke="#7c3aed"
          fill="rgba(124, 58, 237, 0.08)"
        />
        <p class="fb-note">
          统计口径：定义一个视频的生命周期为 7 天。<br>
          7 日前发布视频的平均 LTV = Σ(7 天前发布的每条视频在发布后 7 日内累计 views) / 7 天前发布的视频总数
        </p>
      </div>

      <!-- 表 4 -->
      <div class="fb-chart-card">
        <h3 class="fb-chart-title">内容账号总数 <span class="fb-tag">表4</span></h3>
        <LineChart
          :points="dailyCounts.map(p => ({ x: p.date, y: p.cumulative_accounts }))"
          :height="260"
          stroke="#ef4444"
          fill="rgba(239, 68, 68, 0.08)"
        />
        <p class="fb-note">统计口径：截至当天已经创建（转正）的内容账号总数。</p>
      </div>

      <!-- 表 5 -->
      <div class="fb-chart-card">
        <h3 class="fb-chart-title">全部已发布视频新增总点赞数（likes） <span class="fb-tag">表5</span></h3>
        <LineChart
          :points="dailyCounts.map(p => ({ x: p.date, y: p.new_likes }))"
          :height="260"
          stroke="#f59e0b"
          fill="rgba(245, 158, 11, 0.08)"
        />
        <p class="fb-note">统计口径：当天统计截至当日已经发布过的全部视频，在这一天新增获得的点赞数总和。</p>
      </div>

      <!-- 表 6 -->
      <div v-if="weeklyViews.length" class="fb-chart-card">
        <h3 class="fb-chart-title">每日新增总 views 的周平均值与增长倍数 <span class="fb-tag">表6</span></h3>
        <WeeklyBarLineChart :weeks="weeklyViews" :height="320" />
        <p class="fb-note">
          统计口径：以表1为基础指标，按时间序列将每日观测值划分为连续 7 日窗口，并计算各窗口内每日新增总 views 的算术平均值。
          柱状图表示各 7 日窗口的均值水平，折线图表示相邻窗口均值之间的增长倍数。
        </p>
      </div>

      <!-- Growth summary -->
      <div v-if="growthSummary" class="fb-growth-row">
        <div class="fb-growth-card">
          <div class="fb-growth-title">周增长倍数</div>
          <div class="fb-growth-sub">来源：表6 橙色折线各周增长倍数的平均值。</div>
          <div class="fb-growth-value">{{ growthSummary.weekly ?? '-' }}×</div>
        </div>
        <div class="fb-growth-card">
          <div class="fb-growth-title">月度增长倍数</div>
          <div class="fb-growth-sub">计算：月度增长倍数 = (⁷√平均周增长倍数)^30.5</div>
          <div class="fb-growth-value">{{ growthSummary.monthly ?? '-' }}×</div>
        </div>
        <div class="fb-growth-card">
          <div class="fb-growth-title">季度增长倍数</div>
          <div class="fb-growth-sub">计算：季度增长倍数 = (⁷√平均周增长倍数)^91.5</div>
          <div class="fb-growth-value">{{ growthSummary.quarterly ?? '-' }}×</div>
        </div>
      </div>
    </template>
    <div v-else-if="summary && !summary.daily_counts?.length" class="fb-empty">
      暂无方案数据，点上方「生成方案」开始。
    </div>

    <el-dialog v-model="exportDialogVisible" title="导出 task_ids" width="640px">
      <div class="fb-export-info">共 {{ exportTaskIds.length }} 条</div>
      <el-input
        :model-value="exportTaskIdsJson"
        type="textarea"
        :rows="14"
        readonly
        style="font-family: 'Courier New', monospace; font-size: 12px;"
      />
      <template #footer>
        <el-button @click="copyExport">复制 JSON</el-button>
        <el-button type="primary" @click="downloadExport">下载 .json 文件</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, h, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  clearFormalBackfill,
  exportFormalBackfillTaskIds,
  fetchFormalBackfillSummary,
  generateFormalBackfill,
} from '../api/formal_backfill'

// ── Inline minimal SVG charts (no external chart lib dep) ─────────────────
const _fmt = n => Intl.NumberFormat('en-US').format(n)

const LineChart = {
  props: {
    points: { type: Array, required: true },  // [{x:dateStr, y:number}]
    height: { type: Number, default: 260 },
    stroke: { type: String, default: '#3b82f6' },
    fill: { type: String, default: 'rgba(59,130,246,0.08)' },
    valueLabel: { type: String, default: '数值' },
  },
  setup(props) {
    const hoverIdx = ref(null)
    return () => {
      const W = 1100
      const H = props.height
      const padL = 60, padR = 20, padT = 20, padB = 32
      const innerW = W - padL - padR
      const innerH = H - padT - padB
      const pts = props.points.filter(p => p.y != null)
      if (!pts.length) {
        return h('div', { style: 'color:#94a3b8;padding:20px;text-align:center;font-size:13px' }, '暂无数据')
      }
      const ys = pts.map(p => p.y)
      const yMax = Math.max(...ys, 1)
      const yMin = Math.min(...ys, 0)
      const range = yMax - yMin || 1
      const xOf = i => pts.length <= 1 ? innerW / 2 : (innerW * i) / (pts.length - 1)
      const yOf = v => innerH - (innerH * (v - yMin)) / range
      const polyline = pts.map((p, i) => `${xOf(i)},${yOf(p.y)}`).join(' ')
      const area = `${xOf(0)},${innerH} ${polyline} ${xOf(pts.length - 1)},${innerH}`

      // X labels (sparse)
      const step = Math.max(1, Math.floor(pts.length / 6))
      const xLabels = []
      for (let i = 0; i < pts.length; i += step) {
        xLabels.push({ x: xOf(i), label: pts[i].x.slice(5) })
      }
      const last = pts.length - 1
      if (xLabels[xLabels.length - 1]?.label !== pts[last].x.slice(5)) {
        xLabels.push({ x: xOf(last), label: pts[last].x.slice(5) })
      }

      // Hover overlay: 跟踪鼠标在 SVG 内的 x 坐标，吸附到最近的点
      const onMove = (evt) => {
        const svg = evt.currentTarget.ownerSVGElement
        const ctm = svg.getScreenCTM()
        if (!ctm) return
        const pt = svg.createSVGPoint()
        pt.x = evt.clientX
        pt.y = evt.clientY
        const local = pt.matrixTransform(ctm.inverse())
        const xInChart = local.x - padL
        let bestIdx = 0
        let bestDist = Infinity
        for (let i = 0; i < pts.length; i++) {
          const d = Math.abs(xOf(i) - xInChart)
          if (d < bestDist) { bestDist = d; bestIdx = i }
        }
        hoverIdx.value = bestIdx
      }
      const onLeave = () => { hoverIdx.value = null }

      // Tooltip
      const tooltipNodes = []
      if (hoverIdx.value != null && hoverIdx.value < pts.length) {
        const i = hoverIdx.value
        const p = pts[i]
        const cx = xOf(i)
        const cy = yOf(p.y)
        const label = `${p.x}  ·  ${_fmt(p.y)}`
        // 文字大致宽度估算
        const tw = Math.max(120, label.length * 7 + 16)
        const tipX = Math.min(Math.max(cx - tw / 2, 0), innerW - tw)
        const tipY = Math.max(cy - 38, -padT + 4)
        tooltipNodes.push(
          h('line', { x1: cx, x2: cx, y1: 0, y2: innerH, stroke: '#94a3b8', 'stroke-width': 1, 'stroke-dasharray': '3 3' }),
          h('circle', { cx, cy, r: 4.5, fill: '#fff', stroke: props.stroke, 'stroke-width': 2 }),
          h('g', { transform: `translate(${tipX},${tipY})`, style: 'pointer-events:none' }, [
            h('rect', { x: 0, y: 0, width: tw, height: 28, rx: 4, ry: 4, fill: '#0f172a', opacity: 0.92 }),
            h('text', { x: tw / 2, y: 18, 'text-anchor': 'middle', 'font-size': 12, fill: '#fff' }, label),
          ]),
        )
      }

      return h('svg', {
        viewBox: `0 0 ${W} ${H}`,
        style: 'width:100%;height:auto;display:block',
      }, [
        h('g', { transform: `translate(${padL},${padT})` }, [
          // gridlines
          h('g', null, [
            h('line', { x1: 0, x2: innerW, y1: 0, y2: 0, stroke: '#e2e8f0', 'stroke-width': 1 }),
            h('line', { x1: 0, x2: innerW, y1: innerH / 2, y2: innerH / 2, stroke: '#f1f5f9', 'stroke-width': 1 }),
            h('line', { x1: 0, x2: innerW, y1: innerH, y2: innerH, stroke: '#e2e8f0', 'stroke-width': 1 }),
          ]),
          // area + line
          h('polygon', { points: area, fill: props.fill, stroke: 'none' }),
          h('polyline', { points: polyline, fill: 'none', stroke: props.stroke, 'stroke-width': 2.4, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }),
          // y labels (max + min)
          h('text', { x: -10, y: 8, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' }, _fmt(yMax)),
          h('text', { x: -10, y: innerH + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' }, _fmt(yMin)),
          // x labels
          ...xLabels.map(l => h('text', { x: l.x, y: innerH + 18, 'text-anchor': 'middle', 'font-size': 11, fill: '#94a3b8' }, l.label)),
          // tooltip overlay
          ...tooltipNodes,
          // hover hit area (放最后，覆盖在上面但 fill 透明)
          h('rect', {
            x: 0, y: 0, width: innerW, height: innerH,
            fill: 'transparent',
            onMousemove: onMove,
            onMouseleave: onLeave,
          }),
        ]),
      ])
    }
  },
}

const WeeklyBarLineChart = {
  props: {
    weeks: { type: Array, required: true },  // [{label, avg_daily_views, growth_multiplier}]
    height: { type: Number, default: 320 },
  },
  setup(props) {
    const hoverIdx = ref(null)
    return () => {
      const W = 1100
      const H = props.height
      const padL = 80, padR = 80, padT = 32, padB = 48
      const innerW = W - padL - padR
      const innerH = H - padT - padB
      const ws = props.weeks
      if (!ws.length) return h('div', { style: 'color:#94a3b8;padding:20px;text-align:center;font-size:13px' }, '暂无数据')
      const avgVals = ws.map(w => w.avg_daily_views)
      const growthVals = ws.map(w => w.growth_multiplier)
      const yMaxBar = Math.max(...avgVals, 1) * 1.15
      const yMaxLine = Math.max(...growthVals, 1) * 1.2
      const yMinLine = Math.min(...growthVals, 0.8) * 0.9
      const slot = innerW / ws.length
      const barW = slot * 0.5

      // Hover: 鼠标 x 落在哪个柱子上
      const onMove = (evt) => {
        const svg = evt.currentTarget.ownerSVGElement
        const ctm = svg.getScreenCTM()
        if (!ctm) return
        const pt = svg.createSVGPoint()
        pt.x = evt.clientX
        pt.y = evt.clientY
        const local = pt.matrixTransform(ctm.inverse())
        const xInChart = local.x - padL
        const idx = Math.min(ws.length - 1, Math.max(0, Math.floor(xInChart / slot)))
        hoverIdx.value = idx
      }
      const onLeave = () => { hoverIdx.value = null }

      const tooltipNodes = []
      if (hoverIdx.value != null) {
        const i = hoverIdx.value
        const w = ws[i]
        const cx = slot * i + slot / 2
        const lines = [
          { label: '区间', value: w.label },
          { label: '日均 views', value: _fmt(w.avg_daily_views) },
          { label: '周增长倍数', value: `${w.growth_multiplier.toFixed(2)}×` },
        ]
        const tw = 200
        const tipX = Math.min(Math.max(cx - tw / 2, 0), innerW - tw)
        const tipY = 8
        tooltipNodes.push(
          // 高亮柱
          h('rect', {
            x: cx - slot / 2, y: 0, width: slot, height: innerH,
            fill: 'rgba(118,145,183,0.08)',
          }),
          // tooltip
          h('g', { transform: `translate(${tipX},${tipY})`, style: 'pointer-events:none' }, [
            h('rect', { x: 0, y: 0, width: tw, height: 70, rx: 4, ry: 4, fill: '#0f172a', opacity: 0.92 }),
            ...lines.map((ln, j) => h('g', null, [
              h('text', { x: 12, y: 20 + j * 18, 'font-size': 12, fill: '#cbd5e1' }, ln.label),
              h('text', { x: tw - 12, y: 20 + j * 18, 'text-anchor': 'end', 'font-size': 12, fill: '#fff', 'font-weight': 600 }, ln.value),
            ])),
          ]),
        )
      }

      return h('svg', { viewBox: `0 0 ${W} ${H}`, style: 'width:100%;height:auto;display:block' }, [
        // legend
        h('g', { transform: 'translate(0,0)' }, [
          h('rect', { x: padL + innerW / 2 - 110, y: 4, width: 14, height: 8, fill: '#7691b7' }),
          h('text', { x: padL + innerW / 2 - 90, y: 13, 'font-size': 12, fill: '#475569' }, '日新增总 views 的周均值'),
          h('line', { x1: padL + innerW / 2 + 80, x2: padL + innerW / 2 + 100, y1: 8, y2: 8, stroke: '#d97706', 'stroke-width': 2.5 }),
          h('text', { x: padL + innerW / 2 + 105, y: 13, 'font-size': 12, fill: '#475569' }, '周增长倍数'),
        ]),
        h('text', { x: padL, y: padT - 8, 'font-size': 11, fill: '#64748b' }, '日新增总 views 的周均值'),
        h('text', { x: W - padR, y: padT - 8, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' }, '增长倍数'),

        h('g', { transform: `translate(${padL},${padT})` }, [
          // gridlines
          ...[0, 0.25, 0.5, 0.75, 1].map(p => h('line', { x1: 0, x2: innerW, y1: innerH * p, y2: innerH * p, stroke: '#f1f5f9', 'stroke-width': 1 })),
          // left axis ticks
          ...[0, 0.25, 0.5, 0.75, 1].map(p => h('text', { x: -8, y: innerH * (1 - p) + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#94a3b8' }, _fmt(Math.round(yMaxBar * p)))),
          // right axis ticks
          ...[0, 0.25, 0.5, 0.75, 1].map(p => h('text', { x: innerW + 8, y: innerH * (1 - p) + 4, 'text-anchor': 'start', 'font-size': 11, fill: '#94a3b8' }, (yMinLine + (yMaxLine - yMinLine) * p).toFixed(2) + 'x')),
          // bars
          ...ws.map((w, i) => {
            const cx = slot * i + slot / 2
            const h_ = (innerH * w.avg_daily_views) / yMaxBar
            return h('g', null, [
              h('rect', { x: cx - barW / 2, y: innerH - h_, width: barW, height: h_, fill: '#7691b7' }),
              h('text', { x: cx, y: innerH - h_ - 6, 'text-anchor': 'middle', 'font-size': 11, fill: '#475569', 'font-weight': 600 }, _fmt(w.avg_daily_views)),
              h('text', { x: cx, y: innerH + 16, 'text-anchor': 'middle', 'font-size': 11, fill: '#64748b' }, w.label),
            ])
          }),
          // line for growth (right axis)
          h('polyline', {
            points: ws.map((w, i) => `${slot * i + slot / 2},${innerH - (innerH * (w.growth_multiplier - yMinLine)) / (yMaxLine - yMinLine)}`).join(' '),
            fill: 'none', stroke: '#d97706', 'stroke-width': 2.4, 'stroke-linejoin': 'round',
          }),
          // dots + labels for growth
          ...ws.map((w, i) => {
            const cx = slot * i + slot / 2
            const cy = innerH - (innerH * (w.growth_multiplier - yMinLine)) / (yMaxLine - yMinLine)
            return h('g', null, [
              h('circle', { cx, cy, r: 3.5, fill: '#fff', stroke: '#d97706', 'stroke-width': 2 }),
              h('text', { x: cx, y: cy - 10, 'text-anchor': 'middle', 'font-size': 12, fill: '#d97706', 'font-weight': 700 }, `${w.growth_multiplier.toFixed(2)}×`),
            ])
          }),
          // tooltip overlay
          ...tooltipNodes,
          // hit area
          h('rect', {
            x: 0, y: 0, width: innerW, height: innerH,
            fill: 'transparent',
            onMousemove: onMove,
            onMouseleave: onLeave,
          }),
        ]),
      ])
    }
  },
}

// ── State ──────────────────────────────────────────────────────────────────
const generating = ref(false)
const clearing = ref(false)
const exporting = ref(false)
const summary = ref(null)
const lastResult = ref(null)
const exportDialogVisible = ref(false)
const exportTaskIds = ref([])

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const form = ref({
  targetTotal: 100,
  startDate: '2026-04-01',
  endDate: todayStr(),
  seed: '',
})

const dailyCounts = computed(() => summary.value?.daily_counts || [])
const weeklyViews = computed(() => summary.value?.weekly_views || [])
const growthSummary = computed(() => summary.value?.growth_summary || null)
const ltvPoints = computed(() =>
  dailyCounts.value
    .map(p => ({ x: p.date, y: p.ltv }))
    .filter(p => p.y != null),
)

async function loadSummary() {
  try {
    summary.value = await fetchFormalBackfillSummary({
      startDate: form.value.startDate,
      endDate: form.value.endDate,
    })
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '加载方案失败')
  }
}

async function onGenerate() {
  try {
    await ElMessageBox.confirm(
      '生成方案会先清空当前 formal_video_backfills 表，再按曲线重新随机分配。继续吗？',
      '确认生成',
      { type: 'warning', confirmButtonText: '继续', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  generating.value = true
  try {
    const seed = form.value.seed === '' || form.value.seed === null ? null : Number(form.value.seed)
    lastResult.value = await generateFormalBackfill({
      targetTotal: form.value.targetTotal,
      startDate: form.value.startDate,
      endDate: form.value.endDate,
      seed: Number.isFinite(seed) ? seed : null,
    })
    ElMessage.success(`方案已生成：实际 ${lastResult.value.actual_total} / 目标 ${lastResult.value.target_total}`)
    await loadSummary()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '生成失败')
  } finally {
    generating.value = false
  }
}

async function onClear() {
  try {
    await ElMessageBox.confirm('确认清空 formal_video_backfills 表？', '确认清空', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }
  clearing.value = true
  try {
    const res = await clearFormalBackfill()
    ElMessage.success(`已删除 ${res.deleted} 条`)
    lastResult.value = null
    await loadSummary()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '清空失败')
  } finally {
    clearing.value = false
  }
}

async function onExport() {
  exporting.value = true
  try {
    const res = await exportFormalBackfillTaskIds()
    exportTaskIds.value = res.task_ids || []
    exportDialogVisible.value = true
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

const exportTaskIdsJson = computed(() => JSON.stringify(exportTaskIds.value, null, 2))

async function copyExport() {
  try {
    await navigator.clipboard.writeText(exportTaskIdsJson.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请改用「下载」')
  }
}

function downloadExport() {
  const blob = new Blob([exportTaskIdsJson.value], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `formal_backfill_task_ids_${todayStr()}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

onMounted(loadSummary)

// 改起止日期 → 自动按新范围刷新图表
watch(() => [form.value.startDate, form.value.endDate], () => {
  if (form.value.startDate && form.value.endDate) loadSummary()
})
</script>

<style scoped>
.fb-page { padding: 24px; max-width: 1180px; margin: 0 auto; }
.fb-header h2 { margin: 0 0 8px; font-size: 22px; }
.fb-desc { color: #64748b; font-size: 13px; margin: 0 0 20px; line-height: 1.7; }
.fb-controls {
  display: flex; flex-wrap: wrap; gap: 16px 24px;
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 16px 20px; align-items: flex-end;
}
.fb-field { display: flex; flex-direction: column; gap: 6px; }
.fb-field label { font-size: 12px; color: #475569; font-weight: 600; }
.fb-actions { display: flex; gap: 8px; align-items: center; }
.fb-stats { display: flex; gap: 24px; margin: 20px 0 12px; flex-wrap: wrap; }
.fb-stat {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 12px 18px; display: flex; flex-direction: column; min-width: 140px;
}
.fb-stat strong { font-size: 18px; color: #0f172a; font-weight: 700; }
.fb-stat span { font-size: 12px; color: #64748b; margin-top: 2px; }

.fb-chart-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 22px 26px 18px; margin-top: 18px;
}
.fb-chart-title {
  margin: 0 0 16px; font-size: 16px; color: #0f172a; font-weight: 700;
  display: flex; align-items: baseline; gap: 8px;
}
.fb-tag {
  font-size: 12px; color: #94a3b8; font-weight: 500; margin-left: 4px;
}
.fb-subtle {
  font-size: 13px; color: #94a3b8; font-weight: 400;
}
.fb-note {
  margin: 12px 0 0; color: #475569; font-size: 13px; line-height: 1.7;
}

.fb-growth-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 18px; }
.fb-growth-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 18px 22px;
}
.fb-growth-title { font-size: 14px; color: #0f172a; font-weight: 700; margin-bottom: 4px; }
.fb-growth-sub { font-size: 12px; color: #64748b; margin-bottom: 12px; line-height: 1.6; }
.fb-growth-value { font-size: 30px; font-weight: 700; color: #0f172a; }

.fb-empty { color: #94a3b8; text-align: center; padding: 40px 0; }
.fb-export-info { color: #475569; margin-bottom: 10px; font-size: 13px; }
</style>
