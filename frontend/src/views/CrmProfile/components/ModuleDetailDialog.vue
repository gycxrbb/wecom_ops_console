<template>
  <el-dialog v-model="dialogVisible" :title="title" width="560" append-to-body destroy-on-close>
    <div class="mod-detail">
      <div v-for="row in simpleRows" :key="row.key" class="mod-detail__row">
        <span class="mod-detail__label">{{ row.label }}</span>
        <span class="mod-detail__value">{{ row.value }}</span>
      </div>

      <!-- Body comp metrics -->
      <template v-if="payload.metrics">
        <div class="mod-detail__section">最新指标</div>
        <div class="mod-detail__grid">
          <div v-for="(m, key) in payload.metrics" :key="key" class="mod-detail__grid-item">
            <span class="mod-detail__grid-label">{{ METRIC_NAMES[key] || key }}</span>
            <span class="mod-detail__grid-value">{{ m.value ?? '—' }}{{ m.unit }}</span>
          </div>
        </div>
      </template>

      <!-- Trend metrics -->
      <template v-if="payload.trend_metrics && Object.keys(payload.trend_metrics).length">
        <div class="mod-detail__section">30天趋势</div>
        <div class="mod-detail__grid">
          <div v-for="(info, key) in payload.trend_metrics" :key="key" class="mod-detail__grid-item">
            <span class="mod-detail__grid-label">{{ METRIC_NAMES[key] || key }}</span>
            <span
              class="mod-detail__grid-value"
              :style="{ color: info.diff > 0 ? '#ef4444' : info.diff < 0 ? '#10b981' : 'inherit' }"
            >{{ info.diff > 0 ? '+' : '' }}{{ info.diff }}{{ info.unit }}</span>
          </div>
        </div>
      </template>

      <!-- Habit obstacles -->
      <template v-if="payload.top_obstacles?.length">
        <div class="mod-detail__section">主要障碍</div>
        <div class="mod-detail__tags">
          <el-tag v-for="o in payload.top_obstacles" :key="o" size="small" type="warning" round>{{ o }}</el-tag>
        </div>
      </template>

      <!-- Activity categories -->
      <template v-if="payload.activity_category_counts && Object.keys(payload.activity_category_counts).length">
        <div class="mod-detail__section">活动分类</div>
        <div v-for="(count, cat) in payload.activity_category_counts" :key="cat" class="mod-detail__row">
          <span class="mod-detail__label">{{ cat }}</span>
          <span class="mod-detail__value">{{ count }} 次</span>
        </div>
      </template>

      <!-- Recent earning events -->
      <template v-if="payload.latest_positive_events?.length">
        <div class="mod-detail__section">最近获得记录</div>
        <div v-for="ev in payload.latest_positive_events" :key="ev.date + ev.description" class="mod-detail__row">
          <span class="mod-detail__label">{{ ev.date }}</span>
          <span class="mod-detail__value">{{ ev.description }}（{{ ev.category }}）+{{ ev.num }}</span>
        </div>
      </template>

      <!-- Reminder type distribution -->
      <template v-if="payload.reminders_by_business_type?.length">
        <div class="mod-detail__section">按类型分布</div>
        <div v-for="rt in payload.reminders_by_business_type" :key="rt.type" class="mod-detail__row">
          <span class="mod-detail__label">{{ rt.type }}</span>
          <span class="mod-detail__value">{{ rt.count }} 个 · {{ rt.triggers }} 次</span>
        </div>
      </template>

      <!-- AI Labels -->
      <template v-if="payload.labels?.length">
        <div class="mod-detail__section">标签列表</div>
        <div class="mod-detail__labels">
          <div v-for="lb in payload.labels" :key="lb.key" class="mod-detail__label-chip">
            <span>{{ lb.name_cn }}</span>
            <strong>{{ Math.round(lb.weight * 100) }}%</strong>
          </div>
        </div>
      </template>

      <!-- Safety: risk level, conditions, allergies etc. -->
      <template v-if="payload.risk_level">
        <div class="mod-detail__section">风险评估</div>
        <div class="mod-detail__row">
          <span class="mod-detail__label">风险等级</span>
          <span class="mod-detail__value" :style="{ color: payload.risk_level === 'high' ? '#dc2626' : payload.risk_level === 'medium' ? '#d97706' : '#059669', fontWeight: 600 }">
            {{ payload.risk_level === 'high' ? '高风险' : payload.risk_level === 'medium' ? '中风险' : '低风险' }}
          </span>
        </div>
      </template>
      <template v-if="payload.health_condition_summary">
        <div class="mod-detail__section">健康状况</div>
        <div class="mod-detail__text">{{ payload.health_condition_summary }}</div>
      </template>
      <template v-if="payload.allergies">
        <div class="mod-detail__section">过敏信息</div>
        <div class="mod-detail__tags">
          <el-tag v-for="item in parseList(payload.allergies)" :key="item" type="danger" size="small" round>{{ item }}</el-tag>
        </div>
      </template>
      <template v-if="payload.sport_injuries">
        <div class="mod-detail__section">运动损伤</div>
        <div class="mod-detail__tags">
          <el-tag v-for="item in parseList(payload.sport_injuries)" :key="item" type="warning" size="small" round>{{ item }}</el-tag>
        </div>
      </template>
      <template v-if="payload.contraindications">
        <div class="mod-detail__section">禁忌与病史</div>
        <div class="mod-detail__text">{{ payload.contraindications }}</div>
      </template>
      <template v-if="payload.prescription_summary">
        <div class="mod-detail__section">处方摘要</div>
        <div class="mod-detail__text" style="white-space: pre-line;">{{ payload.prescription_summary }}</div>
      </template>
      <template v-if="payload.missing_critical_fields?.length">
        <div class="mod-detail__section">缺失字段</div>
        <div class="mod-detail__tags">
          <el-tag v-for="f in payload.missing_critical_fields" :key="f" type="info" size="small" round>{{ f }}</el-tag>
        </div>
      </template>

      <!-- Health: trend flags -->
      <template v-if="payload.trend_flags?.length">
        <div class="mod-detail__section">趋势标记</div>
        <div class="mod-detail__tags">
          <el-tag v-for="flag in payload.trend_flags" :key="flag" size="small" type="info" round>{{ flag }}</el-tag>
        </div>
      </template>
      <!-- Health: glucose highlights -->
      <template v-if="payload.glucose_highlights?.length">
        <div class="mod-detail__section">血糖波动</div>
        <div v-for="gh in payload.glucose_highlights" :key="gh.date" class="mod-detail__row">
          <span class="mod-detail__label">{{ gh.date }}</span>
          <span class="mod-detail__value">峰值 {{ gh.peak }} mmol/L · 波动 {{ gh.amplitude }}</span>
        </div>
      </template>
      <!-- Health: meal highlights -->
      <template v-if="payload.meal_highlights?.length">
        <div class="mod-detail__section">近期餐食</div>
        <div v-for="mh in payload.meal_highlights" :key="mh.date" class="mod-detail__row">
          <span class="mod-detail__label">{{ mh.date }}</span>
          <span class="mod-detail__value">
            <template v-for="m in mh.meals" :key="m.type">{{ m.type === 'breakfast' ? '早' : m.type === 'lunch' ? '午' : m.type === 'dinner' ? '晚' : '加餐' }}{{ m.name || '已记录' }} </template>
          </span>
        </div>
      </template>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  visible: boolean
  title: string
  payload: Record<string, any>
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const METRIC_NAMES: Record<string, string> = {
  weight: '体重', bmi: 'BMI', body_fat: '体脂率', muscle: '肌肉量',
}

