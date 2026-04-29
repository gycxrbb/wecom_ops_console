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
              <span class="stat-label"><el-icon class="stat-icon"><User /></el-icon>身高</span>
              <span class="stat-value"><strong>{{ basicPayload.height_cm }}</strong> cm</span>
            </div>
            <div class="stat-divider" v-if="basicPayload.height_cm && basicPayload.weight_kg"></div>
            <div class="crm-hero-stat" v-if="basicPayload.weight_kg">
              <span class="stat-label"><el-icon class="stat-icon"><ScaleToOriginal /></el-icon>体重</span>
              <span class="stat-value"><strong>{{ basicPayload.weight_kg }}</strong> kg</span>
            </div>
            <div class="stat-divider" v-if="basicPayload.weight_kg && basicPayload.bmi"></div>
            <div class="crm-hero-stat" v-if="basicPayload.bmi">
              <span class="stat-label"><el-icon class="stat-icon"><DataAnalysis /></el-icon>BMI</span>
              <span class="stat-value"><strong>{{ basicPayload.bmi }}</strong></span>
            </div>
            <div class="stat-divider" v-if="basicPayload.bmi && basicPayload.points !== undefined"></div>
            <div class="crm-hero-stat" v-if="basicPayload.points !== undefined">
              <span class="stat-label"><el-icon class="stat-icon"><Star /></el-icon>积分</span>
              <span class="stat-value"><strong>{{ basicPayload.points }}</strong></span>
            </div>
            <div class="stat-divider" v-if="basicPayload.points !== undefined && servicePayload.group_count"></div>
            <div class="crm-hero-stat" v-if="servicePayload.group_count">
              <span class="stat-label"><el-icon class="stat-icon"><UserFilled /></el-icon>群组</span>
              <span class="stat-value"><strong>{{ servicePayload.group_count }}</strong> 组</span>
            </div>
            <div class="stat-divider" v-if="selectedCustomer"></div>
            <div class="crm-hero-stat" v-if="selectedCustomer">
              <span class="stat-label"><el-icon class="stat-icon"><User /></el-icon>用户ID</span>
              <span class="stat-value"><strong>{{ selectedCustomer.id }}</strong></span>
            </div>
          </div>
        </section>

        <!-- Workbench: Unified grid layout -->
        <div class="crm-workbench">
          <!-- Safety Card (left, spans 2 rows) -->
          <ProfileCard title="安全档案" :card="safetyCard" variant="danger" class="crm-card--left">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #ef4444; background: rgba(239, 68, 68, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 5h14l-1.5 6H4.5L3 5zM5 11v5M15 11v5M3 11h14" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <!-- Safety Snapshot Picker -->
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
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('safety_profile')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- Health Summary Card (left, spans 2 rows) -->
            <ProfileCard title="健康摘要" :card="getCard('health_summary_7d')" class="crm-card--left">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #10b981; background: rgba(16, 185, 129, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 13l4-4 3 3 5-6" stroke-linecap="round" stroke-linejoin="round"/><rect x="3" y="3" width="14" height="14" rx="2"/></svg>
                </span>
              </template>
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
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('health_summary_7d')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- Points & Engagement -->
            <ProfileCard title="积分活跃" :card="getCard('points_engagement_14d')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #f59e0b; background: rgba(245, 158, 11, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10 2l2.35 5.36L18 8.27l-4.12 3.77L15 18l-5-2.73L5 18l1.12-5.96L2 8.27l5.65-.91L10 2z"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <div class="crm-module-grid">
                  <div class="crm-module-stat" v-if="payload.points_current !== undefined">
                    <span class="crm-module-stat__label">当前积分</span>
                    <span class="crm-module-stat__value">{{ payload.points_current }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.points_total !== undefined">
                    <span class="crm-module-stat__label">累计积分</span>
                    <span class="crm-module-stat__value">{{ payload.points_total }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.active_days_14d !== undefined">
                    <span class="crm-module-stat__label">14天活跃</span>
                    <span class="crm-module-stat__value">{{ payload.active_days_14d }} 天</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.earned_14d !== undefined">
                    <span class="crm-module-stat__label">近期获得</span>
                    <span class="crm-module-stat__value">{{ payload.earned_14d }} 积分</span>
                  </div>
                </div>
                <div v-if="payload.summary" class="crm-module-summary">{{ payload.summary }}</div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('points_engagement_14d')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- Goals & Preferences -->
            <ProfileCard title="目标与偏好" :card="getCard('goals_preferences')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #8b5cf6; background: rgba(139, 92, 246, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="8"/><circle cx="10" cy="10" r="5"/><circle cx="10" cy="10" r="2" fill="currentColor" stroke="none"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <div class="crm-module-grid">
                  <div class="crm-module-stat" v-if="payload.primary_goals">
                    <span class="crm-module-stat__label">主要目标</span>
                    <span class="crm-module-stat__value">{{ payload.primary_goals }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.target_weight_kg">
                    <span class="crm-module-stat__label">目标体重</span>
                    <span class="crm-module-stat__value">{{ payload.target_weight_kg }} kg</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.diet">
                    <span class="crm-module-stat__label">饮食偏好</span>
                    <span class="crm-module-stat__value">{{ payload.diet }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.exercise">
                    <span class="crm-module-stat__label">运动偏好</span>
                    <span class="crm-module-stat__value">{{ payload.exercise }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.sleep">
                    <span class="crm-module-stat__label">睡眠质量</span>
                    <span class="crm-module-stat__value">{{ payload.sleep }}</span>
                  </div>
                </div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('goals_preferences')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- Service Scope -->
            <ProfileCard title="服务关系" :card="getCard('service_scope')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #3b82f6; background: rgba(59, 130, 246, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="7" cy="7" r="3"/><path d="M1 19v-2a4 4 0 014-4h4a4 4 0 014 4v2"/><circle cx="15" cy="7" r="2.5"/><path d="M15 13h1a3 3 0 013 3v1"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <div class="crm-module-grid">
                  <div class="crm-module-stat" v-if="payload.group_names">
                    <span class="crm-module-stat__label">所属群</span>
                    <span class="crm-module-stat__value">{{ payload.group_names }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.current_coach_names">
                    <span class="crm-module-stat__label">负责教练</span>
                    <span class="crm-module-stat__value">{{ payload.current_coach_names }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.group_count">
                    <span class="crm-module-stat__label">群组数</span>
                    <span class="crm-module-stat__value">{{ payload.group_count }} 组</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.staff_count">
                    <span class="crm-module-stat__label">教练数</span>
                    <span class="crm-module-stat__value">{{ payload.staff_count }} 人</span>
                  </div>
                </div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('service_scope')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- Body Composition Card -->
            <ProfileCard title="体成分" :card="getCard('body_comp_latest_30d')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #10b981; background: rgba(16, 185, 129, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10 3C10 3 5 8.5 5 12a5 5 0 0010 0c0-3.5-5-9-5-9z"/><path d="M10 8v5M8 11h4" stroke-linecap="round"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <BodyCompCard :payload="payload" />
              </template>
              <template #empty>
                <div class="crm-bodycomp-silhouette">
                  <svg viewBox="0 0 60 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="30" cy="10" r="8" fill="currentColor" />
                    <path d="M30 18 C20 18, 15 28, 15 38 L15 58 C15 60, 17 62, 19 62 L22 62 L22 82 C22 86, 25 88, 27 88 L27 88 C29 88, 30 86, 30 84 L30 62 L30 84 C30 86, 31 88, 33 88 L33 88 C35 88, 38 86, 38 82 L38 62 L41 62 C43 62, 45 60, 45 58 L45 38 C45 28, 40 18, 30 18Z" fill="currentColor" />
                  </svg>
                  <span style="font-size: 13px;">暂无体成分数据</span>
                </div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('body_comp_latest_30d')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>
        </div>

        <!-- Insights Section: 5 new behavioral modules -->
        <div class="crm-insights">
          <div class="crm-insights__grid">
            <!-- Habit Adherence -->
            <ProfileCard title="习惯执行" :card="getCard('habit_adherence_14d')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #10b981; background: rgba(16, 185, 129, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="8"/><path d="M6.5 10l2.5 2.5 5-5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <div class="crm-module-grid">
                  <div class="crm-module-stat" v-if="payload.active_habits_count !== undefined">
                    <span class="crm-module-stat__label">活跃习惯</span>
                    <span class="crm-module-stat__value">{{ payload.active_habits_count }} 个</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.avg_checkin_completion_rate_14d">
                    <span class="crm-module-stat__label">14天打卡率</span>
                    <span class="crm-module-stat__value">{{ payload.avg_checkin_completion_rate_14d }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.failed_checkin_days_14d !== undefined">
                    <span class="crm-module-stat__label">未打卡</span>
                    <span class="crm-module-stat__value">{{ payload.failed_checkin_days_14d }} 天</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.current_streak_max !== undefined">
                    <span class="crm-module-stat__label">最大连续</span>
                    <span class="crm-module-stat__value">{{ payload.current_streak_max }} 天</span>
                  </div>
                </div>
                <div v-if="payload.top_obstacles?.length" style="margin-top: 10px;">
                  <div class="crm-module-section">主要障碍</div>
                  <el-tag v-for="o in payload.top_obstacles" :key="o" size="small" type="warning" round
                    style="margin: 2px 4px 2px 0;">{{ o }}</el-tag>
                </div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('habit_adherence_14d')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- Plan Progress -->
            <ProfileCard title="计划推进" :card="getCard('plan_progress_14d')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #3b82f6; background: rgba(59, 130, 246, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="16" height="14" rx="2"/><path d="M2 9h16"/><path d="M6 2v4M14 2v4"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <!-- Plan title + status -->
                <div v-if="payload.current_plan_title" style="margin-bottom: 10px;">
                  <div style="font-size: 14px; font-weight: 600; color: var(--text-primary);">{{ payload.current_plan_title }}</div>
                  <span v-if="payload.current_plan_status === '进行中'" class="crm-module-status crm-module-status--active" style="margin-top: 4px;">进行中</span>
                  <span v-else-if="payload.current_plan_status === '已完成'" class="crm-module-status crm-module-status--completed" style="margin-top: 4px;">已完成</span>
                  <span v-else-if="payload.current_plan_status" class="crm-module-status crm-module-status--none" style="margin-top: 4px;">{{ payload.current_plan_status }}</span>
                </div>
                <!-- Progress bar -->
                <div v-if="parsePlanProgress(payload.plan_day_progress) !== null" style="margin-bottom: 12px;">
                  <div class="crm-module-progress-info">
                    <span>{{ payload.plan_day_progress }}</span>
                    <span>{{ parsePlanProgress(payload.plan_day_progress) }}%</span>
                  </div>
                  <div class="crm-module-progress">
                    <div class="crm-module-progress__fill" :style="{ width: parsePlanProgress(payload.plan_day_progress) + '%' }" />
                  </div>
                </div>
                <div class="crm-module-grid">
                  <div class="crm-module-stat" v-if="payload.todo_completion_rate_14d">
                    <span class="crm-module-stat__label">待办完成率</span>
                    <span class="crm-module-stat__value">{{ payload.todo_completion_rate_14d }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.overdue_todo_count > 0">
                    <span class="crm-module-stat__label">逾期待办</span>
                    <span class="crm-module-stat__value crm-module-stat__value--danger">{{ payload.overdue_todo_count }} 项</span>
                  </div>
                </div>
                <div v-if="payload.pause_resume_events" class="crm-module-summary">{{ payload.pause_resume_events }}</div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('plan_progress_14d')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- Reminder Adherence -->
            <ProfileCard title="提醒依从" :card="getCard('reminder_adherence_14d')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #f97316; background: rgba(249, 115, 22, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M10 2a5 5 0 015 5c0 5 2 7 2 7H3s2-2 2-7a5 5 0 015-5z"/><path d="M8 17a2 2 0 004 0"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <div class="crm-module-grid">
                  <div class="crm-module-stat" v-if="payload.active_reminder_count !== undefined">
                    <span class="crm-module-stat__label">活跃提醒</span>
                    <span class="crm-module-stat__value">{{ payload.active_reminder_count }} 个</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.estimated_follow_through_rate">
                    <span class="crm-module-stat__label">估算执行率</span>
                    <span class="crm-module-stat__value">{{ payload.estimated_follow_through_rate }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.trigger_count_total !== undefined">
                    <span class="crm-module-stat__label">总触发</span>
                    <span class="crm-module-stat__value">{{ payload.trigger_count_total }} 次</span>
                  </div>
                </div>
                <div v-if="payload.reminders_by_business_type?.length" style="margin-top: 10px;">
                  <div class="crm-module-section">按类型分布</div>
                  <div class="crm-reminder-types">
                    <div v-for="rt in payload.reminders_by_business_type" :key="rt.type" class="crm-reminder-type-row">
                      <span class="crm-reminder-type-name">{{ rt.type }}</span>
                      <span class="crm-reminder-type-count">{{ rt.count }}个 · {{ rt.triggers }}次</span>
                    </div>
                  </div>
                </div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('reminder_adherence_14d')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- Learning Engagement -->
            <ProfileCard title="学习吸收" :card="getCard('learning_engagement_30d')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #6366f1; background: rgba(99, 102, 241, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M2 3h6a2 2 0 012 2v12a1.5 1.5 0 00-1.5-1.5H2V3z"/><path d="M18 3h-6a2 2 0 00-2 2v12a1.5 1.5 0 011.5-1.5H18V3z"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <div class="crm-module-grid">
                  <div class="crm-module-stat" v-if="payload.course_total_assigned !== undefined">
                    <span class="crm-module-stat__label">分配课程</span>
                    <span class="crm-module-stat__value">{{ payload.course_total_assigned }} 门</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.course_in_progress !== undefined">
                    <span class="crm-module-stat__label">学习中</span>
                    <span class="crm-module-stat__value">{{ payload.course_in_progress }} 门</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.course_completed !== undefined">
                    <span class="crm-module-stat__label">已完成</span>
                    <span class="crm-module-stat__value">{{ payload.course_completed }} 门</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.completion_rate">
                    <span class="crm-module-stat__label">完成率</span>
                    <span class="crm-module-stat__value">{{ payload.completion_rate }}</span>
                  </div>
                  <div class="crm-module-stat" v-if="payload.study_minutes_30d !== undefined">
                    <span class="crm-module-stat__label">30天学习</span>
                    <span class="crm-module-stat__value">{{ payload.study_minutes_30d }} 分钟</span>
                  </div>
                </div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('learning_engagement_30d')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- AI Decision Labels -->
            <ProfileCard title="AI决策标签" :card="getCard('ai_decision_labels')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #8b5cf6; background: rgba(139, 92, 246, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 4.5A1.5 1.5 0 014.5 3H12l5 5-7 7-5-5V4.5z"/><circle cx="7" cy="7" r="1.5" fill="currentColor" stroke="none"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <div v-if="payload.label_summary" class="crm-module-summary" style="margin-top: 0; margin-bottom: 10px;">{{ payload.label_summary }}</div>
                <div v-if="payload.labels?.length" class="crm-labels-grid">
                  <div v-for="lb in payload.labels" :key="lb.key" class="crm-label-chip">
                    <span class="crm-label-name">{{ lb.name_cn }}</span>
                    <span class="crm-label-weight">{{ Math.round(lb.weight * 100) }}%</span>
                  </div>
                </div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('ai_decision_labels')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>

            <!-- Service Issues (用户阻碍) -->
            <ProfileCard title="用户阻碍" :card="getCard('service_issues')">
              <template #title-icon>
                <span class="crm-card-icon" style="color: #ef4444; background: rgba(239, 68, 68, 0.10);">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="8"/><path d="M10 6v4M10 13.5v.5"/></svg>
                </span>
              </template>
              <template #default="{ payload }">
                <div v-if="payload.issue_summary" class="crm-module-summary" style="margin-top: 0; margin-bottom: 10px;">{{ payload.issue_summary }}</div>
                <div v-if="payload.issues?.length" class="crm-issues-list">
                  <div v-for="issue in payload.issues" :key="issue.id" class="crm-issue-row">
                    <div class="crm-issue-header">
                      <span class="crm-issue-status-tag" :class="issue.status === 1 ? 'crm-issue-status-tag--resolved' : 'crm-issue-status-tag--open'">{{ issue.status_text }}</span>
                      <span class="crm-issue-date">{{ issue.created_at }}</span>
                    </div>
                    <div v-if="issue.description" class="crm-issue-desc">{{ issue.description }}</div>
                    <div v-if="issue.status === 1 && issue.solution" class="crm-issue-solution">
                      <span class="crm-issue-solution-label">解决方案:</span> {{ issue.solution }}
                    </div>
                  </div>
                </div>
              </template>
              <template #footer>
                <span class="crm-footer-link" @click="openModuleDetail('service_issues')">
                  查看详情
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 5l5 5-5 5"/></svg>
                </span>
              </template>
            </ProfileCard>
          </div>
        </div>
      </template>

      <!-- Profile load failed -->
      <el-empty v-else description="客户档案加载失败" :image-size="48" />

      <!-- Floating AI Coach Button -->
      <div class="crm-ai-fab" @click="showAiDrawer = true" v-if="profile" :title="aiCoachEnabled ? 'AI 教练助手' : aiCoachReason">
        <el-icon :size="22"><ChatDotRound /></el-icon>
        <span class="crm-ai-fab__label">AI</span>
      </div>

      <!-- AI Coach Drawer -->
      <AiCoachPanel
        v-if="profile"
        v-model="showAiDrawer"
        :customer-id="selectedCustomer?.id ?? null"
        :used-modules="usedModules"
        :data-gaps="dataGaps"
        :disabled-reason="aiCoachReason"
        :health-window-days="currentWindowDays"
        :profile-cache-status="profileCacheStatus"
      />

      <ModuleDetailDialog
        v-model:visible="detailDialog.visible"
        :title="detailDialog.title"
        :payload="detailDialog.payload"
      />
    </template>
  </div>
</template>

<script lang="ts">
export default { name: 'CrmProfile' }
</script>

<script setup lang="ts">
import { ref, computed, onMounted, watch, reactive } from 'vue'
import { Search, ArrowLeft, Warning, ChatDotRound, User, ScaleToOriginal, DataAnalysis, Star, UserFilled } from '@element-plus/icons-vue'
import { useCrmProfile } from './composables/useCrmProfile'
import ProfileCard from './components/ProfileCard.vue'
import BodyCompCard from './components/BodyCompCard.vue'
import AiCoachPanel from './components/AiCoachPanel.vue'
import ModuleDetailDialog from './components/ModuleDetailDialog.vue'

const {
  loading, selectedCustomer, profile,
  selectCustomer, getCard, backToList, restoreFromUrl,
  genderText, calcAge,
  safetySnapshots, safetySnapshotLoading, loadSafetySnapshotDetail,
  currentWindowDays, healthLoading, switchHealthWindow,
  profileCacheStatus,
  // list
  listLoading, listItems, listTotal, listPage, listPageSize,
  filters, filterOptions,
  loadFilterOptions, loadList, resetFilters,
} = useCrmProfile()

const showAiDrawer = ref(false)
const showRx = ref(false)
const detailDialog = reactive({ visible: false, title: '', payload: {} as Record<string, any> })
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

const parsePlanProgress = (text: string | null | undefined): number | null => {
  if (!text) return null
  const m = text.match(/(\d+)\s*\/\s*(\d+)/)
  if (!m) return null
  const cur = parseInt(m[1], 10)
  const total = parseInt(m[2], 10)
  if (total <= 0) return null
  return Math.round((cur / total) * 100)
}

const MODULE_TITLES: Record<string, string> = {
  safety_profile: '安全档案详情',
  health_summary_7d: '健康摘要详情',
  points_engagement_14d: '积分活跃详情',
  goals_preferences: '目标与偏好详情',
  service_scope: '服务关系详情',
  body_comp_latest_30d: '体成分详情',
  habit_adherence_14d: '习惯执行详情',
  plan_progress_14d: '计划推进详情',
  reminder_adherence_14d: '提醒依从详情',
  learning_engagement_30d: '学习吸收详情',
  ai_decision_labels: 'AI决策标签详情',
  service_issues: '用户阻碍详情',
}

const openModuleDetail = (moduleKey: string) => {
  const card = moduleKey === 'safety_profile' ? safetyCard.value : getCard(moduleKey)
  if (!card) return
  detailDialog.title = MODULE_TITLES[moduleKey] || '详情'
  detailDialog.payload = card.payload || {}
  detailDialog.visible = true
}

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
    loadFilterOptions()
    loadList(1, true)
  }
})
</script>

<style scoped>
@import './styles/CrmProfile.css';
</style>
