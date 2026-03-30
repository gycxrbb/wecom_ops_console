<template>
  <div class="dashboard-container">
    <h2>Dashboard</h2>
    <el-row :gutter="20" v-if="dashboardStats">
      <el-col :span="4" v-for="(value, key) in dashboardStats" :key="key">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">{{ formatKey(key) }}</div>
          <div class="stat-value">{{ value }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import request from '@/utils/request'

const dashboardStats = ref<any>(null)

const fetchDashboard = async () => {
  try {
    const res = await request.get('/v1/bootstrap')
    dashboardStats.value = res.dashboard
  } catch (error) {
    console.error(error)
  }
}

const formatKey = (key: string) => {
  const map: Record<string, string> = {
    group_count: '群组数',
    template_count: '模板数',
    schedule_count: '计划数',
    log_count: '日志数',
    pending_approval_count: '待审批',
    success_rate: '成功率'
  }
  return map[key] || key
}

onMounted(() => {
  fetchDashboard()
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
}
.stat-card {
  text-align: center;
}
.stat-title {
  color: #909399;
  font-size: 14px;
}
.stat-value {
  color: #303133;
  font-size: 24px;
  font-weight: bold;
  margin-top: 10px;
}
</style>
