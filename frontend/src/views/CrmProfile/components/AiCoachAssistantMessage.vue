<template>
  <div class="ai-msg ai-msg--assistant">
    <div class="ai-avatar ai-avatar--assistant">
      <img src="https://cdn.mengfugui.com/logo.png" alt="AI Coach" style="width: 100%; height: 100%; border-radius: inherit; object-fit: cover;" />
    </div>
    <div class="ai-msg-content">
      <!-- Error card -->
      <div v-if="msg.errorCode" class="ai-msg-error-card">
        <div class="ai-msg-error-header">
          <el-icon :size="18" class="ai-msg-error-icon"><WarningFilled /></el-icon>
          <span class="ai-msg-error-title">{{ errorTitle }}</span>
        </div>
        <div class="ai-msg-error-detail">{{ msg.errorMessage }}</div>
        <div class="ai-msg-error-hint">{{ errorHint }}</div>
        <div class="ai-msg-error-actions">
          <el-button size="small" type="primary" @click="$emit('retry')">
            <el-icon><RefreshRight /></el-icon> 重新发送
          </el-button>
        </div>
        <!-- If there was partial content before error, still show it -->
        <div v-if="msg.content" class="ai-msg-error-partial">
          <div class="ai-msg-error-partial-label">已接收的部分回复：</div>
          <MarkdownRenderer :content="msg.content" :streaming="false" />
        </div>
      </div>
      <!-- Normal message bubble -->
      <div v-else class="ai-msg-bubble">
        <AiCoachThinkingPanel
          v-if="msg.thinkingVisible && (msg.thinkingContent || msg.streaming)"
          :thinking-content="msg.thinkingContent"
          :loading-stage="msg.loadingStage"
          :streaming="msg.streaming"
          :thinking-done="msg.thinkingDone"
        />
        <MarkdownRenderer v-if="msg.content" :content="msg.content" :streaming="msg.streaming" />
        <div v-else-if="msg.streaming" class="ai-msg-placeholder">正在生成正式回复...</div>
        <div v-if="msg.safetyNotes?.length || msg.requiresMedicalReview" class="ai-msg-safety-hint">
          <el-icon><Warning /></el-icon>
          <span v-if="msg.requiresMedicalReview">涉及医疗相关内容，需医生确认后方可发送给客户</span>
          <span v-else>{{ (msg.safetyNotes || []).join('；') }}</span>
          <div v-if="msg.safetyResult?.reason_codes?.length" class="ai-safety-reasons">
            <span v-for="code in msg.safetyResult.reason_codes" :key="code" class="ai-safety-reason-tag">{{ safetyCodeLabel(code) }}</span>
          </div>
        </div>
      </div>
      <div v-if="showActions" class="ai-msg-actions">
        <el-tooltip content="复制话术" placement="top" :show-after="400">
          <button class="ai-action-btn" @click="$emit('copy', extractCustomerReply)">
            <el-icon><CopyDocument /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="有帮助" placement="top" :show-after="400">
          <button class="ai-action-btn" :class="{ 'is-active is-like': feedbackRating === 'like' }" @click="onLike">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v11"/><path d="M15 5.5 13.5 10H19a2 2 0 0 1 1.7 3L18 17a2 2 0 0 1-1.7 1H7V10l2-5a4 4 0 0 1 3-2.5L15 5.5Z"/></svg>
          </button>
        </el-tooltip>
        <el-tooltip content="没帮助" placement="top" :show-after="400">
          <button class="ai-action-btn" :class="{ 'is-active is-dislike': feedbackRating === 'dislike' }" @click="onDislike">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="transform: scaleY(-1)"><path d="M7 10v11"/><path d="M15 5.5 13.5 10H19a2 2 0 0 1 1.7 3L18 17a2 2 0 0 1-1.7 1H7V10l2-5a4 4 0 0 1 3-2.5L15 5.5Z"/></svg>
          </button>
        </el-tooltip>
        <el-tooltip v-if="msg.requiresMedicalReview" content="标记需医生确认" placement="top" :show-after="400">
          <button class="ai-action-btn" @click="$emit('mark-medical-review', msg)">
            <el-icon><Warning /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="重新生成" placement="top" :show-after="400">
          <button class="ai-action-btn" @click="$emit('regenerate', msg)">
            <el-icon><RefreshRight /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="追问" placement="top" :show-after="400">
          <button class="ai-action-btn" @click="$emit('quote', msg)">
            <el-icon><ChatLineRound /></el-icon>
          </button>
        </el-tooltip>
      </div>
      <div v-if="msg.tokenUsage" class="ai-msg-tokens">Tokens: {{ msg.tokenUsage.total_tokens || 0 }}
        <template v-if="msg.tokenUsage.cached_tokens">
          · 缓存命中 {{ msg.tokenUsage.cached_tokens }}
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CopyDocument, Warning, WarningFilled, RefreshRight, ChatLineRound } from '@element-plus/icons-vue'
import MarkdownRenderer from '#/components/markdown/MarkdownRenderer.vue'
import AiCoachThinkingPanel from './AiCoachThinkingPanel.vue'
import type { AiChatMessage } from '../composables/useAiCoach'

