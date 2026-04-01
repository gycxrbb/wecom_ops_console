<template>
  <div class="image-editor">
    <el-form label-width="100px" size="small">
      <el-form-item label="图片素材">
        <div class="asset-row">
          <el-input :model-value="selectedLabel" readonly placeholder="请选择素材库中的图片" />
          <el-button type="primary" @click="assetPickerVisible = true">选择图片</el-button>
          <el-button v-if="modelValue.asset_id" @click="clearAsset">清空</el-button>
        </div>
      </el-form-item>
    </el-form>

    <el-image
      v-if="previewUrl"
      :src="previewUrl"
      fit="cover"
      class="preview-image"
    />

    <div class="field-hint">
      发送图片消息时，系统会根据所选素材自动读取图片文件并转换为企业微信需要的内容，不需要手动填写服务器路径。
    </div>

    <AssetPicker
      v-model:visible="assetPickerVisible"
      accept-type="image"
      @select="handleAssetSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AssetPicker from './AssetPicker.vue'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const assetPickerVisible = ref(false)

const selectedLabel = computed(() => {
  if (props.modelValue.asset_name) {
    return props.modelValue.asset_name
  }
  if (props.modelValue.asset_id) {
    return `已选择素材 #${props.modelValue.asset_id}`
  }
  return ''
})

const previewUrl = computed(() => props.modelValue.asset_url || '')

const handleAssetSelect = (asset: any) => {
  emit('update:modelValue', {
    ...props.modelValue,
    asset_id: asset.id,
    asset_name: asset.name,
    asset_url: asset.url,
    image_path: ''
  })
}

const clearAsset = () => {
  emit('update:modelValue', {
    ...props.modelValue,
    asset_id: undefined,
    asset_name: '',
    asset_url: '',
  })
}
</script>

<style scoped>
.image-editor {
  padding: 0;
}
.asset-row {
  width: 100%;
  display: flex;
  gap: 8px;
}
.preview-image {
  width: 240px;
  height: 140px;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  margin-top: 8px;
}
.field-hint {
  margin-top: 12px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 6px;
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
}
</style>
