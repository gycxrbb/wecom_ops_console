<template>
  <div class="voice-editor">
    <el-form label-width="100px" size="small">
      <el-form-item label="语音素材">
        <div class="asset-row">
          <el-input :model-value="selectedLabel" readonly placeholder="请选择素材库中的 AMR 语音" />
          <el-button type="primary" @click="assetPickerVisible = true">选择语音</el-button>
          <el-button v-if="modelValue.asset_id" @click="clearAsset">清空</el-button>
        </div>
      </el-form-item>
    </el-form>

    <div class="field-hint">
      企业微信群机器人语音消息需要先上传素材并拿到 `media_id`。系统会自动完成上传，但素材建议使用 `AMR` 格式、大小不超过 `2MB`，且单条语音时长不要超过 `60 秒`。
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
import { ElMessage } from 'element-plus'
import AssetPicker from './AssetPicker.vue'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const assetPickerVisible = ref(false)

const selectedLabel = computed(() => {
  if (props.modelValue.asset_name) return props.modelValue.asset_name
  if (props.modelValue.asset_id) return `已选择素材 #${props.modelValue.asset_id}`
  return ''
})

const isAmrAsset = (asset: any) => {
  const name = String(asset?.name || '').toLowerCase()
  const mimeType = String(asset?.mime_type || '').toLowerCase()
  return name.endsWith('.amr') || mimeType.includes('amr')
}

const handleAssetSelect = (asset: any) => {
  if (!isAmrAsset(asset)) {
    ElMessage.warning('语音消息目前只支持选择 .amr 素材，请先上传 AMR 语音后再选择')
    return
  }
  if (Number(asset?.file_size || 0) > 2 * 1024 * 1024) {
    ElMessage.warning('语音素材大小不能超过 2MB，请压缩后再试')
    return
  }
  emit('update:modelValue', {
    ...props.modelValue,
    asset_id: asset.id,
    asset_name: asset.name,
    media_id: '',
  })
}

const clearAsset = () => {
  emit('update:modelValue', {
    ...props.modelValue,
    asset_id: undefined,
    asset_name: '',
    media_id: '',
  })
}
</script>

<style scoped>
.voice-editor {
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
  line-height: 1.6;
}
</style>
