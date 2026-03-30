<template>
  <el-container class="layout-container">
    <el-aside width="240px" class="custom-aside">
      <div class="logo">
        <el-icon class="logo-icon"><Platform /></el-icon>
        <span class="logo-text">WeCom Ops</span>
      </div>
      <el-menu 
        :default-active="route.path" 
        router 
        class="custom-menu"
        text-color="#F8FAFC" 
        active-text-color="#22C55E">
        <div class="menu-group">MAIN</div>
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon>
          <span>看板</span>
        </el-menu-item>
        <el-menu-item index="/send">
          <el-icon><Promotion /></el-icon>
          <span>发送中心</span>
        </el-menu-item>
        
        <div class="menu-group" style="margin-top: 20px;">MANAGEMENT</div>
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
        
        <div class="menu-group" style="margin-top: 20px;">SYSTEM</div>
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
            <el-avatar :size="32" style="background-color: #22C55E">{{ userStore.user?.display_name?.charAt(0) || 'U' }}</el-avatar>
            <div class="user-info">
              <span class="user-name">{{ userStore.user?.display_name }}</span>
              <span class="user-role">{{ userStore.user?.role }}</span>
            </div>
            <el-icon><CaretBottom /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-aside>
    <el-container class="main-container">
      <el-header class="custom-header">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/' }">WeCom Ops</el-breadcrumb-item>
          <el-breadcrumb-item>{{ getRouteName() }}</el-breadcrumb-item>
        </el-breadcrumb>
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
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import { Platform, DataBoard, Promotion, ChatDotRound, Document, Picture, Timer, Tickets, Stamp, User, CaretBottom } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const handleLogout = async () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  userStore.user = null
  window.location.href = '/login'
}

const handleCommand = (command: string) => {
  if (command === 'logout') {
    handleLogout()
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
    '/users': '用户管理'
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
  background-color: #0F172A; /* Slate 900 */
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 10px rgba(0,0,0,0.1);
  z-index: 10;
}
.logo {
  height: 70px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  color: #F8FAFC;
  gap: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.logo-icon {
  font-size: 24px;
  color: #22C55E;
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
  color: #64748B;
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
  border-top: 1px solid rgba(255,255,255,0.05);
}
.user-dropdown {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  color: white;
  transition: background-color 0.2s;
}
.user-dropdown:hover {
  background-color: rgba(255,255,255,0.05);
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
  color: #94A3B8;
  margin-top: 2px;
  text-transform: capitalize;
}

.main-container {
  display: flex;
  flex-direction: column;
}
.custom-header {
  background-color: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid var(--border-color);
  height: 60px;
  position: sticky;
  top: 0;
  z-index: 5;
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
