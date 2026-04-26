<template>
  <div class="crm-profile-page">

    <!-- ==================== VIEW: Customer List ==================== -->
    <template v-if="!selectedCustomer">
      <!-- Filter Bar -->
      <div class="crm-filter-bar">
        <div class="crm-filter-bar__search">
          <el-input
            v-model="filters.q"
            placeholder="搜索客户姓名..."
            clearable
            @keyup.enter="onFilterSearch"
            @clear="onFilterSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
            <template #suffix>
              <span v-if="listLoading" class="crm-search-spinner" />
            </template>
          </el-input>
        </div>

        <el-select
          v-model="filters.coach_id"
          placeholder="教练/医生"
          clearable
          filterable
          style="width: 160px"
          @change="onFilterChange"
        >
          <el-option
            v-for="opt in filterOptions.coaches"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>

        <el-select
          v-model="filters.group_id"
          placeholder="所在群组"
          clearable
          filterable
          style="width: 160px"
          @change="onFilterChange"
        >
          <el-option
            v-for="opt in filterOptions.groups"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>

        <el-select
          v-model="filters.channel_id"
          placeholder="渠道来源"
          clearable
          filterable
          style="width: 160px"
          @change="onFilterChange"
        >
          <el-option
            v-for="opt in filterOptions.channels"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>

        <el-button @click="onResetFilters">重置</el-button>
      </div>

      <!-- Customer Table -->
      <el-table
        :data="listItems"
        v-loading="listLoading"
        stripe
        highlight-current-row
        style="width: 100%"
        @row-click="onRowClick"
        class="crm-customer-table"
      >
        <el-table-column label="姓名" min-width="100">
          <template #default="{ row }">
            <span class="crm-table-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="性别" width="70" align="center">
          <template #default="{ row }">{{ genderText(row.gender) }}</template>
        </el-table-column>
        <el-table-column label="年龄" width="70" align="center">
          <template #default="{ row }">
            {{ calcAge(row.birthday) !== null ? calcAge(row.birthday) + '岁' : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="负责教练" min-width="120">
          <template #default="{ row }">
            <span v-if="row.coach_names" class="crm-table-tag crm-table-tag--blue">{{ row.coach_names }}</span>
            <span v-else class="crm-table-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="所在群组" min-width="140">
          <template #default="{ row }">
            <span v-if="row.group_names" class="crm-table-tag">{{ row.group_names }}</span>
            <span v-else class="crm-table-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="渠道来源" min-width="100">
          <template #default="{ row }">
            <span v-if="row.channel_name" class="crm-table-tag crm-table-tag--green">{{ row.channel_name }}</span>
            <span v-else class="crm-table-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="积分" width="80" align="center" prop="points" />
        <el-table-column label="城市" width="90" align="center">
          <template #default="{ row }">{{ row.city || '-' }}</template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="crm-pagination">
        <el-pagination
          v-model:current-page="listPage"
          v-model:page-size="listPageSize"
          :total="listTotal"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
      </div>
    </template>

    <!-- ==================== VIEW: Profile Detail ==================== -->
    <template v-else>
      <!-- Back to list -->
      <div class="crm-back-bar">
        <el-button text @click="onBackToList">
          <el-icon><ArrowLeft /></el-icon>
          返回客户列表
        </el-button>
      </div>

      <!-- Loading -->
      <div v-if="loading" v-loading="true" style="min-height: 300px;" />

      <!-- Profile Content -->
      <template v-else-if="profile">
        <!-- Hero Section -->
        <section class="crm-hero">
          <div class="crm-hero__main">
            <div class="crm-identity">
              <div class="crm-avatar">{{ heroName }}</div>
              <div class="crm-identity-info">
                <h1>{{ basicPayload.display_name || '未知客户' }}</h1>
                <p class="crm-identity-subtitle">
                  <span class="text-gender">{{ basicPayload.gender || '未知' }}</span>
                  <template v-if="basicPayload.age"><span class="dot-divider">·</span><span class="text-age">{{ basicPayload.age }}岁</span></template>
                  <template v-if="basicPayload.crm_status"><span class="dot-divider">·</span><span class="text-status">{{ basicPayload.crm_status }}</span></template>
                </p>
                <div class="crm-hero-tags">
                  <span v-if="basicPayload.severity" class="crm-status-pill crm-status-pill--orange">{{ basicPayload.severity }}</span>
                  <span v-if="basicPayload.is_cgm" class="crm-status-pill">CGM 佩戴中</span>
                  <span v-if="servicePayload.current_coach_names" class="crm-status-pill crm-status-pill--blue">{{ servicePayload.current_coach_names }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="crm-hero__rail">
            <div class="crm-hero-stat" v-if="basicPayload.height_cm">
              <span class="stat-label">身高</span>
              <span class="stat-value"><strong>{{ basicPayload.height_cm }}</strong> cm</span>
            </div>
            <div class="stat-divider" v-if="basicPayload.height_cm && basicPayload.weight_kg"></div>
            <div class="crm-hero-stat" v-if="basicPayload.weight_kg">
              <span class="stat-label">体重</span>
              <span class="stat-value"><strong>{{ basicPayload.weight_kg }}</strong> kg</span>
            </div>
            <div class="stat-divider" v-if="basicPayload.weight_kg && basicPayload.bmi"></div>
            <div class="crm-hero-stat" v-if="basicPayload.bmi">
              <span class="stat-label">BMI</span>
              <span class="stat-value"><strong>{{ basicPayload.bmi }}</strong></span>
            </div>
            <div class="stat-divider" v-if="basicPayload.bmi && basicPayload.points !== undefined"></div>
            <div class="crm-hero-stat" v-if="basicPayload.points !== undefined">
              <span class="stat-label">积分</span>
              <span class="stat-value"><strong>{{ basicPayload.points }}</strong></span>
            </div>
            <div class="stat-divider" v-if="basicPayload.points !== undefined && servicePayload.group_count"></div>
            <div class="crm-hero-stat" v-if="servicePayload.group_count">
              <span class="stat-label">群组</span>
              <span class="stat-value"><strong>{{ servicePayload.group_count }}</strong> 组</span>
            </div>
          </div>
        </section>

        <!-- Workbench: Main + Sidebar -->
        <div class="crm-workbench">
          <!-- Main Column -->
          <div class="crm-column">
            <!-- Safety Card -->
            <ProfileCard title="安全档案" :card="safetyCard" variant="danger">
              <template #default="{ payload }">
                <!-- Safety Snapshot Picker — absolute top-right -->
                <div v-if="selectedCustomer && safetySnapshots.length" class="crm-safety-history-picker">
                  <span class="crm-safety-history-picker__label">档案日期</span>
                  <el-select
                    v-model="selectedSafetySnapshotId"
                    size="small"
                    class="crm-safety-history-picker__select"
                    :loading="safetySnapshotLoading || safetySnapshotDetailLoading"
                    :disabled="safetySnapshotLoading || safetySnapshotDetailLoading || !safetySnapshots.length"
                    @change="onSafetySnapshotChange"
                  >
                    <el-option
                      v-for="item in safetySnapshots"
                      :key="item.snapshot_id"
                      :label="item.display_label"
                      :value="item.snapshot_id"
                    />
                  </el-select>
                </div>
                <!-- Risk Level Badge -->
                <div v-if="payload.risk_level" class="crm-risk-badge" :class="`crm-risk-badge--${payload.risk_level}`">
                  <span class="crm-risk-dot" />
                  {{ payload.risk_level === 'high' ? '高风险' : payload.risk_level === 'medium' ? '中风险' : '低风险' }}
                </div>

                <div v-if="payload.snapshot?.reference_time" class="crm-safety-meta">
                  {{ payload.snapshot?.is_current ? '当前有效档案' : '历史档案' }}：
                  {{ payload.snapshot.reference_time }}
                </div>

                <!-- Health Conditions -->
                <div v-if="payload.health_condition_summary" class="crm-safety-section">
                  <div class="crm-safety-label">健康状况</div>
                  <div class="crm-safety-text">{{ payload.health_condition_summary }}</div>
                </div>

                <!-- Allergies — highlighted tags -->
                <div v-if="payload.allergies" class="crm-safety-section">
                  <div class="crm-safety-label">过敏信息</div>
                  <el-tag
                    v-for="(item, idx) in parseList(payload.allergies)"
                    :key="idx"
                    type="danger"
                    size="small"
                    round
                    class="crm-allergy-tag"
                  >{{ item }}</el-tag>
                </div>

                <!-- Sport Injuries -->
                <div v-if="payload.sport_injuries" class="crm-safety-section">
                  <div class="crm-safety-label">运动损伤</div>
                  <el-tag
                    v-for="(item, idx) in parseList(payload.sport_injuries)"
                    :key="idx"
                    type="warning"
                    size="small"
                    round
                    class="crm-allergy-tag"
                  >{{ item }}</el-tag>
                </div>

                <!-- Contraindications -->
                <div v-if="payload.contraindications" class="crm-safety-section">
                  <div class="crm-safety-label">禁忌与病史</div>
                  <div class="crm-safety-text">{{ payload.contraindications }}</div>
                </div>

                <!-- Prescription — collapsible -->
                <div v-if="payload.prescription_summary" class="crm-safety-section crm-safety-rx">
                  <div class="crm-safety-label" @click="toggleRx" style="cursor: pointer; user-select: none;">
                    处方摘要
                    <span class="crm-rx-toggle">{{ showRx ? '收起 ▲' : '展开 ▼' }}</span>
                  </div>
                  <el-collapse-transition>
                    <div v-show="showRx" class="crm-rx-body">
                      <div
                        v-for="(block, idx) in payload.prescription_summary.split('\n')"
                        :key="idx"
                        class="crm-rx-block"
                      >{{ block }}</div>
                    </div>
                  </el-collapse-transition>
                </div>

                <!-- Missing Fields Warning -->
                <div v-if="payload.missing_critical_fields?.length" class="crm-safety-warning">
                  缺失关键字段：{{ payload.missing_critical_fields.join('、') }}
                </div>
              </template>
            </ProfileCard>

            <!-- Health Summary Card -->
            <ProfileCard title="健康摘要" :card="getCard('health_summary_7d')">
              <template #header-extra>
                <el-radio-group
                  v-model="currentWindowDays"
                  size="small"
                  :disabled="healthLoading"
                  @change="(val: number) => selectedCustomer && switchHealthWindow(selectedCustomer.id, val)"
                >
                  <el-radio-button :value="7">近7天</el-radio-button>
                  <el-radio-button :value="14">近14天</el-radio-button>
                  <el-radio-button :value="30">近30天</el-radio-button>
                </el-radio-group>
              </template>
              <template #default="{ payload }">
                <!-- Stale data hint (no recent records but historical data exists) -->
                <div v-if="payload.stale_hint" class="crm-health-stale">
                  <el-icon><Warning /></el-icon>
                  <span>{{ payload.stale_hint }}</span>
                </div>
                <div class="crm-health-meta">
                  <span>{{ healthCoverageText(payload) }}</span>
                  <el-tag v-if="isHealthCoverageLow(payload)" size="small" type="warning" round>覆盖不足</el-tag>
                </div>
                <div class="crm-health-grid">
                  <div class="crm-health-item" v-if="payload.weight">
                    <span>体重</span>
                    <strong>{{ payload.weight }} kg</strong>
                    <span v-if="payload.weight_trend" class="crm-health-trend">{{ payload.weight_trend }}</span>
                  </div>
                  <div class="crm-health-item" v-if="payload.blood_pressure">
                    <span>血压</span><strong>{{ payload.blood_pressure }}</strong>
                  </div>
                  <div class="crm-health-item" v-if="payload.glucose">
                    <span>血糖</span><strong>{{ payload.glucose }}</strong>
                  </div>
                  <div class="crm-health-item" v-if="payload.sleep">
                    <span>睡眠</span><strong>{{ payload.sleep }}</strong>
                  </div>
                  <div class="crm-health-item" v-if="payload.activity">
                    <span>运动</span><strong>{{ payload.activity }}</strong>
                  </div>
                  <div class="crm-health-item" v-if="payload.diet">
                    <span>饮食</span><strong>{{ payload.diet }}</strong>
                  </div>
                </div>
                <div v-if="payload.symptoms" style="margin-top: 10px;">
                  <el-tag type="warning" size="small" round>{{ payload.symptoms }}</el-tag>
                </div>

                <!-- Trend flags -->
                <div v-if="payload.trend_flags?.length" style="margin-top: 10px;">
                  <el-tag v-for="flag in payload.trend_flags" :key="flag" size="small" type="info" round
                          style="margin: 2px 4px 2px 0;">{{ flag }}</el-tag>
                </div>

                <!-- Water & meal summary -->
                <div v-if="payload.water_avg_ml || payload.meal_record_days" class="crm-health-grid" style="margin-top: 10px;">
                  <div class="crm-health-item" v-if="payload.water_avg_ml">
                    <span>日均饮水</span><strong>{{ Math.round(payload.water_avg_ml) }} ml</strong>
                  </div>
                  <div class="crm-health-item" v-if="payload.meal_record_days">
                    <span>饮食记录</span><strong>{{ payload.meal_record_days }} 天（完整 {{ payload.meal_complete_days || 0 }} 天）</strong>
                  </div>
                </div>

                <!-- Glucose highlights -->
                <div v-if="payload.glucose_highlights?.length" style="margin-top: 10px;">
                  <div class="crm-health-subtitle">血糖波动</div>
                  <div v-for="gh in payload.glucose_highlights" :key="gh.date" class="crm-health-highlight">
                    <span>{{ gh.date }}</span>
                    <span>峰值 {{ gh.peak }} mmol/L（{{ gh.peak_time || '--' }}）</span>
                    <span>波动 {{ gh.amplitude }} mmol/L</span>
                  </div>
                </div>

                <!-- Meal highlights (last 3 days) -->
                <div v-if="payload.meal_highlights?.length" style="margin-top: 10px;">
                  <div class="crm-health-subtitle">近期餐食</div>
                  <div v-for="mh in payload.meal_highlights" :key="mh.date" class="crm-health-highlight">
                    <span>{{ mh.date }}</span>
                    <span v-for="m in mh.meals" :key="m.type" class="crm-meal-tag">
                      {{ m.type === 'breakfast' ? '早' : m.type === 'lunch' ? '午' : m.type === 'dinner' ? '晚' : '加餐' }}
                      {{ m.name || '已记录' }}
                      <template v-if="m.kcal">（{{ Math.round(m.kcal) }} kcal）</template>
                    </span>
                  </div>
                </div>

                <!-- Data quality warning -->
                <div v-if="isHealthCoverageLow(payload)" class="crm-health-quality-note">
                  当前窗口内只有 {{ healthRecordDays(payload) }} 天健康记录；如果没有更早记录，切换到近14天/近30天时统计值会保持一致。
                </div>
                <div v-if="payload.data_quality?.missing_weight_days > 3" style="margin-top: 10px;">
                  <el-tag type="warning" size="small" round>
                    体重缺失 {{ payload.data_quality.missing_weight_days }} 天
                  </el-tag>
                </div>
              </template>
            </ProfileCard>

            <!-- Body Composition Card -->
            <ProfileCard title="体成分" :card="getCard('body_comp_latest_30d')">
              <template #default="{ payload }">
                <div v-if="payload.latest" class="crm-data-grid" style="margin-bottom: 10px;">
                  <div class="crm-data-item">
                    <span class="crm-data-label">最新数据</span>
                    <span class="crm-data-value">{{ payload.latest }}</span>
                  </div>
                </div>
                <div v-if="payload.trend" class="crm-data-grid">
                  <div class="crm-data-item">
                    <span class="crm-data-label">30天趋势</span>
                    <span class="crm-data-value">{{ payload.trend }}</span>
                  </div>
                </div>
              </template>
            </ProfileCard>
          </div>

          <!-- Sidebar Column -->
          <div class="crm-column crm-column--side">
            <section class="crm-card crm-ai-card">
              <div class="crm-card__header">
                <div class="crm-card__header-left">
                  <span class="crm-card-kicker">AI</span>
                  <h3 class="crm-card__title">AI 教练助手</h3>
                </div>
                <el-tag v-if="aiCoachEnabled" type="success" size="small" round>可用</el-tag>
                <el-tag v-else type="info" size="small" round>暂不可用</el-tag>
              </div>

              <p class="crm-ai-card__summary">
                {{ aiCoachEnabled ? '可以基于当前客户档案提问，生成教练可复核的建议草稿。' : (aiCoachReason || '当前客户暂时无法使用 AI 对话。') }}
              </p>

              <div class="crm-ai-card__actions">
                <el-button
                  type="primary"
                  :disabled="!aiCoachEnabled"
                  @click="showAiDrawer = true"
                >
                  {{ aiCoachEnabled ? '开始 AI 对话' : '当前不可发起' }}
                </el-button>
              </div>

              <div class="crm-ai-card__tips">
                <span>支持提问：</span>
                <span>总结服务重点、列出跟进问题、生成交接备注</span>
              </div>
            </section>

            <!-- Goals & Preferences -->
            <ProfileCard title="目标与偏好" :card="getCard('goals_preferences')">
              <template #default="{ payload }">
                <div class="crm-data-grid" style="grid-template-columns: 1fr;">
                  <div class="crm-data-item" v-if="payload.primary_goals">
                    <span class="crm-data-label">主要目标</span>
                    <span class="crm-data-value">{{ payload.primary_goals }}</span>
                  </div>
                  <div class="crm-data-item" v-if="payload.target_weight_kg">
                    <span class="crm-data-label">目标体重</span>
                    <span class="crm-data-value">{{ payload.target_weight_kg }} kg</span>
                  </div>
                  <div class="crm-data-item" v-if="payload.diet">
                    <span class="crm-data-label">饮食偏好</span>
                    <span class="crm-data-value">{{ payload.diet }}</span>
                  </div>
                  <div class="crm-data-item" v-if="payload.exercise">
                    <span class="crm-data-label">运动偏好</span>
                    <span class="crm-data-value">{{ payload.exercise }}</span>
                  </div>
                  <div class="crm-data-item" v-if="payload.sleep">
                    <span class="crm-data-label">睡眠质量</span>
                    <span class="crm-data-value">{{ payload.sleep }}</span>
                  </div>
                </div>
              </template>
            </ProfileCard>

            <!-- Points & Engagement -->
            <ProfileCard title="积分活跃" :card="getCard('points_engagement_14d')">
              <template #default="{ payload }">
                <div class="crm-health-grid">
                  <div class="crm-health-item" v-if="payload.points_current !== undefined">
                    <span>当前积分</span><strong>{{ payload.points_current }}</strong>
                  </div>
                  <div class="crm-health-item" v-if="payload.points_total !== undefined">
                    <span>累计积分</span><strong>{{ payload.points_total }}</strong>
                  </div>
                  <div class="crm-health-item" v-if="payload.active_days_14d !== undefined">
                    <span>14天活跃</span><strong>{{ payload.active_days_14d }} 天</strong>
                  </div>
                </div>
                <div v-if="payload.summary" style="margin-top: 10px; font-size: 13px; color: var(--text-secondary);">
                  {{ payload.summary }}
                </div>
              </template>
            </ProfileCard>

            <!-- Service Scope -->
            <ProfileCard title="服务关系" :card="getCard('service_scope')">
              <template #default="{ payload }">
                <div class="crm-data-grid" style="grid-template-columns: 1fr;">
                  <div class="crm-data-item" v-if="payload.group_names">
                    <span class="crm-data-label">所属群</span>
                    <span class="crm-data-value">{{ payload.group_names }}</span>
                  </div>
                  <div class="crm-data-item" v-if="payload.current_coach_names">
                    <span class="crm-data-label">负责教练</span>
                    <span class="crm-data-value">{{ payload.current_coach_names }}</span>
                  </div>
                </div>
              </template>
            </ProfileCard>
          </div>
        </div>
      </template>

      <!-- Profile load failed -->
      <el-empty v-else description="客户档案加载失败" :image-size="48" />

      <!-- AI Coach Drawer -->
      <AiCoachPanel
        v-if="profile"
        v-model="showAiDrawer"
        :customer-id="selectedCustomer?.id ?? null"
        :used-modules="usedModules"
        :data-gaps="dataGaps"
        :disabled-reason="aiCoachReason"
      />
    </template>

  </div>
</template>

<script lang="ts">
export default { name: 'CrmProfile' }
</script>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Search, ArrowLeft, Warning } from '@element-plus/icons-vue'
import { useCrmProfile } from './composables/useCrmProfile'
import ProfileCard from './components/ProfileCard.vue'
import AiCoachPanel from './components/AiCoachPanel.vue'

const {
  loading, selectedCustomer, profile,
  selectCustomer, getCard, backToList, restoreFromUrl,
  genderText, calcAge,
  safetySnapshots, safetySnapshotLoading, loadSafetySnapshotDetail,
  currentWindowDays, healthLoading, switchHealthWindow,
  // list
  listLoading, listItems, listTotal, listPage, listPageSize,
  filters, filterOptions,
  loadFilterOptions, loadList, resetFilters,
} = useCrmProfile()

const showAiDrawer = ref(false)
const showRx = ref(false)
const selectedSafetySnapshotId = ref<number | null>(null)
const safetySnapshotDetailLoading = ref(false)
const safetyCardOverride = ref<any | null>(null)
const aiCoachEnabled = computed(() => profile.value?.ai_chat_enabled ?? false)
const aiCoachReason = computed(() => profile.value?.ai_chat_reason ?? '')

let searchTimer: ReturnType<typeof setTimeout> | null = null

const onFilterSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    loadList(1)
  }, 300)
}

