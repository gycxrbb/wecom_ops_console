<template>
  <div class="ai-history-panel">
    <div class="ai-history-panel__actions">
      <el-button class="ai-history-panel__new-btn" size="small" @click="$emit('new-session')">开始新对话</el-button>
    </div>

    <div v-if="loading" class="ai-history-panel__empty">正在加载历史对话...</div>
    <div v-else-if="!sessions.length" class="ai-history-panel__empty">当前客户还没有历史对话</div>
    <div v-else class="ai-history-panel__list">
      <button
        v-for="session in sessions"
        :key="session.session_id"
        type="button"
        class="ai-history-item"
        :class="{ 'is-active': session.session_id === activeSessionId }"
        @click="$emit('select', session.session_id)"
      >
        <div class="ai-history-item__top">
          <span class="ai-history-item__time">{{ formatTime(session.last_message_at || session.started_at) }}</span>
          <span class="ai-history-item__count">{{ session.message_count }} 条消息</span>
        </div>
        <div class="ai-history-item__preview">{{ session.last_message_preview || '该会话暂无可展示内容' }}</div>
        <div class="ai-history-item__meta">
          <span>{{ sceneLabelMap[session.entry_scene || ''] || '客户档案问答' }}</span>
          <span class="ai-history-item__id">{{ formatSessionId(session.session_id) }}</span>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AiSessionSummary } from '../composables/useAiCoach'

defineProps<{
  sessions: AiSessionSummary[]
  loading: boolean
  activeSessionId?: string | null
}>()

defineEmits<{
  select: [sessionId: string]
  'new-session': []
}>()

const sceneLabelMap: Record<string, string> = {
  customer_profile: '客户档案进入',
  quick_prompt: '快捷提问',
  customer_list: '客户列表进入',
}

const formatSessionId = (sessionId: string) => {
  if (!sessionId) return ''
  return `会话 ${sessionId.slice(0, 8)}`
}

const formatTime = (value?: string | null) => {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  const hour = `${date.getHours()}`.padStart(2, '0')
  const minute = `${date.getMinutes()}`.padStart(2, '0')
  return `${month}-${day} ${hour}:${minute}`
}
</script>

<style scoped>
.ai-history-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-history-panel__actions {
  display: flex;
  justify-content: flex-end;
}

.ai-history-panel__new-btn {
  border-color: #d7dce5;
  background: #fff;
  color: #475569;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
}

.ai-history-panel__new-btn:hover,
.ai-history-panel__new-btn:focus {
  border-color: #b8c2d1;
  background: #f8fafc;
  color: #334155;
}

.ai-history-panel__empty {
  padding: 18px 14px;
  border-radius: 14px;
  background: #f8fafc;
  color: #64748b;
  font-size: 13px;
  text-align: center;
}

.ai-history-panel__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-history-item {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #fff;
  padding: 12px 14px;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ai-history-item:hover {
  border-color: #c7d2fe;
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.08);
}

.ai-history-item.is-active {
  border-color: #6366f1;
  background: linear-gradient(180deg, #ffffff 0%, #f5f3ff 100%);
  box-shadow: 0 10px 24px rgba(99, 102, 241, 0.12);
}

.ai-history-item__top,
.ai-history-item__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.ai-history-item__time {
  color: #111827;
  font-size: 13px;
  font-weight: 600;
}

.ai-history-item__count,
.ai-history-item__meta {
  color: #94a3b8;
  font-size: 12px;
}

.ai-history-item__preview {
  margin: 8px 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ai-history-item__id {
  color: #cbd5e1;
}
</style>
