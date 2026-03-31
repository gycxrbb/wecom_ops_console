<template>
  <div class="profile-container">
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <span>个人中心</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- 账号信息 -->
        <el-tab-pane label="账号信息" name="info">
          <el-descriptions title="当前账号详情" :column="1" border class="info-list">
            <el-descriptions-item label="登录账号">{{ userStore.user?.username }}</el-descriptions-item>
            <el-descriptions-item label="显示名称">{{ userStore.user?.display_name }}</el-descriptions-item>
            <el-descriptions-item label="账号角色">
              <el-tag :type="userStore.user?.role === 'admin' ? 'danger' : 'success'">
                {{ userStore.user?.role === 'admin' ? '系统管理员' : '运营教练' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="账号状态">
              <el-tag type="success">正常</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="注册时间">
              {{ '与系统初始化记录一致' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 权限说明 -->
        <el-tab-pane label="权限说明" name="permissions">
          <el-alert
            v-if="userStore.user?.role === 'admin'"
            title="您拥有系统的最高管理权限"
            type="error"
            description="您可以查看并操作所有功能，包括核心配置、人员管理、权限分配以及全量数据查看。"
            show-icon
            :closable="false"
            class="permission-alert"
          />
          <el-alert
            v-else
            title="您拥有教练/运营基础权限"
            type="success"
            description="您可以管理素材库、创建推送模板、进行发群和审批申请操作，能查看并维护自己负责的业务。"
            show-icon
            :closable="false"
            class="permission-alert"
          />
          
          <el-table :data="permissionsData" border style="width: 100%; margin-top: 20px;">
            <el-table-column prop="module" label="功能模块" width="180" />
            <el-table-column prop="admin" label="管理员权限" />
            <el-table-column prop="coach" label="教练权限" />
          </el-table>
        </el-tab-pane>

        <!-- 密码修改 -->
        <el-tab-pane label="账户安全" name="security">
          <el-alert
            title="功能维护中"
            type="warning"
            description="修改密码功能正在开发对接中，如需修改请联系系统管理员。"
            show-icon
            :closable="false"
            class="permission-alert"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const activeTab = ref('info')

const permissionsData = [
  { module: '首页看板', admin: '查看全生命周期数据', coach: '查看个人相关数据' },
  { module: '发送中心', admin: '测试、预览、多群并发', coach: '测试、预览、多群并发' },
  { module: '群管理', admin: '全量增删改查设置Webhook', coach: '仅能选择使用可见的群' },
  { module: '模板管理', admin: '维护全系统共享模板', coach: '维护个人专属模板' },
  { module: '审批中心', admin: '处理并一键应用审核', coach: '提交定时/发信申请' },
  { module: '系统设置', admin: '可管理所有人员配置', coach: '无访问权限' }
]
</script>

<style scoped>
.profile-container {
  max-width: 800px;
  margin: 0 auto;
}

.profile-card {
  border-radius: 8px;
  background-color: var(--card-bg);
}

.card-header {
  font-weight: bold;
  font-size: 16px;
}

.info-list {
  margin-top: 10px;
}

.permission-alert {
  margin-bottom: 20px;
}

:deep(.el-descriptions__label) {
  width: 120px;
  justify-content: center;
}
</style>