type AssistantMsg = Extract<AiChatMessage, { role: 'assistant' }>

const props = defineProps<{
  msg: AssistantMsg
}>()

const emit = defineEmits<{
  copy: [content: string]
  'mark-medical-review': [msg: AssistantMsg]
  retry: []
  feedback: [msg: AssistantMsg, rating: 'like' | 'dislike']
  regenerate: [msg: AssistantMsg]
  quote: [msg: AssistantMsg]
}>()

const feedbackRating = computed(() => props.msg.feedback?.rating || null)

const showActions = computed(() =>
  props.msg.content && !props.msg.errorCode && !props.msg.streaming
)

const extractCustomerReply = computed(() => {
  const content = props.msg.content || ''
  const m = content.match(/```txt\s*\n([\s\S]*?)```/)
  if (m) return m[1].trim()
  return content
})

const onLike = () => {
  if (feedbackRating.value === 'like') return
  emit('feedback', props.msg, 'like')
}

const onDislike = () => {
  emit('feedback', props.msg, 'dislike')
}

const ERROR_META: Record<string, { title: string; hint: string }> = {
  connection: {
    title: 'AI 服务连接失败',
    hint: '上游 AI 服务暂时无法连接，通常是网络波动或服务商临时不可用，请稍后重试。',
  },
  timeout: {
    title: 'AI 服务响应超时',
    hint: '等待 AI 回复超时，可能是当前请求过于复杂或服务商负载较高，请缩短问题后重试。',
  },
  upstream: {
    title: 'AI 服务返回错误',
    hint: '上游 AI 服务返回了错误状态码，可能是服务商限流或临时故障，请稍后重试。',
  },
  not_configured: {
    title: 'AI 服务未配置',
    hint: '系统尚未正确配置 AI 服务密钥，请联系管理员检查 API Key 设置。',
  },
  unknown: {
    title: 'AI 服务异常',
    hint: '发生了未预期的错误，请重试。如反复出现请联系管理员。',
  },
}

const errorTitle = computed(() => ERROR_META[props.msg.errorCode || 'unknown']?.title || 'AI 服务异常')
const errorHint = computed(() => ERROR_META[props.msg.errorCode || 'unknown']?.hint || '请重试或联系管理员。')

const safetyCodeLabel = (code: string) => {
  const map: Record<string, string> = {
    medical_term: '医疗表述', exercise_contraindication_conflict: '运动禁忌冲突',
    allergen_conflict: '过敏原', allergen_conflict_severe: '严重过敏',
    high_risk_exercise_hint: '高风险运动',
  }
  return map[code] || code
}
</script>

