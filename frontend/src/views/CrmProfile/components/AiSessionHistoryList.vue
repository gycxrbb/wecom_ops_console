<template>
  <div class="ai-history-panel">
    <div class="ai-history-panel__actions">
      <el-input
        v-model="searchKeyword"
        size="small"
        placeholder="搜索对话"
        clearable
        class="ai-history-panel__search"
        @input="onSearchInput"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button class="ai-history-panel__new-btn" size="small" @click="$emit('new-session')">开始新对话</el-button>
    </div>

    <div v-if="loading" class="ai-history-panel__empty">正在加载历史对话...</div>
    <div v-else-if="!sessions.length" class="ai-history-panel__empty">当前客户还没有历史对话</div>
    <div v-else class="ai-history-panel__list">
      <!-- Pinned group -->
      <template v-if="pinnedSessions.length">
        <div class="ai-history-group-label">置顶对话</div>
        <SessionCard
          v-for="session in pinnedSessions" :key="session.session_id"
          :session="session" :active-session-id="activeSessionId"
          :search-keyword="searchKeyword"
          :renaming-session-id="renamingSessionId"
          @select="$emit('select', $event)"
          @start-rename="startRename"
          @confirm-rename="confirmRename"
          @cancel-rename="cancelRename"
          @toggle-pin="$emit('toggle-pin', $event)"
          @delete="$emit('delete', $event)"
        />
      </template>
      <!-- Other sessions -->
      <template v-if="otherSessions.length">
        <div v-if="pinnedSessions.length" class="ai-history-group-label">其他对话</div>
        <SessionCard
          v-for="session in otherSessions" :key="session.session_id"
          :session="session" :active-session-id="activeSessionId"
          :search-keyword="searchKeyword"
          :renaming-session-id="renamingSessionId"
          @select="$emit('select', $event)"
          @start-rename="startRename"
          @confirm-rename="confirmRename"
          @cancel-rename="cancelRename"
          @toggle-pin="$emit('toggle-pin', $event)"
          @delete="$emit('delete', $event)"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { AiSessionSummary } from '../composables/useAiCoach'
import SessionCard from './AiSessionCard.vue'

const props = defineProps<{
  sessions: AiSessionSummary[]
  loading: boolean
  activeSessionId?: string | null
}>()

const emit = defineEmits<{
  select: [sessionId: string]
  'new-session': []
  search: [keyword: string]
  rename: [sessionId: string, title: string]
  'toggle-pin': [sessionId: string]
  delete: [sessionId: string]
}>()

const searchKeyword = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null

const onSearchInput = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => emit('search', searchKeyword.value), 300)
}

const pinnedSessions = computed(() => props.sessions.filter(s => s.is_pinned))
const otherSessions = computed(() => props.sessions.filter(s => !s.is_pinned))

// Inline rename state
const renamingSessionId = ref<string | null>(null)

const startRename = ({ sessionId }: { sessionId: string }) => {
  renamingSessionId.value = sessionId
}
const confirmRename = (sessionId: string, newTitle: string) => {
  emit('rename', sessionId, newTitle)
  renamingSessionId.value = null
}
const cancelRename = () => {
  renamingSessionId.value = null
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
  gap: 8px;
  align-items: center;
}

.ai-history-panel__search {
  flex: 1;
}

.ai-history-panel__new-btn {
  flex-shrink: 0;
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

.ai-history-group-label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 4px 2px;
}
</style>