const FIELD_LABELS: Record<string, string> = {
  // Safety
  risk_level: '风险等级', medical_history: '病史', genetic_history: '遗传史',
  // Health
  days: '记录天数', window_days: '统计窗口', weight: '体重',
  weight_trend: '体重趋势', blood_pressure: '血压', glucose: '血糖',
  activity: '运动', symptoms: '症状',
  glucose_avg: '平均血糖', glucose_peak: '最高血糖', glucose_days: '血糖记录天数',
  glucose_high_days: '血糖偏高天数',
  meal_record_days: '饮食记录天数', meal_complete_days: '完整饮食天数',
  water_avg_ml: '日均饮水', water_on_target_days: '饮水达标天数',
  // Points
  points_current: '当前积分', points_total: '累计积分',
  earned_14d: '近14天获得', spent_14d: '近14天消费', active_days_14d: '14天活跃天数',
  // Goals
  primary_goals: '主要目标', target_weight_kg: '目标体重', target_heart_rate: '目标心率',
  target_glucose: '目标血糖', target_blood_pressure: '目标血压',
  diet: '饮食偏好', exercise: '运动偏好', sleep: '睡眠质量',
  // Service
  group_names: '所属群', group_count: '群组数', current_coach_names: '负责教练', staff_count: '教练数',
  // Body comp
  latest_date: '最新日期', body_score: '身体评分',
  // Habit
  active_habits_count: '活跃习惯数', avg_checkin_completion_rate_14d: '14天打卡率',
  failed_checkin_days_14d: '未打卡天数', current_streak_max: '最大连续天数',
  // Plan
  current_plan_title: '当前计划', current_plan_status: '计划状态',
  plan_day_progress: '进度', todo_completion_rate_14d: '待办完成率',
  overdue_todo_count: '逾期待办数', pause_resume_events: '暂停/恢复记录',
  // Reminder
  active_reminder_count: '活跃提醒数', estimated_follow_through_rate: '估算执行率',
  trigger_count_total: '总触发次数', last_triggered_at: '最近触发时间',
  // Learning
  course_total_assigned: '分配课程数', course_in_progress: '学习中',
  course_completed: '已完成', completion_rate: '完成率',
  study_minutes_30d: '30天学习时长', last_learning_at: '最近学习时间',
  // Labels
  label_count: '标签数量',
}

