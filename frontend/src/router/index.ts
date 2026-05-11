import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '#/stores/user'
import { canAccess, type PermissionKey } from '#/utils/permissions'
import Layout from '#/layout/index.vue'

/**
 * 扩展 RouteMeta：菜单元信息统一在路由表声明，作为唯一真值源。
 * - title:        菜单/面包屑显示文本
 * - icon:         Element Plus 图标组件名
 * - group:        菜单分组（未填则不在侧边栏显示）
 * - order:        同组内排序（越小越靠前）
 * - hideInMenu:   显式隐藏于菜单（仍可被路由访问）
 * - role:         要求的用户角色
 * - permission:   要求的模块权限 key
 */
declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    title?: string
    icon?: string
    group?: string
    order?: number
    hideInMenu?: boolean
    role?: string
    permission?: PermissionKey
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('#/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('#/views/Dashboard.vue'),
        meta: { requiresAuth: true, title: '看板', icon: 'DataBoard', group: '核心业务', order: 10 },
      },
      {
        path: 'send',
        name: 'SendCenter',
        component: () => import('#/views/SendCenter/index.vue'),
        meta: { requiresAuth: true, title: '发送中心', icon: 'Promotion', group: '核心业务', order: 20, permission: 'send' },
      },
      {
        path: 'auto-ranking',
        name: 'AutoRanking',
        component: () => import('#/views/AutoRanking/index.vue'),
        meta: { requiresAuth: true, title: '自动排行推送', icon: 'TrendCharts', group: '核心业务', order: 30, role: 'admin' },
      },

      {
        path: 'groups',
        name: 'Groups',
        component: () => import('#/views/Groups/index.vue'),
        meta: { requiresAuth: true, title: '群管理', icon: 'ChatDotRound', group: '数据管理', order: 10, permission: 'group' },
      },
      {
        path: 'templates',
        name: 'Templates',
        component: () => import('#/views/Templates/index.vue'),
        meta: { requiresAuth: true, title: '模板中心', icon: 'Document', group: '数据管理', order: 20, permission: 'template' },
      },
      {
        path: 'assets',
        name: 'Assets',
        component: () => import('#/views/Assets/index.vue'),
        meta: { requiresAuth: true, title: '素材库', icon: 'Picture', group: '数据管理', order: 30, permission: 'asset' },
      },
      {
        path: 'schedules',
        name: 'Schedules',
        component: () => import('#/views/Schedules.vue'),
        meta: { requiresAuth: true, title: '定时任务', icon: 'Timer', group: '数据管理', order: 40, permission: 'schedule' },
      },
      {
        path: 'sop-docs',
        name: 'SopDocsHome',
        component: () => import('#/views/SopDocs/index.vue'),
        meta: { requiresAuth: true, title: '飞书文档', icon: 'Notebook', group: '数据管理', order: 50, permission: 'sop' },
      },
      {
        path: 'sop-docs/governance',
        name: 'SopDocsGovernance',
        component: () => import('#/views/SopDocs/Governance.vue'),
        meta: { requiresAuth: true, title: '飞书文档', permission: 'sop', hideInMenu: true },
      },
      {
        path: 'sop-docs/workspace/:id',
        name: 'WorkspaceDetail',
        component: () => import('#/views/SopDocs/WorkspaceDetail.vue'),
        meta: { requiresAuth: true, title: '飞书文档', permission: 'sop', hideInMenu: true },
      },

      {
        path: 'crm-profile',
        name: 'CrmProfile',
        component: () => import('#/views/CrmProfile/index.vue'),
        meta: { requiresAuth: true, title: '客户档案', icon: 'UserFilled', group: '运营配置', order: 10, permission: 'crm_profile' },
      },
      {
        path: 'speech-templates',
        name: 'SpeechTemplates',
        component: () => import('#/views/SpeechTemplates.vue'),
        meta: { requiresAuth: true, title: '话术管理', icon: 'ChatLineSquare', group: '运营配置', order: 20, permission: 'speech_template' },
      },

      {
        path: 'system-teaching',
        name: 'SystemTeaching',
        component: () => import('#/views/SystemTeaching.vue'),
        meta: { requiresAuth: true, title: '系统教学', icon: 'Reading', group: '系统设置', order: 10 },
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('#/views/Logs.vue'),
        meta: { requiresAuth: true, title: '发送记录', icon: 'Tickets', group: '系统设置', order: 20, permission: 'log' },
      },
      {
        path: 'approvals',
        name: 'Approvals',
        component: () => import('#/views/Approvals.vue'),
        meta: { requiresAuth: true, title: '审批中心', icon: 'Stamp', group: '系统设置', order: 30, permission: 'approval' },
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('#/views/Users.vue'),
        meta: { requiresAuth: true, title: '用户管理', icon: 'User', group: '系统设置', order: 40, role: 'admin' },
      },
      {
        path: 'permissions',
        name: 'Permissions',
        component: () => import('#/views/Permissions.vue'),
        meta: { requiresAuth: true, title: '权限管理', icon: 'Lock', group: '系统设置', order: 50, role: 'admin' },
      },
      {
        path: 'prompt-manage',
        name: 'PromptManage',
        component: () => import('#/views/PromptManage/index.vue'),
        meta: { requiresAuth: true, title: '提示词管理', icon: 'EditPen', group: '系统设置', order: 60, role: 'admin' },
      },
      {
        path: 'feedback-review',
        name: 'FeedbackReview',
        component: () => import('#/views/FeedbackReview/index.vue'),
        meta: { requiresAuth: true, title: '反馈审核', icon: 'Comment', group: '系统设置', order: 70, role: 'admin' },
      },
      {
        path: 'rag-manage',
        name: 'RagManage',
        component: () => import('#/views/RagManage/index.vue'),
        meta: { requiresAuth: true, title: '知识库管理', icon: 'Coin', group: '系统设置', order: 80, role: 'admin' },
      },

      {
        path: 'profile',
        name: 'Profile',
        component: () => import('#/views/Profile.vue'),
        meta: { requiresAuth: true, title: '个人中心', hideInMenu: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const userStore = useUserStore()
  if (!to.meta.requiresAuth) {
    next()
    return
  }

  if (!userStore.user) {
    try {
      await userStore.fetchUser()
    } catch {
      next('/login')
      return
    }
  }

  // 使用与菜单一致的 canAccess 做统一权限判断
  if (!canAccess(userStore.user, to.meta)) {
    next('/dashboard')
    return
  }
  next()
})

export default router
