<template>
  <div class="view-container">
    <h2>发送记录</h2>
    <el-table :data="logs" style="width: 100%" v-loading="loading">
      <el-table-column prop="created_at" label="时间" width="180" />
      <el-table-column prop="group_name" label="群组" />
      <el-table-column prop="msg_type" label="消息类型" />
      <el-table-column prop="run_mode" label="触发方式" />
      <el-table-column label="状态">
        <template #default="{ row }">
          <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column type="expand">
        <template #default="props">
          <div style="padding: 20px;">
            <p><strong>请求内容:</strong></p>
            <pre>{{ formatPayload(props.row.request_json) }}</pre>
            <p><strong>响应内容/错误信息:</strong></p>
            <pre>{{ props.row.error_message || formatPayload(props.row.response_json) }}</pre>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button type="primary" link @click="retryLog(row)" v-if="!row.success">重试</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

const logs = ref([])
const loading = ref(false)

const fetchLogs = async () => {
  loading.value = true
  try {
    const res = await request.get('/v1/logs')
    logs.value = res.list || res
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const retryLog = async (row: any) => {
  try {
    await request.post(`/v1/logs/${row.id}/retry`)
    ElMessage.success('重试成功')
    fetchLogs()
  } catch (e) { console.error(e) }
}

const formatPayload = (value: any) => {
  if (!value) return '-'
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
}

onMounted(() => {
  fetchLogs()
})
</script>

<style scoped>
.view-container {
  padding: 20px;
  background: var(--card-bg);
  border-radius: 4px;
  overflow-x: auto;
}
pre {
  background: var(--bg-color);
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
@media (max-width: 768px) {
  .view-container { padding: 12px; }
}
</style>
