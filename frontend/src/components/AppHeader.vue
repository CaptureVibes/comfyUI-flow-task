<template>
  <header class="app-header">
    <div class="header-left">
      <button class="hamburger-btn" @click="$emit('toggle-sidebar')">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      <nav class="breadcrumb">
        <template v-for="(crumb, idx) in breadcrumbs" :key="idx">
          <span v-if="idx > 0" class="breadcrumb-sep">/</span>
          <router-link
            v-if="crumb.path"
            :to="crumb.path"
            class="breadcrumb-link"
          >{{ crumb.label }}</router-link>
          <span v-else class="breadcrumb-current">{{ crumb.label }}</span>
        </template>
      </nav>
    </div>

    <div class="header-right">
      <!-- User dropdown menu -->
      <el-dropdown trigger="hover" @command="handleMenuCommand">
        <div class="user-dropdown-trigger">
          <div class="user-avatar">
            <img v-if="userAvatar" :src="userAvatar" alt="avatar" class="avatar-img" />
            <span v-else class="avatar-letter">{{ avatarLetter }}</span>
          </div>
          <span class="user-name">{{ displayName }}</span>
          <el-icon class="dropdown-arrow"><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon>
              <span>个人资料</span>
            </el-dropdown-item>
            <el-dropdown-item divided command="logout" class="logout-item">
              <el-icon><SwitchButton /></el-icon>
              <span>退出登录</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script setup>
import { ArrowDown, SwitchButton, User } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getProfile } from '../api/auth'
import { clearToken, getUsername, isLoggedIn } from '../composables/useAuth'
import { USERNAME_KEY } from '../utils/constants'

defineEmits(['toggle-sidebar'])

const route = useRoute()
const router = useRouter()
const username = getUsername()

// User profile data (cached locally, not reactive to avoid frequent API calls)
const userProfile = ref(null)

const displayName = computed(() => userProfile.value?.display_name || username)

const userAvatar = computed(() => userProfile.value?.avatar_url || null)

const avatarLetter = computed(() => {
  const name = userProfile.value?.display_name || username
  return (name[0] || 'A').toUpperCase()
})

const menuLabels = {
  tasks: '任务列表',
  templates: '工作流模板',
  settings: '设置',
  users: '用户管理',
  profile: '个人资料'
}

const breadcrumbs = computed(() => {
  const crumbs = []
  const parent = route.meta?.parent
  if (parent && menuLabels[parent]) {
    crumbs.push({
      label: menuLabels[parent],
      path: parent === 'tasks' ? '/dashboard' : `/dashboard/${parent}`
    })
  }
  const title = route.meta?.title
  if (title) {
    crumbs.push({ label: title, path: '' })
  }
  return crumbs
})

// Load profile once on mount (silently, no error shown)
async function loadUserProfile() {
  if (!isLoggedIn()) return
  try {
    const data = await getProfile()
    userProfile.value = data
  } catch {
    // Silently fail - fallback to username
  }
}

// Initial load
loadUserProfile()

async function handleMenuCommand(command) {
  switch (command) {
    case 'profile':
      router.push('/dashboard/profile')
      break
    case 'logout':
      handleLogout()
      break
  }
}

function handleLogout() {
  clearToken()
  router.replace('/login')
}

// Expose refresh method for external calls (e.g. after profile update)
defineExpose({
  refreshProfile: loadUserProfile
})
</script>

<style scoped>
.app-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-6);
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 5;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.hamburger-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) ease;
}

.hamburger-btn:hover {
  background: var(--surface-tertiary);
  color: var(--text-primary);
}

/* ── Breadcrumb ── */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 14px;
}

.breadcrumb-sep {
  color: var(--text-tertiary);
  font-size: 12px;
}

.breadcrumb-link {
  color: var(--text-tertiary);
  text-decoration: none;
  transition: color var(--duration-fast) ease;
}

.breadcrumb-link:hover {
  color: var(--brand);
}

.breadcrumb-current {
  color: var(--text-primary);
  font-weight: 600;
}

/* ── Right side ── */
.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

/* User dropdown trigger */
.user-dropdown-trigger {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 4px var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast) ease;
}

.user-dropdown-trigger:hover {
  background: var(--surface-tertiary);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  overflow: hidden;
  background: linear-gradient(135deg, var(--brand) 0%, var(--accent) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-letter {
  font-size: 14px;
  font-weight: 700;
  color: #fff;
}

.user-name {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown-arrow {
  font-size: 12px;
  color: var(--text-tertiary);
  transition: transform var(--duration-fast) ease;
}

.user-dropdown-trigger:hover .dropdown-arrow {
  transform: rotate(180deg);
}

/* Dropdown menu items */
:deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 12px;
  min-width: 140px;
}

:deep(.el-dropdown-menu__item .el-icon) {
  font-size: 16px;
  color: var(--text-secondary);
}

:deep(.el-dropdown-menu__item:hover .el-icon) {
  color: var(--brand);
}

/* Logout item - light red style */
:deep(.el-dropdown-menu__item.logout-item) {
  color: #f87171;
}

:deep(.el-dropdown-menu__item.logout-item .el-icon) {
  color: #f87171;
}

:deep(.el-dropdown-menu__item.logout-item:hover) {
  background: #fef2f2;
  color: #ef4444;
}

:deep(.el-dropdown-menu__item.logout-item:hover .el-icon) {
  color: #ef4444;
}
</style>
