<template>
  <div class="bodycomp">
    <!-- Freshness -->
    <div class="bodycomp-freshness" v-if="payload.latest_date">
      <svg viewBox="0 0 16 16" fill="none" class="bodycomp-clock">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/>
        <path d="M8 4.5V8.5L10.5 10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
      </svg>
      <span>最新数据 {{ payload.latest_date }}</span>
    </div>

    <!-- Metrics Grid -->
    <div class="bodycomp-metrics">
      <div class="bodycomp-metric" v-for="m in displayMetrics" :key="m.key">
        <div class="bodycomp-metric-icon" :style="{ background: m.bg }">
          <svg viewBox="0 0 20 20" fill="none" v-html="m.svg"/>
        </div>
        <div class="bodycomp-metric-text">
          <span class="bodycomp-metric-label">{{ m.label }}</span>
          <span class="bodycomp-metric-value">{{ m.display }}</span>
        </div>
      </div>
    </div>

    <!-- Body Score -->
    <div class="bodycomp-score" v-if="payload.body_score != null">
      <span class="bodycomp-score-label">身体评分</span>
      <span class="bodycomp-score-value">{{ payload.body_score }} 分</span>
    </div>

    <!-- 30-Day Trend -->
    <div class="bodycomp-trend" v-if="hasTrend">
      <div class="bodycomp-trend-header">30天趋势</div>
      <div class="bodycomp-trend-items">
        <div
          class="bodycomp-trend-item"
          v-for="(info, key) in payload.trend_metrics"
          :key="key"
        >
          <span class="bodycomp-trend-val" :class="trendCls(info.diff)">
            <svg v-if="info.diff > 0" viewBox="0 0 10 10" class="bodycomp-arrow">
              <path d="M5 2L8.5 7H1.5L5 2Z" fill="currentColor"/>
            </svg>
            <svg v-else-if="info.diff < 0" viewBox="0 0 10 10" class="bodycomp-arrow">
              <path d="M5 8L1.5 3H8.5L5 8Z" fill="currentColor"/>
            </svg>
            {{ fmtTrend(info) }}
          </span>
          <span class="bodycomp-trend-sub">{{ trendLabels[key] || key }}</span>
        </div>
      </div>
      <!-- Sparkline -->
      <div class="bodycomp-chart" v-if="payload.chart_data?.length >= 2">
        <svg :viewBox="`0 0 ${cw} ${ch}`" preserveAspectRatio="none">
          <defs>
            <linearGradient id="bc-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#3B82F6" stop-opacity="0.25"/>
              <stop offset="100%" stop-color="#3B82F6" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <polygon :points="areaPts" fill="url(#bc-grad)"/>
          <polyline
            :points="linePts"
            fill="none"
            stroke="#3B82F6"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ payload: Record<string, any> }>()

const METRIC_DEFS = [
  {
    key: 'weight',
    label: '体重',
    bg: '#EEF2FF',
    svg: '<path d="M3 10h14M5 10V7a2 2 0 012-2h6a2 2 0 012 2v3" stroke="#3B82F6" stroke-width="1.5" stroke-linecap="round"/><rect x="3" y="10" width="3" height="5" rx="1" fill="#3B82F6" opacity="0.35"/><rect x="14" y="10" width="3" height="5" rx="1" fill="#3B82F6" opacity="0.35"/>',
  },
  {
    key: 'bmi',
    label: 'BMI',
    bg: '#F3E8FF',
    svg: '<rect x="3" y="10" width="3" height="6" rx="0.5" fill="#8B5CF6" opacity="0.45"/><rect x="8" y="6" width="3" height="10" rx="0.5" fill="#8B5CF6" opacity="0.65"/><rect x="13" y="8" width="3" height="8" rx="0.5" fill="#8B5CF6"/>',
  },
  {
    key: 'body_fat',
    label: '体脂率',
    bg: '#FFF7ED',
    svg: '<path d="M10 3C10 3 5 8.5 5 12a5 5 0 0010 0c0-3.5-5-9-5-9z" fill="#F59E0B" opacity="0.55"/>',
  },
  {
    key: 'muscle',
    label: '肌肉量',
    bg: '#ECFDF5',
    svg: '<path d="M6 5a3 3 0 00-3 3v2a3 3 0 003 3c.5 0 1-.5 1-1V6c0-.5-.5-1-1-1zM14 5a3 3 0 013 3v2a3 3 0 01-3 3c-.5 0-1-.5-1-1V6c0-.5.5-1 1-1z" fill="#10B981" opacity="0.5"/><rect x="7" y="8" width="6" height="3" rx="1.5" fill="#10B981" opacity="0.7"/>',
  },
]

