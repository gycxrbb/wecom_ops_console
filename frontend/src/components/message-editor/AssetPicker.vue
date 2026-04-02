<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="选择素材"
    width="700px"
    append-to-body
  >
    <!-- 上传区 -->
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center">
      <el-radio-group v-model="listFilter" size="small">
        <el-radio-button label="all">全部</el-radio-button>
        <el-radio-button label="image">图片</el-radio-button>
        <el-radio-button label="file">文件</el-radio-button>
      </el-radio-group>
      <el-upload
        :http-request="handleUpload"
        :show-file-list="false"
        :accept="acceptType === 'image' ? 'image/*' : undefined"
      >
        <el-button type="primary" size="small">上传新素材</el-button>
      </el-upload>
    </div>
    <div class="upload-hint">{{ uploadHint }}</div>

    <!-- 素材列表 -->
    <div v-loading="loading" style="min-height: 200px">
      <el-empty v-if="filteredList.length === 0" description="暂无素材" />
      <!-- 图片模式：网格 -->
      <div v-if="listFilter === 'image' || listFilter === 'all'" class="asset-grid">
        <div
          v-for="item in filteredList"
          :key="item.id"
          class="asset-item"
          :class="{ selected: selectedId === item.id }"
          @click="selectedId = item.id; selectedAsset = item"
        >
          <div class="asset-thumb">
            <el-image
              v-if="isImage(item)"
              :src="buildAssetPreviewUrl(item)"
              fit="cover"
              style="width: 100%; height: 100%"
            />
            <el-icon v-else :size="32"><Document /></el-icon>
          </div>
          <div class="asset-name">{{ item.name }}</div>
        </div>
      </div>
      <!-- 文件模式：列表 -->
      <el-table
        v-if="listFilter === 'file'"
        :data="filteredList"
        highlight-current-row
        @current-change="(row: any) => { selectedId = row?.id; selectedAsset = row }"
        size="small"
      >
        <el-table-column prop="name" label="文件名" />
        <el-table-column prop="material_type" label="类型" width="80" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
      </el-table>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :disabled="!selectedId" @click="confirmSelect">确认选择</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Document } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import { ASSET_UPLOAD_HINT, buildAssetAuthUrl, validateAssetUpload } from '@/utils/assets'

const props = defineProps<{
  visible: boolean
  acceptType?: 'image' | 'file' | 'all'
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'select', asset: any): void
}>()

const assets = ref<any[]>([])
const loading = ref(false)
const listFilter = ref(props.acceptType || 'all')
const selectedId = ref<number | null>(null)
const selectedAsset = ref<any>(null)
const uploadHint = ASSET_UPLOAD_HINT

const filteredList = computed(() => {
  if (listFilter.value === 'all') return assets.value
  return assets.value.filter((a: any) => a.material_type === listFilter.value)
})

const isImage = (item: any) => item.material_type === 'image' || (item.mime_type || '').startsWith('image/')
const buildAssetPreviewUrl = (item: any) => buildAssetAuthUrl(item.preview_url || item.url)

const formatSize = (bytes: number) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const fetchAssets = async () => {
  loading.value = true
  try {
    const res = await request.get('/v1/assets')
    assets.value = res.list || res
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleUpload = async (options: any) => {
  const validation = validateAssetUpload(options.file, props.acceptType || 'all')
  if (!validation.valid) {
    ElMessage.warning(validation.message)
    return
  }

  const formData = new FormData()
  formData.append('file', options.file)
  try {
    const res = await request.post('/v1/assets', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success('上传成功')
    await fetchAssets()
    // 自动选中新上传的
    const newAsset = assets.value.find((a: any) => a.name === options.file.name)
    if (newAsset) {
      selectedId.value = newAsset.id
      selectedAsset.value = newAsset
    }
  } catch (e) {
    ElMessage.error('上传失败')
  }
}

const confirmSelect = () => {
  if (selectedAsset.value) {
    emit('select', selectedAsset.value)
    emit('update:visible', false)
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    selectedId.value = null
    selectedAsset.value = null
    listFilter.value = props.acceptType || 'all'
    fetchAssets()
  }
})
</script>

<style scoped>
.upload-hint {
  margin-bottom: 16px;
  font-size: 12px;
  color: #909399;
}
.asset-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.asset-item {
  cursor: pointer;
  border: 2px solid transparent;
  border-radius: 8px;
  padding: 8px;
  text-align: center;
  transition: border-color 0.2s;
}
.asset-item:hover {
  border-color: var(--el-color-primary-light-5);
}
.asset-item.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.asset-thumb {
  width: 100%;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 4px;
}
.asset-name {
  font-size: 12px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
