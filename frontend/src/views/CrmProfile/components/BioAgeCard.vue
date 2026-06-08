<template>
  <div class="bioage">
    <!-- Header -->
    <div class="bioage__head">
      <div class="bioage__head-left">
        <span class="crm-card-icon" style="color: #6366f1; background: rgba(99, 102, 241, 0.10);">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M10 2a8 8 0 100 16 8 8 0 000-16z" />
            <path d="M10 6v4.5l3 2.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <span class="bioage__title">生物年龄</span>
        <el-tag v-if="result" :type="confidenceType" size="small" round>{{ confidenceLabel }}</el-tag>
      </div>
      <el-button
        type="primary"
        size="small"
        :loading="calculating"
        :disabled="calculating || !canCalculate"
        @click="onCalculate"
      >
        {{ calculating ? '测算中' : '测算' }}
      </el-button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="bioage__loading">
      <span class="bioage__loading-text">加载中...</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="bioage__msg bioage__msg--error">
      <el-icon :size="13"><Warning /></el-icon>
      {{ error }}
    </div>

    <!-- Has Result -->
    <div v-else-if="result" class="bioage__body">
      <!-- Left: Age Numbers -->
      <div class="bioage__left">
        <div class="bioage__age-item">
          <div class="bioage__age-label">
            生物年龄
            <span class="bioage__age-badge">{{ result.n_biomarkers }}/{{ result.total_biomarkers }}项</span>
          </div>
          <div class="bioage__age-num bioage__age-num--primary">
            {{ result.biological_age.toFixed(1) }}<small>岁</small>
          </div>
          <div v-if="historyData && historyData.history.length >= 2 && historyData.trend?.last_change != null"
               class="bioage__age-sub" :class="changeClass">
            {{ changeDirection }} 较上次{{ changeText }}
          </div>
        </div>
        <div class="bioage__age-divider" />
        <div class="bioage__age-item">
          <div class="bioage__age-label">实际年龄</div>
          <div class="bioage__age-num">{{ result.chronological_age.toFixed(1) }}<small>岁</small></div>
          <div class="bioage__age-sub" :class="deltaClass">
            老化{{ deltaLabel }} {{ Math.abs(result.age_acceleration).toFixed(1) }} 岁
          </div>
        </div>
      </div>

      <!-- Right: Dimension Bars -->
      <div v-if="dimensionBars.length" class="bioage__right">
        <div v-for="dim in dimensionBars" :key="dim.key" class="bioage__dim">
          <div class="bioage__dim-head">
            <span class="bioage__dim-name">{{ dim.label }}</span>
            <span class="bioage__dim-tag" :style="{ background: dim.color + '18', color: dim.color }">{{ dim.level }}</span>
          </div>
          <div class="bioage__dim-track">
            <div class="bioage__dim-bar" :style="{ width: dim.percent + '%', background: dim.color }" />
          </div>
        </div>
      </div>
    </div>

    <!-- Empty: No result yet -->
    <div v-else class="bioage__body">
      <div class="bioage__left">
        <div class="bioage__age-item">
          <div class="bioage__age-label">生物年龄</div>
          <div class="bioage__age-num bioage__age-num--muted">--<small>岁</small></div>
          <div class="bioage__age-sub bioage--muted">暂无数据</div>
        </div>
        <div class="bioage__age-divider" />
        <div class="bioage__age-item">
          <div class="bioage__age-label">实际年龄</div>
          <div class="bioage__age-num bioage__age-num--muted">--<small>岁</small></div>
        </div>
      </div>
      <div class="bioage__right bioage__right--empty">
        <template v-if="readiness && !readiness.can_calculate">
          <div class="bioage__empty-hint">数据尚不完备</div>
          <div class="bioage__missing">
            <span v-for="code in readiness.missing" :key="code" class="bioage__missing-tag">{{ biomarkerLabel(code) }}</span>
          </div>
          <div class="bioage__ready-bar">
            <div class="bioage__ready-fill" :style="{ width: (readiness.n_available / readiness.total * 100) + '%' }" />
          </div>
          <div class="bioage__ready-text">{{ readiness.n_available }}/{{ readiness.total }} 项已就绪</div>
        </template>
        <template v-else-if="readiness?.can_calculate">
          <div class="bioage__empty-hint">数据已就绪</div>
          <div class="bioage__ready-text">点击「测算」获取生物年龄分析</div>
        </template>
        <template v-else>
          <div class="bioage__empty-hint">等待数据加载</div>
        </template>
      </div>
    </div>

    <!-- Footer: AI Reading + Actions -->
    <template v-if="result">
      <div v-if="result.llm_reading" class="bioage__ai">
        <div class="bioage__ai-text">{{ result.llm_reading }}</div>
      </div>
      <div v-if="result.llm_actions?.length" class="bioage__actions">
        <div v-for="(action, idx) in result.llm_actions" :key="idx" class="bioage__action">
          <span class="bioage__action-dot" :style="{ background: actionColor(idx) }" />
          {{ action }}
        </div>
      </div>
      <div v-if="result.created_at" class="bioage__ts">{{ result.created_at }}</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { Warning } from '@element-plus/icons-vue'
