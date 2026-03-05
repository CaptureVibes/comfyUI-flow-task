import { createRouter, createWebHistory } from 'vue-router'

import DashboardLayout from '../layouts/DashboardLayout.vue'
import LandingLayout from '../layouts/LandingLayout.vue'
import LoginView from '../views/LoginView.vue'
import { TOKEN_KEY } from '../utils/constants'

const routes = [
  /* ── Landing page (public, full screen) ── */
  {
    path: '/',
    component: LandingLayout,
    meta: { public: true },
    children: [
      {
        path: '',
        name: 'landing',
        component: () => import('../views/LandingView.vue'),
        meta: { public: true }
      }
    ]
  },

  /* ── Login (standalone, no layout wrapper) ── */
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { public: true }
  },

  /* ── Dashboard (sidebar + header layout) ── */
  {
    path: '/dashboard',
    component: DashboardLayout,
    children: [
      {
        path: '',
        name: 'tasks',
        component: () => import('../views/TaskListView.vue'),
        meta: { title: '任务列表' }
      },
      {
        path: 'tasks/new',
        name: 'task-create',
        component: () => import('../views/TaskFormView.vue'),
        meta: { title: '创建任务', parent: 'tasks' }
      },
      {
        path: 'tasks/:id/edit',
        name: 'task-edit',
        component: () => import('../views/TaskFormView.vue'),
        meta: { title: '编辑任务', parent: 'tasks' }
      },
      {
        path: 'tasks/:id',
        name: 'task-detail',
        component: () => import('../views/TaskDetailView.vue'),
        meta: { title: '任务详情', parent: 'tasks' }
      },
      {
        path: 'templates',
        name: 'templates',
        component: () => import('../views/TaskTemplateListView.vue'),
        meta: { title: '工作流模板' }
      },
      {
        path: 'templates/new',
        name: 'template-create',
        component: () => import('../views/TaskTemplateFormView.vue'),
        meta: { title: '新建工作流', parent: 'templates' }
      },
      {
        path: 'templates/:id/edit',
        name: 'template-edit',
        component: () => import('../views/TaskTemplateFormView.vue'),
        meta: { title: '编辑工作流', parent: 'templates' }
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../views/SettingsView.vue'),
        meta: { title: '设置' }
      },
      {
        path: 'comfyui',
        name: 'comfyui',
        component: () => import('../views/ComfyUIView.vue'),
        meta: { title: 'ComfyUI 编辑器' }
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('../views/ProfileView.vue'),
        meta: { title: '个人资料' }
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('../views/UserManageView.vue'),
        meta: { title: '用户管理' }
      },
      {
        path: 'video-library',
        name: 'video-library',
        component: () => import('../views/VideoLibraryView.vue'),
        meta: { title: '视频库' }
      },
      {
        path: 'video-library/new',
        name: 'video-library-create',
        component: () => import('../views/VideoSourceFormView.vue'),
        meta: { title: '添加视频', parent: 'video-library' }
      },
      {
        path: 'video-library/:id',
        name: 'video-detail',
        component: () => import('../views/VideoDetailView.vue'),
        meta: { title: '视频详情', parent: 'video-library' }
      },
      {
        path: 'video-ai-templates',
        name: 'video-ai-templates',
        component: () => import('../views/VideoAITemplateListView.vue'),
        meta: { title: '视频AI模板' }
      },
      {
        path: 'video-ai-templates/new',
        name: 'video-ai-template-create',
        component: () => import('../views/VideoAITemplateFormView.vue'),
        meta: { title: '新建视频AI模板', parent: 'video-ai-templates' }
      },
      {
        path: 'video-ai-templates/:id/edit',
        name: 'video-ai-template-edit',
        component: () => import('../views/VideoAITemplateFormView.vue'),
        meta: { title: '编辑视频AI模板', parent: 'video-ai-templates' }
      },
      {
        path: 'accounts',
        name: 'accounts',
        component: () => import('../views/AccountListView.vue'),
        meta: { title: '账号配置' }
      },
      {
        path: 'accounts/new',
        name: 'account-create',
        component: () => import('../views/AccountFormView.vue'),
        meta: { title: '新建账号', parent: 'accounts' }
      },
      {
        path: 'accounts/:id',
        name: 'account-detail',
        component: () => import('../views/AccountDetailView.vue'),
        meta: { title: '账号详情', parent: 'accounts' }
      },
      {
        path: 'accounts/:id/edit',
        name: 'account-edit',
        component: () => import('../views/AccountFormView.vue'),
        meta: { title: '编辑账号', parent: 'accounts' }
      },
      {
        path: 'accounts/:id/generate',
        name: 'video-generate',
        component: () => import('../views/VideoGenerationFormView.vue'),
        meta: { title: '生成视频', parent: 'accounts' }
      },
      {
        path: 'daily-tasks',
        name: 'daily-tasks',
        component: () => import('../views/DailyTasksView.vue'),
        meta: { title: '每日生成任务' }
      }
    ]
  },

  /* ── Backward-compatible redirects ── */
  { path: '/tasks/new', redirect: '/dashboard/tasks/new' },
  { path: '/tasks/:id/edit', redirect: to => `/dashboard/tasks/${to.params.id}/edit` },
  { path: '/tasks/:id', redirect: to => `/dashboard/tasks/${to.params.id}` },
  { path: '/templates', redirect: '/dashboard/templates' },
  { path: '/templates/new', redirect: '/dashboard/templates/new' },
  { path: '/templates/:id/edit', redirect: to => `/dashboard/templates/${to.params.id}/edit` },
  { path: '/settings', redirect: '/dashboard/settings' }
]

const router = createRouter({
  // 支持子路径部署（如 /comfyui-flow/）
  history: createWebHistory(import.meta.env.BASE_URL || '/comfyui-flow/'),
  routes
})

router.beforeEach((to) => {
  // iframe 模式下，如果父系统传递了 token，则不需要检查
  const isInIframe = window.parent !== window
  const token = localStorage.getItem(TOKEN_KEY)
  const isPublic = Boolean(to.meta?.public)

  // iframe 模式且有 token，或普通模式有 token，允许访问
  if (!token && !isPublic) {
    // 在 iframe 中且没有 token，通知父系统
    if (isInIframe) {
      window.parent.postMessage({ type: 'requestAuth', source: 'comfyui-flow' }, '*')
      return false // 暂时不跳转，等待父系统响应
    }
    return '/login'
  }
  if (token && to.path === '/login') {
    return '/dashboard'
  }
  return true
})

export default router
