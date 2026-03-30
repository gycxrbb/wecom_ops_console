<template>
  <el-container class="layout-container">
    <el-aside width="200px">
      <div class="logo">WeCom Ops</div>
      <el-menu :default-active="route.path" router background-color="#304156" text-color="#bfcbd9" active-text-color="#409EFF">
        <el-menu-item index="/dashboard">
          <span>看板</span>
        </el-menu-item>
        <el-menu-item index="/send">
          <span>发送中心</span>
        </el-menu-item>
        <el-menu-item index="/groups">
          <span>群管理</span>
        </el-menu-item>
        <el-menu-item index="/templates">
          <span>模板中心</span>
        </el-menu-item>
        <el-menu-item index="/assets">
          <span>素材库</span>
        </el-menu-item>
        <el-menu-item index="/schedules">
          <span>定时任务</span>
        </el-menu-item>
        <el-menu-item index="/logs">
          <span>发送记录</span>
        </el-menu-item>
        <el-menu-item index="/approvals">
          <span>审批中心</span>
        </el-menu-item>
        <el-menu-item index="/users" v-if="userStore.user?.role === 'admin'">
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header>
        <div class="header-right">
          <span>{{ userStore.user?.display_name }} ({{ userStore.user?.role }})</span>
          <el-button type="primary" link @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import request from '@/utils/request'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const handleLogout = async () => {
  await request.post('/auth/logout')
  window.location.href = '/login'
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: #fff;
  font-size: 20px;
  background: #2b3643;
}
.el-menu {
  border-right: none;
}
.el-header {
  background: #fff;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  border-bottom: 1px solid #e6e6e6;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}
.el-main {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
