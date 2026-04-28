<template>
  <div class="ai-msg ai-msg--reference">
    <div class="ai-avatar ai-avatar--reference">
      <el-icon :size="18" color="#6366f1"><Document /></el-icon>
    </div>
    <div class="ai-msg-content">
      <div class="ai-ref-card" :class="`ai-ref-card--${msg.messageType === 'rag_attachment' ? 'asset' : 'script'}`">
        <div class="ai-ref-card__header">
          <span class="ai-ref-card__badge">{{ msg.messageType === 'rag_attachment' ? '素材' : msg.content_kind === 'script' ? '话术' : '知识' }}</span>
          <span class="ai-ref-card__title">{{ msg.title }}</span>
          <span v-if="'score' in msg && msg.score" class="ai-ref-card__score">{{ (msg.score * 100).toFixed(0) }}%</span>
        </div>
        <div v-if="'snippet' in msg && msg.snippet" class="ai-ref-card__snippet">{{ msg.snippet }}</div>
        <div class="ai-ref-card__actions">
          <button v-if="'snippet' in msg && msg.snippet" class="ai-ref-action" @click="handleCopy">
            <el-icon :size="12"><CopyDocument /></el-icon> 复制
          </button>
          <a v-if="'asset' in msg && msg.asset.preview_url" :href="msg.asset.preview_url" target="_blank" class="ai-ref-action">
            <el-icon :size="12"><View /></el-icon> 预览
          </a>
          <a v-if="'asset' in msg && msg.asset.download_url" :href="msg.asset.download_url" target="_blank" class="ai-ref-action">
            <el-icon :size="12"><Download /></el-icon> 下载
          </a>
          <button v-if="msg.messageType === 'rag_attachment'" class="ai-ref-action ai-ref-action--send" @click="handleSendToCenter">
            <el-icon :size="12"><Promotion /></el-icon> 发到发送中心
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { CopyDocument, Document, View, Download, Promotion } from '@element-plus/icons-vue'
import type { AiChatMessage } from '../composables/useAiCoach'

type RefMsg = Extract<AiChatMessage, { role: 'reference' }>

const props = defineProps<{
  msg: RefMsg
}>()

const emit = defineEmits<{
  (e: 'send-to-center', msg: RefMsg): void
}>()

const handleCopy = () => {
  const text = 'snippet' in props.msg ? props.msg.snippet : ''
  if (!text) return
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制参考话术')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

const handleSendToCenter = () => {
  emit('send-to-center', props.msg)
}
</script>

<style scoped>
.ai-msg--reference { display: flex; align-items: flex-start; gap: 14px; animation: msg-in 0.25s ease-out; }
@keyframes msg-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.ai-avatar { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ai-avatar--reference { background: #eef2ff; }
:global(html.dark) .ai-avatar--reference { background: rgba(99,102,241,0.15); }
.ai-msg-content { max-width: 80%; min-width: 0; }
.ai-ref-card { padding: 10px 14px; border-radius: 10px; border: 1px solid #e5e7eb; background: #f9fafb; font-size: 13px; line-height: 1.5; }
.ai-ref-card--script { border-left: 3px solid #6366f1; }
.ai-ref-card--asset { border-left: 3px solid #10b981; }
:global(html.dark) .ai-ref-card { border-color: #374151; background: rgba(255,255,255,0.04); }
.ai-ref-card__header { display: flex; align-items: center; gap: 6px; }
.ai-ref-card__badge { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; color: #fff; background: #6366f1; flex-shrink: 0; }
.ai-ref-card--asset .ai-ref-card__badge { background: #10b981; }
.ai-ref-card__title { font-weight: 500; color: #374151; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
:global(html.dark) .ai-ref-card__title { color: #d1d5db; }
.ai-ref-card__score { font-size: 11px; font-weight: 600; color: #6366f1; flex-shrink: 0; }
.ai-ref-card__snippet { margin-top: 6px; color: #6b7280; font-size: 12px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.ai-ref-card__actions { margin-top: 6px; display: flex; gap: 10px; }
.ai-ref-action { display: inline-flex; align-items: center; gap: 3px; font-size: 12px; color: #6366f1; cursor: pointer; text-decoration: none; background: none; border: none; padding: 0; }
.ai-ref-action:hover { text-decoration: underline; }
.ai-ref-action--send { color: #10b981; }
</style>
