import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '@/store/user';
import Layout from '@/layout/index.vue';
const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/login',
            name: 'Login',
            component: () => import('@/views/Login.vue'),
            meta: { requiresAuth: false }
        },
        {
            path: '/',
            component: Layout,
            redirect: '/dashboard',
            children: [
                { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { requiresAuth: true, title: '看板' } },
                { path: 'send', name: 'SendCenter', component: () => import('@/views/SendCenter.vue'), meta: { requiresAuth: true, title: '发送中心' } },
                { path: 'groups', name: 'Groups', component: () => import('@/views/Groups.vue'), meta: { requiresAuth: true, title: '群管理' } },
                { path: 'templates', name: 'Templates', component: () => import('@/views/Templates.vue'), meta: { requiresAuth: true, title: '模板中心' } },
                { path: 'assets', name: 'Assets', component: () => import('@/views/Assets.vue'), meta: { requiresAuth: true, title: '素材库' } },
                { path: 'schedules', name: 'Schedules', component: () => import('@/views/Schedules.vue'), meta: { requiresAuth: true, title: '定时任务' } },
                { path: 'logs', name: 'Logs', component: () => import('@/views/Logs.vue'), meta: { requiresAuth: true, title: '发送记录' } },
                { path: 'approvals', name: 'Approvals', component: () => import('@/views/Approvals.vue'), meta: { requiresAuth: true, title: '审批中心' } },
                { path: 'users', name: 'Users', component: () => import('@/views/Users.vue'), meta: { requiresAuth: true, title: '用户管理' } }
            ]
        }
    ]
});
router.beforeEach(async (to, from, next) => {
    const userStore = useUserStore();
    if (to.meta.requiresAuth) {
        if (!userStore.user) {
            try {
                await userStore.fetchUser();
                next();
            }
            catch (error) {
                next('/login');
            }
        }
        else {
            next();
        }
    }
    else {
        next();
    }
});
export default router;
//# sourceMappingURL=index.js.map