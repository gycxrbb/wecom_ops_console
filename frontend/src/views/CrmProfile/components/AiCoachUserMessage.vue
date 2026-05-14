<template>
  <div class="ai-msg ai-msg--user">
    <div class="ai-avatar ai-avatar--user">
      <img v-if="userAvatar || isAdmin" :src="userAvatar || '/images/admain.jpg'" style="width: 100%; height: 100%; object-fit: cover; border-radius: inherit;" />
      <span v-else class="ai-avatar-text">{{ (userDisplayName || '我').substring(0, 1) }}</span>
    </div>
    <div class="ai-msg-content">
      <div v-if="msg.attachments?.length" class="ai-msg-attachments">
        <template v-for="(att, idx) in msg.attachments" :key="idx">
          <!-- Image thumbnail -->
          <div v-if="att.mime_type?.startsWith('image/')" class="ai-msg-att-image" @click="previewImage(att)">
            <img :src="att.url" :alt="att.filename" class="ai-msg-att-img" />
          </div>
          <!-- File chip -->
          <a v-else :href="att.url" target="_blank" class="ai-msg-att-file-card">
            <div class="ai-att-card-file-icon" :class="getFileIconClass(att.filename)">
              <el-icon :size="20"><Document /></el-icon>
            </div>
            <div class="ai-att-card-file-info">
              <span class="ai-msg-att-label">{{ att.filename }}</span>
              <span class="ai-msg-att-size">{{ formatSize(att.file_size) }}</span>
            </div>
          </a>
        </template>
      </div>
      <div class="ai-msg-bubble">
        <MarkdownRenderer :content="msg.content" />
      </div>
    </div>
    <!-- Image preview overlay -->
    <el-image-viewer
      v-if="previewVisible"
      :url-list="previewUrls"
      :initial-index="previewIndex"
      @close="previewVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Document } from '@element-plus/icons-vue'
import MarkdownRenderer from '#/components/markdown/MarkdownRenderer.vue'
import type { AiAttachment, AiChatMessage } from '../composables/useAiCoach'

type UserMsg = Extract<AiChatMessage, { role: 'user' }>

const props = defineProps<{
  msg: UserMsg
  userAvatar?: string
  userDisplayName?: string
  isAdmin?: boolean
}>()

const previewVisible = ref(false)
const previewIndex = ref(0)

const imageAttachments = computed(() =>
  (props.msg.attachments || []).filter(a => a.mime_type?.startsWith('image/') && a.url)
)

const previewUrls = computed(() => imageAttachments.value.map(a => a.url!))

const previewImage = (att: AiAttachment) => {
  if (!att.url) return
  const idx = imageAttachments.value.findIndex(a => a.attachment_id === att.attachment_id)
  previewIndex.value = idx >= 0 ? idx : 0
  previewVisible.value = true
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
}

const getFileIconClass = (filename?: string) => {
  if (!filename) return 'is-unknown'
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  if (['doc', 'docx'].includes(ext)) return 'is-doc'
  if (['xls', 'xlsx', 'csv'].includes(ext)) return 'is-excel'
  if (ext === 'pdf') return 'is-pdf'
  return 'is-unknown'
}
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
.ai-msg-attachments { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.ai-msg-att-image {
  width: 120px; height: 90px; border-radius: 10px; overflow: hidden; cursor: pointer;
  border: 1px solid #e2e8f0; transition: all 0.2s; background: #f8fafc;
}
.ai-msg-att-image:hover { border-color: #6366f1; box-shadow: 0 4px 12px rgba(99,102,241,0.15); }
.ai-msg-att-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ai-msg-att-file-card {
  display: inline-flex; align-items: center; gap: 8px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 8px; min-width: 160px; max-width: 200px;
  text-decoration: none; transition: all 0.15s;
  height: 56px; box-sizing: border-box;
}
.ai-msg-att-file-card:hover { border-color: #6366f1; box-shadow: 0 2px 8px rgba(99,102,241,0.08); }
.ai-att-card-file-icon {
  width: 38px; height: 38px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; flex-shrink: 0;
}
.ai-att-card-file-icon.is-doc { background: #2b70f0; }
.ai-att-card-file-icon.is-pdf { background: #f53f3f; }
.ai-att-card-file-icon.is-excel { background: #00b42a; }
.ai-att-card-file-icon.is-unknown { background: #8b5cf6; }
.ai-att-card-file-info {
  display: flex; flex-direction: column; justify-content: center;
  overflow: hidden; min-width: 0; align-self: stretch;
}
.ai-msg-att-label { 
  font-size: 13px; font-weight: 500; color: #1f2937;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.4;
}
.ai-msg-att-size { font-size: 11px; color: #94a3b8; margin-top: 2px; line-height: 1; }
@media (max-width: 768px) {
  .ai-msg-att-image { width: 100px; height: 75px; }
}
</style>
