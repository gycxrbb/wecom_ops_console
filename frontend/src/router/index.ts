import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '#/stores/user'
import { hasPermission, type PermissionKey } from '#/utils/permissions'
import Layout from '#/layout/index.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('#/views/Login.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      component: Layout,
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', name: 'Dashboard', component: () => import('#/views/Dashboard.vue'), meta: { requiresAuth: true, title: '看板' } },
        { path: 'send', name: 'SendCenter', component: () => import('#/views/SendCenter/index.vue'), meta: { requiresAuth: true, title: '发送中心', permission: 'send' as PermissionKey } },
        { path: 'groups', name: 'Groups', component: () => import('#/views/Groups/index.vue'), meta: { requiresAuth: true, title: '群管理', permission: 'group' as PermissionKey } },
        { path: 'templates', name: 'Templates', component: () => import('#/views/Templates/index.vue'), meta: { requiresAuth: true, title: '模板中心', permission: 'template' as PermissionKey } },
        { path: 'speech-templates', name: 'SpeechTemplates', component: () => import('#/views/SpeechTemplates.vue'), meta: { requiresAuth: true, title: '话术管理', permission: 'speech_template' as PermissionKey } },
        { path: 'assets', name: 'Assets', component: () => import('#/views/Assets/index.vue'), meta: { requiresAuth: true, title: '素材库', permission: 'asset' as PermissionKey } },
        { path: 'schedules', name: 'Schedules', component: () => import('#/views/Schedules.vue'), meta: { requiresAuth: true, title: '定时任务', permission: 'schedule' as PermissionKey } },
        { path: 'sop-docs', name: 'SopDocsHome', component: () => import('#/views/SopDocs/index.vue'), meta: { requiresAuth: true, title: '飞书文档', permission: 'sop' as PermissionKey } },
        { path: 'sop-docs/governance', name: 'SopDocsGovernance', component: () => import('#/views/SopDocs/Governance.vue'), meta: { requiresAuth: true, title: '飞书文档', permission: 'sop' as PermissionKey } },
        { path: 'sop-docs/workspace/:id', name: 'WorkspaceDetail', component: () => import('#/views/SopDocs/WorkspaceDetail.vue'), meta: { requiresAuth: true, title: '飞书文档', permission: 'sop' as PermissionKey } },
        { path: 'crm-profile', name: 'CrmProfile', component: () => import('#/views/CrmProfile/index.vue'), meta: { requiresAuth: true, title: '客户档案', permission: 'crm_profile' as PermissionKey } },
        { path: 'system-teaching', name: 'SystemTeaching', component: () => import('#/views/SystemTeaching.vue'), meta: { requiresAuth: true, title: '系统教学' } },
        { path: 'logs', name: 'Logs', component: () => import('#/views/Logs.vue'), meta: { requiresAuth: true, title: '发送记录', permission: 'log' as PermissionKey } },
        { path: 'approvals', name: 'Approvals', component: () => import('#/views/Approvals.vue'), meta: { requiresAuth: true, title: '审批中心', permission: 'approval' as PermissionKey } },
        { path: 'users', name: 'Users', component: () => import('#/views/Users.vue'), meta: { requiresAuth: true, title: '用户管理', role: 'admin' } },
        { path: 'permissions', name: 'Permissions', component: () => import('#/views/Permissions.vue'), meta: { requiresAuth: true, title: '权限管理', role: 'admin' } },
        { path: 'prompt-manage', name: 'PromptManage', component: () => import('#/views/PromptManage/index.vue'), meta: { requiresAuth: true, title: '提示词管理', role: 'admin' } },
        { path: 'feedback-review', name: 'FeedbackReview', component: () => import('#/views/FeedbackReview/index.vue'), meta: { requiresAuth: true, title: '反馈审核', role: 'admin' } },
        { path: 'auto-ranking', name: 'AutoRanking', component: () => import('#/views/AutoRanking/index.vue'), meta: { requiresAuth: true, title: '自动排行推送', role: 'admin' } },
        { path: 'rag-manage', name: 'RagManage', component: () => import('#/views/RagManage/index.vue'), meta: { requiresAuth: true, title: '知识库管理', role: 'admin' } },
        { path: 'profile', name: 'Profile', component: () => import('#/views/Profile.vue'), meta: { requiresAuth: true, title: '个人中心' } }
      ]
    }
  ]
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()
  if (to.meta.requiresAuth) {
    if (!userStore.user) {
      try {
        await userStore.fetchUser()
      } catch {
        next('/login')
        return
      }
    }
    // 角色检查
    if (to.meta.role && userStore.user?.role !== to.meta.role) {
      next('/dashboard')
      return
    }
    // 权限检查
    if (to.meta.permission && !hasPermission(userStore.user, to.meta.permission as PermissionKey)) {
      next('/dashboard')
      return
    }
    next()
  } else {
    next()
  }
})

export default router
