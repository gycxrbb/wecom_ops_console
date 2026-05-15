<template>
  <button
    type="button"
    class="ai-history-item"
    :class="{ 'is-active': session.session_id === activeSessionId, 'is-pinned': session.is_pinned }"
    @click="!isRenaming && $emit('select', session.session_id)"
  >
    <div class="ai-history-item__top">
      <span class="ai-history-item__time">{{ formatTime(session.last_message_at || session.started_at) }}</span>
      <span class="ai-history-item__badges">
        <span v-if="session.is_pinned" class="ai-history-item__pin" title="已置顶">&#128204;</span>
        <span class="ai-history-item__count">{{ session.message_count }} 条</span>
      </span>
    </div>

    <!-- Inline rename input -->
    <div v-if="isRenaming" class="ai-history-item__rename" @click.stop>
      <el-input
        v-model="localRenameValue"
        size="small"
        maxlength="60"
        @keydown.enter="onConfirmRename"
        @keydown.escape="$emit('cancel-rename')"
      />
    </div>

    <!-- Normal display -->
    <template v-else>
      <div class="ai-history-item__preview" v-html="highlightedTitle" />
    </template>

    <div class="ai-history-item__meta">
      <span>{{ sceneLabelMap[session.entry_scene || ''] || '客户档案问答' }}</span>
      <div class="ai-history-item__actions" @click.stop>
        <el-dropdown trigger="hover" placement="bottom-end" @command="onCommand">
          <span class="ai-history-item__more">&#8943;</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="rename">重命名</el-dropdown-item>
              <el-dropdown-item command="pin">
                {{ session.is_pinned ? '取消置顶' : '置顶' }}
              </el-dropdown-item>
              <el-dropdown-item command="delete" divided style="color: #ef4444">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
  </button>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AiSessionSummary } from '../composables/useAiCoach'

const props = defineProps<{
  session: AiSessionSummary
  activeSessionId?: string | null
  searchKeyword?: string
  renamingSessionId?: string | null
}>()

const emit = defineEmits<{
  select: [sessionId: string]
  'start-rename': [payload: { sessionId: string; currentTitle: string }]
  'confirm-rename': [sessionId: string, newTitle: string]
  'cancel-rename': []
  'toggle-pin': [sessionId: string]
  delete: [sessionId: string]
}>()

const sceneLabelMap: Record<string, string> = {
  customer_profile: '客户档案进入',
  quick_prompt: '快捷提问',
  customer_list: '客户列表进入',
}

const isRenaming = computed(() => props.renamingSessionId === props.session.session_id)
const localRenameValue = ref('')

watch(isRenaming, (val) => {
  if (val) localRenameValue.value = displayTitle.value
})

const onConfirmRename = () => {
  const trimmed = localRenameValue.value.trim()
  if (trimmed) emit('confirm-rename', props.session.session_id, trimmed)
  emit('cancel-rename')
}

const displayTitle = computed(() => {
  return props.session.display_title || props.session.last_message_preview || '该会话暂无可展示内容'
})

const highlightedTitle = computed(() => {
  const text = displayTitle.value
  const kw = (props.searchKeyword || '').trim()
  if (!kw) return escapeHtml(text)
  const escaped = escapeHtml(text)
  const escapedKw = escapeHtml(kw)
  const regex = new RegExp(`(${escapeRegex(escapedKw)})`, 'gi')
  return escaped.replace(regex, '<mark>$1</mark>')
})

const onCommand = (cmd: string) => {
  if (cmd === 'rename') {
    emit('start-rename', {
      sessionId: props.session.session_id,
      currentTitle: displayTitle.value,
    })
  } else if (cmd === 'pin') {
    emit('toggle-pin', props.session.session_id)
  } else if (cmd === 'delete') {
    emit('delete', props.session.session_id)
  }
}

const formatTime = (value?: string | null) => {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  const hour = `${date.getHours()}`.padStart(2, '0')
  const minute = `${date.getMinutes()}`.padStart(2, '0')
  return `${month}-${day} ${hour}:${minute}`
}

function escapeHtml(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function escapeRegex(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
</script>

<style scoped>
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

.ai-history-item.is-pinned {
  border-left: 3px solid #f59e0b;
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

.ai-history-item__badges {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ai-history-item__pin {
  font-size: 12px;
}

.ai-history-item__count {
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

.ai-history-item__preview :deep(mark) {
  background: #fef08a;
  color: inherit;
  border-radius: 2px;
  padding: 0 1px;
}

.ai-history-item__rename {
  margin: 6px 0;
}

.ai-history-item__meta {
  color: #94a3b8;
  font-size: 12px;
}

.ai-history-item__actions {
  opacity: 0;
  transition: opacity 0.15s;
}

.ai-history-item:hover .ai-history-item__actions {
  opacity: 1;
}

.ai-history-item__more {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  font-size: 18px;
  font-weight: 700;
  color: #94a3b8;
  cursor: pointer;
}

.ai-history-item__more:hover {
  background: #f1f5f9;
  color: #475569;
}
</style>
