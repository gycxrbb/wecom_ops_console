<template>
  <div class="ai-messages" ref="messagesRef">
    <!-- Data gaps -->
    <template v-if="visibleDataGaps.length">
      <el-alert v-for="g in visibleDataGaps" :key="g" :title="g" type="warning" :closable="true" show-icon @close="$emit('dismiss-data-gap', g)" style="border-radius:10px; margin-bottom:4px;" />
    </template>

    <!-- Audit meta bar for restored history -->
    <div v-if="restoredSessionMeta && chatHistory.length" class="ai-audit-meta-bar">
      <span class="ai-audit-meta-tag">历史会话</span>
      <span v-if="restoredSessionMeta.sceneKey" class="ai-audit-meta-item">场景：{{ sceneLabel(restoredSessionMeta.sceneKey) }}</span>
      <span v-if="restoredSessionMeta.outputStyle" class="ai-audit-meta-item">模式：{{ restoredSessionMeta.outputStyle }}</span>
      <span v-if="restoredSessionMeta.promptVersion" class="ai-audit-meta-item">Prompt：{{ restoredSessionMeta.promptVersion }}</span>
    </div>

    <!-- Welcome -->
    <div class="ai-welcome-container" v-if="chatHistory.length === 0 && !disabledReason">
      <div class="ai-welcome-hero">
        <div class="ai-welcome-icon-wrap">
          <img src="https://cdn.mengfugui.com/logo.png" alt="AI Coach" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;" />
        </div>
        <h3>我是您的 <span class="ai-text-gradient">AI 教练助手</span></h3>
        <p>准备好为{{ customerName || '客户' }}提供专业的健康建议</p>
      </div>
      <div class="ai-quick-section">
        <p class="ai-quick-label"><el-icon><MagicStick /></el-icon> 快捷指令</p>
        <div class="ai-quick-grid">
          <div v-for="qp in quickPromptItems" :key="qp.text" class="ai-quick-card" @click="$emit('quick-ask', qp.text)">
            <span class="ai-quick-card__icon" :style="{ background: qp.color }">
              <el-icon :size="15" color="#fff"><component :is="qp.icon" /></el-icon>
            </span>
            <span class="ai-quick-card__text">{{ qp.text }}</span>
            <el-icon class="ai-quick-card__arrow"><ArrowRight /></el-icon>
          </div>
        </div>
      </div>
    </div>

    <!-- Messages -->
    <template v-for="(msg, i) in chatHistory" :key="i">
      <div v-if="selectMode"
        class="ai-msg-selectable"
        :class="{ 'is-selected': selectedIndices?.has(i) }"
        @click="emit('toggle-select', i)"
      >
        <el-checkbox :model-value="selectedIndices?.has(i)" @click.stop @change="emit('toggle-select', i)" class="ai-msg-checkbox" />
        <div class="ai-msg-content-wrap">
          <AiCoachAssistantMessage v-if="msg.role === 'assistant'" :msg="msg" @copy="$emit('copy', $event)" @mark-medical-review="$emit('mark-medical-review', $event)" />
          <AiCoachReferenceMessage v-else-if="msg.role === 'reference'" :msg="msg" @send-to-center="emit('send-to-center', $event)" />
          <AiCoachUserMessage v-else :msg="msg" :user-avatar="userAvatar" :user-display-name="userDisplayName" :is-admin="isAdmin" />
        </div>
      </div>
      <template v-else>
        <AiCoachAssistantMessage v-if="msg.role === 'assistant'" :msg="msg" @copy="$emit('copy', $event)" @mark-medical-review="$emit('mark-medical-review', $event)" />
        <AiCoachReferenceMessage v-else-if="msg.role === 'reference'" :msg="msg" @send-to-center="emit('send-to-center', $event)" />
        <AiCoachUserMessage v-else :msg="msg" :user-avatar="userAvatar" :user-display-name="userDisplayName" :is-admin="isAdmin" />
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { MagicStick, ArrowRight, EditPen, Search, ChatLineRound } from '@element-plus/icons-vue'
import AiCoachAssistantMessage from './AiCoachAssistantMessage.vue'
import AiCoachUserMessage from './AiCoachUserMessage.vue'
import AiCoachReferenceMessage from './AiCoachReferenceMessage.vue'
import type { AiChatMessage } from '../composables/useAiCoach'