const SUFFIX_MAP: Record<string, string> = {
  points_current: ' 积分', points_total: ' 积分', earned_14d: ' 积分', spent_14d: ' 积分',
  active_days_14d: ' 天', group_count: ' 组', staff_count: ' 人', days: ' 天', body_score: ' 分',
  target_weight_kg: ' kg', active_habits_count: ' 个', failed_checkin_days_14d: ' 天',
  current_streak_max: ' 天', overdue_todo_count: ' 项', active_reminder_count: ' 个',
  trigger_count_total: ' 次', course_total_assigned: ' 门', course_in_progress: ' 门',
  course_completed: ' 门', study_minutes_30d: ' 分钟', label_count: ' 个',
  window_days: ' 天', weight: ' kg', water_avg_ml: ' ml', glucose_days: ' 天',
  glucose_high_days: ' 天', meal_record_days: ' 天', meal_complete_days: ' 天',
  water_on_target_days: ' 天',
}

const SKIP_KEYS = new Set([
  'summary', 'latest', 'trend', 'chart_data', 'metrics', 'trend_metrics',
  'label_summary', 'if_then_plan_summary',
  'top_obstacles', 'activity_category_counts', 'latest_positive_events',
  'reminders_by_business_type', 'labels',
  // Safety - rendered in dedicated sections
  'health_condition_summary', 'allergies', 'sport_injuries', 'contraindications',
  'prescription_summary', 'risk_level', 'missing_critical_fields', 'snapshot',
  'medical_history', 'genetic_history',
  // Health - rendered in dedicated sections
  'weight_trend', 'stale_hint', 'trend_flags', 'glucose_highlights', 'meal_highlights',
  'data_quality',
])

const parseList = (text: string): string[] => {
  if (!text) return []
  return text.split(/[；;、,，]/).map(s => s.trim()).filter(Boolean)
}

const simpleRows = computed(() => {
  if (!props.payload) return []
  return Object.entries(props.payload)
    .filter(([key, val]) => !SKIP_KEYS.has(key) && val != null && val !== '' && typeof val !== 'object')
    .map(([key, val]) => ({
      key,
      label: FIELD_LABELS[key] || key,
      value: String(val) + (SUFFIX_MAP[key] || ''),
    }))
})
</script>

<style scoped>
.mod-detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mod-detail__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--fill-color-light, #f8fafc);
}

.mod-detail__label {
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
  flex-shrink: 0;
}

.mod-detail__value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #111827);
  text-align: right;
  max-width: 60%;
  word-break: break-word;
}

.mod-detail__section {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary, #374151);
  margin-top: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}

.mod-detail__text {
  font-size: 14px;
  color: var(--text-primary, #111827);
  line-height: 1.6;
  padding: 6px 0;
}

.mod-detail__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mod-detail__grid-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--fill-color-light, #f8fafc);
}

.mod-detail__grid-label {
  font-size: 12px;
  color: var(--text-muted, #9ca3af);
}

.mod-detail__grid-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.mod-detail__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mod-detail__labels {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mod-detail__label-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.15);
  font-size: 13px;
  color: var(--text-primary);
}

.mod-detail__label-chip strong {
  color: #7c3aed;
}

:global(html.dark) .mod-detail__row,
:global(html.dark) .mod-detail__grid-item {
  background: rgba(255, 255, 255, 0.04);
}

:global(html.dark) .mod-detail__section {
  border-color: rgba(255, 255, 255, 0.08);
}

:global(html.dark) .mod-detail__label-chip {
  background: rgba(139, 92, 246, 0.15);
  border-color: rgba(139, 92, 246, 0.25);
}

:global(html.dark) .mod-detail__label-chip strong {
  color: #a78bfa;
}

/* ---- Mobile ---- */
@media (max-width: 600px) {
  .mod-detail__grid {
    grid-template-columns: 1fr;
  }
}
</style>
