<template>
  <div class="image-editor">
    <div v-if="selectedAsset" class="selected-preview">
      <el-image
        :src="selectedAsset.url"
        fit="cover"
        class="preview-thumb"
      />
      <div class="preview-info">
        <div class="preview-name">{{ selectedAsset.name }}</div>
        <div class="preview-meta">{{ formatSize(selectedAsset.file_size) }} · {{ selectedAsset.mime_type }}</div>
      </div>
      <el-button type="danger" :icon="Delete" circle size="small" @click="clearSelection" />
    </div>

    <div v-else class="empty-state">
      <el-button type="primary" @click="openPicker">从素材库选择图片</el-button>
    </div>

    <AssetPicker
      v-model:visible="pickerVisible"
      accept-type="image"
      @select="handleSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Delete } from '@element-plus/icons-vue'
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

// 初始化：如果已有 asset_id，尝试恢复
watch(() => props.modelValue, (val) => {
  if (val?.asset_id && !selectedAsset.value) {
    // 资产信息需要在组件外提供或通过接口获取
    // 这里简化处理：只设 id，不回填详细信息
  }
}, { immediate: true })
</script>

<style scoped>
.image-editor {
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
.preview-thumb {
  width: 80px;
  height: 80px;
  border-radius: 4px;
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
