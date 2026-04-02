<template>
  <div class="page-container">
    <div class="page-header">
      <div class="title-group">
        <h1 class="page-title">素材库</h1>
        <p class="page-subtitle">图片和文件分区管理，图片只看缩略图，文件按列表查看。</p>
        <div class="upload-hint">{{ uploadHint }}</div>
      </div>

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

    <div class="summary-strip">
      <div class="summary-chip">
        <span class="summary-label">全部</span>
        <strong>{{ assets.length }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">图片</span>
        <strong>{{ imageAssets.length }}</strong>
      </div>
      <div class="summary-chip">
        <span class="summary-label">文件</span>
        <strong>{{ fileAssets.length }}</strong>
      </div>
    </div>

    <el-card shadow="never" class="section-card" v-loading="loading">
      <div class="section-header">
        <div>
          <h2>图片素材</h2>
          <p>按缩略图浏览，适合快速挑选要发送的图片。</p>
        </div>
      </div>

      <el-empty v-if="imageAssets.length === 0" description="暂无图片素材" />
      <div v-else class="image-grid">
        <div v-for="item in imageAssets" :key="item.id" class="image-card">
          <div class="image-frame">
            <el-image
              :src="buildAssetAuthUrl(item.preview_url || item.url)"
              fit="cover"
              class="image-thumb"
            />
          </div>
          <div class="image-name" :title="item.name">{{ item.name }}</div>
          <div class="image-meta">{{ formatSize(item.file_size) }}</div>
          <div class="card-actions">
            <el-button link type="primary" @click="handleDownload(item)">下载</el-button>
            <el-popconfirm title="确定要删除该素材吗？" @confirm="handleDelete(item)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card">
      <div class="section-header">
        <div>
          <h2>文件素材</h2>
          <p>按列表管理，清楚查看文件名、类型、大小和上传时间。</p>
        </div>
      </div>

      <el-empty v-if="fileAssets.length === 0" description="暂无文件素材" />
      <el-table v-else :data="fileAssets" style="width: 100%">
        <el-table-column prop="name" label="文件名" min-width="280" />
        <el-table-column prop="mime_type" label="类型" min-width="180" />
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
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import { Upload } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { ASSET_UPLOAD_HINT, buildAssetAuthUrl, buildAssetDownloadHeaders, validateAssetUpload } from '@/utils/assets'

const assets = ref<any[]>([])
const loading = ref(false)
const uploading = ref(false)
const uploadHint = ASSET_UPLOAD_HINT

const isImage = (item: any) => item.material_type === 'image' || (item.mime_type || '').startsWith('image/')
const imageAssets = computed(() => assets.value.filter((item) => isImage(item)))
const fileAssets = computed(() => assets.value.filter((item) => !isImage(item)))

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
  const validation = validateAssetUpload(options.file, 'all')
  if (!validation.valid) {
    ElMessage.warning(validation.message)
    return
  }

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
    await fetchAssets()
  } catch (error) {
    console.error(error)
  } finally {
    uploading.value = false
  }
}

const handleDownload = async (row: any) => {
  const targetUrl = row.download_url || row.url
  try {
    const response = await axios.get(targetUrl, {
      responseType: 'blob',
      headers: buildAssetDownloadHeaders()
    })
    const downloadUrl = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = row.name || 'asset'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(downloadUrl)
  } catch (error) {
    console.error(error)
  }
}

const handleDelete = async (row: any) => {
  try {
    await request.delete('/v1/assets/' + row.id)
    ElMessage.success('删除成功')
    await fetchAssets()
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
  max-width: 1240px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 18px;
}

.title-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.page-title {
  margin: 0;
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.upload-btn {
  flex-shrink: 0;
}

.upload-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.summary-strip {
  display: flex;
  gap: 12px;
  margin-bottom: 18px;
}

.summary-chip {
  min-width: 110px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  background: #fff;
}

.summary-label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.section-card {
  margin-bottom: 18px;
  border-radius: 14px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h2 {
  margin: 0 0 4px;
  font-size: 18px;
}

.section-header p {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 14px;
}

.image-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 10px;
  background: #fff;
}

.image-frame {
  aspect-ratio: 1 / 1;
  border-radius: 10px;
  overflow: hidden;
  background: #f5f7fa;
  margin-bottom: 10px;
}

.image-thumb {
  width: 100%;
  height: 100%;
}

.image-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.image-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.card-actions {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}
</style>
