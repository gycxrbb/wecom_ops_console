<template>
  <div class="ai-msg ai-msg--assistant">
    <div class="ai-avatar ai-avatar--assistant">
      <img src="https://cdn.mengfugui.com/logo.png" alt="AI Coach" style="width: 100%; height: 100%; border-radius: inherit; object-fit: cover;" />
    </div>
    <div class="ai-msg-content">
      <div class="ai-msg-bubble">
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
      <div v-if="msg.content && !msg.content.startsWith('[错误]')" class="ai-msg-actions">
        <el-button size="small" text @click="$emit('copy', msg.content)">
          <el-icon><CopyDocument /></el-icon> 复制{{ msg.requiresMedicalReview ? '供内部复核' : '草稿' }}
        </el-button>
        <el-button v-if="!msg.requiresMedicalReview" size="small" text @click="$emit('mark-medical-review', msg)">
          <el-icon><Warning /></el-icon> 标记需医生确认
        </el-button>
      </div>
      <div v-if="msg.tokenUsage" class="ai-msg-tokens">Tokens: {{ msg.tokenUsage.total_tokens || 0 }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CopyDocument, Warning } from '@element-plus/icons-vue'
import MarkdownRenderer from '#/components/markdown/MarkdownRenderer.vue'
import AiCoachThinkingPanel from './AiCoachThinkingPanel.vue'
import type { AiChatMessage } from '../composables/useAiCoach'

type AssistantMsg = Extract<AiChatMessage, { role: 'assistant' }>

defineProps<{
  msg: AssistantMsg
}>()

defineEmits<{
  copy: [content: string]
  'mark-medical-review': [msg: AssistantMsg]
}>()

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
.ai-msg-content { max-width: 80%; display: flex; flex-direction: column; gap: 4px; }
.ai-msg-bubble { padding: 14px 18px; font-size: 14.5px; line-height: 1.65; word-break: break-word; transition: all 0.2s; }
.ai-msg--assistant .ai-msg-bubble { background: #ffffff; color: #374151; border-radius: 4px 18px 18px 18px; box-shadow: 0 4px 16px rgba(0,0,0,0.04); border: 1px solid #f0f2f5; }
:global(html.dark) .ai-msg--assistant .ai-msg-bubble { background: rgba(255,255,255,0.06); }
.ai-msg-placeholder { font-size: 13px; color: #9ca3af; }
.ai-msg-safety-hint { margin-top: 8px; padding: 6px 10px; border-radius: 8px; background: color-mix(in srgb, var(--el-color-warning-light-9) 60%, transparent); color: #92400e; font-size: 12px; line-height: 1.5; display: flex; align-items: flex-start; gap: 6px; }
.ai-msg-safety-hint .el-icon { margin-top: 2px; font-size: 14px; flex-shrink: 0; }
:global(html.dark) .ai-msg-safety-hint { background: color-mix(in srgb, var(--el-color-warning-dark-2) 20%, transparent); color: #fbbf24; }
.ai-safety-reasons { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px; }
.ai-safety-reason-tag { display: inline-block; padding: 1px 6px; border-radius: 4px; background: #fef3c7; color: #92400e; font-size: 11px; font-weight: 500; }
.ai-msg-actions { margin-top: 10px; display: flex; justify-content: flex-end; gap: 6px; opacity: 0; transition: opacity 0.2s; }
.ai-msg-content:hover .ai-msg-actions { opacity: 1; }
.ai-msg-actions .el-button { margin: 0; }
.ai-msg-tokens { margin-top: 6px; text-align: right; font-size: 11px; color: #d1d5db; font-variant-numeric: tabular-nums; }
</style>
