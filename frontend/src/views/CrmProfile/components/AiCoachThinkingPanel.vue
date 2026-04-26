<template>
  <div class="ai-thinking-box">
    <div class="ai-thinking-box__header" @click="thinkingDone && (collapsed = !collapsed)" :style="thinkingDone ? 'cursor:pointer' : ''">
      <el-icon class="ai-thinking-box__icon" :class="{ 'is-loading': streaming && !thinkingContent }"><MagicStick /></el-icon>
      <span>思考摘要</span>
      <span v-if="thinkingDone" style="margin-left:auto; font-size:11px; color:#94a3b8;">{{ collapsed ? '展开' : '收起' }}</span>
    </div>
    <div v-if="!collapsed" class="ai-thinking-box__body">
      <template v-if="loadingStage && !thinkingContent">
        <div class="ai-skeleton-line" style="width: 80%"></div>
        <div class="ai-skeleton-line" style="width: 60%"></div>
        <div class="ai-skeleton-line" style="width: 45%"></div>
      </template>
      <MarkdownRenderer v-else :content="thinkingContent || '正在整理当前客户的关键信息与回复思路...'" :streaming="streaming && !thinkingDone" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { MagicStick } from '@element-plus/icons-vue'
import MarkdownRenderer from '#/components/markdown/MarkdownRenderer.vue'

const props = defineProps<{
  thinkingContent?: string
  loadingStage?: 'prepare' | 'model_call'
  streaming?: boolean
  thinkingDone?: boolean
}>()

const collapsed = ref(false)

watch(() => props.thinkingDone, (val) => {
  if (val) {
    setTimeout(() => { collapsed.value = true }, 300)
  }
})
</script>

<style scoped>
.ai-thinking-box { margin-bottom: 12px; padding: 10px 14px; border-radius: 12px; background: #f8fafc; border: 1px dashed #e5e7eb; max-width: 420px; }
.ai-thinking-box__header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; font-size: 12px; font-weight: 600; color: #6b7280; }
.ai-thinking-box__icon { font-size: 13px; }
.ai-thinking-box__icon.is-loading { color: #6366f1; animation: spin 2s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }
.ai-skeleton-line { height: 12px; border-radius: 6px; background: linear-gradient(90deg, #e5e7eb 25%, #f3f4f6 50%, #e5e7eb 75%); background-size: 200% 100%; animation: skeleton-breathe 1.5s ease-in-out infinite; margin-bottom: 8px; }
@keyframes skeleton-breathe { 0%, 100% { background-position: 200% 0; } 50% { background-position: -200% 0; } }
:global(html.dark) .ai-skeleton-line { background: linear-gradient(90deg, #374151 25%, #4b5563 50%, #374151 75%); background-size: 200% 100%; }
.ai-thinking-box__body { max-height: 120px; overflow-y: auto; font-size: 12px; line-height: 1.65; color: #6b7280; word-break: break-word; }
</style>
