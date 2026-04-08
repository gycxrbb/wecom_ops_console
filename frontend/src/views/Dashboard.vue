<template>
  <div class="dashboard-container">
    <!-- Welcome Header -->
    <div class="welcome-section">
      <div class="welcome-text">
        <h1 class="welcome-title">系统看板</h1>
        <p class="welcome-desc">企业微信消息运营平台数据概览</p>
      </div>
      <el-button class="refresh-btn" @click="fetchDashboard" :loading="loading">
        <el-icon><RefreshRight /></el-icon>
        刷新数据
      </el-button>
    </div>

    <!-- Stats Row -->
    <div class="stats-grid" v-if="dashboardStats">
      <div class="stat-card stat-card--blue">
        <div class="stat-card__icon-wrap">
          <el-icon :size="24"><ChatDotRound /></el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__label">群组总数</span>
          <span class="stat-card__value">{{ dashboardStats.group_count || 0 }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--purple">
        <div class="stat-card__icon-wrap">
          <el-icon :size="24"><Document /></el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__label">消息模板</span>
          <span class="stat-card__value">{{ dashboardStats.template_count || 0 }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--orange">
        <div class="stat-card__icon-wrap">
          <el-icon :size="24"><Timer /></el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__label">定时任务</span>
          <span class="stat-card__value">{{ dashboardStats.schedule_count || 0 }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--green">
        <div class="stat-card__icon-wrap">
          <el-icon :size="24"><Tickets /></el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__label">发送日志</span>
          <span class="stat-card__value">{{ dashboardStats.log_count || 0 }}</span>
        </div>
      </div>
    </div>

    <!-- Bottom Row -->
    <div class="bottom-grid" v-if="dashboardStats">
      <!-- System Status -->
      <div class="panel">
        <div class="panel__header">
          <div class="panel__header-icon panel__header-icon--blue">
            <el-icon :size="18"><Monitor /></el-icon>
          </div>
          <h3 class="panel__title">系统运行状态</h3>
        </div>
        <div class="panel__body">
          <div class="status-list">
            <div class="status-item">
              <div class="status-item__left">
                <span class="status-dot status-dot--warning"></span>
                <span class="status-item__label">待审批任务</span>
              </div>
              <span class="status-item__value status-item__value--warning">{{ dashboardStats.pending_approval_count || 0 }}</span>
            </div>
            <div class="status-item">
              <div class="status-item__left">
                <span class="status-dot status-dot--success"></span>
                <span class="status-item__label">发送成功率</span>
              </div>
              <span class="status-item__value status-item__value--success">{{ formatSuccessRate(dashboardStats.success_rate) }}</span>
            </div>
            <div class="status-item">
              <div class="status-item__left">
                <span class="status-dot status-dot--blue"></span>
                <span class="status-item__label">系统环境</span>
              </div>
              <span class="status-item__value status-item__value--blue">健康</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="panel">
        <div class="panel__header">
          <div class="panel__header-icon panel__header-icon--green">
            <el-icon :size="18"><Promotion /></el-icon>
          </div>
          <h3 class="panel__title">快速操作</h3>
        </div>
        <div class="panel__body">
          <div class="quick-grid">
            <div class="quick-card" @click="router.push('/send')">
              <div class="quick-card__icon quick-card__icon--green">
                <el-icon :size="22"><Position /></el-icon>
              </div>
              <span class="quick-card__label">发送消息</span>
            </div>
            <div class="quick-card" @click="router.push('/groups')">
              <div class="quick-card__icon quick-card__icon--blue">
                <el-icon :size="22"><ChatDotRound /></el-icon>
              </div>
              <span class="quick-card__label">群组管理</span>
            </div>
            <div class="quick-card" @click="router.push('/templates')">
              <div class="quick-card__icon quick-card__icon--purple">
                <el-icon :size="22"><Document /></el-icon>
              </div>
              <span class="quick-card__label">模板中心</span>
            </div>
            <div class="quick-card" @click="router.push('/schedules')">
              <div class="quick-card__icon quick-card__icon--orange">
                <el-icon :size="22"><Timer /></el-icon>
              </div>
              <span class="quick-card__label">定时任务</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
import {
  RefreshRight, ChatDotRound, Document, Timer, Tickets,
  Monitor, Promotion, Position
} from '@element-plus/icons-vue'

const router = useRouter()
const dashboardStats = ref<any>(null)
const loading = ref(false)

const formatSuccessRate = (value: unknown) => {
  const num = typeof value === 'number' ? value : Number(value)
  if (Number.isFinite(num)) {
    return `${num}%`
  }
  return '0%'
}

const fetchDashboard = async () => {
  loading.value = true
  try {
    const res = await request.get('/v1/dashboard/summary')
    dashboardStats.value = {
      ...res,
      pending_approval_count: res.pending_approval_count ?? 0
    }
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboard()
})
</script>

<style scoped>
.dashboard-container {
  max-width: 1280px;
  margin: 0 auto;
  animation: fadeIn 0.4s ease;
}

/* Welcome Section */
.welcome-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}
.welcome-title {
  font-size: 26px;
  font-weight: 800;
  margin: 0;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}
.welcome-desc {
  margin: 4px 0 0;
  font-size: 14px;
  color: var(--text-muted);
}
.refresh-btn {
  border-radius: 8px;
  font-weight: 500;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}
@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-card {
  border-radius: 16px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 18px;
  transition: transform 0.2s, box-shadow 0.2s;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  position: relative;
  overflow: hidden;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.stat-card__icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-card--blue .stat-card__icon-wrap {
  background: linear-gradient(135deg, #dbeafe, #eff6ff);
  color: #3b82f6;
}
.stat-card--purple .stat-card__icon-wrap {
  background: linear-gradient(135deg, #ede9fe, #f5f3ff);
  color: #8b5cf6;
}
.stat-card--orange .stat-card__icon-wrap {
  background: linear-gradient(135deg, #ffedd5, #fff7ed);
  color: #f97316;
}
.stat-card--green .stat-card__icon-wrap {
  background: linear-gradient(135deg, #dcfce7, #f0fdf4);
  color: #10b981;
}

:global(html.dark) .stat-card--blue .stat-card__icon-wrap {
  background: rgba(59, 130, 246, 0.15);
}
:global(html.dark) .stat-card--purple .stat-card__icon-wrap {
  background: rgba(139, 92, 246, 0.15);
}
:global(html.dark) .stat-card--orange .stat-card__icon-wrap {
  background: rgba(249, 115, 22, 0.15);
}
:global(html.dark) .stat-card--green .stat-card__icon-wrap {
  background: rgba(16, 185, 129, 0.15);
}

.stat-card__content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-card__label {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 500;
}
.stat-card__value {
  font-size: 30px;
  font-weight: 800;
  line-height: 1.1;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

/* Bottom Grid */
.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
@media (max-width: 900px) {
  .bottom-grid {
    grid-template-columns: 1fr;
  }
}

/* Panel */
.panel {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.panel:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}
.panel__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.015);
}
:global(html.dark) .panel__header {
  background: rgba(255, 255, 255, 0.02);
}
.panel__header-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.panel__header-icon--blue {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}
.panel__header-icon--green {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}
.panel__title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
}
.panel__body {
  padding: 20px 22px;
}

/* Status List */
.status-list {
  display: flex;
  flex-direction: column;
}
.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--border-color);
}
.status-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.status-item:first-child {
  padding-top: 0;
}
.status-item__left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot--warning { background: #f59e0b; }
.status-dot--success { background: #10b981; }
.status-dot--blue { background: #3b82f6; }
.status-item__label {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}
.status-item__value {
  font-size: 15px;
  font-weight: 700;
}
.status-item__value--warning { color: #f59e0b; }
.status-item__value--success { color: #10b981; }
.status-item__value--blue { color: #3b82f6; }

/* Quick Actions Grid */
.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}
.quick-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px 12px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s;
  background: var(--bg-color);
}
.quick-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.1);
}
.quick-card__icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.quick-card__icon--green { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.quick-card__icon--blue { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }
.quick-card__icon--purple { background: rgba(139, 92, 246, 0.1); color: #8b5cf6; }
.quick-card__icon--orange { background: rgba(249, 115, 22, 0.1); color: #f97316; }
.quick-card__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ---- Mobile / Tablet ---- */
@media (max-width: 767px) {
  .dashboard-container {
    padding: 0;
  }
  .welcome-section {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  .stat-value {
    font-size: 24px;
  }
  .bottom-grid {
    grid-template-columns: 1fr;
  }
  .quick-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  .stat-card {
    gap: 12px;
  }
}
</style>
