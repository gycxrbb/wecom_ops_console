<template>
  <div class="doc-filter-bar">
    <el-select
      :model-value="workspaceId"
      @update:model-value="$emit('update:workspaceId', $event ?? null)"
      placeholder="全部项目"
      clearable
      style="width: 200px;"
    >
      <el-option v-for="ws in workspaces" :key="ws.id" :label="ws.name" :value="ws.id" />
    </el-select>
    <el-select
      :model-value="stageTermId"
      @update:model-value="$emit('update:stageTermId', $event ?? null)"
      placeholder="全部阶段"
      clearable
      style="width: 160px;"
    >
      <el-option v-for="t in stageTerms" :key="t.id" :label="t.label" :value="t.id" />
    </el-select>
    <el-input
      :model-value="keyword"
      @update:model-value="$emit('update:keyword', $event)"
      placeholder="搜索文档标题..."
      :prefix-icon="Search"
      clearable
      style="width: 240px;"
    />
  </div>
</template>

<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'

defineProps<{
  workspaces: any[]
  stageTerms: any[]
  workspaceId: number | null
  stageTermId: number | null
  keyword: string
}>()
defineEmits<{
  'update:workspaceId': [val: number | null]
  'update:stageTermId': [val: number | null]
  'update:keyword': [val: string]
}>()
</script>
