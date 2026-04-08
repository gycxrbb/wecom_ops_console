<template>
  <div class="cron-builder">
    <div class="cron-builder__modes">
      <button
        v-for="item in modes"
        :key="item.value"
        type="button"
        class="cron-builder__mode"
        :class="{ 'is-active': state.mode === item.value }"
        @click="state.mode = item.value"
      >
        {{ item.label }}
      </button>
    </div>

    <template v-if="state.mode !== 'custom'">
      <div class="cron-builder__grid">
        <label class="cron-builder__field">
          <span class="cron-builder__label">时</span>
          <el-input-number v-model="state.hour" :min="0" :max="23" controls-position="right" />
        </label>
        <label class="cron-builder__field">
          <span class="cron-builder__label">分</span>
          <el-input-number v-model="state.minute" :min="0" :max="59" controls-position="right" />
        </label>
      </div>

      <div v-if="state.mode === 'weekly'" class="cron-builder__weekday">
        <span class="cron-builder__label">每周几</span>
        <div class="cron-builder__weekday-list">
          <button
            v-for="item in weekdayOptions"
            :key="item.value"
            type="button"
            class="cron-builder__weekday-chip"
            :class="{ 'is-active': state.weekdays.includes(item.value) }"
            @click="toggleWeekday(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <label v-if="state.mode === 'monthly'" class="cron-builder__field cron-builder__field--wide">
        <span class="cron-builder__label">每月日期</span>
        <el-input-number v-model="state.dayOfMonth" :min="1" :max="31" controls-position="right" />
      </label>
    </template>

    <template v-else>
      <el-input v-model="state.customExpr" placeholder="例如: 0 9 * * *" />
      <div class="cron-builder__hint">
        自定义模式适合复杂规则。格式为：分 时 日 月 周。
      </div>
    </template>

    <div class="cron-builder__summary">
      <span class="cron-builder__summary-label">当前表达式</span>
      <code>{{ outputExpr }}</code>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

type BuilderMode = 'daily' | 'weekdays' | 'weekly' | 'monthly' | 'custom'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const modes: Array<{ label: string; value: BuilderMode }> = [
  { label: '每天', value: 'daily' },
  { label: '工作日', value: 'weekdays' },
  { label: '每周', value: 'weekly' },
  { label: '每月', value: 'monthly' },
  { label: '自定义', value: 'custom' }
]

const weekdayOptions = [
  { label: '一', value: 1 },
  { label: '二', value: 2 },
  { label: '三', value: 3 },
  { label: '四', value: 4 },
  { label: '五', value: 5 },
  { label: '六', value: 6 },
  { label: '日', value: 0 }
]

const defaultState = () => ({
  mode: 'daily' as BuilderMode,
  minute: 0,
  hour: 9,
  weekdays: [1] as number[],
  dayOfMonth: 1,
  customExpr: ''
})

const state = reactive(defaultState())

const parseCron = (expr: string | undefined | null) => {
  const next = defaultState()
  const trimmed = (expr || '').trim()
  next.customExpr = trimmed
  if (!trimmed) return next

  const parts = trimmed.split(/\s+/)
  if (parts.length !== 5) {
    next.mode = 'custom'
    return next
  }

  const [minute, hour, day, month, week] = parts
  const parsedMinute = Number(minute)
  const parsedHour = Number(hour)
  if (!Number.isInteger(parsedMinute) || !Number.isInteger(parsedHour)) {
    next.mode = 'custom'
    return next
  }

  next.minute = parsedMinute
  next.hour = parsedHour

  if (day === '*' && month === '*' && week === '*') {
    next.mode = 'daily'
    return next
  }
  if (day === '*' && month === '*' && week === '1-5') {
    next.mode = 'weekdays'
    return next
  }
  if (day === '*' && month === '*' && /^\d(?:,\d)*$/.test(week)) {
    next.mode = 'weekly'
    next.weekdays = week.split(',').map((item) => Number(item)).filter((item) => Number.isInteger(item))
    return next
  }
  if (/^\d+$/.test(day) && month === '*' && week === '*') {
    next.mode = 'monthly'
    next.dayOfMonth = Number(day)
    return next
  }

  next.mode = 'custom'
  return next
}

const outputExpr = computed(() => {
  if (state.mode === 'custom') {
    return state.customExpr.trim()
  }
  if (state.mode === 'daily') {
    return `${state.minute} ${state.hour} * * *`
  }
  if (state.mode === 'weekdays') {
    return `${state.minute} ${state.hour} * * 1-5`
  }
  if (state.mode === 'weekly') {
    const weekdays = [...state.weekdays].sort((a, b) => a - b)
    return `${state.minute} ${state.hour} * * ${weekdays.join(',') || '1'}`
  }
  return `${state.minute} ${state.hour} ${state.dayOfMonth} * *`
})

const syncFromValue = (value: string) => {
  Object.assign(state, parseCron(value))
}

const toggleWeekday = (value: number) => {
  const next = new Set(state.weekdays)
  if (next.has(value)) {
    if (next.size === 1) return
    next.delete(value)
  } else {
    next.add(value)
  }
  state.weekdays = [...next]
}

watch(
  () => props.modelValue,
  (value) => {
    if ((value || '').trim() !== outputExpr.value.trim()) {
      syncFromValue(value || '')
    }
  },
  { immediate: true }
)

watch(outputExpr, (value) => {
  emit('update:modelValue', value)
})
</script>

<style scoped>
.cron-builder {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cron-builder__modes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cron-builder__mode,
.cron-builder__weekday-chip {
  appearance: none;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cron-builder__mode.is-active,
.cron-builder__weekday-chip.is-active {
  border-color: color-mix(in srgb, var(--el-color-primary, #2563eb) 55%, var(--border-color));
  background: color-mix(in srgb, var(--el-color-primary, #2563eb) 12%, var(--bg-color));
  color: var(--el-color-primary, #2563eb);
}

.cron-builder__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 180px));
  gap: 12px;
}

.cron-builder__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cron-builder__field--wide {
  max-width: 220px;
}

.cron-builder__label,
.cron-builder__summary-label {
  font-size: 12px;
  color: var(--text-muted);
}

.cron-builder__weekday {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cron-builder__weekday-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cron-builder__summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cron-builder__summary code,
.cron-builder__hint {
  font-size: 12px;
  line-height: 1.5;
}

.cron-builder__summary code {
  background: var(--bg-color);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 4px 8px;
}

.cron-builder__hint {
  color: var(--text-muted);
}

@media (max-width: 640px) {
  .cron-builder__grid {
    grid-template-columns: 1fr;
  }
}
</style>
