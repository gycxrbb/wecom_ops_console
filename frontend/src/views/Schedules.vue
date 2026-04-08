<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">定时任务</h1>
      <el-button type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon> 新建任务
      </el-button>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="schedules" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="任务名称" />
        <el-table-column label="目标群组" width="120">
          <template #default="scope">
            {{ scope.row.group_count || scope.row.group_ids?.length || 0 }} 个群
          </template>
        </el-table-column>
        <el-table-column prop="schedule_type" label="类型" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.schedule_type === 'cron' ? 'primary' : 'info'" size="small">
              {{ scope.row.schedule_type === 'cron' ? '周期任务' : '一次性' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cron_expr" label="Cron表达式/时间" width="160">
          <template #default="scope">
            {{ scope.row.schedule_type === 'cron' ? scope.row.cron_expr : formatDate(scope.row.run_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)" size="small">
              {{ formatStatus(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="next_run_at" label="下次执行" width="160">
          <template #default="scope">
            {{ formatDate(scope.row.next_run_at) }}
          </template>
        </el-table-column>
        <el-table-column label="执行预览" min-width="220">
          <template #default="scope">
            <div v-if="scope.row.next_runs?.length" class="next-run-list">
              <span v-for="run in scope.row.next_runs.slice(0, 3)" :key="run" class="next-run-chip">
                {{ formatDate(run) }}
              </span>
            </div>
            <span v-else class="error-text">暂无后续执行时间</span>
          </template>
        </el-table-column>
        <el-table-column prop="last_sent_at" label="最近执行" width="160">
          <template #default="scope">
            {{ formatDate(scope.row.last_sent_at) }}
          </template>
        </el-table-column>
        <el-table-column label="规则" min-width="180">
          <template #default="scope">
            <div class="rule-tags">
              <el-tag v-if="scope.row.approval_required" size="small" type="warning">需审批</el-tag>
              <el-tag v-if="scope.row.skip_weekends" size="small">跳过周末</el-tag>
              <el-tag v-if="scope.row.skip_dates?.length" size="small" type="info">跳过 {{ scope.row.skip_dates.length }} 天</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最近错误" min-width="180">
          <template #default="scope">
            <span class="error-text">{{ scope.row.last_error || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="scope">
            <el-switch v-model="scope.row.enabled" @change="toggleEnable(scope.row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="handleEdit(scope.row)">编辑</el-button>
            <el-button link type="primary" @click="handleRunNow(scope.row)">运行</el-button>
            <el-button link type="primary" @click="handleClone(scope.row)">克隆</el-button>
            <el-popconfirm title="确定要删除该任务吗？" @confirm="handleDelete(scope.row)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEditMode ? '编辑任务' : '新建任务'" width="680px">
      <el-form label-width="100px" v-loading="saving">
        <el-form-item label="类型">
          <el-radio-group v-model="form.schedule_type">
            <el-radio value="once">一次性任务</el-radio>
            <el-radio value="cron">周期任务 (Cron)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="任务名称">
          <el-input v-model="form.title" placeholder="如: 每日简报" />
        </el-form-item>
        <el-form-item label="目标群组" v-if="isEditMode">
          <div class="readonly-field">
            {{ form.group_count }} 个群组
            <span v-if="form.group_ids?.length"> · ID: {{ form.group_ids.join(', ') }}</span>
          </div>
        </el-form-item>
        <el-form-item label="执行时间" v-if="form.schedule_type === 'once'">
          <el-date-picker
            v-model="form.run_at"
            type="datetime"
            placeholder="选择未来执行时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="Cron表达式" v-else>
          <CronBuilder v-model="form.cron_expr" />
        </el-form-item>
        <el-form-item label="时区">
          <el-select v-model="form.timezone" style="width: 100%">
            <el-option label="Asia/Shanghai" value="Asia/Shanghai" />
            <el-option label="UTC" value="UTC" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行规则">
          <div class="rule-editor">
            <el-checkbox v-model="form.approval_required">需要审批</el-checkbox>
            <el-checkbox v-model="form.skip_weekends">跳过周末</el-checkbox>
          </div>
        </el-form-item>
        <el-form-item label="跳过日期">
          <el-select
            v-model="form.skip_dates"
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
            <template v-if="previewRuns.length">
              <span v-for="run in previewRuns" :key="run" class="preview-chip">
                {{ formatDate(run) }}
              </span>
            </template>
            <span v-else class="preview-empty">{{ previewHint }}</span>
          </div>
        </el-form-item>
      </el-form>
      <div class="dialog-tip">
        {{ isEditMode
          ? '这里可以调整执行时间、规则和审批方式；消息内容本身仍建议回发送中心修改。'
          : '完整创建任务请前往【发送中心】选择消息体后保存为定时任务。这里主要承担管理和规则调整。' }}
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button v-if="!isEditMode" type="primary" @click="router.push('/send')">去发送中心创建</el-button>
        <el-button v-else type="primary" :loading="saving" @click="handleSaveEdit">保存修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import request from '@/utils/request'
import CronBuilder from '@/components/CronBuilder.vue'

const router = useRouter()
const schedules = ref<any[]>([])
const loading = ref(false)
const previewRuns = ref<string[]>([])
const previewHint = ref('修改时间或规则后，这里会显示未来几次执行时间。')
const previewLoading = ref(false)
let previewTimer: ReturnType<typeof setTimeout> | null = null

const dialogVisible = ref(false)
const saving = ref(false)
const form = ref<any>({
  id: null,
  title: '',
  schedule_type: 'once',
  run_at: '',
  cron_expr: '',
  timezone: 'Asia/Shanghai',
  approval_required: false,
  skip_weekends: false,
  skip_dates: [],
  enabled: true,
  group_ids: [],
  group_count: 0,
  template_id: null,
  msg_type: 'text',
  content_json: {},
  variables_json: {}
})

const isEditMode = computed(() => !!form.value.id)

const resetForm = () => {
  form.value = {
    id: null,
    title: '',
    schedule_type: 'once',
    run_at: '',
    cron_expr: '',
    timezone: 'Asia/Shanghai',
    approval_required: false,
    skip_weekends: false,
    skip_dates: [],
    enabled: true,
    group_ids: [],
    group_count: 0,
    template_id: null,
    msg_type: 'text',
    content_json: {},
    variables_json: {}
  }
}

const fetchSchedules = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/schedules')
    schedules.value = res
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const getStatusType = (status: string) => {
  switch(status) {
    case 'draft': return 'info'
    case 'pending_approval': return 'warning'
    case 'approved': return 'success'
    case 'rejected': return 'danger'
    case 'completed': return 'success'
    default: return 'info'
  }
}

const formatStatus = (status: string) => {
  switch(status) {
    case 'draft': return '草稿'
    case 'pending_approval': return '待审批'
    case 'approved': return '已通过/生效'
    case 'rejected': return '已拒绝'
    case 'completed': return '已完成'
    default: return status
  }
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

const toggleEnable = async (row: any) => {
  try {
    const updated: any = await request.post(`/v1/schedules/${row.id}/toggle`, { enabled: row.enabled })
    Object.assign(row, updated)
    ElMessage.success('操作成功')
  } catch(error) {
    row.enabled = !row.enabled
    console.error(error)
  }
}

const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row: any) => {
  form.value = {
    id: row.id,
    title: row.title || '',
    schedule_type: row.schedule_type || 'once',
    run_at: row.run_at || '',
    cron_expr: row.cron_expr || '',
    timezone: row.timezone || 'Asia/Shanghai',
    approval_required: !!row.approval_required,
    skip_weekends: !!row.skip_weekends,
    skip_dates: [...(row.skip_dates || [])],
    enabled: !!row.enabled,
    group_ids: [...(row.group_ids || [])],
    group_count: row.group_count || row.group_ids?.length || 0,
    template_id: row.template_id ?? null,
    msg_type: row.msg_type || 'text',
    content_json: row.content_json || {},
    variables_json: row.variables_json || {}
  }
  dialogVisible.value = true
}

const refreshPreview = async () => {
  const payload = {
    schedule_type: form.value.schedule_type,
    run_at: form.value.schedule_type === 'once' ? form.value.run_at || null : null,
    cron_expr: form.value.schedule_type === 'cron' ? form.value.cron_expr || '' : '',
    timezone: form.value.timezone || 'Asia/Shanghai',
    skip_weekends: !!form.value.skip_weekends,
    skip_dates: [...(form.value.skip_dates || [])]
  }

  if (!dialogVisible.value || !isEditMode.value) {
    previewRuns.value = []
    previewHint.value = '编辑任务时，这里会显示未来几次执行时间。'
    return
  }

  if (payload.schedule_type === 'once' && !payload.run_at) {
    previewRuns.value = []
    previewHint.value = '请选择一次性任务的执行时间。'
    return
  }

  if (payload.schedule_type === 'cron' && !payload.cron_expr) {
    previewRuns.value = []
    previewHint.value = '输入 Cron 表达式后，这里会显示未来几次执行时间。'
    return
  }

  previewLoading.value = true
  try {
    const res: any = await request.post('/v1/schedules/preview-runs', payload)
    previewRuns.value = res.next_runs || []
    previewHint.value = previewRuns.value.length ? '未来执行时间预览' : '当前规则下没有未来执行时间，请检查配置。'
  } catch {
    previewRuns.value = []
    previewHint.value = '执行预览暂时不可用，请检查时间、Cron 或跳过规则。'
  } finally {
    previewLoading.value = false
  }
}

const handleRunNow = async (row: any) => {
  try {
    await request.post(`/v1/schedules/${row.id}/run-now`)
    ElMessage.success('已触发运行')
  } catch(error) {
    console.error(error)
  }
}

const handleClone = async (row: any) => {
  try {
    await request.post(`/v1/schedules/${row.id}/clone`)
    ElMessage.success('克隆成功')
    fetchSchedules()
  } catch(error) {
    console.error(error)
  }
}

const handleDelete = async (row: any) => {
  try {
    await request.delete(`/v1/schedules/${row.id}`)
    ElMessage.success('删除成功')
    fetchSchedules()
  } catch (error) {
    console.error(error)
  }
}

const handleSaveEdit = async () => {
  if (!form.value.title) {
    ElMessage.warning('请填写任务名称')
    return
  }
  if (form.value.schedule_type === 'once' && !form.value.run_at) {
    ElMessage.warning('请选择执行时间')
    return
  }
  if (form.value.schedule_type === 'cron' && !form.value.cron_expr) {
    ElMessage.warning('请填写 Cron 表达式')
    return
  }
  saving.value = true
  try {
    await request.post('/v1/schedules', {
      id: form.value.id,
      title: form.value.title,
      group_ids: form.value.group_ids,
      template_id: form.value.template_id,
      msg_type: form.value.msg_type,
      content_json: form.value.content_json,
      variables_json: form.value.variables_json,
      schedule_type: form.value.schedule_type,
      run_at: form.value.schedule_type === 'once' ? form.value.run_at : null,
      cron_expr: form.value.schedule_type === 'cron' ? form.value.cron_expr : '',
      timezone: form.value.timezone,
      approval_required: form.value.approval_required,
      skip_weekends: form.value.skip_weekends,
      skip_dates: form.value.skip_dates,
      enabled: form.value.enabled
    })
    ElMessage.success('任务已更新')
    dialogVisible.value = false
    fetchSchedules()
  } catch (error) {
    console.error(error)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchSchedules()
})

watch(
  () => [
    dialogVisible.value,
    isEditMode.value,
    form.value.schedule_type,
    form.value.run_at,
    form.value.cron_expr,
    form.value.timezone,
    form.value.skip_weekends,
    JSON.stringify(form.value.skip_dates || [])
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
.page-container {
  max-width: 1200px;
  margin: 0 auto;
}
.table-card {
  border-radius: 12px;
}
.next-run-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.next-run-chip {
  padding: 4px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--el-color-success, #16a34a) 14%, transparent);
  color: var(--el-color-success-dark-2, #15803d);
  font-size: 12px;
  line-height: 1.4;
}
.readonly-field {
  min-height: 32px;
  display: flex;
  align-items: center;
  color: var(--text-secondary);
}
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
  opacity: 0.72;
}
.preview-chip {
  padding: 4px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--el-color-success, #16a34a) 14%, transparent);
  color: var(--el-color-success-dark-2, #15803d);
  font-size: 12px;
  line-height: 1.4;
}
.preview-empty {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}
.rule-editor {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
.dialog-tip {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: 100px;
  margin-bottom: 20px;
  line-height: 1.6;
}
.rule-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.error-text {
  color: var(--text-secondary);
}
</style>
