<template>
  <el-container class="layout-container">
    <el-aside width="240px" class="custom-aside">
      <div class="logo">
        <div class="logo-wrapper">
          <img :src="isDark ? '/images/light-logo.svg' : '/images/dark-logo.svg'" alt="logo" class="logo-img" />
        </div>
        <span class="logo-text">企微运营平台</span>
      </div>
      <el-menu
        :default-active="route.path"
        router
        class="custom-menu"
        :text-color="isDark ? '#E5EAF3' : '#334155'"
        active-text-color="#22C55E">
        <div class="menu-group">核心业务</div>
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <span>看板</span>
        </el-menu-item>
        <el-menu-item index="/send">
          <el-icon><Promotion /></el-icon>
          <span>发送中心</span>
        </el-menu-item>
        
        <div class="menu-group" style="margin-top: 20px;">数据管理</div>
        <el-menu-item index="/groups">
          <el-icon><ChatDotRound /></el-icon>
          <span>群管理</span>
        </el-menu-item>
        <el-menu-item index="/templates">
          <el-icon><Document /></el-icon>
          <span>模板中心</span>
        </el-menu-item>
        <el-menu-item index="/assets">
          <el-icon><Picture /></el-icon>
          <span>素材库</span>
        </el-menu-item>
        <el-menu-item index="/schedules">
          <el-icon><Timer /></el-icon>
          <span>定时任务</span>
        </el-menu-item>
        
        <div class="menu-group" style="margin-top: 20px;">系统设置</div>
        <el-menu-item index="/logs">
          <el-icon><Tickets /></el-icon>
          <span>发送记录</span>
        </el-menu-item>
        <el-menu-item index="/approvals">
          <el-icon><Stamp /></el-icon>
          <span>审批中心</span>
        </el-menu-item>
        <el-menu-item index="/users" v-if="userStore.user?.role === 'admin'">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
      
      <div class="user-footer">
        <el-dropdown trigger="click" @command="handleCommand">
          <span class="user-dropdown">
            <el-avatar 
              :size="32" 
              :src="userStore.user?.avatar_url || (userStore.user?.role === 'admin' ? '/images/admain.jpg' : '')"
              style="background-color: #22C55E">
              {{ userStore.user?.role === 'admin' ? '' : (userStore.user?.display_name?.charAt(0) || 'U') }}
            </el-avatar>
            <div class="user-info">
              <span class="user-name">{{ userStore.user?.display_name }}</span>
              <span class="user-role">{{ userStore.user?.role }}</span>
            </div>
            <el-icon><CaretBottom /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-aside>
    <el-container class="main-container">
      <el-header class="custom-header">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/' }">企微运营平台</el-breadcrumb-item>
          <el-breadcrumb-item>{{ getRouteName() }}</el-breadcrumb-item>
        </el-breadcrumb>
        <div class="header-right">
          <el-tooltip content="刷新页面" placement="bottom">
            <el-button :icon="RefreshRight" circle class="refresh-btn" @click="handleRefresh" />
          </el-tooltip>
          <ThemeToggle v-model="isDark" @change="handleThemeChange" />
        </div>
      </el-header>
      <el-main class="custom-main">
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { Platform, DataBoard, Promotion, ChatDotRound, Document, Picture, Timer, Tickets, Stamp, User, CaretBottom, RefreshRight } from '@element-plus/icons-vue'
import ThemeToggle from '@/components/ThemeToggle.vue'

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

const handleRefresh = () => {
  router.go(0)
}

const handleLogout = async () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  userStore.user = null
  window.location.href = '/login'
}

const handleCommand = (command: string) => {
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
    '/assets': '素材库',
    '/schedules': '定时任务',
    '/logs': '发送记录',
    '/approvals': '审批中心',
    '/users': '用户管理',
    '/profile': '个人中心'
  }
  return map[route.path] || '页面'
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background-color: var(--bg-color);
}
.custom-aside {
  background-color: var(--card-bg);
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 8px rgba(0,0,0,0.05);
  z-index: 10;
  border-right: 1px solid var(--border-color);
}
.logo {
  min-height: 60px;
  display: flex;
  align-items: center;
  padding: 16px 20px;
  color: var(--text-primary);
  gap: 16px;
  border-bottom: 1px solid var(--border-color);
  box-sizing: border-box;
  overflow: hidden;
}
.logo-icon {
  font-size: 24px;
  color: var(--primary-color);
}
.logo-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: transparent;
  padding: 4px;
  box-sizing: border-box;
}
:global(html.dark) .logo-wrapper {
  background: radial-gradient(circle, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0) 70%);
}
.logo-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
:global(html.dark) .logo-img {
  filter: drop-shadow(0px 0px 8px rgba(255, 255, 255, 0.6)) drop-shadow(0px 0px 2px rgba(255, 255, 255, 1));
}
.logo-text {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.custom-menu {
  border-right: none;
  background-color: transparent;
  flex: 1;
  padding: 20px 0;
}
.menu-group {
  padding: 0 24px 8px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}
.el-menu-item {
  height: 44px;
  line-height: 44px;
  margin: 4px 16px;
  border-radius: 8px;
}
.el-menu-item:hover, .el-menu-item.is-active {
  background-color: rgba(34, 197, 94, 0.1) !important;
}

.user-footer {
  padding: 16px;
  border-top: 1px solid var(--border-color);
}
.user-dropdown {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-primary);
  transition: background-color 0.2s;
}
.user-dropdown:hover {
  background-color: rgba(128,128,128,0.1);
}
.user-info {
  display: flex;
  flex-direction: column;
  flex: 1;
}
.user-name {
  font-size: 14px;
  font-weight: 500;
  line-height: 1.2;
}
.user-role {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
  text-transform: capitalize;
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
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
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
.custom-main {
  padding: 24px 32px;
  height: calc(100vh - 60px);
  overflow-y: auto;
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
