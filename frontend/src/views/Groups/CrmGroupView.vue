<template>
  <div class="crm-group-view">
    <!-- CRM 不可用提示 -->
    <el-alert
      v-if="!loading && !available"
      title="CRM 数据库未配置或不可用"
      description="外部群运营视图需要连接 CRM 数据库（mfgcrmdb），请联系管理员配置 CRM 数据库连接信息。"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />

    <!-- 统计摘要 -->
    <div v-if="available && stats" class="crm-stats-bar">
      <div class="crm-stat-item">
        <span class="crm-stat-value">{{ stats.total_groups }}</span>
        <span class="crm-stat-label">外部群</span>
      </div>
      <div class="crm-stat-item">
        <span class="crm-stat-value">{{ stats.total_customers }}</span>
        <span class="crm-stat-label">客户总数</span>
      </div>
      <div class="crm-stat-item">
        <span class="crm-stat-value">{{ formatPoints(stats.total_points) }}</span>
        <span class="crm-stat-label">累计总积分</span>
      </div>
      <el-button plain size="small" :icon="RefreshRight" @click="handleRefresh" :loading="loading">刷新</el-button>
    </div>

    <div v-if="available">
      <!-- 移动端卡片 -->
      <div v-if="isMobile" v-loading="loading" class="m-card-list">
        <div v-for="g in groups" :key="g.id" class="m-card" @click="openMembers(g)">
          <div class="m-card__row">
            <strong class="m-card__title">{{ g.name }}</strong>
            <el-tag size="small">{{ g.member_count }} 人</el-tag>
          </div>
          <div class="m-card__stats">
            <span>总积分 {{ formatPoints(g.total_points_sum) }}</span>
            <span>人均 {{ g.avg_points }}</span>
          </div>
        </div>
        <el-empty v-if="!loading && !groups.length" :image-size="48" description="暂无外部群数据" />
      </div>

      <!-- 桌面端表格 -->
      <el-table v-else :data="groups" style="width: 100%" v-loading="loading" @row-click="openMembers" highlight-current-row cursor="pointer">
        <el-table-column prop="name" label="群名称" min-width="140" />
        <el-table-column prop="member_count" label="成员数" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.member_count }} 人</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前总积分" width="130" align="right">
          <template #default="{ row }">{{ formatPoints(row.points_sum) }}</template>
        </el-table-column>
        <el-table-column label="累计总积分" width="130" align="right">
          <template #default="{ row }">{{ formatPoints(row.total_points_sum) }}</template>
        </el-table-column>
        <el-table-column label="人均积分" width="110" align="right">
          <template #default="{ row }">{{ row.avg_points }}</template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 成员详情弹窗 -->
    <el-dialog v-model="memberDialogVisible" :title="`${currentGroupName} — 成员列表`" width="640px" destroy-on-close>
      <el-table :data="members" v-loading="memberLoading" style="width: 100%" max-height="400">
        <el-table-column prop="name" label="姓名" min-width="100" />
        <el-table-column prop="points" label="当前积分" width="120" align="right">
          <template #default="{ row }">{{ row.points }}</template>
        </el-table-column>
        <el-table-column prop="total_points" label="累计积分" width="120" align="right">
          <template #default="{ row }">{{ row.total_points }}</template>
        </el-table-column>
      </el-table>
      <div v-if="members.length" class="member-summary">
        共 {{ members.length }} 人，当前积分合计 {{ memberPointsSum }}，累计合计 {{ memberTotalSum }}
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RefreshRight } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useMobile } from '@/composables/useMobile'

const { isMobile } = useMobile()

const groups = ref<any[]>([])
const loading = ref(false)
const available = ref(false)
const stats = ref<any>(null)

const members = ref<any[]>([])
const memberLoading = ref(false)
const memberDialogVisible = ref(false)
const currentGroupName = ref('')

const memberPointsSum = computed(() => members.value.reduce((s, m) => s + m.points, 0))
const memberTotalSum = computed(() => members.value.reduce((s, m) => s + m.total_points, 0))

const formatPoints = (v: number) => {
  if (v >= 10000) return (v / 10000).toFixed(1) + '万'
  return String(v)
}

const fetchGroups = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/crm-groups')
    available.value = res.available ?? false
    groups.value = res.groups || []
  } catch {
    available.value = false
    groups.value = []
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    stats.value = await request.get('/v1/crm-groups/stats')
  } catch {
    stats.value = null
  }
}

const openMembers = async (row: any) => {
  currentGroupName.value = row.name
  memberDialogVisible.value = true
  memberLoading.value = true
  members.value = []
  try {
    const res: any = await request.get(`/v1/crm-groups/${row.id}/members`)
    members.value = res.members || []
  } catch {
    members.value = []
  } finally {
    memberLoading.value = false
  }
}

const handleRefresh = async () => {
  try { await request.post('/v1/crm-groups/refresh-cache') } catch { /* ignore */ }
  await Promise.all([fetchGroups(), fetchStats()])
}

onMounted(() => {
  fetchGroups()
  fetchStats()
})
</script>

<style scoped>
.crm-group-view {
  background: var(--card-bg, #fff);
  border-radius: 4px;
}

.crm-stats-bar {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 14px 18px;
  margin-bottom: 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}
.crm-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.crm-stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--primary-color);
}
.crm-stat-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.m-card-list { display: flex; flex-direction: column; gap: 10px; }
.m-card {
  padding: 14px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--card-bg);
  cursor: pointer;
  transition: border-color 0.2s;
}
.m-card:hover { border-color: var(--primary-color); }
.m-card__row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.m-card__title { font-size: 14px; color: var(--text-primary); }
.m-card__stats {
  display: flex; gap: 16px;
  margin-top: 6px; font-size: 13px; color: var(--text-muted);
}

.member-summary {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(34, 197, 94, 0.06);
  font-size: 13px;
  color: var(--text-secondary);
}

:global(html.dark) .crm-stats-bar {
  background: #1d1e1f !important;
  border-color: #414243 !important;
}
:global(html.dark) .member-summary {
  background: rgba(74, 222, 128, 0.08);
}

@media (max-width: 768px) {
  .crm-stats-bar {
    flex-wrap: wrap;
    gap: 12px;
    padding: 12px;
  }
  .crm-stat-value { font-size: 18px; }
}
</style>
