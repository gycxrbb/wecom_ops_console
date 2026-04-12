<template>
  <div class="dashboard-container">
    <!-- Welcome Header -->
    <div class="welcome-section">
      <div class="welcome-text">
        <h1 class="welcome-title">{{ greeting }}，{{ userName }}</h1>
        <p class="welcome-desc">{{ todayDate }} · {{ isAdmin ? '系统看板' : '运营工作台' }}</p>
      </div>
      <el-button class="refresh-btn" @click="fetchDashboard" :loading="loading">
        <el-icon><RefreshRight /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- Stats Row -->
    <div class="stats-grid" v-if="data">
      <div class="stat-card stat-card--green">
        <div class="stat-card__icon-wrap"><el-icon :size="24"><Position /></el-icon></div>
        <div class="stat-card__content">
          <span class="stat-card__label">今日待发送</span>
          <span class="stat-card__value">{{ data.today_schedules?.length || 0 }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--blue">
        <div class="stat-card__icon-wrap"><el-icon :size="24"><ChatDotRound /></el-icon></div>
        <div class="stat-card__content">
          <span class="stat-card__label">今日已发送</span>
          <span class="stat-card__value">{{ data.today_sent || 0 }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--orange" v-if="isAdmin">
        <div class="stat-card__icon-wrap"><el-icon :size="24"><Stamp /></el-icon></div>
        <div class="stat-card__content">
          <span class="stat-card__label">待审批</span>
          <span class="stat-card__value">{{ data.pending_approval_count || 0 }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--purple">
        <div class="stat-card__icon-wrap"><el-icon :size="24"><Tickets /></el-icon></div>
        <div class="stat-card__content">
          <span class="stat-card__label">发送成功率</span>
          <span class="stat-card__value">{{ formatRate(data.success_rate) }}</span>
        </div>
      </div>
      <div class="stat-card stat-card--blue-dark">
        <div class="stat-card__icon-wrap"><el-icon :size="24"><Timer /></el-icon></div>
        <div class="stat-card__content">
          <span class="stat-card__label">定时任务总数</span>
          <span class="stat-card__value">{{ data.schedule_count || 0 }}</span>
        </div>
      </div>
    </div>

    <div class="bottom-grid">
      <!-- 今日待发送 -->
      <div class="panel">
        <div class="panel__header">
          <div class="panel__header-icon panel__header-icon--green">
            <el-icon :size="18"><Position /></el-icon>
          </div>
          <h3 class="panel__title">今日待发送</h3>
          <span class="panel__badge">{{ data?.today_schedules?.length || 0 }}</span>
        </div>
        <div class="panel__body">
          <div v-if="data?.today_schedules?.length" class="todo-list">
            <div v-for="s in data.today_schedules" :key="s.id" class="todo-item" @click="router.push('/schedules')">
              <div class="todo-item__left">
                <span class="todo-item__time">{{ formatTime(s.run_at) }}</span>
                <span class="todo-item__title">{{ s.title }}</span>
              </div>
              <span class="todo-item__type">{{ msgTypeLabel(s.msg_type) }}</span>
            </div>
          </div>
          <el-empty v-else :image-size="48" description="今天没有待发送任务" />
        </div>
      </div>

      <!-- 最近编排 -->
      <div class="panel">
        <div class="panel__header">
          <div class="panel__header-icon panel__header-icon--purple">
            <el-icon :size="18"><Document /></el-icon>
          </div>
          <h3 class="panel__title">最近编排</h3>
        </div>
        <div class="panel__body">
          <div v-if="data?.recent_plans?.length" class="todo-list">
            <div v-for="p in data.recent_plans" :key="p.id" class="todo-item" @click="router.push('/templates')">
              <div class="todo-item__left">
                <span class="todo-item__title">{{ p.name }}</span>
                <span class="todo-item__meta">{{ p.day_count }} 天 · {{ p.stage || '未设阶段' }}</span>
              </div>
              <span class="todo-item__date">{{ formatDate(p.updated_at) }}</span>
            </div>
          </div>
          <el-empty v-else :image-size="48" description="暂无运营计划" />
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="panel" style="margin-top: 20px;">
      <div class="panel__header">
        <div class="panel__header-icon panel__header-icon--blue">
          <el-icon :size="18"><Promotion /></el-icon>
        </div>
        <h3 class="panel__title">快速入口</h3>
      </div>
      <div class="panel__body">
        <div class="quick-grid">
          <div class="quick-card" @click="router.push('/send')">
            <div class="quick-card__icon quick-card__icon--green"><el-icon :size="22"><Position /></el-icon></div>
            <span class="quick-card__label">发送消息</span>
          </div>
          <div class="quick-card" @click="router.push('/templates')">
            <div class="quick-card__icon quick-card__icon--purple"><el-icon :size="22"><Document /></el-icon></div>
            <span class="quick-card__label">运营编排</span>
          </div>
          <div class="quick-card" @click="router.push('/schedules')">
            <div class="quick-card__icon quick-card__icon--orange"><el-icon :size="22"><Timer /></el-icon></div>
            <span class="quick-card__label">定时任务</span>
          </div>
          <div class="quick-card" @click="router.push('/sop-docs')">
            <div class="quick-card__icon quick-card__icon--blue"><el-icon :size="22"><Notebook /></el-icon></div>
            <span class="quick-card__label">飞书文档</span>
          </div>
          <div class="quick-card" @click="router.push('/groups')">
            <div class="quick-card__icon quick-card__icon--blue-dark"><el-icon :size="22"><ChatDotRound /></el-icon></div>
            <span class="quick-card__label">群管理</span>
          </div>
          <div class="quick-card" @click="router.push('/assets')">
            <div class="quick-card__icon quick-card__icon--green"><el-icon :size="22"><Picture /></el-icon></div>
            <span class="quick-card__label">素材库</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import request from '@/utils/request'
import {
  RefreshRight, ChatDotRound, Document, Timer, Tickets, Stamp,
  Position, Promotion, Picture, Notebook
} from '@element-plus/icons-vue'

const MSG_TYPE_LABELS: Record<string, string> = {
  text: '文本', markdown: 'Markdown', news: '图文', image: '图片',
  file: '文件', template_card: '卡片', raw_json: '原始JSON',
}

const router = useRouter()
const userStore = useUserStore()
const data = ref<any>(null)
const loading = ref(false)

const userName = computed(() => userStore.user?.display_name || userStore.user?.username || '教练')
const isAdmin = computed(() => userStore.user?.role === 'admin')

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const todayDate = computed(() => {
  const d = new Date()
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 周${weekdays[d.getDay()]}`
})

const formatRate = (v: any) => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? `${n}%` : '0%'
}

const formatTime = (iso: string) => {
  if (!iso) return '--:--'
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const formatDate = (iso: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

const msgTypeLabel = (type: string) => MSG_TYPE_LABELS[type] || type

const fetchDashboard = async () => {
  loading.value = true
  try {
    const res = await request.get('/v1/dashboard/summary')
    data.value = { ...res, pending_approval_count: res.pending_approval_count ?? 0 }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchDashboard)
</script>

<style scoped>
.dashboard-container {
  max-width: 1280px;
  margin: 0 auto;
  animation: fadeIn 0.4s ease;
}

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
.refresh-btn { border-radius: 8px; font-weight: 500; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  border-radius: 16px;
  padding: 20px 22px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: transform 0.2s, box-shadow 0.2s;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}
.stat-card__icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-card--green .stat-card__icon-wrap { background: linear-gradient(135deg, #dcfce7, #f0fdf4); color: #10b981; }
.stat-card--blue .stat-card__icon-wrap { background: linear-gradient(135deg, #dbeafe, #eff6ff); color: #3b82f6; }
.stat-card--orange .stat-card__icon-wrap { background: linear-gradient(135deg, #ffedd5, #fff7ed); color: #f97316; }
.stat-card--purple .stat-card__icon-wrap { background: linear-gradient(135deg, #ede9fe, #f5f3ff); color: #8b5cf6; }
.stat-card--blue-dark .stat-card__icon-wrap { background: linear-gradient(135deg, #e0e7ff, #eef2ff); color: #6366f1; }

:global(html.dark) .stat-card--green .stat-card__icon-wrap { background: rgba(16, 185, 129, 0.15); }
:global(html.dark) .stat-card--blue .stat-card__icon-wrap { background: rgba(59, 130, 246, 0.15); }
:global(html.dark) .stat-card--orange .stat-card__icon-wrap { background: rgba(249, 115, 22, 0.15); }
:global(html.dark) .stat-card--purple .stat-card__icon-wrap { background: rgba(139, 92, 246, 0.15); }
:global(html.dark) .stat-card--blue-dark .stat-card__icon-wrap { background: rgba(99, 102, 241, 0.15); }

.stat-card__content { display: flex; flex-direction: column; gap: 4px; }
.stat-card__label { font-size: 13px; color: var(--text-muted); font-weight: 500; }
.stat-card__value { font-size: 28px; font-weight: 800; line-height: 1.1; color: var(--text-primary); letter-spacing: -0.02em; }

.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
@media (max-width: 900px) {
  .bottom-grid { grid-template-columns: 1fr; }
}

.panel {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.panel:hover { box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06); }
.panel__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.015);
}
:global(html.dark) .panel__header { background: rgba(255, 255, 255, 0.02); }
.panel__header-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.panel__header-icon--green { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.panel__header-icon--purple { background: rgba(139, 92, 246, 0.1); color: #8b5cf6; }
.panel__header-icon--blue { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }
.panel__title { font-size: 15px; font-weight: 600; margin: 0; color: var(--text-primary); }
.panel__badge {
  margin-left: auto;
  display: inline-flex;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.12);
  color: #f59e0b;
  font-size: 12px;
  font-weight: 700;
}
.panel__body { padding: 16px 20px; }

.todo-list { display: flex; flex-direction: column; }
.todo-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  transition: background 0.15s;
}
.todo-item:last-child { border-bottom: none; padding-bottom: 0; }
.todo-item:first-child { padding-top: 0; }
.todo-item:hover { opacity: 0.75; }
.todo-item__left { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.todo-item__time {
  font-size: 14px;
  font-weight: 700;
  color: var(--primary-color);
  min-width: 40px;
}
.todo-item__title {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.todo-item__type {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-color);
  padding: 2px 8px;
  border-radius: 999px;
  flex-shrink: 0;
}
.todo-item__meta {
  font-size: 12px;
  color: var(--text-muted);
}
.todo-item__date {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}
.quick-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 12px;
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
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.quick-card__icon--green { background: rgba(16, 185, 129, 0.1); color: #10b981; }
.quick-card__icon--blue { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }
.quick-card__icon--purple { background: rgba(139, 92, 246, 0.1); color: #8b5cf6; }
.quick-card__icon--orange { background: rgba(249, 115, 22, 0.1); color: #f97316; }
.quick-card__icon--blue-dark { background: rgba(99, 102, 241, 0.1); color: #6366f1; }
.quick-card__label { font-size: 13px; font-weight: 600; color: var(--text-primary); }

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 767px) {
  .welcome-section { flex-direction: column; align-items: flex-start; gap: 12px; }
  .stats-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .bottom-grid { grid-template-columns: 1fr; }
  .quick-grid { grid-template-columns: repeat(3, 1fr); }
  .stat-card { padding: 14px; gap: 10px; }
  .stat-card__value { font-size: 22px; }
  .stat-card__icon-wrap { width: 40px; height: 40px; }
  .welcome-title { font-size: 20px; }
  .todo-item__type { display: none; }
}
@media (max-width: 480px) {
  .stats-grid { grid-template-columns: 1fr 1fr; gap: 8px; }
  .quick-grid { grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .quick-card { padding: 10px 6px; }
  .panel__body { padding: 12px; }
  .todo-item__meta { display: none; }
}
</style>
