<template>
  <div class="dashboard-container">
    <div class="page-header">
      <h1 class="page-title">系统看板</h1>
      <el-button type="primary" @click="fetchDashboard">
        <el-icon><RefreshRight /></el-icon> 刷新数据
      </el-button>
    </div>

    <!-- Stats Row -->
    <el-row :gutter="24" v-if="dashboardStats" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-header">
            <span class="stat-title">群组总数</span>
            <el-icon class="stat-icon text-blue"><ChatDotRound /></el-icon>
          </div>
          <div class="stat-value">{{ dashboardStats.group_count || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-header">
            <span class="stat-title">消息模板</span>
            <el-icon class="stat-icon text-purple"><Document /></el-icon>
          </div>
          <div class="stat-value">{{ dashboardStats.template_count || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-header">
            <span class="stat-title">定时任务</span>
            <el-icon class="stat-icon text-orange"><Timer /></el-icon>
          </div>
          <div class="stat-value">{{ dashboardStats.schedule_count || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-header">
            <span class="stat-title">发送日志</span>
            <el-icon class="stat-icon text-green"><Tickets /></el-icon>
          </div>
          <div class="stat-value">{{ dashboardStats.log_count || 0 }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Detailed Stats Row -->
    <el-row :gutter="24" class="mt-6" v-if="dashboardStats">
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>系统运行状态</span>
            </div>
          </template>
          <div class="status-list">
            <div class="status-item">
              <span class="status-label">待审批任务</span>
              <span class="status-val warning">{{ dashboardStats.pending_approval_count || 0 }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">发送成功率</span>
              <span class="status-val success">{{ formatSuccessRate(dashboardStats.success_rate) }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">系统环境</span>
              <span class="status-val normal">健康</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span>快速操作</span>
            </div>
          </template>
          <div class="quick-actions">
            <el-button @click="router.push('/send')">发送测试消息</el-button>
            <el-button @click="router.push('/groups')">添加机器人群</el-button>
            <el-button @click="router.push('/templates')">管理素材模板</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
import { RefreshRight, ChatDotRound, Document, Timer, Tickets } from '@element-plus/icons-vue'

const router = useRouter()
const dashboardStats = ref<any>(null)

const formatSuccessRate = (value: unknown) => {
  const num = typeof value === 'number' ? value : Number(value)
  if (Number.isFinite(num)) {
    return `${num}%`
  }
  return '0%'
}

const fetchDashboard = async () => {
  try {
    const res = await request.get('/v1/dashboard/summary')
    dashboardStats.value = {
      ...res,
      pending_approval_count: res.pending_approval_count ?? 0
    }
  } catch (error) {
    console.error(error)
  }
}

onMounted(() => {
  fetchDashboard()
})
</script>

<style scoped>
.dashboard-container {
  max-width: 1200px;
  margin: 0 auto;
}

.stat-row {
  margin-bottom: 24px;
}

.stat-card {
  height: 120px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-radius: 12px;
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.stat-title {
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
}

.stat-icon {
  font-size: 20px;
  padding: 8px;
  border-radius: 8px;
  background-color: var(--bg-color);
}

.text-blue { color: #3b82f6; }
.text-purple { color: #8b5cf6; }
.text-orange { color: #f97316; }
.text-green { color: #10b981; }

.stat-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  color: var(--text-primary);
}

.chart-card {
  min-height: 240px;
}

.card-header {
  font-weight: 600;
  font-size: 16px;
}

.mt-6 {
  margin-top: 24px;
}

.status-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-color);
}
.status-item:last-child {
  border-bottom: none;
}

.status-label {
  color: var(--text-secondary);
  font-weight: 500;
}
.status-val {
  font-weight: 600;
  font-size: 16px;
}
.status-val.warning { color: #f59e0b; }
.status-val.success { color: #10b981; }
.status-val.normal { color: #3b82f6; }

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 8px;
}
</style>
