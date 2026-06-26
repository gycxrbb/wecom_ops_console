<template>
  <el-dialog
    :model-value="modelValue"
    title="销转下危机"
    width="min(92vw, 640px)"
    append-to-body
    destroy-on-close
    class="ai-crisis-dialog"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="resetLocalState"
  >
    <div class="ai-crisis-body">
      <div class="ai-crisis-summary">
        <span class="ai-crisis-summary__icon">
          <el-icon><Warning /></el-icon>
        </span>
        <div>
          <div class="ai-crisis-summary__title">生成教练成交前风险沟通话术</div>
          <div class="ai-crisis-summary__text">
            系统会结合客户档案、正式健康数据、本次补充信息和附件，输出风险分层、问诊话术、产品承接与医疗边界提醒。
          </div>
        </div>
      </div>

      <div class="ai-crisis-field">
        <label>本次补充信息</label>
        <el-input
          v-model="extraInfo"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 8 }"
          maxlength="2000"
          show-word-limit
          placeholder="例如：客户最近担心指标恶化、预算犹豫、家属支持情况、线下复查结果、想重点推出的健康管理方案..."
        />
      </div>

      <div class="ai-crisis-field">
        <div class="ai-crisis-upload-head">
          <label>补充附件</label>
          <span>最多 3 个，支持图片/PDF/Word/Excel/文本</span>
        </div>
        <input
          ref="fileInputRef"
          type="file"
          accept="image/jpeg,image/png,image/webp,application/pdf,.docx,.xlsx,.txt,.md"
          style="display:none"
          @change="onFileInputChange"
        />
        <button class="ai-crisis-upload-btn" type="button" :disabled="loading || attachments.length >= 3" @click="fileInputRef?.click()">
          <el-icon><Upload /></el-icon>
          <span>上传体检报告或沟通材料</span>
        </button>
      </div>

      <div v-if="attachments.length" class="ai-crisis-attachments">
        <div
          v-for="(att, idx) in attachments"
          :key="att.attachment_id"
          class="ai-crisis-att"
          :class="{ 'is-uploading': att.uploading }"
        >
          <div
            class="ai-crisis-att__thumb"
            :class="{ 'is-image': att.mime_type.startsWith('image/') }"
            @click="att.mime_type.startsWith('image/') && emit('preview-attachment', att)"
          >
            <img v-if="att.mime_type.startsWith('image/') && att.url" :src="att.url" alt="" />
            <el-icon v-else><Document /></el-icon>
          </div>
          <div class="ai-crisis-att__meta">
            <div class="ai-crisis-att__name">{{ att.filename }}</div>
            <div class="ai-crisis-att__status">
              {{ att.uploading ? uploadStatus(att.progress) : fileSizeLabel(att.file_size) }}
            </div>
          </div>
          <el-icon class="ai-crisis-att__remove" @click="emit('remove-attachment', idx)"><Close /></el-icon>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="confirming" :disabled="loading" @click="emit('confirm', extraInfo)">
        开始生成
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Close, Document, Upload, Warning } from '@element-plus/icons-vue'
import type { AiAttachment } from '../composables/useAiCoach'

defineProps<{
  modelValue: boolean
  attachments: AiAttachment[]
  loading?: boolean
  confirming?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'file-selected': [file: File]
  'remove-attachment': [index: number]
  'preview-attachment': [attachment: AiAttachment]
  confirm: [extraInfo: string]
}>()

const extraInfo = ref('')
const fileInputRef = ref<HTMLInputElement>()

const resetLocalState = () => {
  extraInfo.value = ''
  if (fileInputRef.value) fileInputRef.value.value = ''
}

const onFileInputChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) emit('file-selected', file)
  target.value = ''
}

const uploadStatus = (progress?: number) => {
  const pct = Math.max(1, Math.round(progress || 1))
  return pct >= 90 ? '处理中' : `上传 ${pct}%`
}

const fileSizeLabel = (size?: number) => {
  if (!size) return '已上传'
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped>
.ai-crisis-body { display: flex; flex-direction: column; gap: 18px; }
.ai-crisis-summary { display: flex; gap: 12px; padding: 14px; border: 1px solid #fee2e2; border-radius: 8px; background: #fffafa; }
.ai-crisis-summary__icon { width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center; justify-content: center; background: #ef4444; color: #fff; flex-shrink: 0; }
.ai-crisis-summary__title { font-size: 15px; font-weight: 700; color: #111827; margin-bottom: 4px; }
.ai-crisis-summary__text { font-size: 13px; line-height: 1.6; color: #6b7280; }
.ai-crisis-field { display: flex; flex-direction: column; gap: 8px; }
.ai-crisis-field label { font-size: 13px; font-weight: 700; color: #374151; }
.ai-crisis-upload-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.ai-crisis-upload-head span { font-size: 12px; color: #9ca3af; }
.ai-crisis-upload-btn { height: 42px; border: 1px dashed #d1d5db; border-radius: 8px; background: #fff; color: #4b5563; display: flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer; transition: all 0.15s; }
.ai-crisis-upload-btn:hover:not(:disabled) { border-color: #ef4444; color: #ef4444; background: #fffafa; }
.ai-crisis-upload-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ai-crisis-attachments { display: grid; gap: 10px; }
.ai-crisis-att { display: flex; align-items: center; gap: 10px; padding: 10px; border: 1px solid #f3f4f6; border-radius: 8px; background: #fff; }
.ai-crisis-att__thumb { width: 42px; height: 42px; border-radius: 8px; background: #f3f4f6; color: #6b7280; display: flex; align-items: center; justify-content: center; overflow: hidden; flex-shrink: 0; }
.ai-crisis-att__thumb.is-image { cursor: pointer; }
.ai-crisis-att__thumb img { width: 100%; height: 100%; object-fit: cover; }
.ai-crisis-att__meta { min-width: 0; flex: 1; }
.ai-crisis-att__name { font-size: 13px; font-weight: 600; color: #374151; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ai-crisis-att__status { font-size: 12px; color: #9ca3af; margin-top: 2px; }
.ai-crisis-att.is-uploading .ai-crisis-att__status { color: #ef4444; }
.ai-crisis-att__remove { color: #9ca3af; cursor: pointer; flex-shrink: 0; }
.ai-crisis-att__remove:hover { color: #ef4444; }
@media (max-width: 767px) {
  .ai-crisis-upload-head { align-items: flex-start; flex-direction: column; gap: 4px; }
}
</style>

