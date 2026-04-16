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

    <!-- 骨架屏 -->
    <div v-if="loading && !available" class="crm-skeleton">
      <div class="crm-skeleton__stats">
        <div v-for="i in 3" :key="i" class="crm-skeleton__stat" />
      </div>
      <div v-for="i in 5" :key="i" class="crm-skeleton__row" />
    </div>

    <!-- 正式内容 -->
    <Transition name="crm-fade">
      <div v-if="available" class="crm-content">
        <!-- 统计摘要 -->
        <div v-if="stats" class="crm-stats-bar">
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
          <div class="crm-stat-item">
            <span class="crm-stat-value">{{ formatPoints(stats.total_week_points ?? 0) }}</span>
            <span class="crm-stat-label">本周总积分</span>
          </div>
          <div class="crm-stat-item">
            <span class="crm-stat-value">{{ formatPoints(stats.total_month_points ?? 0) }}</span>
            <span class="crm-stat-label">本月总积分</span>
          </div>
          <div class="crm-stats-actions">
            <el-button plain size="small" :icon="RefreshRight" @click="handleRefresh" :loading="loading">刷新</el-button>
            <button class="lb-trigger-btn" @click="leaderboardVisible = true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5C7 4 7 7 7 7"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5C17 4 17 7 17 7"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>
              <span>积分榜单</span>
            </button>
          </div>
        </div>

        <!-- 搜索栏 -->
        <div class="crm-search-bar">
          <el-input
            v-model="searchQuery"
            placeholder="搜索群名称或用户名称"
            clearable
            :prefix-icon="Search"
            @input="handleSearchInput"
            @clear="clearSearch"
          />
          <div v-if="searchMode" class="crm-search-hint">
            <span v-if="searchMode === 'user'">
              正在搜索用户"<strong>{{ searchQuery }}</strong>"
              <span v-if="searchTotal > 0">，找到 {{ searchTotal }} 条结果</span>
            </span>
            <el-button v-if="searchMode === 'group'" link type="primary" size="small" @click="switchToUserSearch">
              改为搜索用户
            </el-button>
          </div>
        </div>

        <!-- ===== 搜索结果：用户模式 ===== -->
        <template v-if="searchMode === 'user'">
          <div v-if="isMobile" v-loading="searchLoading" class="m-card-list">
            <div v-for="u in searchResults" :key="u.id" class="m-card m-card--user">
              <div class="m-card__row">
                <strong class="m-card__title">{{ u.name }}</strong>
                <span class="m-card__points">{{ u.current_points ?? u.total_points }} 分</span>
              </div>
              <div class="m-card__meta">
                <span v-if="u.group_names">{{ u.group_names }}</span>
                <span>本周 +{{ u.week_points ?? 0 }} / 本月 +{{ u.month_points ?? 0 }}</span>
              </div>
            </div>
            <el-empty v-if="!searchLoading && !searchResults.length" :image-size="48" description="未找到匹配用户" />
          </div>
          <el-table v-else :data="searchResults" v-loading="searchLoading" style="width: 100%">
            <el-table-column prop="name" label="姓名" min-width="100" />
            <el-table-column prop="group_names" label="所属群组" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="group-tag">{{ row.group_names || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="当前积分" width="110" align="right">
              <template #default="{ row }">{{ row.current_points ?? row.points }}</template>
            </el-table-column>
            <el-table-column label="本周积分" width="110" align="right">
              <template #default="{ row }"><strong>{{ row.week_points ?? 0 }}</strong></template>
            </el-table-column>
            <el-table-column label="本月积分" width="110" align="right">
              <template #default="{ row }">{{ row.month_points ?? 0 }}</template>
            </el-table-column>
          </el-table>
          <div v-if="searchTotal > searchPageSize" class="crm-pagination">
            <el-pagination
              v-model:current-page="searchPage"
              :page-size="searchPageSize"
              :total="searchTotal"
              layout="total, prev, pager, next"
              @current-change="fetchUserSearch"
            />
          </div>
        </template>

        <!-- ===== 正常群列表 / 群名过滤 ===== -->
        <template v-else>
        <!-- 移动端卡片 -->
        <div v-if="isMobile" v-loading="loading" class="m-card-list">
          <div v-for="g in filteredGroups" :key="g.id" class="m-card" @click="openMembers(g)">
            <div class="m-card__row">
              <strong class="m-card__title">{{ g.name }}</strong>
              <el-tag size="small">{{ g.member_count }} 人</el-tag>
            </div>
            <div class="m-card__stats">
              <span>群总积分 {{ formatPoints(g.current_points_sum ?? g.total_points_sum) }}</span>
              <span>本周 +{{ g.week_points_sum ?? 0 }} / 本月 +{{ g.month_points_sum ?? 0 }}</span>
            </div>
          </div>
          <el-empty v-if="!loading && !filteredGroups.length" :image-size="48" :description="searchQuery ? '未找到匹配群组' : '暂无外部群数据'" />
        </div>

        <!-- 桌面端表格 -->
        <el-table v-else :data="filteredGroups" style="width: 100%" v-loading="loading" @row-click="openMembers" highlight-current-row cursor="pointer">
          <el-table-column prop="name" label="群名称" min-width="140" />
          <el-table-column prop="member_count" label="成员数" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small">{{ row.member_count }} 人</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="群总积分" width="130" align="right">
            <template #default="{ row }">{{ formatPoints(row.current_points_sum ?? row.total_points_sum) }}</template>
          </el-table-column>
          <el-table-column label="本周积分" width="130" align="right">
            <template #default="{ row }"><strong>{{ formatPoints(row.week_points_sum ?? 0) }}</strong></template>
          </el-table-column>
          <el-table-column label="本月积分" width="110" align="right">
            <template #default="{ row }">{{ formatPoints(row.month_points_sum ?? 0) }}</template>
          </el-table-column>
        </el-table>
        </template>
      </div>
    </Transition>

    <!-- 成员详情弹窗 -->
    <el-dialog v-model="memberDialogVisible" :title="`${currentGroupName} — 成员列表`" width="640px" destroy-on-close>
      <el-table :data="members" v-loading="memberLoading" style="width: 100%" max-height="400">
        <el-table-column prop="name" label="姓名" min-width="100" />
        <el-table-column label="当前积分" width="110" align="right">
          <template #default="{ row }">{{ row.current_points ?? row.total_points }}</template>
        </el-table-column>
        <el-table-column label="本周积分" width="110" align="right">
          <template #default="{ row }"><strong>{{ row.week_points ?? 0 }}</strong></template>
        </el-table-column>
        <el-table-column label="本月积分" width="110" align="right">
          <template #default="{ row }">{{ row.month_points ?? 0 }}</template>
        </el-table-column>
      </el-table>
      <div v-if="members.length" class="member-summary">
        共 {{ members.length }} 人，当前积分合计 {{ memberCurrentSum }}，本周合计 {{ memberWeekSum }}，本月合计 {{ memberMonthSum }}
      </div>
    </el-dialog>

    <!-- 积分榜单弹窗 -->
    <el-dialog v-model="leaderboardVisible" title="积分榜单" width="860px" destroy-on-close top="5vh">
      <CrmLeaderboard />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RefreshRight, Search } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useMobile } from '@/composables/useMobile'
