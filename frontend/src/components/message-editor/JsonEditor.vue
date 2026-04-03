<template>
  <div class="json-editor">
    <div class="toolbar">
      <el-button size="small" text @click="formatJson">格式化</el-button>
      <el-button size="small" text @click="compressJson">压缩</el-button>
      <el-tag v-if="error" type="danger" size="small" class="error-tag">JSON 格式错误</el-tag>
      <el-tag v-else-if="jsonStr" type="success" size="small" class="error-tag">格式正确</el-tag>
    </div>
    <el-input
      type="textarea"
      :rows="rows"
      :model-value="jsonStr"
      @update:model-value="handleChange"
      :class="{ 'json-error': error }"
      placeholder="请输入 JSON 内容"
      class="json-textarea"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: any
  rows?: number
}>(), {
  rows: 8
})

const emit = defineEmits<{
  (e: 'update:modelValue', val: any): void
}>()

const jsonStr = ref('')
const error = ref(false)

watch(() => props.modelValue, (val) => {
  if (val === undefined || val === null) {
    jsonStr.value = ''
    error.value = false
    return
  }
  const newStr = JSON.stringify(val, null, 2)
  // 只在外部变化时更新，避免光标跳动
  if (newStr !== jsonStr.value) {
    jsonStr.value = newStr
    error.value = false
  }
}, { deep: true, immediate: true })

const handleChange = (val: string) => {
  jsonStr.value = val
  if (!val.trim()) {
    error.value = false
    emit('update:modelValue', {})
    return
  }
  try {
    const parsed = JSON.parse(val)
    error.value = false
    emit('update:modelValue', parsed)
  } catch {
    error.value = true
    // JSON不合法时不emit，保持上次有效值
  }
}

const formatJson = () => {
  try {
    const parsed = JSON.parse(jsonStr.value)
    jsonStr.value = JSON.stringify(parsed, null, 2)
    error.value = false
  } catch {
    error.value = true
  }
}

const compressJson = () => {
  try {
    const parsed = JSON.parse(jsonStr.value)
    jsonStr.value = JSON.stringify(parsed)
    error.value = false
  } catch {
    error.value = true
  }
}
</script>

<style scoped>
.json-editor {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}
.toolbar {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-color);
  border-bottom: 1px solid var(--border-color);
  gap: 4px;
}
.error-tag {
  margin-left: auto;
}
.json-textarea :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  padding: 14px 16px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  box-shadow: none !important;
}
.json-error :deep(.el-textarea__inner) {
  border-color: var(--el-color-danger) !important;
  border-width: 2px;
  border-style: solid;
}
</style>
