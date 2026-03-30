<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">审批中心</h1>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="approvals" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="target_type" label="类型" width="120">
          <template #default="scope">
            <el-tag size="small">{{ scope.row.target_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_id" label="目标ID" width="100" />
        <el-table-column prop="reason" label="申请理由" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)" size="small">
              {{ formatStatus(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="申请时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button 
              v-if="scope.row.status === 'pending' && userStore.user?.role === 'admin'"
              link type="success" 
              @click="handleAction(scope.row, 'approve')"
            >同意</el-button>
            <el-button 
              v-if="scope.row.status === 'pending' && userStore.user?.role === 'admin'"
              link type="danger" 
              @click="handleAction(scope.row, 'reject')"
            >拒绝</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top:20px; display:flex; justify-content:flex-end;">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchApprovals"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="actionType === 'approve' ? '审批同意' : '审批拒绝'" width="400px">
      <el-form label-width="80px">
        <el-form-item label="审批意见">
          <el-input v-model="comment" type="textarea" :rows="3" placeholder="可选填"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button :type="actionType === 'approve' ? 'success' : 'danger'" @click="submitAction" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { useUserStore } from '@/store/user'

const userStore = useUserStore()
const approvals = ref<any[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const dialogVisible = ref(false)
const actionType = ref('')
const currentApproval = ref<any>(null)
const comment = ref('')
const submitting = ref(false)

const fetchApprovals = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/approvals', {
      params: { page: page.value, page_size: pageSize.value }
    })
    approvals.value = res.list
    total.value = res.total
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const getStatusType = (status: string) => {
  switch(status) {
    case 'pending': return 'warning'
    case 'approved': return 'success'
    case 'rejected': return 'danger'
    default: return 'info'
  }
}

const formatStatus = (status: string) => {
  switch(status) {
    case 'pending': return '待审批'
    case 'approved': return '已通过'
    case 'rejected': return '已拒绝'
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

const handleAction = (row: any, action: string) => {
  currentApproval.value = row
  actionType.value = action
  comment.value = ''
  dialogVisible.value = true
}

const submitAction = async () => {
  submitting.value = true
  try {
    await request.post(/v1/approvals/\/\, {
      comment: comment.value
    })
    ElMessage.success('操作成功')
    dialogVisible.value = false
    fetchApprovals()
  } catch(error) {
    console.error(error)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchApprovals()
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