import CrmLeaderboard from './CrmLeaderboard.vue'

const { isMobile } = useMobile()

const groups = ref<any[]>([])
const loading = ref(false)
const available = ref(false)
const stats = ref<any>(null)

const members = ref<any[]>([])
const memberLoading = ref(false)
const memberDialogVisible = ref(false)
const currentGroupName = ref('')
const leaderboardVisible = ref(false)

const memberCache = new Map<number, any[]>()

// --- 搜索 ---
const searchQuery = ref('')
const searchMode = ref<'group' | 'user' | null>(null)
const searchResults = ref<any[]>([])
const searchLoading = ref(false)
const searchPage = ref(1)
const searchPageSize = 20
const searchTotal = ref(0)
let searchTimer: ReturnType<typeof setTimeout> | null = null

const filteredGroups = computed(() => {
  if (!searchQuery.value || searchMode.value === 'user') return groups.value
  const q = searchQuery.value.toLowerCase()
  return groups.value.filter(g => g.name.toLowerCase().includes(q))
})

const formatPoints = (v: number) => {
  if (v >= 10000) return (v / 10000).toFixed(1) + '万'
  return String(v)
}

const handleSearchInput = () => {
  if (searchTimer) clearTimeout(searchTimer)
  const q = searchQuery.value.trim()

  if (!q) {
    searchMode.value = null
    searchResults.value = []
    return
  }

  // 先尝试群名本地过滤
  const localMatch = groups.value.filter(g => g.name.toLowerCase().includes(q.toLowerCase()))

  if (localMatch.length > 0) {
    searchMode.value = 'group'
    return
  }

  // 群名无匹配，自动切到用户搜索
  searchMode.value = 'user'
  searchPage.value = 1
  searchTimer = setTimeout(() => fetchUserSearch(), 300)
}

