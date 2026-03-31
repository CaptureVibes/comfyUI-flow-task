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
        path: 'video-library',
        name: 'video-library',
        component: () => import('../views/VideoLibraryView.vue'),
        meta: { title: '视频库' }
      },
      {
        path: 'tiktok-bloggers',
        name: 'tiktok-bloggers',
        component: () => import('../views/TiktokBloggerListView.vue'),
        meta: { title: 'TK博主' }
      },
      {
        path: 'topics',
        name: 'topics',
        component: () => import('../views/TopicListView.vue'),
        meta: { title: '主题词管理' }
      },
      {
        path: 'topics/:id',
        name: 'topic-detail',
        component: () => import('../views/TopicDetailView.vue'),
        meta: { title: '主题词详情', parent: 'topics' }
      },
      {
        path: 'candidate-library',
        name: 'candidate-library',
        component: () => import('../views/CandidateLibraryView.vue'),
        meta: { title: '候选库' }
      },
      {
        path: 'face-library',
        name: 'face-library',
        component: () => import('../views/FaceLibraryView.vue'),
        meta: { title: '人脸库' }
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
        meta: { title: 'AI模板' }
      },
      {
        path: 'video-ai-templates/new',
        name: 'video-ai-template-create',
        component: () => import('../views/VideoAITemplateFormView.vue'),
        meta: { title: '新建AI模板', parent: 'video-ai-templates' }
      },
      {
        path: 'video-ai-templates/:id/edit',
        name: 'video-ai-template-edit',
        component: () => import('../views/VideoAITemplateFormView.vue'),
        meta: { title: '编辑AI模板', parent: 'video-ai-templates' }
      },
      {
        path: 'accounts',
        name: 'accounts',
        component: () => import('../views/AccountListView.vue'),
        meta: { title: 'AI博主' }
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
        component: () => import('../views/VideoTasksView.vue'),
        meta: { title: '任务管理' }
      },
      {
        path: 'daily-tasks/config',
        name: 'task-config',
        component: () => import('../views/TaskConfigView.vue'),
        meta: { title: '任务配置', parent: 'daily-tasks' }
      },
      {
        path: 'video-tasks/:id',
        name: 'video-task-detail',
        component: () => import('../views/VideoTaskDetailView.vue'),
        meta: { title: '任务详情', parent: 'daily-tasks' }
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../views/SettingsView.vue'),
        meta: { title: '设置' }
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
    ]
  },

  /* ── Backward-compatible redirects ── */
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
