<template>
  <div class="image-editor">
    <el-form label-width="100px" size="small">
      <el-form-item label="图片素材">
        <div class="asset-row">
          <el-input :model-value="selectedLabel" readonly :placeholder="placeholderText" />
          <el-button type="primary" @click="assetPickerVisible = true">{{ selectButtonText }}</el-button>
          <el-button v-if="modelValue.asset_id" @click="clearAsset">清空</el-button>
        </div>
      </el-form-item>
    </el-form>

    <el-image
      v-if="previewUrl"
      :src="previewUrl"
      fit="contain"
      class="preview-image"
    />

    <div class="field-hint">{{ hintText }}</div>

    <AssetPicker
      v-model:visible="assetPickerVisible"
      accept-type="image"
      :preferred-folder="props.variant === 'emotion' ? 'emotion' : 'all'"
      @select="handleAssetSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AssetPicker from './AssetPicker.vue'
import { buildAssetAuthUrl } from '@/utils/assets'

const props = withDefaults(defineProps<{ modelValue: Record<string, any>; variant?: 'image' | 'emotion' }>(), {
  variant: 'image'
})
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

const previewUrl = computed(() => buildAssetAuthUrl(props.modelValue.asset_url || ''))
const placeholderText = computed(() => props.variant === 'emotion' ? '请选择素材库中的表情包静态图' : '请选择素材库中的图片')
const selectButtonText = computed(() => props.variant === 'emotion' ? '选择表情包' : '选择图片')
const hintText = computed(() => (
  props.variant === 'emotion'
    ? '企微群机器人不支持直接发送 GIF 动图，表情包会按静态图片发送。建议运营同学先在企微或微信客户端保存想要的表情图，再上传到素材库的“表情包”目录后选择发送。'
    : '发送图片消息时，系统会根据所选素材自动读取图片文件并转换为企业微信需要的内容，不需要手动填写服务器路径。'
))

const handleAssetSelect = (asset: any) => {
  emit('update:modelValue', {
    ...props.modelValue,
    asset_id: asset.id,
    asset_name: asset.name,
    asset_url: asset.preview_url || asset.url,
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
  border: 1px solid var(--border-color);
  margin-top: 8px;
  object-fit: contain;
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
