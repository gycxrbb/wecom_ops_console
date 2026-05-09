<template>
  <el-container class="layout-container">
    <!-- Desktop sidebar: hidden on mobile/tablet -->
    <el-aside width="240px" class="custom-aside hide-on-mobile">
      <SidebarContent
        :is-dark="isDark"
        :route-path="route.path"
        :user-store="userStore"
        @command="handleCommand"
      />
    </el-aside>

    <!-- Mobile drawer sidebar -->
    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      :size="260"
      :show-close="false"
      :with-header="false"
      class="mobile-sidebar-drawer"
      @close="drawerVisible = false"
    >
      <SidebarContent
        :is-dark="isDark"
        :route-path="route.path"
        :user-store="userStore"
        @command="handleCommand"
        @navigate="drawerVisible = false"
      />
    </el-drawer>

    <el-container class="main-container">
      <el-header class="custom-header">
        <div class="header-left">
          <button class="hamburger-btn show-on-mobile" @click="drawerVisible = true">
            <el-icon :size="20"><Expand /></el-icon>
          </button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">企微运营平台</el-breadcrumb-item>
            <el-breadcrumb-item>{{ getRouteName() }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <span class="header-clock hide-on-mobile">{{ currentTime }}</span>
          <el-tooltip content="刷新页面" placement="bottom">
            <el-button :icon="RefreshRight" circle class="refresh-btn" @click="handleRefresh" />
          </el-tooltip>
          <ThemeToggle v-model="isDark" @change="handleThemeChange" />
        </div>
      </el-header>
      <el-main class="custom-main">
        <router-view v-slot="{ Component, route }">
          <KeepAlive :include="keepAliveList" :max="8">
            <component :is="Component" :key="route.name" />
          </KeepAlive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '#/stores/user'
import { Expand, RefreshRight } from '@element-plus/icons-vue'
import ThemeToggle from '#/components/ThemeToggle.vue'
import SidebarContent from './SidebarContent.vue'

const isDark = ref(localStorage.getItem('theme') === 'dark' || !localStorage.getItem('theme'))

onMounted(() => {
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
})

const handleThemeChange = (val: boolean) => {
  if (val) {
    document.documentElement.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const drawerVisible = ref(false)

// Keep-alive: only low-risk list pages, not editors with complex state
const keepAliveList = [
  'Dashboard', 'Groups', 'Templates', 'Schedules',
  'Assets', 'SpeechTemplates', 'SopDocsHome',
]

// Navigate时关闭 drawer
watch(() => route.path, () => {
  drawerVisible.value = false
})

const handleRefresh = () => {
  router.go(0)
}

const currentTime = ref('')
let clockTimer: ReturnType<typeof setInterval> | null = null
const updateClock = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  currentTime.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}
updateClock()
clockTimer = setInterval(updateClock, 1000)

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
})

const handleLogout = async () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  userStore.user = null
  window.location.href = '/login'
}

const handleCommand = (command: string) => {
  drawerVisible.value = false
  if (command === 'logout') {
    handleLogout()
  } else if (command === 'profile') {
    router.push('/profile')
  }
}

const getRouteName = () => {
  const map: Record<string, string> = {
    '/': '首页看板',
    '/dashboard': '面板看板',
    '/send': '发送中心',
    '/groups': '群管理',
    '/templates': '模板中心',
    '/speech-templates': '话术管理',
    '/assets': '素材库',
    '/schedules': '定时任务',
    '/crm-profile': '客户档案',
    '/logs': '发送记录',
    '/approvals': '审批中心',
    '/users': '用户管理',
    '/permissions': '权限管理',
    '/profile': '个人中心',
    '/feedback-review': '反馈审核',
    '/auto-ranking': '自动排行推送',
    '/rag-manage': '知识库管理'
  }
  return map[route.path] || '页面'
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background-color: var(--bg-color);
}

/* ---- Responsive visibility ---- */
.hide-on-mobile {
  display: flex;
}
.show-on-mobile {
  display: none !important;
}

.custom-aside {
  background-color: var(--card-bg);
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 8px rgba(0,0,0,0.05);
  z-index: 10;
  border-right: 1px solid var(--border-color);
}

.main-container {
  display: flex;
  flex-direction: column;
}
.custom-header {
  background-color: var(--card-bg);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid var(--border-color);
  height: 60px;
  position: sticky;
  top: 0;
  z-index: 5;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.header-clock {
  font-size: 13px;
  font-family: 'SF Mono', 'Cascadia Code', 'Menlo', monospace;
  color: var(--text-muted);
  letter-spacing: 0.02em;
  white-space: nowrap;
  user-select: none;
}
.refresh-btn {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  transition: all 0.2s;
}
.refresh-btn:hover {
  color: var(--primary-color);
  background: rgba(34, 197, 94, 0.08);
}
.hamburger-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}
.hamburger-btn:hover {
  background: rgba(128, 128, 128, 0.1);
}
.custom-main {
  padding: 24px 32px;
  height: calc(100vh - 60px);
  overflow-y: auto;
}

/* ---- Mobile / Tablet: ≤991px ---- */
@media (max-width: 991px) {
  .hide-on-mobile {
    display: none !important;
  }
  .show-on-mobile {
    display: flex !important;
  }
  .custom-header {
    padding: 0 16px;
    height: 52px;
  }
  .custom-main {
    padding: 16px;
    height: calc(100vh - 52px);
  }
}

/* ---- Small phone: ≤480px ---- */
@media (max-width: 480px) {
  .custom-main {
    padding: 12px;
  }
}

/* ---- Drawer overrides ---- */
.mobile-sidebar-drawer :deep(.el-drawer__body) {
  padding: 0;
}

/* ---- Global mobile overrides (non-scoped) ---- */
</style>

<style>
/* 全局弹窗：小屏幕自适应宽度 */
@media (max-width: 768px) {
  .el-dialog {
    --el-dialog-width: 92% !important;
    width: 92% !important;
    margin-top: 5vh !important;
  }
  .el-dialog__body {
    max-height: 70vh;
    overflow-y: auto;
  }
}

/* 全局表格：移动端横向可滚动 */
@media (max-width: 768px) {
  .el-table {
    font-size: 12px;
  }
  .el-table th, .el-table td {
    padding: 6px 0;
  }
}

/* 全局表单：移动端 label 改为顶部对齐 */
@media (max-width: 600px) {
  .el-form--default-label-width .el-form-item__label,
  .el-form-item__label {
    float: none !important;
    display: block !important;
    text-align: left !important;
    padding-bottom: 4px !important;
    width: auto !important;
  }
  .el-form-item__content {
    margin-left: 0 !important;
  }
}

/* 防止 pre 标签横向溢出 */
pre {
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 分页器移动端精简 */
@media (max-width: 600px) {
  .el-pagination {
    flex-wrap: wrap;
    justify-content: center;
  }
  .el-pagination .el-pagination__sizes,
  .el-pagination .el-pagination__jump {
    display: none;
  }
}

/* Animations */
.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.2s ease;
}
.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}
.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(10px);
}
</style>