const onFilterChange = () => {
  loadList(1)
}

const onResetFilters = () => {
  resetFilters()
}

const onPageChange = (page: number) => {
  loadList(page)
}

const onPageSizeChange = (size: number) => {
  listPageSize.value = size
  loadList(1)
}

const onRowClick = (row: any) => {
  selectCustomer(row)
}

const onBackToList = () => {
  backToList()
}

const basicPayload = computed(() => getCard('basic_profile')?.payload || {})
const servicePayload = computed(() => getCard('service_scope')?.payload || {})
const safetyCard = computed(() => safetyCardOverride.value || getCard('safety_profile'))

const healthWindowDays = (payload: any) =>
  Number(payload?.window_days || payload?.data_quality?.expected_days || currentWindowDays.value || 7)

const healthRecordDays = (payload: any) =>
  Number(payload?.days ?? payload?.data_quality?.total_record_days ?? 0)

const healthCoverageText = (payload: any) => {
  const windowDays = healthWindowDays(payload)
  const recordDays = healthRecordDays(payload)
  return `近 ${windowDays} 天内共 ${recordDays} 天记录`
}

const isHealthCoverageLow = (payload: any) => {
  const windowDays = healthWindowDays(payload)
  const recordDays = healthRecordDays(payload)
  return windowDays > 0 && recordDays > 0 && recordDays < windowDays
}

