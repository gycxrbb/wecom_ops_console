<template>
  <div class="card-panel">
    <div class="card-header">
      <div class="card-header-icon card-header-icon--blue">
        <el-icon :size="16"><Monitor /></el-icon>
      </div>
      <h3 class="card-header-title">预览结果</h3>
    </div>
    <div class="card-body">
      <div v-if="isPreviewing" class="loading-state">
        <el-icon class="is-loading" :size="28"><Loading /></el-icon>
        <div style="margin-top: 12px;">正在生成预览...</div>
      </div>
      <div v-else-if="previewResult && previewResult !== '暂无预览...'" class="preview-box">{{ previewResult }}</div>
      <div v-else class="empty-state">
        <el-icon class="empty-state__icon"><Monitor /></el-icon>
        <span class="empty-state__text">点击「预览消息」查看发送效果</span>
      </div>
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
