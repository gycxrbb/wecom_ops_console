<template>
  <div class="file-editor">
    <div v-if="selectedAsset" class="selected-preview">
      <el-icon :size="32" class="file-icon"><Document /></el-icon>
      <div class="preview-info">
        <div class="preview-name">{{ selectedAsset.name }}</div>
        <div class="preview-meta">
          {{ formatSize(selectedAsset.file_size) }} · {{ selectedAsset.material_type }}
        </div>
      </div>
      <el-button type="danger" :icon="Delete" circle size="small" @click="clearSelection" />
    </div>

    <div v-else class="empty-state">
      <el-button type="primary" @click="openPicker">从素材库选择文件</el-button>
    </div>

    <AssetPicker
      v-model:visible="pickerVisible"
      accept-type="file"
      @select="handleSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Document, Delete } from '@element-plus/icons-vue'
import AssetPicker from './AssetPicker.vue'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const pickerVisible = ref(false)
const selectedAsset = ref<any>(null)

const formatSize = (bytes: number) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const openPicker = () => {
  pickerVisible.value = true
}

const handleSelect = (asset: any) => {
  selectedAsset.value = asset
  emit('update:modelValue', { ...props.modelValue, asset_id: asset.id })
}

const clearSelection = () => {
  selectedAsset.value = null
  emit('update:modelValue', { ...props.modelValue, asset_id: undefined })
}

watch(() => props.modelValue, () => {
  // 初始化留空，需外部提供完整数据
}, { immediate: true })
</script>

<style scoped>
.file-editor {
  padding: 0;
}
.selected-preview {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: #f9fafb;
}
.file-icon {
  color: #909399;
  flex-shrink: 0;
}
.preview-info {
  flex: 1;
  min-width: 0;
}
.preview-name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-meta {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.empty-state {
  padding: 24px;
  text-align: center;
  border: 2px dashed var(--el-border-color);
  border-radius: 8px;
}
</style>
