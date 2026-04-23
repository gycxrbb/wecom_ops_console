<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="发布到群"
    width="640px"
    :close-on-click-modal="false"
  >
    <div class="pub-intro">
      <strong v-if="isCampaignMode">将积分运营计划按触发规则创建定时任务</strong>
      <strong v-else>将运营计划的所有节点按天转化为定时任务</strong>
      <span v-if="isCampaignMode">系统会根据每个阶段的触发规则自动创建 cron 或一次性任务。</span>
      <span v-else>系统会根据开始日期和各时段发送时间，为每个节点创建一条"一次性"定时任务。</span>
    </div>

    <el-form label-width="96px" class="pub-form">
      <el-form-item label="运营计划">
        <div class="pub-plan-name">{{ planName }}</div>
      </el-form-item>

      <el-form-item label="目标群">
        <el-select
          v-model="form.groupIds"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择要推送的群"
          style="width: 100%"
          filterable
        >
          <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
        </el-select>
      </el-form-item>

      <el-form-item :label="isCampaignMode ? '运营周期' : '开始日期'">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-date-picker
            v-model="form.startDate"
            type="date"
            :placeholder="isCampaignMode ? '开始日期' : '选择开始日期'"
            value-format="YYYY-MM-DD"
            style="flex: 1"
            :disabled-date="disablePastDates"
          />
          <el-date-picker
            v-if="isCampaignMode"
            v-model="form.endDate"
            type="date"
            placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="flex: 1"
            :disabled-date="disablePastDates"
          />
        </div>
      </el-form-item>

      <template v-if="!isCampaignMode">
        <el-form-item label="发送时段">
          <div class="pub-time-grid">
            <div v-for="slot in timeSlots" :key="slot.key" class="pub-time-row">
              <span class="pub-time-label">{{ slot.label }}</span>
              <el-time-select
                v-model="form.sendTimes[slot.key]"
                :start="'06:00'"
                :step="'00:15'"
                :end="'23:00'"
                placeholder="选择时间"
                style="flex: 1"
              />
            </div>
          </div>
        </el-form-item>

        <el-form-item label="跳过周末">
          <el-switch v-model="form.skipWeekends" />
        </el-form-item>
      </template>

      <el-form-item label="需要审批">
        <el-switch v-model="form.requireApproval" />
        <span class="pub-hint" v-if="form.requireApproval">admin 发布会自动通过审批</span>
      </el-form-item>
    </el-form>

    <div v-if="previewCount > 0" class="pub-preview">
      <strong>预计创建 {{ previewCount }} 条定时任务</strong>
      <span v-if="!isCampaignMode && form.skipWeekends">（已跳过周末）</span>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="publishing" :disabled="!canPublish" @click="handlePublish">
        确认发布
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

interface GroupItem { id: number; name: string }

const props = defineProps<{
  visible: boolean
  planId: number | null
  planName: string
  planMode: string
  nodeCount: number
  dayCount: number
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  'published': []
}>()

const isCampaignMode = computed(() => props.planMode === 'points_campaign')
const publishing = ref(false)
const groups = ref<GroupItem[]>([])

const form = reactive({
  groupIds: [] as number[],
  startDate: '',
  endDate: '',
  sendTimes: {
    morning: '08:00',
    before_lunch: '11:00',
    lunch: '12:00',
    afternoon: '15:00',
    evening: '18:00',
    night: '21:00',
  } as Record<string, string>,
  skipWeekends: false,
  requireApproval: true,
})

const timeSlots = [
  { key: 'morning', label: '早安/早餐' },
  { key: 'before_lunch', label: '午餐前' },
  { key: 'lunch', label: '午餐提醒' },
  { key: 'afternoon', label: '下午内容' },
  { key: 'evening', label: '晚餐提醒' },
  { key: 'night', label: '晚安/总结' },
]

const previewCount = computed(() => {
  if (!props.nodeCount) return 0
  if (isCampaignMode.value) {
    return props.nodeCount
  }
  if (form.skipWeekends) {
    const weekdays = Math.ceil(props.dayCount * 5 / 7)
    return weekdays * props.nodeCount / props.dayCount
  }
  return props.nodeCount
})

const canPublish = computed(() => {
  if (!props.planId || form.groupIds.length === 0) return false
  if (!form.startDate) return false
  if (isCampaignMode.value && !form.endDate) return false
  return true
})

const disablePastDates = (date: Date) => date < new Date(new Date().setHours(0, 0, 0, 0))

const fetchGroups = async () => {
  try {
    const res = await request.get('/v1/groups')
    groups.value = Array.isArray(res) ? res.map((g: any) => ({ id: g.id, name: g.name })) : []
  } catch { /* ignore */ }
}

watch(() => props.visible, (val) => {
  if (val) {
    fetchGroups()
    form.groupIds = []
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    form.startDate = tomorrow.toISOString().slice(0, 10)
    if (isCampaignMode.value) {
      const end = new Date(tomorrow)
      end.setDate(end.getDate() + 30)
      form.endDate = end.toISOString().slice(0, 10)
    } else {
      form.endDate = ''
    }
  }
})

const handlePublish = async () => {
  if (!props.planId) return
  publishing.value = true
  try {
    const result: any = await request.post(`/v1/operation-plans/${props.planId}/publish`, {
      group_ids: form.groupIds,
      start_date: form.startDate,
      end_date: form.endDate,
      send_times: form.sendTimes,
      skip_weekends: form.skipWeekends,
      require_approval: form.requireApproval,
    })
    ElMessage.success(`已创建 ${result.created_count} 条定时任务`)
    emit('update:visible', false)
    emit('published')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '发布失败')
  } finally {
    publishing.value = false
  }
}
</script>

<style scoped>
.pub-intro {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  margin-bottom: 18px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.pub-intro strong {
  color: var(--text-primary);
}

.pub-form {
  max-height: 50vh;
  overflow-y: auto;
}

.pub-plan-name {
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(34, 197, 94, 0.08);
  color: var(--primary-color);
  font-weight: 600;
}

.pub-time-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  width: 100%;
}

@media (max-width: 600px) {
  .pub-time-grid {
    grid-template-columns: 1fr;
  }
  .pub-time-label {
    min-width: 60px;
  }
}

.pub-time-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pub-time-label {
  min-width: 80px;
  color: var(--text-secondary);
  font-size: 13px;
}

.pub-hint {
  margin-left: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.pub-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  color: var(--primary-color);
  font-size: 13px;
  margin-top: 12px;
}

:global(html.dark) .pub-intro {
  background: rgba(255, 255, 255, 0.04);
}

:global(html.dark) .pub-plan-name {
  background: rgba(34, 197, 94, 0.14);
}

:global(html.dark) .pub-preview {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(74, 222, 128, 0.24);
}
</style>
