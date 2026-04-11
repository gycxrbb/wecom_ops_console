<template>
  <div class="cal-panel">
    <div class="cal-header">
      <el-button text @click="shiftRange(-7)"><el-icon><ArrowLeft /></el-icon></el-button>
      <strong class="cal-header__title">{{ rangeLabel }}</strong>
      <el-button text @click="shiftRange(7)"><el-icon><ArrowRight /></el-icon></el-button>
      <el-button text size="small" @click="resetRange" style="margin-left: 8px">回到本周</el-button>
    </div>
    <div v-loading="loading" class="cal-grid">
      <div v-for="day in dayList" :key="day.date" class="cal-day" :class="{ 'is-today': day.isToday, 'is-empty': !day.items.length }">
        <div class="cal-day__head">
          <span class="cal-day__weekday">{{ day.weekday }}</span>
          <span class="cal-day__num">{{ day.dayNum }}</span>
          <span v-if="day.items.length" class="cal-day__count">{{ day.items.length }}</span>
        </div>
        <div v-if="day.items.length" class="cal-day__items">
          <div
            v-for="item in day.items"
            :key="`${item.id}-${item.run_at}`"
            class="cal-item"
            :class="{ 'is-cron': item.schedule_type === 'cron' }"
            @click="$emit('select-schedule', item.id)"
          >
            <span class="cal-item__time">{{ formatTime(item.run_at) }}</span>
            <span class="cal-item__title">{{ item.title }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import request from '@/utils/request'

interface CalItem {
  id: number
  title: string
  run_at: string
  msg_type: string
  schedule_type: string
  status: string
}

const props = defineProps<{
  groupId?: number | null
}>()

defineEmits<{
  'select-schedule': [id: number]
}>()

const loading = ref(false)
const calendarData = ref<Record<string, CalItem[]>>({})
const offsetDays = ref(0)

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const dayList = computed(() => {
  const result = []
  const now = new Date()
  for (let i = 0; i < 14; i++) {
    const d = new Date(now)
    d.setDate(d.getDate() + i + offsetDays.value)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    const isToday = key === `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    result.push({
      date: key,
      weekday: WEEKDAYS[d.getDay()],
      dayNum: d.getDate(),
      isToday,
      items: calendarData.value[key] || [],
    })
  }
  return result
})

const rangeLabel = computed(() => {
  const first = dayList.value[0]
  const last = dayList.value[dayList.value.length - 1]
  if (!first || !last) return ''
  return `${first.date} ~ ${last.date}`
})

const formatTime = (iso: string) => {
  if (!iso) return '--:--'
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const fetchCalendar = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = { days: 14 }
    if (props.groupId) params.group_id = props.groupId
    const res: any = await request.get('/v1/schedules/calendar', { params })
    calendarData.value = res.days || {}
  } catch {
    calendarData.value = {}
  } finally {
    loading.value = false
  }
}

const shiftRange = (delta: number) => {
  offsetDays.value += delta
}

const resetRange = () => {
  offsetDays.value = 0
}

watch(offsetDays, fetchCalendar)

onMounted(fetchCalendar)
</script>

<style scoped>
.cal-panel {
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: var(--card-bg);
  overflow: hidden;
}

.cal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-color);
}
.cal-header__title {
  color: var(--text-primary);
  font-size: 14px;
}

.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
  background: var(--border-color);
  min-height: 320px;
}

.cal-day {
  background: var(--card-bg);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 100px;
}
.cal-day.is-today {
  background: rgba(34, 197, 94, 0.04);
}
.cal-day.is-empty {
  opacity: 0.5;
}

.cal-day__head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.cal-day__weekday {
  font-size: 11px;
  color: var(--text-muted);
}
.cal-day__num {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.cal-day.is-today .cal-day__num {
  color: var(--primary-color);
}
.cal-day__count {
  margin-left: auto;
  display: inline-flex;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.1);
  color: var(--primary-color);
  font-size: 11px;
  font-weight: 700;
}

.cal-day__items {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  overflow-y: auto;
}

.cal-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: 6px;
  background: rgba(34, 197, 94, 0.06);
  cursor: pointer;
  transition: background 0.15s;
}
.cal-item:hover {
  background: rgba(34, 197, 94, 0.12);
}
.cal-item.is-cron {
  background: rgba(59, 130, 246, 0.06);
}
.cal-item.is-cron:hover {
  background: rgba(59, 130, 246, 0.12);
}
.cal-item__time {
  font-size: 11px;
  font-weight: 700;
  color: var(--primary-color);
  min-width: 34px;
}
.cal-item.is-cron .cal-item__time {
  color: #3b82f6;
}
.cal-item__title {
  font-size: 12px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:global(html.dark) .cal-day.is-today {
  background: rgba(74, 222, 128, 0.06);
}
:global(html.dark) .cal-item {
  background: rgba(74, 222, 128, 0.08);
}
:global(html.dark) .cal-item:hover {
  background: rgba(74, 222, 128, 0.14);
}
:global(html.dark) .cal-item.is-cron {
  background: rgba(96, 165, 250, 0.08);
}
:global(html.dark) .cal-item.is-cron:hover {
  background: rgba(96, 165, 250, 0.14);
}

@media (max-width: 1000px) {
  .cal-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
@media (max-width: 600px) {
  .cal-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
