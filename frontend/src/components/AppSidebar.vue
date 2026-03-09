<template>
  <aside class="sidebar" :class="{ collapsed: collapsed }">
    <!-- Brand -->
    <div class="sidebar-brand">
      <router-link to="/" class="brand-link">
        <div class="brand-icon">
          <svg width="28" height="28" viewBox="0 0 512 512" fill="none">
            <!-- White background -->
            <rect x="0" y="0" width="512" height="512" rx="96" fill="#ffffff"/>
            <!-- Lightbulb shape -->
            <path d="M -80 -140
                     C -140 -140, -140 -60, -80 -35
                     L -80 60
                     C -80 110, -35 135, 35 135
                     L 80 60
                     C 140 -60, 140 -140, 80 -140
                     Z"
                  fill="none" stroke="url(#brandGrad)" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" transform="translate(256, 280) scale(1.15)"/>
            <!-- Filament -->
            <line x1="-40" y1="-55" x2="-15" y2="55" stroke="url(#brandGrad)" stroke-width="10" stroke-linecap="round" opacity="0.8" transform="translate(256, 280) scale(1.15)"/>
            <line x1="15" y1="-55" x2="40" y2="55" stroke="url(#brandGrad)" stroke-width="10" stroke-linecap="round" opacity="0.8" transform="translate(256, 280) scale(1.15)"/>
            <line x1="-65" y1="25" x2="65" y2="25" stroke="url(#brandGrad)" stroke-width="7" stroke-linecap="round" opacity="0.5" transform="translate(256, 280) scale(1.15)"/>
            <!-- Light rays -->
            <line x1="0" y1="-210" x2="0" y2="-250" stroke="url(#brandGrad)" stroke-width="10" stroke-linecap="round" opacity="0.7" transform="translate(256, 280) scale(1.15)"/>
            <line x1="-200" y1="-120" x2="-230" y2="-140" stroke="url(#brandGrad)" stroke-width="8" stroke-linecap="round" opacity="0.7" transform="translate(256, 280) scale(1.15)"/>
            <line x1="200" y1="-120" x2="230" y2="-140" stroke="url(#brandGrad)" stroke-width="8" stroke-linecap="round" opacity="0.7" transform="translate(256, 280) scale(1.15)"/>
            <defs>
              <linearGradient id="brandGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#f97316" />
                <stop offset="100%" stop-color="#8b5cf6" />
              </linearGradient>
            </defs>
          </svg>
        </div>
        <transition name="sidebar-text">
          <span v-if="!collapsed" class="brand-text">ComfyUI Flow</span>
        </transition>
      </router-link>
    </div>

    <!-- Navigation -->
    <nav class="sidebar-nav">
      <router-link
        v-for="item in menuItems"
        :key="item.name"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.name) }"
      >
        <div class="nav-icon">
          <component :is="item.iconComponent" />
        </div>
        <transition name="sidebar-text">
          <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
        </transition>
        <el-tooltip
          v-if="collapsed"
          :content="item.label"
          placement="right"
          :show-after="100"
        >
          <span class="nav-tooltip-trigger" />
        </el-tooltip>
      </router-link>
    </nav>

    <!-- Collapse toggle -->
    <div class="sidebar-footer">
      <button class="collapse-btn" @click="$emit('toggle')">
        <svg
          class="collapse-icon"
          :class="{ rotated: collapsed }"
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
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
import { useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth'

defineProps({
  collapsed: Boolean
})

defineEmits(['toggle'])

const route = useRoute()
const { isAdmin } = useAuth()

/* ── SVG Icon components ── */
const IconList = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('rect', { x: 3, y: 3, width: 7, height: 7, rx: 1.5 }),
  h('rect', { x: 14, y: 3, width: 7, height: 7, rx: 1.5 }),
  h('rect', { x: 3, y: 14, width: 7, height: 7, rx: 1.5 }),
  h('rect', { x: 14, y: 14, width: 7, height: 7, rx: 1.5 })
])

const IconFlow = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('circle', { cx: 5, cy: 6, r: 2.5 }),
  h('circle', { cx: 19, cy: 6, r: 2.5 }),
  h('circle', { cx: 12, cy: 18, r: 2.5 }),
  h('path', { d: 'M7 7.5L10.5 16' }),
  h('path', { d: 'M17 7.5L13.5 16' })
])

const IconSetting = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('circle', { cx: 12, cy: 12, r: 3 }),
  h('path', { d: 'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z' })
])

const IconComfyUI = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('rect', { x: 2, y: 3, width: 5, height: 5, rx: 1 }),
  h('rect', { x: 17, y: 3, width: 5, height: 5, rx: 1 }),
  h('rect', { x: 9.5, y: 16, width: 5, height: 5, rx: 1 }),
  h('path', { d: 'M7 5.5h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H7' }),
  h('path', { d: 'M17 5.5h-4a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h4' }),
  h('line', { x1: 12, y1: 11.5, x2: 12, y2: 16 })
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

// 个人资料图标 (单人轮廓)
const IconProfile = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('path', { d: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2' }),
  h('circle', { cx: 12, cy: 7, r: 4 })
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

// 视频AI模板图标 (sparkle/wand)
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

// 账号配置图标 (id card)
const IconAccount = () => h('svg', {
  width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none',
  stroke: 'currentColor', 'stroke-width': 1.75,
  'stroke-linecap': 'round', 'stroke-linejoin': 'round'
}, [
  h('rect', { x: 2, y: 5, width: 20, height: 14, rx: 2 }),
  h('circle', { cx: 8, cy: 12, r: 2.5 }),
  h('path', { d: 'M14 9h5M14 12h4M14 15h3' })
])

const baseMenuItems = [
  { path: '/dashboard', name: 'tasks', label: '任务列表', iconComponent: IconList },
  { path: '/dashboard/templates', name: 'templates', label: '工作流模板', iconComponent: IconFlow },
  { path: '/dashboard/comfyui', name: 'comfyui', label: 'ComfyUI 编辑器', iconComponent: IconComfyUI },
  { path: '/dashboard/video-library', name: 'video-library', label: '视频库', iconComponent: IconVideoLibrary },
  { path: '/dashboard/video-ai-templates', name: 'video-ai-templates', label: '视频AI模板', iconComponent: IconVideoAI },
  { path: '/dashboard/accounts', name: 'accounts', label: '账号配置', iconComponent: IconAccount },
  { path: '/dashboard/daily-tasks', name: 'daily-tasks', label: '任务管理', iconComponent: IconTaskMgmt },
  { path: '/dashboard/settings', name: 'settings', label: '设置', iconComponent: IconSetting }
]

const menuItems = isAdmin()
  ? [...baseMenuItems, { path: '/dashboard/users', name: 'users', label: '用户管理', iconComponent: IconUsers }]
  : baseMenuItems

function isActive(name) {
  const routeName = route.name || ''
  const parentName = route.meta?.parent || ''
  return routeName === name || parentName === name
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
