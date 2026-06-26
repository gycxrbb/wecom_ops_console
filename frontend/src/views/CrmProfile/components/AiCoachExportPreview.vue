<template>
  <aside class="ai-export-preview">
    <header class="ai-export-preview__header">
      <div class="ai-export-preview__title-group">
        <span class="ai-export-preview__eyebrow">预览与导出</span>
        <h3>{{ previewTitle }}</h3>
      </div>
      <button class="ai-export-preview__close" title="关闭预览" @click="$emit('close')">
        <el-icon><Close /></el-icon>
      </button>
    </header>

    <div class="ai-export-preview__toolbar">
      <div class="ai-export-preview__tabs" role="tablist" aria-label="预览格式">
        <button
          v-for="item in previewFormats"
          :key="item.value"
          class="ai-export-preview__tab"
          :class="{ 'is-active': previewFormat === item.value }"
          type="button"
          @click="previewFormat = item.value"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="ai-export-preview__actions">
        <el-button size="small" plain @click="copyContent">
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
        <el-select v-model="downloadFormat" size="small" class="ai-export-preview__download-select">
          <el-option label="Word" value="docx" />
          <el-option label="PDF" value="pdf" />
          <el-option label="MD" value="md" />
        </el-select>
        <el-button size="small" type="primary" :loading="downloading" @click="downloadFile">
          <el-icon><Download /></el-icon>
          下载
        </el-button>
      </div>
    </div>

    <main class="ai-export-preview__body" :class="`is-${previewFormat}`">
      <div v-if="previewFormat === 'md'" class="ai-export-preview__markdown">
        <pre>{{ message.content }}</pre>
      </div>
      <div v-else-if="previewFormat === 'docx'" class="ai-export-preview__word">
        <div class="ai-export-preview__doc-head">
          <h1>{{ previewTitle }}</h1>
          <p>{{ customerName || '当前客户' }} · AI 教练回复</p>
        </div>
        <MarkdownRenderer :content="message.content" :streaming="false" />
      </div>
      <div v-else class="ai-export-preview__pdf-shell">
        <div class="ai-export-preview__pdf-page">
          <div class="ai-export-preview__doc-head">
            <h1>{{ previewTitle }}</h1>
            <p>{{ customerName || '当前客户' }} · AI 教练回复</p>
          </div>
          <MarkdownRenderer :content="message.content" :streaming="false" />
        </div>
      </div>
    </main>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Close, CopyDocument, Download } from '@element-plus/icons-vue'
import MarkdownRenderer from '#/components/markdown/MarkdownRenderer.vue'
import type { AiChatMessage } from '../composables/useAiCoach'

type AssistantMsg = Extract<AiChatMessage, { role: 'assistant' }>
type PreviewFormat = 'md' | 'docx' | 'pdf'

const props = defineProps<{
  message: AssistantMsg
  customerId: number | null
  customerName?: string
}>()

defineEmits<{
  close: []
}>()

const previewFormats: Array<{ label: string; value: PreviewFormat }> = [
  { label: 'Word', value: 'docx' },
  { label: 'PDF', value: 'pdf' },
  { label: 'MD', value: 'md' },
]

const previewFormat = ref<PreviewFormat>('docx')
const downloadFormat = ref<PreviewFormat>('docx')
const downloading = ref(false)

const previewTitle = computed(() => {
  const firstHeading = props.message.content.match(/^#{1,3}\s+(.+)$/m)?.[1]?.trim()
  return (firstHeading || 'AI教练回复').slice(0, 60)
})

const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(props.message.content)
    ElMessage.success('已复制当前回复内容')
  } catch {
    ElMessage.warning('复制失败，请手动选择复制')
  }
}

