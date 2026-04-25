<template>
  <el-dialog
    v-model="visible"
    title="文件过大 — 建议压缩"
    width="520px"
    :close-on-click-modal="false"
    :append-to-body="true"
  >
    <div class="compress-info">
      <div class="compress-file">
        <el-icon :size="20" color="var(--el-color-warning)"><WarningFilled /></el-icon>
        <div>
          <div class="compress-file__name">{{ file?.name }}</div>
          <div class="compress-file__size">原始大小：<strong>{{ formatFileSize(file?.size || 0) }}</strong></div>
        </div>
      </div>
    </div>

    <template v-if="canCompress">
      <div class="compress-section">
        <div class="compress-section__title">选择压缩程度</div>
        <div class="compress-presets">
          <div
            v-for="(preset, index) in COMPRESS_PRESETS"
            :key="index"
            class="compress-preset"
            :class="{ 'is-active': selectedPreset === index }"
            @click="selectedPreset = index"
          >
            <div class="compress-preset__radio">
              <span class="compress-preset__dot" />
            </div>
            <div class="compress-preset__content">
              <div class="compress-preset__label">{{ preset.label }}</div>
              <div class="compress-preset__desc">{{ preset.desc }}</div>
            </div>
            <div class="compress-preset__estimate">
              ≈ {{ formatFileSize(estimatedSize) }}
            </div>
          </div>
        </div>
      </div>

      <div v-if="previewResult" class="compress-preview">
        <span>压缩后大小：<strong style="color: #67c23a">{{ formatFileSize(previewResult.compressedSize) }}</strong></span>
        <span class="compress-preview__ratio">
          减少 {{ Math.round((1 - previewResult.compressedSize / previewResult.originalSize) * 100) }}%
        </span>
      </div>
    </template>

    <template v-else>
      <div class="compress-unsupported">
        <p>该文件类型不支持自动压缩。建议在本地压缩后再上传。</p>
      </div>
    </template>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button v-if="canCompress" type="primary" @click="handleCompress" :loading="compressing">
        压缩并上传
      </el-button>
      <el-button @click="handleUploadOriginal" :loading="compressing">
        直接上传原图
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'
import {
  compressImage,
  formatFileSize,
  estimateCompressedSize,
  isCompressibleImage,
  COMPRESS_PRESETS,
} from '#/utils/imageCompress'

const props = defineProps<{
  modelValue: boolean
  file: File | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'compress', blob: Blob, originalFile: File): void
  (e: 'upload-original', file: File): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const selectedPreset = ref(1)
const compressing = ref(false)
const previewResult = ref<{ compressedSize: number; originalSize: number } | null>(null)

const canCompress = computed(() => props.file ? isCompressibleImage(props.file) : false)

const estimatedSize = computed(() => {
  if (!props.file || !canCompress.value) return 0
  const preset = COMPRESS_PRESETS[selectedPreset.value]
  return estimateCompressedSize(props.file, preset.quality)
})

// 切换预设时预览压缩效果
watch(selectedPreset, async () => {
  previewResult.value = null
  if (!props.file || !canCompress.value) return
  try {
    const preset = COMPRESS_PRESETS[selectedPreset.value]
    const result = await compressImage(props.file, {
      quality: preset.quality,
      maxWidth: preset.maxWidth,
      maxHeight: preset.maxHeight,
    })
    previewResult.value = { compressedSize: result.compressedSize, originalSize: result.originalSize }
  } catch {
    previewResult.value = null
  }
})

// 打开时重置并触发预览
watch(visible, (val) => {
  if (val) {
    selectedPreset.value = 1
    previewResult.value = null
  }
})

const handleCompress = async () => {
  if (!props.file || !canCompress.value) return
  compressing.value = true
  try {
    const preset = COMPRESS_PRESETS[selectedPreset.value]
    const result = await compressImage(props.file, {
      quality: preset.quality,
      maxWidth: preset.maxWidth,
      maxHeight: preset.maxHeight,
    })
    // 用原始文件名改后缀为 .jpg
    const newName = props.file.name.replace(/\.[^.]+$/, '.jpg')
    const newFile = new File([result.blob], newName, { type: 'image/jpeg' })
    emit('compress', result.blob, props.file)
    visible.value = false
  } catch {
    // 压缩失败，走原图
    emit('upload-original', props.file)
    visible.value = false
  } finally {
    compressing.value = false
  }
}

const handleUploadOriginal = () => {
  if (!props.file) return
  emit('upload-original', props.file)
  visible.value = false
}
</script>

<style scoped>
.compress-info {
  margin-bottom: 20px;
}
.compress-file {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(230, 162, 60, 0.06);
  border: 1px solid rgba(230, 162, 60, 0.2);
  border-radius: 10px;
}
.compress-file__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  word-break: break-all;
}
.compress-file__size {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.compress-section {
  margin-bottom: 16px;
}
.compress-section__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.compress-presets {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.compress-preset {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  flex-wrap: wrap;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
}
.compress-preset:hover {
  border-color: var(--el-color-primary);
}
.compress-preset.is-active {
  border-color: var(--el-color-primary);
  background: rgba(var(--el-color-primary-rgb), 0.04);
}
.compress-preset__radio {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: border-color 0.15s;
}
.compress-preset.is-active .compress-preset__radio {
  border-color: var(--el-color-primary);
}
.compress-preset__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: transparent;
  transition: background 0.15s;
}
.compress-preset.is-active .compress-preset__dot {
  background: var(--el-color-primary);
}
.compress-preset__content {
  flex: 1;
  min-width: 0;
}
.compress-preset__label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.compress-preset__desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}
.compress-preset__estimate {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-color-primary);
  white-space: nowrap;
}

.compress-preview {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: rgba(103, 194, 58, 0.04);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}
.compress-preview__ratio {
  font-weight: 600;
  color: #67c23a;
}

.compress-unsupported {
  padding: 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}
</style>