const props = defineProps<{
  chatHistory: AiChatMessage[]
  customerName?: string
  restoredSessionMeta?: { sceneKey: string; outputStyle: string; promptVersion: string } | null
  sessionId?: string | null
  loading?: boolean
  userAvatar?: string
  userDisplayName?: string
  isAdmin?: boolean
  disabledReason?: string
  visibleDataGaps: string[]
  selectMode?: boolean
  selectedIndices?: Set<number>
}>()

const emit = defineEmits<{
  copy: [content: string]
  'mark-medical-review': [msg: AiChatMessage]
  'quick-ask': [text: string]
  'dismiss-data-gap': [gap: string]
  'toggle-select': [index: number]
  'send-to-center': [msg: AiChatMessage]
}>()

const messagesRef = ref<HTMLElement>()

function forceScrollToBottom() {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

function scrollToBottom() {
  if (messagesRef.value) {
    const el = messagesRef.value
    // If user has scrolled up more than 100px from the bottom, don't auto-scroll
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    if (isAtBottom) {
      el.scrollTop = el.scrollHeight
    }
  }
}

defineExpose({ scrollToBottom, forceScrollToBottom })

const sceneLabel = (key: string) => {
  const map: Record<string, string> = { meal_review: '餐评', data_monitoring: '数据监测', abnormal_intervention: '异常干预', qa_support: '问题答疑', period_review: '周月复盘', long_term_maintenance: '长期维护' }
  return map[key] || key
}

const quickPromptItems = [
  { text: '总结服务重点', icon: EditPen, color: '#10b981' },
  { text: '列出跟进问题', icon: Search, color: '#6366f1' },
  { text: '生成交接备注', icon: ChatLineRound, color: '#8b5cf6' },
]
</script>

<style scoped>
.ai-messages { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 28px; background: transparent; }
.ai-audit-meta-bar { display: flex; align-items: center; gap: 10px; padding: 8px 14px; background: #f0f4ff; border-radius: 10px; font-size: 12px; color: #475569; border: 1px solid #dbeafe; flex-shrink: 0; }
.ai-audit-meta-tag { background: #6366f1; color: #fff; padding: 2px 8px; border-radius: 6px; font-weight: 600; font-size: 11px; }
.ai-audit-meta-item { color: #64748b; }
/* Welcome */
.ai-welcome-container { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; padding: 32px 20px; }
.ai-welcome-hero { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 24px 20px 36px; }
.ai-welcome-icon-wrap { width: 90px; height: 90px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: linear-gradient(135deg, #eef2ff, #e0e7ff); margin-bottom: 24px; position: relative; box-shadow: inset 0 2px 10px rgba(255,255,255,0.8), 0 4px 20px rgba(99,102,241,0.08); }
.ai-welcome-hero h3 { font-size: 20px; font-weight: 700; color: #1f2937; margin: 0 0 10px; }
.ai-text-gradient { color: #6366f1; }
.ai-welcome-hero p { font-size: 14px; color: #6b7280; margin: 0; }
.ai-quick-section { width: 100%; max-width: 560px; padding: 0 8px; }
.ai-quick-label { font-size: 13px; font-weight: 600; color: #9ca3af; display: flex; align-items: center; gap: 6px; margin-bottom: 14px; padding-left: 4px; }
.ai-quick-label .el-icon { color: #6366f1; }
.ai-quick-grid { display: flex; gap: 12px; flex-wrap: wrap; }
.ai-quick-card { flex: 1 1 140px; min-width: 140px; display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: 14px; background: #fff; border: 1px solid #f0f2f5; cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 12px rgba(0,0,0,0.02); }
.ai-quick-card:hover { border-color: #6366f1; background: #fff; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(99,102,241,0.08); }
.ai-quick-card__icon { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; border-radius: 10px; flex-shrink: 0; }
.ai-quick-card__text { flex: 1; font-size: 13px; font-weight: 500; color: #374151; white-space: nowrap; }
.ai-quick-card__arrow { color: #d1d5db; font-size: 13px; flex-shrink: 0; transition: color 0.2s, transform 0.2s; }
.ai-quick-card:hover .ai-quick-card__arrow { color: #6366f1; transform: translateX(3px); }
/* Select mode */
.ai-msg-selectable { display: flex; align-items: flex-start; gap: 10px; cursor: pointer; padding: 6px 8px; border-radius: 12px; transition: background 0.15s; }
.ai-msg-selectable:hover { background: rgba(99, 102, 241, 0.04); }
.ai-msg-selectable.is-selected { background: rgba(99, 102, 241, 0.08); }
.ai-msg-checkbox { margin-top: 12px; flex-shrink: 0; }
.ai-msg-content-wrap { flex: 1; min-width: 0; }
</style>