const trendLabels: Record<string, string> = {
  weight: '体重变化',
  bmi: 'BMI变化',
}

const displayMetrics = computed(() =>
  METRIC_DEFS.map((def) => {
    const m = props.payload.metrics?.[def.key]
    const val = m?.value
    return { ...def, display: val != null ? `${val}${m.unit}` : '—' }
  })
)

const hasTrend = computed(
  () => props.payload.trend_metrics && Object.keys(props.payload.trend_metrics).length > 0
)

function trendCls(diff: number) {
  if (diff > 0) return 'bodycomp-trend-up'
  if (diff < 0) return 'bodycomp-trend-down'
  return ''
}

function fmtTrend(info: { diff: number; unit: string }) {
  const sign = info.diff > 0 ? '+' : ''
  return `${sign}${info.diff}${info.unit}`
}

// ---- Sparkline helpers ----
const cw = 280
const ch = 56
const pad = 4

function buildPoints() {
  const data = props.payload.chart_data
  if (!data || data.length < 2) return { line: '', area: '' }
  const vals = data.map((d: any) => d.value)
  const mn = Math.min(...vals)
  const mx = Math.max(...vals)
  const range = mx - mn || 1
  const pw = cw - pad * 2
  const ph = ch - pad * 2
  const pts = data.map((d: any, i: number) => {
    const x = pad + (i / (data.length - 1)) * pw
    const y = pad + (1 - (d.value - mn) / range) * ph
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const lastX = (pad + pw).toFixed(1)
  return {
    line: pts.join(' '),
    area: `${pad},${ch} ${pts.join(' ')} ${lastX},${ch}`,
  }
}

const linePts = computed(() => buildPoints().line)
const areaPts = computed(() => buildPoints().area)
</script>

<style scoped>
.bodycomp {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Freshness */
.bodycomp-freshness {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted, #9CA3AF);
}

.bodycomp-clock {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

/* Metrics grid */
.bodycomp-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.bodycomp-metric {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bodycomp-metric-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bodycomp-metric-icon svg {
  width: 20px;
  height: 20px;
}

.bodycomp-metric-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.bodycomp-metric-label {
  font-size: 12px;
  color: var(--text-muted, #6B7280);
}

.bodycomp-metric-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

/* Body score */
.bodycomp-score {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #EFF6FF;
  border-radius: 10px;
}

.bodycomp-score-label {
  font-size: 13px;
  color: var(--text-secondary, #374151);
}

.bodycomp-score-value {
  font-size: 18px;
  font-weight: 700;
  color: #3B82F6;
}

/* 30-day trend */
.bodycomp-trend {
  border-top: 1px solid var(--border-color, #F3F4F6);
  padding-top: 12px;
}

.bodycomp-trend-header {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary, #374151);
  margin-bottom: 10px;
}

.bodycomp-trend-items {
  display: flex;
  gap: 20px;
  margin-bottom: 10px;
}

.bodycomp-trend-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.bodycomp-trend-val {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 600;
}

.bodycomp-arrow {
  width: 10px;
  height: 10px;
}

.bodycomp-trend-up {
  color: #EF4444;
}

.bodycomp-trend-down {
  color: #10B981;
}

.bodycomp-trend-sub {
  font-size: 11px;
  color: var(--text-muted, #9CA3AF);
}

/* Sparkline chart */
.bodycomp-chart {
  width: 100%;
  height: 56px;
}

.bodycomp-chart svg {
  width: 100%;
  height: 100%;
}

/* Dark mode */
:global(html.dark) .bodycomp-score {
  background: rgba(59, 130, 246, 0.12);
}

:global(html.dark) .bodycomp-metric-value {
  color: #E5E7EB;
}

:global(html.dark) .bodycomp-score-value {
  color: #60A5FA;
}

:global(html.dark) .bodycomp-trend {
  border-color: rgba(255, 255, 255, 0.08);
}
</style>