import { useBioAge } from '../composables/useBioAge'

const props = defineProps<{ customerId: number | null }>()

const {
  result, readiness, history: historyData,
  loading, calculating, error,
  loadAll, calculate,
} = useBioAge()

watch(() => props.customerId, (id) => { if (id) loadAll(id) }, { immediate: true })

const canCalculate = computed(() => readiness.value?.can_calculate ?? false)

const confidenceType = computed(() => {
  const c = result.value?.confidence
  if (c === 'high') return 'success'
  if (c === 'medium') return 'warning'
  return 'danger'
})
const confidenceLabel = computed(() => {
  const c = result.value?.confidence
  if (c === 'high') return '高置信'
  if (c === 'medium') return '中置信'
  return '低置信'
})

const deltaClass = computed(() => {
  const baa = result.value?.age_acceleration ?? 0
  return baa > 0 ? 'bioage--bad' : 'bioage--good'
})
const deltaLabel = computed(() => (result.value?.age_acceleration ?? 0) > 0 ? '超前' : '优势')

const changeClass = computed(() => {
  const c = historyData.value?.trend?.last_change
  if (c == null) return ''
  return c < 0 ? 'bioage--good' : 'bioage--bad'
})
const changeDirection = computed(() => {
  const c = historyData.value?.trend?.last_change
  return c != null && c < 0 ? '↓' : '↑'
})
const changeText = computed(() => {
  const c = historyData.value?.trend?.last_change
  if (c == null) return ''
  const abs = Math.abs(c).toFixed(1)
  return c < 0 ? `改善 ${abs} 岁` : `增加 ${abs} 岁`
})

interface DimBar { key: string; label: string; percent: number; level: string; color: string }

const DIM_META: Record<string, string> = {
  glucose: '糖代谢', vascular: '血管弹性', metabolic: '新陈代谢',
  hepatorenal: '肝肾功能', skeletal: '骨骼',
}
const RISK_COLORS: Record<string, string> = {
  high: '#ef4444', elevated: '#f97316', moderate: '#eab308',
  low: '#22C55E', good: '#10b981',
}

const dimensionBars = computed<DimBar[]>(() => {
  const ds = result.value?.dim_scores
  if (!ds) return []
  const entries = Object.entries(ds).filter(([, v]) => v != null) as [string, number][]
  if (!entries.length) return []
  const maxVal = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.01)
  return entries
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .map(([key, val]) => {
      const ratio = Math.abs(val) / maxVal
      const level = ratio > 0.7 ? { k: 'high', t: '高' }
        : ratio > 0.45 ? { k: 'elevated', t: '偏高' }
        : ratio > 0.25 ? { k: 'moderate', t: '中等' }
        : ratio > 0.1 ? { k: 'low', t: '偏低' }
        : { k: 'good', t: '良好' }
      return { key, label: DIM_META[key] || key, percent: Math.max(ratio * 100, 10), level: level.t, color: RISK_COLORS[level.k] }
    })
})

const BIOMARKER_LABELS: Record<string, string> = {
  hba1c: '糖化血红蛋白', albumin: '白蛋白', creatinine: '肌酐',
  alp: '碱性磷酸酶', hscrp: '超敏C反应蛋白', tc: '总胆固醇',
  sbp: '收缩压', pp: '脉压差',
}
const biomarkerLabel = (code: string) => BIOMARKER_LABELS[code] || code

const ACTION_COLORS = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b']
const actionColor = (idx: number) => ACTION_COLORS[idx % ACTION_COLORS.length]

const onCalculate = () => { if (props.customerId) calculate(props.customerId) }
</script>

<style scoped>
/* ---- Card Shell ---- */
.bioage {
  margin-top: 20px;
  padding: 18px 24px;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--card-bg);
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.06);
}

/* ---- Header ---- */
.bioage__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}
.bioage__head-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bioage__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ---- Shared Icon (matches other cards) ---- */
.crm-card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  flex-shrink: 0;
}
.crm-card-icon svg {
  width: 20px;
  height: 20px;
}

