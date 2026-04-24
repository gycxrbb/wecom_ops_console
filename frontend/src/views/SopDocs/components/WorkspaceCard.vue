<template>
  <button type="button" class="ws-card" @click="$emit('click', workspace)">
    <div class="ws-card__name">{{ workspace.name }}</div>
    <div style="margin-bottom: 8px;">
      <span class="ws-card__badge" :class="`ws-card__badge--${workspace.workspace_type}`">
        {{ typeLabel }}
      </span>
      <span v-if="workspace.status" class="ws-card__badge ws-card__badge--status" style="opacity:.7">
        {{ statusLabel }}
      </span>
    </div>
    <div class="ws-card__meta" v-if="workspace.current_stage_label">
      当前阶段：{{ workspace.current_stage_label }}
    </div>
    <div class="ws-card__meta">
      <span v-if="workspace.owner_name">负责人：{{ workspace.owner_name }}</span>
      <span v-if="workspace.doc_count !== undefined"> · {{ workspace.doc_count }} 篇文档</span>
    </div>
    <div class="ws-card__meta" style="opacity:.6;">{{ workspaceDescription }}</div>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ workspace: any }>()
defineEmits<{ click: [workspace: any] }>()

const typeLabels: Record<string, string> = {
  project: '项目',
  campaign: '活动',
  customer: '客户',
  template_hub: '模板库',
  inbox: '待整理',
}
const typeLabel = computed(() => typeLabels[props.workspace.workspace_type] || props.workspace.workspace_type)

const statusLabels: Record<string, string> = {
  planning: '筹备中',
  running: '进行中',
  reviewing: '复盘中',
  archived: '已归档',
}
const statusLabel = computed(() => statusLabels[props.workspace.status] || props.workspace.status || '')

const fallbackDescriptions: Record<string, string> = {
  template_hub: '沉淀可复用的标准模板',
  inbox: '先放这里，后续再整理归类',
}
const workspaceDescription = computed(() =>
  props.workspace.description || fallbackDescriptions[props.workspace.workspace_type] || '',
)
</script>
