<template>
  <el-dialog v-model="visible" :title="mode === 'create' ? '新建文件夹' : '重命名文件夹'" width="400px" @close="$emit('close')">
    <el-input v-model="folderName" placeholder="输入文件夹名称" maxlength="64" @keyup.enter="handleConfirm" />
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :disabled="!folderName.trim()">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  modelValue: boolean
  mode: 'create' | 'rename'
  initialName?: string
}>()

const emit = defineEmits(['update:modelValue', 'confirm', 'close'])

const visible = ref(props.modelValue)
const folderName = ref('')

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) folderName.value = props.initialName || ''
})

watch(visible, (val) => emit('update:modelValue', val))

const handleConfirm = () => {
  const name = folderName.value.trim()
  if (!name) return
  emit('confirm', name)
  visible.value = false
}
</script>