const heroName = computed(() => {
  const name = basicPayload.value.display_name || ''
  return name ? name.charAt(0) : '?'
})

const usedModules = computed(() =>
  (profile.value?.cards || []).filter(c => c.status === 'ok').map(c => c.key)
)

const dataGaps = computed(() => {
  const gaps: string[] = []
  for (const card of profile.value?.cards || []) {
    if (card.status === 'empty') gaps.push(`${card.key} 无数据`)
    for (const w of card.warnings || []) gaps.push(w)
  }
  return gaps
})

const toggleRx = () => { showRx.value = !showRx.value }

const getCurrentSafetySnapshotId = () => {
  const rawId = getCard('safety_profile')?.payload?.snapshot?.snapshot_id
  return typeof rawId === 'number' ? rawId : null
}

const onSafetySnapshotChange = async (snapshotId: number) => {
  if (!selectedCustomer.value) return
  const currentSnapshotId = getCurrentSafetySnapshotId()
  showRx.value = false

  if (!snapshotId || snapshotId === currentSnapshotId) {
    safetyCardOverride.value = null
    selectedSafetySnapshotId.value = currentSnapshotId
    return
  }

  safetySnapshotDetailLoading.value = true
  try {
    safetyCardOverride.value = await loadSafetySnapshotDetail(selectedCustomer.value.id, snapshotId)
  } catch {
    safetyCardOverride.value = null
    selectedSafetySnapshotId.value = currentSnapshotId
  } finally {
    safetySnapshotDetailLoading.value = false
  }
}

const parseList = (text: string): string[] => {
  if (!text) return []
  return text.split(/[；;、,，]/).map(s => s.trim()).filter(Boolean)
}

watch(
  () => profile.value?.customer_id,
  () => {
    safetyCardOverride.value = null
    showRx.value = false
    selectedSafetySnapshotId.value = getCurrentSafetySnapshotId()
  },
  { immediate: true }
)

watch(
  () => safetySnapshots.value,
  (items) => {
    if (!items.length) {
      selectedSafetySnapshotId.value = null
      return
    }
    if (!items.some(item => item.snapshot_id === selectedSafetySnapshotId.value)) {
      const current = items.find(item => item.is_current) || items[0]
      selectedSafetySnapshotId.value = current?.snapshot_id ?? null
    }
  },
  { immediate: true }
)

onMounted(async () => {
  await restoreFromUrl()
  if (!selectedCustomer.value) {
    loadList(1, true)
  }
})
</script>

<style scoped>
@import './styles/CrmProfile.css';
</style>