<style scoped>
.ai-msg { display: flex; align-items: flex-start; gap: 14px; position: relative; animation: msg-in 0.25s ease-out; width: 100%; }
@keyframes msg-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.ai-avatar { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.ai-avatar--assistant { background: transparent; box-shadow: 0 4px 10px rgba(99,102,241,0.15); }
.ai-msg-content { width: 100%; max-width: min(960px, calc(100% - 54px)); display: flex; flex-direction: column; gap: 4px; }
.ai-msg-bubble { width: 100%; box-sizing: border-box; padding: 14px 18px; font-size: 14.5px; line-height: 1.65; word-break: break-word; transition: all 0.2s; }
.ai-msg--assistant .ai-msg-bubble { background: #ffffff; color: #374151; border-radius: 4px 18px 18px 18px; box-shadow: 0 4px 16px rgba(0,0,0,0.04); border: 1px solid #f0f2f5; }
:global(html.dark) .ai-msg--assistant .ai-msg-bubble { background: rgba(255,255,255,0.06); }
.ai-msg-placeholder { font-size: 13px; color: #9ca3af; }
.ai-msg-safety-hint { margin-top: 8px; padding: 6px 10px; border-radius: 8px; background: color-mix(in srgb, var(--el-color-warning-light-9) 60%, transparent); color: #92400e; font-size: 12px; line-height: 1.5; display: flex; align-items: flex-start; gap: 6px; }
.ai-msg-safety-hint .el-icon { margin-top: 2px; font-size: 14px; flex-shrink: 0; }
:global(html.dark) .ai-msg-safety-hint { background: color-mix(in srgb, var(--el-color-warning-dark-2) 20%, transparent); color: #fbbf24; }
.ai-safety-reasons { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px; }
.ai-safety-reason-tag { display: inline-block; padding: 1px 6px; border-radius: 4px; background: #fef3c7; color: #92400e; font-size: 11px; font-weight: 500; }
.ai-msg-actions { margin-top: 10px; display: flex; justify-content: flex-end; gap: 4px; opacity: 0; transition: opacity 0.2s; }
.ai-msg-content:hover .ai-msg-actions { opacity: 1; }
.ai-action-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border: none; border-radius: 8px;
  background: transparent; color: #9ca3af; cursor: pointer;
  transition: all 0.15s; font-size: 15px;
}
.ai-action-btn:hover { background: #f3f4f6; color: #374151; }
.ai-action-btn.is-active { pointer-events: auto; }
.ai-action-btn.is-like { color: #22c55e; background: rgba(34, 197, 94, 0.1); }
.ai-action-btn.is-like:hover { background: rgba(34, 197, 94, 0.18); }
.ai-action-btn.is-dislike { color: #ef4444; background: rgba(239, 68, 68, 0.1); }
.ai-action-btn.is-dislike:hover { background: rgba(239, 68, 68, 0.18); }
:global(html.dark) .ai-action-btn:hover { background: rgba(255,255,255,0.08); color: #e5e7eb; }
:global(html.dark) .ai-action-btn.is-like { color: #4ade80; background: rgba(74, 222, 128, 0.12); }
:global(html.dark) .ai-action-btn.is-dislike { color: #f87171; background: rgba(248, 113, 113, 0.12); }
.ai-msg-tokens { margin-top: 6px; text-align: right; font-size: 11px; color: #d1d5db; font-variant-numeric: tabular-nums; }

/* Error card */
.ai-msg-error-card { padding: 16px 18px; border-radius: 4px 18px 18px 18px; background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
:global(html.dark) .ai-msg-error-card { background: rgba(239,68,68,0.1); border-color: rgba(239,68,68,0.25); color: #fca5a5; }
.ai-msg-error-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ai-msg-error-icon { color: #dc2626; flex-shrink: 0; }
:global(html.dark) .ai-msg-error-icon { color: #f87171; }
.ai-msg-error-title { font-size: 14px; font-weight: 600; }
.ai-msg-error-detail { font-size: 12.5px; color: #b91c1c; margin-bottom: 6px; padding: 6px 10px; background: rgba(0,0,0,0.04); border-radius: 6px; word-break: break-all; }
:global(html.dark) .ai-msg-error-detail { color: #fca5a5; background: rgba(255,255,255,0.06); }
.ai-msg-error-hint { font-size: 12.5px; color: #92400e; line-height: 1.6; margin-bottom: 12px; }
:global(html.dark) .ai-msg-error-hint { color: #d4d4d8; }
.ai-msg-error-actions { display: flex; gap: 8px; }
.ai-msg-error-partial { margin-top: 12px; padding-top: 12px; border-top: 1px dashed #fecaca; }
.ai-msg-error-partial-label { font-size: 11px; color: #9ca3af; margin-bottom: 4px; }
@media (max-width: 768px) {
  .ai-msg { gap: 10px; }
  .ai-avatar { width: 34px; height: 34px; border-radius: 10px; }
  .ai-msg-content { max-width: calc(100% - 44px); }
  .ai-msg-bubble { padding: 12px 14px; }
}
</style>
