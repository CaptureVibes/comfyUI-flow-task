<template>
  <aside class="sidebar" :class="{ collapsed: collapsed }">
    <!-- Brand -->
    <div class="sidebar-brand">
      <router-link to="/" class="brand-link">
        <div class="brand-icon">
          <svg width="28" height="28" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" style="border-radius:7px">
            <defs>
              <linearGradient id="sb-bg" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stop-color="#6366f1"/>
                <stop offset="100%" stop-color="#4f46e5"/>
              </linearGradient>
            </defs>
            <rect width="48" height="48" rx="12" fill="url(#sb-bg)"/>
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
        </div>
        <transition name="sidebar-text">
          <span v-if="!collapsed" class="brand-text">EchoMatrix™</span>
        </transition>
      </router-link>
    </div>

    <!-- Navigation -->
    <nav class="sidebar-nav">
      <a v-for="item in menuItems" :key="item.name" class="nav-item" :class="{ active: isActive(item.name) }"
        @click.prevent="handleNavClick(item)">
        <div class="nav-icon">
          <component :is="item.iconComponent" />
        </div>
        <transition name="sidebar-text">
          <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
        </transition>
        <el-tooltip v-if="collapsed" :content="item.label" placement="right" :show-after="100">
          <span class="nav-tooltip-trigger" />
        </el-tooltip>
      </a>
    </nav>

    <!-- Collapse toggle -->
    <div class="sidebar-footer">
      <button class="collapse-btn" @click="$emit('toggle')">
        <svg class="collapse-icon" :class="{ rotated: collapsed }" width="18" height="18" viewBox="0 0 24 24"
          fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        <transition name="sidebar-text">
          <span v-if="!collapsed" class="collapse-label">收起菜单</span>
        </transition>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

defineProps({
  collapsed: Boolean
})

defineEmits(['toggle'])

const route = useRoute()
const router = useRouter()
const { isAdmin } = useAuth()

/* ── SVG Icon components ── */

const IconSetting = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('circle', { cx: 12, cy: 12, r: 3 }),
  h('path', { d: 'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z' })
])

const IconUsers = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
  h('circle', { cx: 9, cy: 7, r: 4 }),
  h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
  h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })
])

// 视频库图标 (film/play)
const IconVideoLibrary = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('rect', { x: 2, y: 4, width: 20, height: 16, rx: 2 }),
  h('path', { d: 'M10 9l5 3-5 3V9z', fill: 'currentColor', stroke: 'none', opacity: 0.7 }),
  h('line', { x1: 2, y1: 8, x2: 22, y2: 8 }),
  h('line', { x1: 2, y1: 16, x2: 22, y2: 16 })
])

// AI模板图标 (sparkle/wand)
const IconVideoAI = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('path', { d: 'M12 2l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5z' }),
  h('path', { d: 'M5 14l1 2 2 1-2 1-1 2-1-2-2-1 2-1 1-2z' })
])

// 任务管理图标 (calendar check)
const IconTaskMgmt = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('rect', { x: 3, y: 4, width: 18, height: 18, rx: 2 }),
  h('line', { x1: 16, y1: 2, x2: 16, y2: 6 }),
  h('line', { x1: 8, y1: 2, x2: 8, y2: 6 }),
  h('line', { x1: 3, y1: 10, x2: 21, y2: 10 }),
  h('polyline', { points: '9 16 11 18 15 14' })
])

// 审核人统计图标 (users)
const IconOperatorStats = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('path', { d: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2' }),
  h('circle', { cx: 9, cy: 7, r: 4 }),
  h('path', { d: 'M23 21v-2a4 4 0 0 0-3-3.87' }),
  h('path', { d: 'M16 3.13a4 4 0 0 1 0 7.75' })
])

// AI博主图标 (id card)
const IconAccount = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('rect', { x: 2, y: 5, width: 20, height: 14, rx: 2 }),
  h('circle', { cx: 8, cy: 12, r: 2.5 }),
  h('path', { d: 'M14 9h5M14 12h4M14 15h3' })
])

// 主题词图标 (hashtag)
const IconTopic = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('line', { x1: 4, y1: 9, x2: 20, y2: 9 }),
  h('line', { x1: 4, y1: 15, x2: 20, y1: 15 }),
  h('line', { x1: 10, y1: 3, x2: 8, y2: 21 }),
  h('line', { x1: 16, y1: 3, x2: 14, y2: 21 })
])

// TikTok博主图标 (person + music note)
const IconTiktokBlogger = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('circle', { cx: 8, cy: 7, r: 3 }),
  h('path', { d: 'M2 21v-2a5 5 0 0 1 5-5h4a5 5 0 0 1 2.2.5' }),
  h('path', { d: 'M17 8v5' }),
  h('path', { d: 'M21 8v5' }),
  h('path', { d: 'M17 8a3 3 0 0 1 4 0' }),
  h('circle', { cx: 17, cy: 13, r: 1, fill: 'currentColor', stroke: 'none' }),
  h('circle', { cx: 21, cy: 13, r: 1, fill: 'currentColor', stroke: 'none' })
])

// 候选库图标 (film strip with search)
const IconCandidateLibrary = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('rect', { x: 2, y: 7, width: 14, height: 10, rx: 1 }),
  h('path', { d: 'M16 11l4-3v8l-4-3' }),
  h('line', { x1: 6, y1: 7, x2: 6, y2: 17 }),
  h('line', { x1: 10, y1: 7, x2: 10, y2: 17 })
])

