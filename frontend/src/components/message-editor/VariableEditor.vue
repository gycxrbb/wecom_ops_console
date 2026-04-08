<template>
  <div class="variable-editor">
    <div v-if="rows.length === 0" class="empty-box">
      <div class="empty-title">当前没有自定义变量</div>
      <div class="empty-desc">点击下方按钮添加一组变量，或者保持空白直接使用内置变量。</div>
    </div>

    <div v-for="(row, index) in rows" :key="row.id" class="row-item">
      <el-input v-model="row.key" placeholder="变量名，例如 course_name" @input="syncRows" />
      <el-input v-model="row.value" placeholder="默认值，例如 减脂营" @input="syncRows" />
      <el-button text type="danger" @click="removeRow(index)">删除</el-button>
    </div>

    <div class="actions">
      <el-button size="small" @click="addRow()">新增变量</el-button>
      <el-button size="small" @click="fillExample">插入示例</el-button>
    </div>

    <el-collapse class="advanced-box">
      <el-collapse-item title="高级模式（JSON）" name="json">
        <JsonEditor
          :model-value="modelValue"
          @update:model-value="handleJsonUpdate"
          :rows="4"
        />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import JsonEditor from './JsonEditor.vue'

type VariableRow = {
  id: number
  key: string
  value: string
}

const props = defineProps<{
  modelValue: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: Record<string, any>): void
}>()

const rows = ref<VariableRow[]>([])
let rowSeed = 1
let selfUpdate = false

const rebuildRows = (value: Record<string, any>) => {
  const entries = Object.entries(value || {})
  rows.value = entries.map(([key, val]) => ({
    id: rowSeed++,
    key,
    value: val == null ? '' : String(val)
  }))
}

watch(() => props.modelValue, (value) => {
  if (selfUpdate) return
  rebuildRows(value || {})
}, { deep: true, immediate: true })

const syncRows = () => {
  const nextValue = rows.value.reduce<Record<string, string>>((acc, row) => {
    const key = row.key.trim()
    if (!key) return acc
    acc[key] = row.value
    return acc
  }, {})
  selfUpdate = true
  emit('update:modelValue', nextValue)
  Promise.resolve().then(() => { selfUpdate = false })
}

const addRow = (key = '', value = '') => {
  rows.value.push({
    id: rowSeed++,
    key,
    value
  })
}

const removeRow = (index: number) => {
  rows.value.splice(index, 1)
  syncRows()
}

const fillExample = () => {
  rows.value = [
    { id: rowSeed++, key: 'course_name', value: '减脂营' },
    { id: rowSeed++, key: 'deadline', value: '今晚 20:00' }
  ]
  syncRows()
}

const handleJsonUpdate = (value: Record<string, any>) => {
  emit('update:modelValue', value || {})
}
</script>

<style scoped>
.variable-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-box {
  padding: 16px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #fff;
}

.empty-title {
  margin-bottom: 4px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.empty-desc {
  font-size: 12px;
  color: #64748b;
}

.row-item {
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(220px, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.actions {
  display: flex;
  gap: 8px;
}

.advanced-box {
  margin-top: 4px;
}
</style>
