<template>
  <div class="crm-leaderboard">
    <!-- CRM 不可用 -->
    <el-alert
      v-if="!loading && !available"
      title="CRM 数据库未配置或不可用"
      type="info"
      :closable="false"
      show-icon
    />

    <!-- 骨架屏 -->
    <div v-if="loading && !available" class="lb-skeleton">
      <div class="lb-skeleton__summary" />
      <div class="lb-skeleton__tabs" />
      <div v-for="i in 6" :key="i" class="lb-skeleton__row" />
    </div>

    <Transition name="lb-fade">
      <div v-if="available" class="lb-content">
        <!-- 统计摘要 -->
        <div v-if="globalStats" class="lb-summary">
          <span>{{ globalStats.total_customers }} 位客户</span>
          <span class="lb-summary__sep">|</span>
          <span>{{ globalStats.total_groups }} 个群组</span>
          <span class="lb-summary__sep">|</span>
          <span>累计总积分 {{ formatPoints(globalStats.total_points) }}</span>
          <span class="lb-summary__sep">|</span>
          <span>本周总积分 {{ formatPoints(globalStats.total_week_points ?? 0) }}</span>
          <span class="lb-summary__sep">|</span>
          <span>本月总积分 {{ formatPoints(globalStats.total_month_points ?? 0) }}</span>
        </div>

        <!-- Tab 切换 -->
        <div class="lb-tabs">
          <button
            class="lb-tab"
            :class="{ 'is-active': activeTab === 'individual' }"
            @click="switchTab('individual')"
          >个人榜单</button>
          <button
            class="lb-tab"
            :class="{ 'is-active': activeTab === 'group' }"
            @click="switchTab('group')"
          >群组榜单</button>
        </div>

        <!-- ===== 个人榜单 ===== -->
        <Transition name="lb-fade" mode="out-in">
          <div v-if="activeTab === 'individual'" key="individual">
            <!-- 移动端卡片 -->
            <div v-if="isMobile" v-loading="loading" class="m-card-list">
              <div v-for="item in list" :key="item.id" class="m-card" :class="rankClass(item.rank)">
                <div class="m-card__rank">
                  <MedalIcon v-if="item.rank <= 3" :rank="item.rank as 1|2|3" />
                  <span v-else class="rank-num">{{ item.rank }}</span>
                </div>
                <div class="m-card__body">
                  <div class="m-card__row">
                    <strong class="m-card__name">{{ item.name }}</strong>
                    <span class="m-card__points">{{ item.current_points ?? item.total_points }} 分</span>
                  </div>
                  <div class="m-card__meta">
                    <span v-if="item.group_names" class="m-card__groups">{{ item.group_names }}</span>
                    <span>本周 +{{ item.week_points ?? 0 }} / 本月 +{{ item.month_points ?? 0 }}</span>
                  </div>
                </div>
              </div>
              <el-empty v-if="!loading && !list.length" :image-size="48" description="暂无数据" />
            </div>

            <!-- 桌面端表格 -->
            <el-table v-else :data="list" v-loading="loading" style="width: 100%">
              <el-table-column label="排名" width="72" align="center">
                <template #default="{ row }">
                  <MedalIcon v-if="row.rank <= 3" :rank="row.rank as 1|2|3" />
                  <span v-else class="rank-badge">{{ row.rank }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="name" label="姓名" min-width="100" />
              <el-table-column prop="group_names" label="所属群组" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="group-tag">{{ row.group_names || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="当前积分" width="110" align="right">
                <template #default="{ row }">{{ row.current_points ?? row.points }}</template>
              </el-table-column>
              <el-table-column label="本周积分" width="110" align="right">
                <template #default="{ row }">
                  <strong>{{ row.week_points ?? 0 }}</strong>
                </template>
              </el-table-column>
              <el-table-column label="本月积分" width="110" align="right">
                <template #default="{ row }">{{ row.month_points ?? 0 }}</template>
              </el-table-column>
            </el-table>
          </div>

          <!-- ===== 群组榜单 ===== -->
          <div v-else key="group">
            <!-- 移动端卡片 -->
            <div v-if="isMobile" v-loading="loading" class="m-card-list">
              <div v-for="item in list" :key="item.id" class="m-card" :class="rankClass(item.rank)">
                <div class="m-card__rank">
                  <MedalIcon v-if="item.rank <= 3" :rank="item.rank as 1|2|3" />
                  <span v-else class="rank-num">{{ item.rank }}</span>
                </div>
                <div class="m-card__body">
                  <div class="m-card__row">
                    <strong class="m-card__name">{{ item.name }}</strong>
                    <el-tag size="small">{{ item.member_count }} 人</el-tag>
                  </div>
                  <div class="m-card__meta">
                    <span>当前 {{ formatPoints(item.current_points_sum ?? item.total_points_sum) }}</span>
                    <span>本周 +{{ item.week_points_sum ?? 0 }} / 本月 +{{ item.month_points_sum ?? 0 }}</span>
                  </div>
                </div>
              </div>
              <el-empty v-if="!loading && !list.length" :image-size="48" description="暂无数据" />
            </div>

            <!-- 桌面端表格 -->
            <el-table v-else :data="list" v-loading="loading" style="width: 100%">
              <el-table-column label="排名" width="72" align="center">
                <template #default="{ row }">
                  <MedalIcon v-if="row.rank <= 3" :rank="row.rank as 1|2|3" />
                  <span v-else class="rank-badge">{{ row.rank }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="name" label="群名称" min-width="140" />
              <el-table-column prop="member_count" label="成员数" width="100" align="center">
                <template #default="{ row }">
                  <el-tag size="small">{{ row.member_count }} 人</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="当前总积分" width="130" align="right">
                <template #default="{ row }">{{ formatPoints(row.current_points_sum ?? row.points_sum) }}</template>
              </el-table-column>
              <el-table-column label="本周积分" width="130" align="right">
                <template #default="{ row }">
                  <strong>{{ formatPoints(row.week_points_sum ?? 0) }}</strong>
                </template>
              </el-table-column>
              <el-table-column label="本月积分" width="110" align="right">
                <template #default="{ row }">{{ formatPoints(row.month_points_sum ?? 0) }}</template>
              </el-table-column>
            </el-table>
          </div>
        </Transition>

        <!-- 分页 -->
        <div v-if="total > pageSize" class="lb-pagination">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="fetchData"
          />
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import request from '@/utils/request'
import { useMobile } from '@/composables/useMobile'
import MedalIcon from '@/components/MedalIcon.vue'

const { isMobile } = useMobile()

const activeTab = ref<'individual' | 'group'>('individual')
const list = ref<any[]>([])
const loading = ref(false)
const available = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const globalStats = ref<any>(null)

const formatPoints = (v: number) => {
  if (v >= 10000) return (v / 10000).toFixed(1) + '万'
  return String(v)
}

const rankClass = (rank: number) => {
  if (rank <= 3) return `m-card--top${rank}`
  return ''
}

const switchTab = (tab: 'individual' | 'group') => {
  if (activeTab.value === tab) return
  activeTab.value = tab
  page.value = 1
  fetchData()
}

const fetchData = async () => {
  loading.value = true
  try {
    const endpoint = activeTab.value === 'individual'
      ? '/v1/crm-groups/leaderboard/individual'
      : '/v1/crm-groups/leaderboard/group'
    const res: any = await request.get(endpoint, {
      params: { page: page.value, page_size: pageSize }
    })
    available.value = res.available ?? false
    list.value = res.list || []
    const p = res.pagination
    if (p) total.value = p.total
  } catch {
    available.value = false
    list.value = []
  } finally {
    loading.value = false
  }
}

const fetchGlobalStats = async () => {
  try {
    globalStats.value = await request.get('/v1/crm-groups/stats')
  } catch {
    globalStats.value = null
  }
}

onMounted(() => {
  fetchData()
  fetchGlobalStats()
})
</script>

<style scoped>
.crm-leaderboard {
  min-height: 200px;
}

.lb-fade-enter-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.lb-fade-enter-from { opacity: 0; transform: translateY(6px); }
.lb-fade-leave-active { transition: opacity 0.15s ease; }
.lb-fade-leave-to { opacity: 0; }

/* 骨架屏 */
.lb-skeleton {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lb-skeleton__summary {
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(90deg, var(--border-color) 25%, transparent 50%, var(--border-color) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.lb-skeleton__tabs {
  width: 200px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(90deg, var(--border-color) 25%, transparent 50%, var(--border-color) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.lb-skeleton__row {
  height: 44px;
  border-radius: 8px;
  background: linear-gradient(90deg, var(--border-color) 25%, transparent 50%, var(--border-color) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 统计摘要 */
.lb-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  margin-bottom: 14px;
  border-radius: 10px;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  font-size: 13px;
  color: var(--text-secondary);
}
.lb-summary__sep {
  color: var(--border-color);
}

/* Tab 切换 */
.lb-tabs {
  display: inline-flex;
  padding: 3px;
  margin-bottom: 16px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}
.lb-tab {
  appearance: none;
  border: none;
  padding: 7px 20px;
  border-radius: 7px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}
.lb-tab.is-active {
  background: rgba(34, 197, 94, 0.1);
  color: var(--primary-color);
  font-weight: 600;
}
.lb-tab:hover:not(.is-active) {
  color: var(--text-primary);
}

/* 排名徽章（非前三名） */
.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  background: var(--card-bg);
  border: 1px solid var(--border-color);
}

/* 群组标签 */
.group-tag {
  font-size: 13px;
  color: var(--text-muted);
}

/* 移动端卡片 */
.m-card-list { display: flex; flex-direction: column; gap: 10px; }
.m-card {
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--card-bg);
  transition: border-color 0.2s;
}
.m-card:hover { border-color: var(--primary-color); }

.m-card__rank {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  flex-shrink: 0;
}
.rank-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  background: var(--card-bg);
  border: 1px solid var(--border-color);
}

.m-card--top1 { border-left: 3px solid #FFD700; }
.m-card--top2 { border-left: 3px solid #C0C0C0; }
.m-card--top3 { border-left: 3px solid #CD7F32; }

.m-card__body { flex: 1; min-width: 0; }
.m-card__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.m-card__name { font-size: 14px; color: var(--text-primary); }
.m-card__points { font-size: 14px; font-weight: 600; color: var(--primary-color); }
.m-card__meta {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}
.m-card__groups {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 分页 */
.lb-pagination {
  display: flex;
  justify-content: center;
  margin-top: 18px;
}

/* 暗色模式 */
:global(html.dark) .lb-summary {
  background: #1d1e1f !important;
  border-color: #414243 !important;
}
:global(html.dark) .lb-tabs {
  background: #1d1e1f;
  border-color: #414243;
}
:global(html.dark) .rank-badge,
:global(html.dark) .rank-num {
  background: #2a2b2c;
  border-color: #414243;
}

@media (max-width: 768px) {
  .lb-summary {
    flex-wrap: wrap;
    gap: 6px;
    font-size: 12px;
  }
}
</style>
