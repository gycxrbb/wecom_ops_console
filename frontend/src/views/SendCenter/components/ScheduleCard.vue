<template>
  <div class="card-panel">
    <div class="card-header">
      <div class="card-header-icon card-header-icon--amber">
        <el-icon :size="16"><Timer /></el-icon>
      </div>
      <h3 class="card-header-title">定时任务</h3>
    </div>
    <div class="card-body">
      <el-form label-width="90px" label-position="left">
        <el-form-item label="任务标题" required>
          <el-input v-model="scheduleForm.title" placeholder="如: 每日早报推送" />
        </el-form-item>

        <el-form-item label="任务类型">
          <el-radio-group v-model="scheduleForm.schedule_type">
            <el-radio-button label="once">一次性</el-radio-button>
            <el-radio-button label="cron">周期性</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <transition name="el-zoom-in-top" mode="out-in">
          <el-form-item label="执行时间" v-if="scheduleForm.schedule_type === 'once'" required>
            <el-date-picker
              v-model="scheduleForm.run_at"
              type="datetime"
              placeholder="选择未来执行时间"
              value-format="YYYY-MM-DDTHH:mm:ss"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item label="Cron表达式" v-else required>
            <CronBuilder v-model="scheduleForm.cron_expr" />
            <div class="cron-hint">
              可直接用上面的规则生成周期任务；如果切到“自定义”，仍可手输完整 Cron 表达式。
            </div>
          </el-form-item>
        </transition>

        <el-form-item label="时区">
          <el-select v-model="scheduleForm.timezone" style="width: 100%">
            <el-option label="Asia/Shanghai" value="Asia/Shanghai" />
            <el-option label="UTC" value="UTC" />
          </el-select>
        </el-form-item>

        <el-form-item label="执行规则">
          <el-checkbox v-model="scheduleForm.skip_weekends">跳过周末</el-checkbox>
          <el-checkbox v-model="scheduleForm.approval_required">需要审批后执行</el-checkbox>
        </el-form-item>

        <el-form-item label="跳过日期">
          <el-select
            v-model="scheduleForm.skip_dates"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入 2026-04-08 这样的日期"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="执行预览">
          <div class="preview-panel" :class="{ 'is-loading': previewLoading }">
            <template v-if="schedulePreview.length">
              <span v-for="run in schedulePreview" :key="run" class="preview-chip">
                {{ formatPreviewDate(run) }}
              </span>
            </template>
            <span v-else class="preview-empty">
              {{ previewHint }}
            </span>
          </div>
        </el-form-item>

        <div class="action-footer">
          <el-button type="success" @click="$emit('schedule')" :loading="isScheduling">
            <template #icon><el-icon><Clock /></el-icon></template>
            {{ buttonLabel }}
          </el-button>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { Timer, Clock } from '@element-plus/icons-vue'
import request from '@/utils/request'
import CronBuilder from '@/components/CronBuilder.vue'

const props = defineProps({
  scheduleForm: { type: Object, required: true },
  isScheduling: { type: Boolean, default: false },
  buttonLabel: { type: String, default: '创建计划任务' }
})

defineEmits(['schedule'])

const schedulePreview = ref<string[]>([])
const previewHint = ref('填写执行规则后，这里会显示未来几次执行时间。')
const previewLoading = ref(false)
let previewTimer: ReturnType<typeof setTimeout> | null = null

const formatPreviewDate = (value: string) =>
  new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })

const refreshPreview = async () => {
  const payload = {
    schedule_type: props.scheduleForm.schedule_type,
    run_at: props.scheduleForm.schedule_type === 'once' ? props.scheduleForm.run_at || null : null,
    cron_expr: props.scheduleForm.schedule_type === 'cron' ? props.scheduleForm.cron_expr || '' : '',
    timezone: props.scheduleForm.timezone || 'Asia/Shanghai',
    skip_weekends: !!props.scheduleForm.skip_weekends,
    skip_dates: [...(props.scheduleForm.skip_dates || [])]
  }

  if (payload.schedule_type === 'once' && !payload.run_at) {
    schedulePreview.value = []
    previewHint.value = '请选择一次性任务的执行时间。'
    return
  }

  if (payload.schedule_type === 'cron' && !payload.cron_expr) {
    schedulePreview.value = []
    previewHint.value = '输入 Cron 表达式后，这里会显示未来几次执行时间。'
    return
  }

  previewLoading.value = true
  try {
    const res: any = await request.post('/v1/schedules/preview-runs', payload)
    schedulePreview.value = res.next_runs || []
    previewHint.value = schedulePreview.value.length ? '未来执行时间预览' : '当前规则下没有未来执行时间，请检查配置。'
  } catch {
    schedulePreview.value = []
    previewHint.value = '执行预览暂时不可用，请检查时间、Cron 或跳过规则。'
  } finally {
    previewLoading.value = false
  }
}

watch(
  () => [
    props.scheduleForm.schedule_type,
    props.scheduleForm.run_at,
    props.scheduleForm.cron_expr,
    props.scheduleForm.timezone,
    props.scheduleForm.skip_weekends,
    JSON.stringify(props.scheduleForm.skip_dates || [])
  ],
  () => {
    if (previewTimer) clearTimeout(previewTimer)
    previewTimer = setTimeout(() => {
      refreshPreview()
    }, 220)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (previewTimer) clearTimeout(previewTimer)
})
</script>

<style scoped>
.preview-panel {
  min-height: 42px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px dashed var(--border-color);
  background: color-mix(in srgb, var(--bg-color) 92%, transparent);
}
.preview-panel.is-loading {
  opacity: 0.7;
}
.preview-chip {
  padding: 4px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--el-color-success, #16a34a) 14%, transparent);
  color: var(--el-color-success-dark-2, #15803d);
  font-size: 12px;
}
.preview-empty {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}
.cron-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
  line-height: 1.5;
}
.action-footer {
  margin-top: 8px;
}
.cron-hint code {
  background: var(--bg-color);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}
</style>
