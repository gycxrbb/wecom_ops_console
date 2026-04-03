<template>
  <div class="file-editor">
    <el-form label-width="100px" size="small">
      <el-form-item label="文件素材">
        <div class="asset-row">
          <el-input :model-value="selectedLabel" readonly placeholder="请选择素材库中的文件" />
          <el-button type="primary" @click="assetPickerVisible = true">选择文件</el-button>
          <el-button v-if="modelValue.asset_id" @click="clearAsset">清空</el-button>
        </div>
      </el-form-item>
    </el-form>

    <div class="field-hint">
      发送文件消息时，系统会根据所选素材自动上传到企业微信并完成发送，不需要手动填写 `media_id`。
    </div>

    <AssetPicker
      v-model:visible="assetPickerVisible"
      accept-type="file"
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

const handleAssetSelect = (asset: any) => {
  emit('update:modelValue', {
    ...props.modelValue,
    asset_id: asset.id,
    asset_name: asset.name,
    media_id: ''
  })
}

const clearAsset = () => {
  emit('update:modelValue', {
    ...props.modelValue,
    asset_id: undefined,
    asset_name: ''
  })
}
</script>

<style scoped>
.file-editor {
  padding: 0;
}
.asset-row {
  width: 100%;
  display: flex;
  gap: 8px;
}
.field-hint {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-color);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}
</style>
