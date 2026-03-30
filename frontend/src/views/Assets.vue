<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">素材库</h1>
      <el-upload
        class="upload-btn"
        action="javascript:;"
        :show-file-list="false"
        :http-request="handleUpload"
      >
        <el-button type="primary" :loading="uploading">
          <el-icon><Upload /></el-icon> 上传素材
        </el-button>
      </el-upload>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="assets" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="文件名" />
        <el-table-column prop="material_type" label="类型" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.material_type === 'image' ? 'success' : 'info'" size="small">
              {{ scope.row.material_type.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="mime_type" label="MIME" width="180" />
        <el-table-column label="大小" width="120">
          <template #default="scope">
            {{ formatSize(scope.row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="handleDownload(scope.row)">下载</el-button>
            <el-popconfirm title="确定要删除该素材吗？" @confirm="handleDelete(scope.row)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const assets = ref<any[]>([])
const loading = ref(false)
const uploading = ref(false)

const fetchAssets = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/assets')
    assets.value = res
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleUpload = async (options: any) => {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', options.file)
    await request.post('/v1/assets', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    ElMessage.success('上传成功')
    fetchAssets()
  } catch (error) {
    console.error(error)
  } finally {
    uploading.value = false
  }
}

const handleDownload = (row: any) => {
  window.open(row.url + '?token=' + localStorage.getItem('access_token'), '_blank')
}

const handleDelete = async (row: any) => {
  try {
    await request.delete('/v1/assets/' + row.id)
    ElMessage.success('删除成功')
    fetchAssets()
  } catch (error) {
    console.error(error)
  }
}

const formatSize = (bytes: number) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

onMounted(() => {
  fetchAssets()
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
.upload-btn {
  display: inline-block;
}
</style>
