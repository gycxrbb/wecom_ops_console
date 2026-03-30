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
        <el-table-column label="启用" width="80">
          <template #default="scope">
            <el-switch v-model="scope.row.enabled" @change="toggleEnable(scope.row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
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

    <el-dialog v-model="dialogVisible" title="新建任务" width="600px">
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
      </el-form>
      <div style="font-size: 12px; color: #999; margin-left:100px; margin-bottom:20px;">
        *完整创建任务请前往【发送中心】选择消息体后保存为定时任务。此面板主要用于管理和查看。
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="router.push('/send')">去发送中心创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import request from '@/utils/request'

const router = useRouter()
const schedules = ref<any[]>([])
const loading = ref(false)

const dialogVisible = ref(false)
const saving = ref(false)
const form = ref({ title: '', schedule_type: 'once' })

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
    await request.post(/v1/schedules/\/toggle, { enabled: row.enabled })
    ElMessage.success('操作成功')
  } catch(error) {
    row.enabled = !row.enabled
    console.error(error)
  }
}

const handleCreate = () => {
  dialogVisible.value = true
}

const handleRunNow = async (row: any) => {
  try {
    await request.post(/v1/schedules/\/run-now)
    ElMessage.success('已触发运行')
  } catch(error) {
    console.error(error)
  }
}

const handleClone = async (row: any) => {
  try {
    await request.post(/v1/schedules/\/clone)
    ElMessage.success('克隆成功')
    fetchSchedules()
  } catch(error) {
    console.error(error)
  }
}

const handleDelete = async (row: any) => {
  try {
    await request.delete(/v1/schedules/\)
    ElMessage.success('删除成功')
    fetchSchedules()
  } catch (error) {
    console.error(error)
  }
}

onMounted(() => {
  fetchSchedules()
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
</style>
