<template>
  <div class="card-panel">
    <div class="card-header">
      <el-icon color="#3b82f6"><Monitor /></el-icon>
      <h3 class="card-header-title">预览结果</h3>
    </div>
    <div class="card-body">
      <div v-if="isPreviewing" class="loading-state" style="padding: 20px; text-align: center;">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <div style="margin-top: 8px; color: var(--text-muted); font-size: 13px;">正在生成预览...</div>
      </div>
      <pre v-else class="preview-box">{{ previewResult }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Monitor, Loading } from '@element-plus/icons-vue'

defineProps({
  previewResult: { type: String, default: '暂无预览...' },
  isPreviewing: { type: Boolean, default: false }
})
</script>