// 人脸库图标 (person face / portrait)
const IconFaceLibrary = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('circle', { cx: 12, cy: 8, r: 4 }),
  h('path', { d: 'M9 11.5c0 1.5 1.343 3 3 3s3-1.5 3-3' }),
  h('rect', { x: 3, y: 3, width: 18, height: 18, rx: 3 }),
  h('path', { d: 'M6 21v-1a6 6 0 0 1 12 0v1' })
])

const IconPublicationStats = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('path', { d: 'M4 19h16' }),
  h('rect', { x: 6, y: 10, width: 3, height: 6, rx: 1 }),
  h('rect', { x: 11, y: 7, width: 3, height: 9, rx: 1 }),
  h('rect', { x: 16, y: 4, width: 3, height: 12, rx: 1 })
])

const baseMenuItems = [
  { path: '/dashboard/topics', name: 'topics', label: '主题词', iconComponent: IconTopic },
  { path: '/dashboard/candidate-library', name: 'candidate-library', label: '候选库', iconComponent: IconCandidateLibrary },
  { path: '/dashboard/video-library', name: 'video-library', label: '视频库', iconComponent: IconVideoLibrary },
  { path: '/dashboard/video-ai-templates', name: 'video-ai-templates', label: 'AI模板', iconComponent: IconVideoAI },
  { path: '/dashboard/face-library', name: 'face-library', label: '人脸库', iconComponent: IconFaceLibrary },
  { path: '/dashboard/accounts', name: 'accounts', label: 'AI博主', iconComponent: IconAccount },
  { path: '/dashboard/daily-tasks', name: 'daily-tasks', label: 'TASKS', iconComponent: IconTaskMgmt },
  { path: '/dashboard/operator-stats', name: 'operator-stats', label: '审核统计', iconComponent: IconOperatorStats },
  { path: '/dashboard/publication-stats', name: 'publication-stats', label: '数据统计', iconComponent: IconPublicationStats },
  { path: '/dashboard/tiktok-bloggers', name: 'tiktok-bloggers', label: 'TK博主', iconComponent: IconTiktokBlogger },
  { path: '/dashboard/settings', name: 'settings', label: '设置', iconComponent: IconSetting }
]

const menuItems = isAdmin()
  ? [
      ...baseMenuItems,
      { path: '/dashboard/formal-backfill', name: 'formal-backfill', label: '正式号回填', iconComponent: IconUsers },
      { path: '/dashboard/users', name: 'users', label: '用户管理', iconComponent: IconUsers },
    ]
  : [
      ...baseMenuItems,
      { path: '/dashboard/formal-backfill', name: 'formal-backfill', label: '正式号回填', iconComponent: IconUsers },
    ]

function isActive(name) {
  const routeName = route.name || ''
  const parentName = route.meta?.parent || ''
  return routeName === name || parentName === name
}

function handleNavClick(item) {
  router.push(item.path)
}
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--sidebar-bg);
  display: flex;
  flex-direction: column;
  transition: width var(--sidebar-transition);
  overflow: hidden;
  position: fixed;
  top: 0;
  left: 0;
  z-index: 10;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

/* ── Brand ── */
.sidebar-brand {
  height: var(--header-height);
  display: flex;
  align-items: center;
  padding: 0 var(--space-5);
  border-bottom: 1px solid var(--sidebar-divider);
}

.brand-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-decoration: none;
  overflow: hidden;
}

.brand-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-text {
  font-size: 16px;
  font-weight: 700;
  color: #111827;
  white-space: nowrap;
  letter-spacing: -0.02em;
}

/* ── Navigation ── */
.sidebar-nav {
  flex: 1;
  padding: var(--space-3) var(--space-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-3);
  height: 42px;
  border-radius: var(--radius-md);
  color: var(--sidebar-text);
  text-decoration: none;
  transition: all var(--duration-fast) ease;
  position: relative;
  overflow: hidden;
}

.nav-item:hover {
  color: var(--sidebar-text-hover);
  background: var(--sidebar-item-hover);
}

.nav-item.active {
  color: var(--sidebar-text-active);
  background: var(--sidebar-item-active);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--sidebar-accent-border);
}

.nav-icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-label {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  letter-spacing: -0.01em;
}

.nav-tooltip-trigger {
  position: absolute;
  inset: 0;
}

/* ── Footer / Collapse ── */
.sidebar-footer {
  padding: var(--space-3) var(--space-2);
  border-top: 1px solid var(--sidebar-divider);
}

.collapse-btn {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-3);
  height: 38px;
  width: 100%;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--sidebar-text);
  cursor: pointer;
  transition: all var(--duration-fast) ease;
  overflow: hidden;
}

.collapse-btn:hover {
  color: var(--sidebar-text-hover);
  background: var(--sidebar-item-hover);
}

.collapse-icon {
  flex-shrink: 0;
  transition: transform var(--sidebar-transition);
}

.collapse-icon.rotated {
  transform: rotate(180deg);
}

.collapse-label {
  font-size: 13px;
  white-space: nowrap;
}

/* ── Text transition ── */
.sidebar-text-enter-active {
  transition: opacity 0.2s ease 0.1s, max-width 0.3s ease;
}

.sidebar-text-leave-active {
  transition: opacity 0.1s ease, max-width 0.25s ease 0.05s;
}

.sidebar-text-enter-from,
.sidebar-text-leave-to {
  opacity: 0;
  max-width: 0;
  overflow: hidden;
}

.sidebar-text-enter-to,
.sidebar-text-leave-from {
  opacity: 1;
  max-width: 200px;
}
</style>
