<template>
  <button type="button" class="priority-card" @click="$emit('open', doc)">
    <div class="priority-card__number">{{ index }}</div>
    <div class="priority-card__body">
      <div class="priority-card__title">{{ doc.title }}</div>
      <div class="priority-card__meta">
        <span v-if="doc.workspace_name">{{ doc.workspace_name }}</span>
        <span v-if="doc.stage_label">{{ doc.stage_label }}</span>
        <span>{{ doc.updated_at?.slice(0, 10) }}<template v-if="doc.updated_by_name"> · {{ doc.updated_by_name }}</template></span>
      </div>
      <div v-if="doc.remark" class="priority-card__remark">{{ doc.remark }}</div>
    </div>
    <el-icon class="priority-card__arrow"><ArrowRight /></el-icon>
  </button>
</template>

<script setup lang="ts">
import { ArrowRight } from '@element-plus/icons-vue'

defineProps<{
  doc: any
  index: number
}>()
defineEmits<{ open: [doc: any] }>()
</script>
