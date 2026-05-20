<template>
  <div class="ai-msg ai-msg--reference">
    <div class="ai-avatar ai-avatar--visual">
      <el-icon :size="18" color="#f59e0b"><PictureFilled /></el-icon>
    </div>
    <div class="ai-msg-content">
      <div class="ai-visual-card" :class="`ai-visual-card--${statusClass}`">
        <div class="ai-visual-card__header">
          <span class="ai-visual-card__badge">{{ statusLabel }}</span>
          <span class="ai-visual-card__topic">{{ msg.topic }}</span>
          <span v-if="msg.confidence" class="ai-visual-card__score">{{ (msg.confidence * 100).toFixed(0) }}%</span>
        </div>

        <!-- Manual confirm -->
        <div v-if="msg.status === 'manual_confirm_required'" class="ai-visual-confirm">
          <p class="ai-visual-confirm__question">{{ msg.confirmQuestion || '是否需要为这个问题生成一张知识卡片？' }}</p>
          <div class="ai-visual-confirm__actions">
            <el-button type="primary" size="small" @click="handleConfirm(true)">生成图片</el-button>
            <el-button size="small" @click="handleConfirm(false)">不需要</el-button>
          </div>
        </div>

        <!-- Generating placeholder -->
        <div v-else-if="msg.status === 'queued' || msg.status === 'generating'" class="ai-visual-progress">
          <el-icon class="is-loading" :size="16"><Loading /></el-icon>
          <span>知识卡片生成中...</span>
        </div>

        <!-- Failed -->
        <div v-else-if="msg.status === 'failed'" class="ai-visual-error">
          <span>{{ msg.errorMessage || '图片生成失败' }}</span>
          <el-button size="small" text type="primary" @click="$emit('retry', msg)">重试</el-button>
        </div>

        <!-- Ready with image preview -->
        <div v-else-if="msg.status === 'ready' && msg.previewUrl" class="ai-visual-preview">
          <el-image :src="msg.previewUrl" :alt="msg.topic" fit="contain"
            :preview-src-list="[msg.previewUrl]" class="ai-visual-preview__img" />
          <div class="ai-visual-actions">
            <el-button size="small" text @click="$emit('retry', msg)">重新生成</el-button>
            <el-button size="small" text @click="$emit('hide', msg)">隐藏</el-button>
            <span class="ai-visual-feedback">
              <el-button size="small" text :type="msg.feedback === 'like' ? 'primary' : ''" @click="$emit('feedback', msg, 'like')">
                <el-icon><Select /></el-icon>
              </el-button>
              <el-button size="small" text :type="msg.feedback === 'dislike' ? 'danger' : ''" @click="$emit('feedback', msg, 'dislike')">
                <el-icon><CloseBold /></el-icon>
              </el-button>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { PictureFilled, Loading, Select, CloseBold } from '@element-plus/icons-vue'
import type { AiChatMessage } from '../composables/useAiCoach'

type VisualMsg = Extract<AiChatMessage, { messageType: 'generated_visual' }>

const props = defineProps<{
  msg: VisualMsg
  sessionId?: string | null
}>()

const emit = defineEmits<{
  (e: 'retry', msg: VisualMsg): void
  (e: 'hide', msg: VisualMsg): void
  (e: 'feedback', msg: VisualMsg, feedback: 'like' | 'dislike'): void
  (e: 'confirmed', msg: VisualMsg, jobId: string | null): void
}>()

const STATUS_MAP: Record<string, string> = {
  manual_confirm_required: '待确认',
  queued: '排队中',
  generating: '生成中',
  qa_pending: '审核中',
  ready: '已生成',
  failed: '失败',
  manual_declined: '已跳过',
}

const statusLabel = computed(() => STATUS_MAP[props.msg.status] || props.msg.status)
const statusClass = computed(() => {
  if (props.msg.status === 'failed') return 'failed'
  if (props.msg.status === 'manual_confirm_required') return 'confirm'
  if (props.msg.status === 'ready') return 'ready'
  return 'progress'
})

const handleConfirm = async (confirmed: boolean) => {
  if (!confirmed) {
    ;(props.msg as any).status = 'manual_declined'
    return
  }
  // Emit confirmed event — parent (useAiCoach) handles the API call + polling
  emit('confirmed', props.msg, null)
}
</script>

<style scoped>
.ai-msg--reference { display: flex; align-items: flex-start; gap: 14px; animation: msg-in 0.25s ease-out; }
@keyframes msg-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.ai-avatar { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ai-avatar--visual { background: #fff7ed; }
.ai-msg-content { max-width: 80%; min-width: 0; }
.ai-visual-card { padding: 10px 14px; border-radius: 10px; border: 1px solid #e5e7eb; background: #f9fafb; font-size: 13px; line-height: 1.5; border-left: 3px solid #f59e0b; }
.ai-visual-card--failed { border-left-color: #f56c6c; }
.ai-visual-card--confirm { border-left-color: #e6a23c; }
.ai-visual-card--ready { border-left-color: #67c23a; }
.ai-visual-card__header { display: flex; align-items: center; gap: 6px; }
.ai-visual-card__badge { display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; color: #fff; background: #f59e0b; flex-shrink: 0; }
.ai-visual-card__topic { font-weight: 500; color: #374151; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.ai-visual-card__score { font-size: 11px; font-weight: 600; color: #f59e0b; flex-shrink: 0; }
.ai-visual-confirm { margin-top: 8px; }
.ai-visual-confirm__question { font-size: 13px; color: #606266; margin: 0 0 8px; }
.ai-visual-confirm__actions { display: flex; gap: 8px; }
.ai-visual-progress { margin-top: 6px; display: flex; align-items: center; gap: 6px; color: #909399; font-size: 13px; }
.ai-visual-error { margin-top: 6px; display: flex; align-items: center; gap: 8px; color: #f56c6c; font-size: 13px; }
.ai-visual-preview { margin-top: 8px; }
.ai-visual-preview__img { max-width: 100%; border-radius: 8px; cursor: pointer; }
.ai-visual-actions { display: flex; align-items: center; gap: 4px; margin-top: 6px; padding-top: 6px; border-top: 1px solid #f0f0f0; }
.ai-visual-feedback { display: inline-flex; gap: 2px; }
</style>
