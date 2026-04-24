<template>
  <button type="button" class="res-card" @click="$emit('open', doc)">
    <div class="res-card__title">{{ doc.title }}</div>
    <div class="res-card__meta">
      <span v-if="doc.relation_role" class="role-badge" :class="`role-badge--${doc.relation_role}`">
        {{ roleLabel }}
      </span>
      <span v-if="doc.doc_type">{{ docTypeLabel }}</span>
      <span v-if="displayTime">{{ displayTime }}</span>
    </div>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ doc: any }>()
defineEmits<{ open: [doc: any] }>()

const roleLabels: Record<string, string> = {
  official: '当前在用',
  support: '参考资料',
  candidate: '备选方案',
  archive: '历史归档',
}
const roleLabel = computed(() => roleLabels[props.doc.relation_role] || props.doc.relation_role)

const docTypeLabels: Record<string, string> = {
  doc: '文档',
  sheet: '表格',
  bitable: '多维表',
  wiki: '知识库',
  folder: '文件夹',
}
const docTypeLabel = computed(() => docTypeLabels[props.doc.doc_type] || props.doc.doc_type)

const displayTime = computed(() => {
  const value = props.doc.last_opened_at || props.doc.updated_at
  return value ? formatDate(value) : ''
})

const formatDate = (val: string) => {
  if (!val) return ''
  const date = new Date(val)
  if (Number.isNaN(date.getTime())) return val.slice(0, 10)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
</script>
