<template>
  <div class="ai-msg ai-msg--user">
    <div class="ai-avatar ai-avatar--user">
      <img v-if="userAvatar || isAdmin" :src="userAvatar || '/images/admain.jpg'" style="width: 100%; height: 100%; object-fit: cover; border-radius: inherit;" />
      <span v-else class="ai-avatar-text">{{ (userDisplayName || '我').substring(0, 1) }}</span>
    </div>
    <div class="ai-msg-content">
      <div v-if="msg.attachments?.length" class="ai-msg-attachments">
        <template v-for="(att, idx) in visibleAttachments" :key="idx">
          <div class="ai-msg-att-chip">
            <el-icon :size="14"><Document /></el-icon>
            <span class="ai-msg-att-label">{{ att.filename }}</span>
          </div>
        </template>
        <span v-if="msg.attachments.length > 3" class="ai-msg-att-more">
          +{{ msg.attachments.length - 3 }}
        </span>
      </div>
      <div class="ai-msg-bubble">
        <MarkdownRenderer :content="msg.content" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Document } from '@element-plus/icons-vue'
import MarkdownRenderer from '#/components/markdown/MarkdownRenderer.vue'
import type { AiChatMessage } from '../composables/useAiCoach'

type UserMsg = Extract<AiChatMessage, { role: 'user' }>

const props = defineProps<{
  msg: UserMsg
  userAvatar?: string
  userDisplayName?: string
  isAdmin?: boolean
}>()

const visibleAttachments = computed(() => (props.msg.attachments || []).slice(0, 3))
</script>

<style scoped>
.ai-msg { display: flex; align-items: flex-start; gap: 14px; position: relative; animation: msg-in 0.25s ease-out; width: 100%; }
@keyframes msg-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
.ai-msg--user { flex-direction: row-reverse; }
.ai-avatar { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.ai-avatar--user { background: #e2e8f0; color: #475569; font-weight: 600; font-size: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.ai-avatar-text { display: inline-block; transform: translateY(-1px); }
.ai-msg-content { max-width: 80%; display: flex; flex-direction: column; gap: 4px; }
.ai-msg--user .ai-msg-content { align-items: flex-end; }
.ai-msg-bubble { padding: 14px 18px; font-size: 14.5px; line-height: 1.65; word-break: break-word; transition: all 0.2s; }
.ai-msg--user .ai-msg-bubble { background: #eef2ff; color: #312e81; border-radius: 18px 4px 18px 18px; box-shadow: 0 4px 16px rgba(99,102,241,0.06); }
.ai-msg-attachments { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; }
.ai-msg-att-chip {
  display: inline-flex; align-items: center; gap: 4px;
  background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px;
  padding: 2px 8px; font-size: 12px; color: #475569;
}
.ai-msg-att-label { max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ai-msg-att-more { font-size: 12px; color: #6366f1; align-self: center; }
</style>
