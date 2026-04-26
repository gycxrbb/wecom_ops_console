<template>
  <div class="ai-msg ai-msg--user">
    <div class="ai-avatar ai-avatar--user">
      <img v-if="userAvatar || isAdmin" :src="userAvatar || '/images/admain.jpg'" style="width: 100%; height: 100%; object-fit: cover; border-radius: inherit;" />
      <span v-else class="ai-avatar-text">{{ (userDisplayName || '我').substring(0, 1) }}</span>
    </div>
    <div class="ai-msg-content">
      <div class="ai-msg-bubble">
        <MarkdownRenderer :content="msg.content" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import MarkdownRenderer from '#/components/markdown/MarkdownRenderer.vue'
import type { AiChatMessage } from '../composables/useAiCoach'

defineProps<{
  msg: AiChatMessage
  userAvatar?: string
  userDisplayName?: string
  isAdmin?: boolean
}>()
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
</style>
