<template>
  <div style="display:flex;align-items:center;gap:12px;">
    <el-input
      :model-value="keyword"
      @update:model-value="$emit('update:keyword', $event)"
      placeholder="搜索文档标题..."
      :prefix-icon="Search"
      clearable
      style="width:260px;"
    />
  </div>
</template>

<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'

defineProps<{ keyword: string }>()
defineEmits<{ 'update:keyword': [val: string] }>()
</script>
