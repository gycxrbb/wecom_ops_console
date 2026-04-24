<template>
  <div class="res-card" :class="{ 'res-card--editable': editable }">
    <div class="res-card__header">
      <button type="button" class="res-card__title-btn" @click="$emit('open', doc)">
        <span class="res-card__title">{{ doc.title }}</span>
      </button>
      <div v-if="editable" class="res-card__actions">
        <el-button size="small" text @click.stop="$emit('edit', doc)">
          <el-icon><EditPen /></el-icon>
        </el-button>
        <el-button size="small" text type="danger" @click.stop="handleRemove">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>
    <div class="res-card__meta">
      <span v-if="doc.relation_role" class="role-badge" :class="`role-badge--${doc.relation_role}`">
        {{ roleLabel }}
      </span>
      <span v-if="doc.doc_type">{{ docTypeLabel }}</span>
      <span v-if="doc.workspace_name" style="color:var(--primary-color);">{{ doc.workspace_name }}</span>
    </div>
    <div class="res-card__meta" style="margin-top:2px;">
      <span v-if="doc.stage_label">阶段：{{ doc.stage_label }}</span>
      <span v-if="doc.deliverable_label"> · {{ doc.deliverable_label }}</span>
    </div>
    <div v-if="doc.summary" class="res-card__summary">{{ doc.summary }}</div>
    <div v-if="doc.remark" class="res-card__remark">备注：{{ doc.remark }}</div>
    <div class="res-card__meta" style="margin-top:2px;">
      <span v-if="verificationTag" class="res-card__verify" :class="`res-card__verify--${doc.verification_status}`">
        {{ verificationTag }}
      </span>
      <span v-if="displayTime">{{ displayTime }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { EditPen, Delete } from '@element-plus/icons-vue'

const props = defineProps<{
  doc: any
  editable?: boolean
}>()
const emit = defineEmits<{
  open: [doc: any]
  edit: [doc: any]
  remove: [doc: any]
}>()

const roleLabels: Record<string, string> = {
  official: '当前在用',
  support: '参考资料',
  candidate: '备选方案',
  archive: '历史归档',
}
const roleLabel = computed(() => roleLabels[props.doc.relation_role] || props.doc.relation_role)

const docTypeLabels: Record<string, string> = {
  doc: '文档', sheet: '表格', bitable: '多维表', wiki: '知识库', folder: '文件夹',
}
const docTypeLabel = computed(() => docTypeLabels[props.doc.doc_type] || props.doc.doc_type)

const verificationTags: Record<string, string> = {
  broken: '链接失效', need_check: '待复核', unverified: '待确认',
}
const verificationTag = computed(() => verificationTags[props.doc.verification_status] || '')

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

const handleRemove = () => {
  emit('remove', props.doc)
}
</script>