const switchToUserSearch = () => {
  searchMode.value = 'user'
  searchPage.value = 1
  fetchUserSearch()
}

const fetchUserSearch = async () => {
  const q = searchQuery.value.trim()
  if (!q) return
  searchLoading.value = true
  try {
    const res: any = await request.get('/v1/crm-groups/search/customers', {
      params: { q, page: searchPage.value, page_size: searchPageSize }
    })
    searchResults.value = res.list || []
    const p = res.pagination
    if (p) searchTotal.value = p.total
  } catch {
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

const clearSearch = () => {
  searchQuery.value = ''
  searchMode.value = null
  searchResults.value = []
}

const memberCurrentSum = computed(() => members.value.reduce((s, m) => s + (m.current_points ?? m.total_points ?? 0), 0))
const memberWeekSum = computed(() => members.value.reduce((s, m) => s + (m.week_points ?? 0), 0))
const memberMonthSum = computed(() => members.value.reduce((s, m) => s + (m.month_points ?? 0), 0))

const fetchGroups = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/crm-groups')
    available.value = res.available ?? false
    groups.value = res.groups || []
  } catch {
    available.value = false
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

  if (memberCache.has(row.id)) {
    members.value = memberCache.get(row.id)!
    memberLoading.value = false
    return
  }

  memberLoading.value = true
  members.value = []
  try {
    const res: any = await request.get(`/v1/crm-groups/${row.id}/members`)
    const list = res.members || []
    memberCache.set(row.id, list)
    members.value = list
  } catch {
    members.value = []
  } finally {
    memberLoading.value = false
  }
}

const handleRefresh = async () => {
  try { await request.post('/v1/crm-groups/refresh-cache') } catch { /* ignore */ }
  memberCache.clear()
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

.crm-fade-enter-active { transition: opacity 0.3s ease, transform 0.3s ease; }
.crm-fade-enter-from { opacity: 0; transform: translateY(8px); }

.crm-skeleton {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.crm-skeleton__stats {
  display: flex;
  gap: 24px;
  padding: 14px 18px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}
.crm-skeleton__stat {
  width: 60px;
  height: 40px;
  border-radius: 6px;
  background: linear-gradient(90deg, var(--border-color) 25%, transparent 50%, var(--border-color) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.crm-skeleton__row {
  height: 48px;
  border-radius: 8px;
  background: linear-gradient(90deg, var(--border-color) 25%, transparent 50%, var(--border-color) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
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
.crm-stats-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
  align-items: center;
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

.lb-trigger-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: linear-gradient(135deg, #FFD700 0%, #FFA000 100%);
  color: #5D4037;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}
.lb-trigger-btn:hover {
  box-shadow: 0 2px 8px rgba(255, 193, 7, 0.4);
  transform: translateY(-1px);
}
.lb-trigger-btn svg {
  width: 16px;
  height: 16px;
}

/* 搜索栏 */
.crm-search-bar {
  margin-bottom: 16px;
  position: relative;
}
.crm-search-bar :deep(.el-input__wrapper) {
  border-radius: 10px;
}
.crm-search-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 8px;
}
.crm-search-hint strong {
  color: var(--primary-color);
}
.group-tag {
  font-size: 13px;
  color: var(--text-muted);
}
.m-card--user { cursor: default; }

.crm-pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
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
:global(html.dark) .lb-trigger-btn {
  background: linear-gradient(135deg, #B8860B 0%, #8B6914 100%);
  color: #FFF8E1;
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
  .crm-stats-actions { margin-left: 0; width: 100%; justify-content: center; }
}
</style>