/* ---- Body: Two Column ---- */
.bioage__body {
  display: flex;
  gap: 32px;
  align-items: stretch;
}
.bioage__left {
  flex: 0 0 200px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.bioage__right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
}
.bioage__right--empty {
  justify-content: center;
  align-items: center;
  text-align: center;
}

/* ---- Age Items ---- */
.bioage__age-item { padding: 6px 0; }
.bioage__age-divider {
  height: 1px;
  background: var(--border-color);
  margin: 4px 0;
}
.bioage__age-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 5px;
}
.bioage__age-badge {
  font-size: 10px;
  padding: 0 5px;
  border-radius: 3px;
  background: rgba(99, 102, 241, 0.08);
  color: #6366f1;
  line-height: 16px;
}
.bioage__age-num {
  font-size: 30px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.15;
  letter-spacing: -0.03em;
}
.bioage__age-num small {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-left: 2px;
  letter-spacing: 0;
}
.bioage__age-num--primary { color: #6366f1; }
.bioage__age-num--muted {
  color: var(--text-muted);
  font-size: 26px;
}
.bioage__age-num--muted small { color: var(--text-muted); }
.bioage__age-sub {
  margin-top: 3px;
  font-size: 11px;
  font-weight: 500;
}
.bioage--good { color: #16a34a; }
.bioage--bad  { color: #ef4444; }
.bioage--muted { color: var(--text-muted); }

/* ---- Dimension Bars ---- */
.bioage__dim-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.bioage__dim-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}
.bioage__dim-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 3px;
  line-height: 16px;
}
.bioage__dim-track {
  height: 5px;
  background: var(--border-color);
  border-radius: 2.5px;
  overflow: hidden;
}
.bioage__dim-bar {
  height: 100%;
  border-radius: 2.5px;
  transition: width 0.5s ease;
}

/* ---- AI Reading ---- */
.bioage__ai {
  margin-top: 14px;
  padding: 10px 12px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.04), rgba(139, 92, 246, 0.04));
  border: 1px solid rgba(99, 102, 241, 0.08);
  border-radius: 8px;
}
.bioage__ai-text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

/* ---- Actions ---- */
.bioage__actions {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.bioage__action {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.bioage__action-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}

/* ---- Timestamp ---- */
.bioage__ts {
  margin-top: 10px;
  font-size: 10px;
  color: var(--text-muted);
}

/* ---- Loading / Error ---- */
.bioage__loading { text-align: center; padding: 24px 0; }
.bioage__loading-text { font-size: 13px; color: var(--text-muted); }
.bioage__msg {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
}
.bioage__msg--error {
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.10);
  color: #dc2626;
}

/* ---- Empty State ---- */
.bioage__empty-hint {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}
.bioage__missing {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
  margin-bottom: 12px;
}
.bioage__missing-tag {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 3px;
  background: rgba(245, 158, 11, 0.08);
  color: #d97706;
}
.bioage__ready-bar {
  height: 3px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
  width: 140px;
  margin: 0 auto 5px;
}
.bioage__ready-fill {
  height: 100%;
  background: var(--primary-color);
  border-radius: 2px;
  transition: width 0.4s ease;
}
.bioage__ready-text { font-size: 11px; color: var(--text-muted); }

/* ---- Dark Mode ---- */
:global(html.dark) .bioage {
  background: var(--card-bg);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}
:global(html.dark) .bioage__age-badge { background: rgba(99, 102, 241, 0.15); color: #818cf8; }
:global(html.dark) .bioage__age-num--primary { color: #818cf8; }
:global(html.dark) .bioage--good { color: #4ade80; }
:global(html.dark) .bioage--bad  { color: #f87171; }
:global(html.dark) .bioage__ai { background: rgba(99, 102, 241, 0.06); border-color: rgba(99, 102, 241, 0.12); }
:global(html.dark) .bioage__dim-track { background: rgba(255, 255, 255, 0.08); }
:global(html.dark) .bioage__msg--error { background: rgba(239, 68, 68, 0.10); border-color: rgba(239, 68, 68, 0.18); }
:global(html.dark) .bioage__missing-tag { background: rgba(245, 158, 11, 0.12); color: #fbbf24; }

/* ---- Responsive ---- */
@media (max-width: 600px) {
  .bioage { padding: 14px; }
  .bioage__body { flex-direction: column; gap: 16px; }
  .bioage__left { flex: none; }
  .bioage__age-num { font-size: 24px; }
}
</style>