const downloadFile = async () => {
  const format = downloadFormat.value
  if (format === 'md') {
    downloadBlob(
      new Blob([props.message.content], { type: 'text/markdown;charset=utf-8' }),
      `${safeFilename(previewTitle.value)}.md`,
    )
    return
  }
  if (!props.customerId) {
    ElMessage.warning('缺少客户 ID，无法导出 Word/PDF')
    return
  }
  downloading.value = true
  try {
    const token = localStorage.getItem('access_token')
    const response = await axios.post(
      `/api/v1/crm-customers/${props.customerId}/ai/export`,
      {
        format,
        content: props.message.content,
        title: previewTitle.value,
        customer_name: props.customerName || '',
      },
      {
        responseType: 'blob',
        withCredentials: true,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      },
    )
    const filename = parseDispositionFilename(response.headers['content-disposition'])
      || `${safeFilename(previewTitle.value)}.${format}`
    downloadBlob(response.data, filename)
    ElMessage.success('导出文件已生成')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '导出失败，请稍后重试')
  } finally {
    downloading.value = false
  }
}

const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

const parseDispositionFilename = (value?: string) => {
  if (!value) return ''
  const match = value.match(/filename\*=UTF-8''([^;]+)/i)
  if (match?.[1]) {
    try {
      return decodeURIComponent(match[1])
    } catch {
      return match[1]
    }
  }
  return value.match(/filename="?([^"]+)"?/i)?.[1] || ''
}

const safeFilename = (value: string) => value.replace(/[\\/:*?"<>|]+/g, '_').trim() || 'AI教练回复'
</script>

<style scoped>
.ai-export-preview {
  width: auto;
  min-width: 560px;
  height: 100%;
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  background: #f6f8fb;
  border-left: 1px solid #e5e7eb;
  box-shadow: -12px 0 28px rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.ai-export-preview__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 18px 12px;
  background: #ffffff;
  border-bottom: 1px solid #edf0f4;
}

.ai-export-preview__eyebrow {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: #6b7280;
}

.ai-export-preview__title-group h3 {
  margin: 0;
  font-size: 16px;
  line-height: 1.35;
  color: #111827;
  font-weight: 700;
}

.ai-export-preview__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
}

.ai-export-preview__close:hover {
  background: #f3f4f6;
  color: #374151;
}

.ai-export-preview__toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 18px;
  background: #fff;
  border-bottom: 1px solid #edf0f4;
}

.ai-export-preview__tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  padding: 4px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
}

.ai-export-preview__tab {
  height: 30px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
}

.ai-export-preview__tab.is-active {
  background: #fff;
  color: #4f46e5;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
  font-weight: 600;
}

.ai-export-preview__actions {
  display: grid;
  grid-template-columns: auto minmax(92px, 1fr) auto;
  gap: 8px;
  align-items: center;
}

.ai-export-preview__download-select {
  width: 100%;
}

.ai-export-preview__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 20px 24px;
}

.ai-export-preview__markdown {
  min-height: 100%;
  padding: 16px;
  border: 1px solid #dbe3ee;
  border-radius: 8px;
  background: #0f172a;
  color: #e5e7eb;
}

.ai-export-preview__markdown pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  font-family: "Consolas", "Microsoft YaHei", monospace;
}

.ai-export-preview__word,
.ai-export-preview__pdf-page {
  color: #1f2937;
  font-size: 14px;
  line-height: 1.75;
}

.ai-export-preview__word {
  min-height: 100%;
  padding: 32px 34px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  background: #fff;
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}

.ai-export-preview__pdf-shell {
  min-height: 100%;
  display: flex;
  justify-content: center;
}

.ai-export-preview__pdf-page {
  width: min(100%, 620px);
  min-height: 594px;
  padding: 36px 42px;
  background: #fff;
  border: 1px solid #d9dee8;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
}

.ai-export-preview__doc-head {
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid #edf0f4;
}

.ai-export-preview__doc-head h1 {
  margin: 0 0 6px;
  font-size: 20px;
  line-height: 1.35;
  color: #111827;
}

.ai-export-preview__doc-head p {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
}

@media (max-width: 980px) {
  .ai-export-preview {
    position: absolute;
    inset: 0;
    z-index: 35;
    width: 100%;
    min-width: 0;
    flex-basis: auto;
  }
}
</style>
