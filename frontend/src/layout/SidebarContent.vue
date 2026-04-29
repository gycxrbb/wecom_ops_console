<template>
  <div class="sidebar-content">
    <div class="logo">
      <div class="logo-wrapper">
        <img :src="isDark ? '/images/light-logo.svg' : '/images/dark-logo.svg'" alt="logo" class="logo-img" />
      </div>
      <span class="logo-text">企微运营平台</span>
    </div>
    <el-menu
      :default-active="routePath"
      router
      class="custom-menu"
      :text-color="isDark ? '#E5EAF3' : '#334155'"
      active-text-color="#22C55E"
      @select="onMenuSelect"
    >
      <div class="menu-group">核心业务</div>
      <el-menu-item index="/">
        <el-icon><DataBoard /></el-icon>
        <span>看板</span>
      </el-menu-item>
      <el-menu-item index="/send" v-if="moduleVisible('send')">
        <el-icon><Promotion /></el-icon>
        <span>发送中心</span>
      </el-menu-item>

      <div class="menu-group" style="margin-top: 20px;">数据管理</div>
      <el-menu-item index="/groups" v-if="moduleVisible('group')">
        <el-icon><ChatDotRound /></el-icon>
        <span>群管理</span>
      </el-menu-item>
      <el-menu-item index="/templates" v-if="moduleVisible('template')">
        <el-icon><Document /></el-icon>
        <span>模板中心</span>
      </el-menu-item>
      <el-menu-item index="/assets" v-if="moduleVisible('asset')">
        <el-icon><Picture /></el-icon>
        <span>素材库</span>
      </el-menu-item>
      <el-menu-item index="/schedules" v-if="moduleVisible('schedule')">
        <el-icon><Timer /></el-icon>
        <span>定时任务</span>
      </el-menu-item>
      <el-menu-item index="/sop-docs" v-if="moduleVisible('sop')">
        <el-icon><Notebook /></el-icon>
        <span>飞书文档</span>
      </el-menu-item>

      <div class="menu-group" style="margin-top: 20px;">运营配置</div>
      <el-menu-item index="/crm-profile" v-if="moduleVisible('crm_profile')">
        <el-icon><UserFilled /></el-icon>
        <span>客户档案</span>
      </el-menu-item>
      <el-menu-item index="/speech-templates" v-if="moduleVisible('speech_template')">
        <el-icon><ChatLineSquare /></el-icon>
        <span>话术管理</span>
      </el-menu-item>

      <div class="menu-group" style="margin-top: 20px;">系统设置</div>
      <el-menu-item index="/system-teaching">
        <el-icon><Reading /></el-icon>
        <span>系统教学</span>
      </el-menu-item>
      <el-menu-item index="/logs" v-if="moduleVisible('log')">
        <el-icon><Tickets /></el-icon>
        <span>发送记录</span>
      </el-menu-item>
      <el-menu-item index="/approvals" v-if="moduleVisible('approval')">
        <el-icon><Stamp /></el-icon>
        <span>审批中心</span>
      </el-menu-item>
      <el-menu-item index="/users" v-if="userStore.user?.role === 'admin'">
        <el-icon><User /></el-icon>
        <span>用户管理</span>
      </el-menu-item>
      <el-menu-item index="/permissions" v-if="userStore.user?.role === 'admin'">
        <el-icon><Lock /></el-icon>
        <span>权限管理</span>
      </el-menu-item>
      <el-menu-item index="/prompt-manage" v-if="userStore.user?.role === 'admin'">
        <el-icon><EditPen /></el-icon>
        <span>提示词管理</span>
      </el-menu-item>
    </el-menu>

    <div class="user-footer">
      <el-dropdown trigger="click" @command="$emit('command', $event)">
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
  </div>
</template>

<script setup lang="ts">
import { DataBoard, Promotion, ChatDotRound, Document, Picture, Timer, Tickets, Stamp, User, Lock, CaretBottom, Notebook, ChatLineSquare, Reading, UserFilled, EditPen } from '@element-plus/icons-vue'
import { moduleVisible as checkVisible, type PermissionKey } from '#/utils/permissions'

const props = defineProps<{
  isDark: boolean
  routePath: string
  userStore: any
}>()

const emit = defineEmits<{
  (e: 'command', command: string): void
  (e: 'navigate'): void
}>()

const moduleVisible = (key: string) => checkVisible(props.userStore?.user, key as PermissionKey)

const onMenuSelect = () => {
  emit('navigate')
}
</script>

<style scoped>
.sidebar-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--card-bg);
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
</style>
