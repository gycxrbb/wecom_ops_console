/** File upload composable for AI coach attachments. */
import { computed, reactive, ref } from 'vue'
import type { Ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { AiAttachment } from './aiCoachTypes'

interface UseAiFileUploadDeps {
  loading: Ref<boolean>
  uploadAttachmentDirect: (customerId: number, file: File, onProgress?: (pct: number) => void, contentHash?: string) => Promise<AiAttachment>
  getCustomerId: () => number | null
}

const ACCEPTED_TYPES = [
  'image/jpeg', 'image/png', 'image/webp', 'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.document',
  'text/plain', 'text/markdown',
]

async function hashFile(file: File): Promise<string> {
  try {
    if (!window.crypto?.subtle) return ''
    const digest = await window.crypto.subtle.digest('SHA-256', await file.arrayBuffer())
    return Array.from(new Uint8Array(digest))
      .map(byte => byte.toString(16).padStart(2, '0'))
      .join('')
  } catch {
    return ''
  }
}

function compressImage(file: File): Promise<File> {
  return new Promise((resolve) => {
    if (!file.type.startsWith('image/')) { resolve(file); return }
    const img = new Image()
    const objectUrl = URL.createObjectURL(file)
    img.onload = () => {
      URL.revokeObjectURL(objectUrl)
      const MAX = 1920
      let { width: w, height: h } = img
      if (w <= MAX && h <= MAX) {
        const canvas = document.createElement('canvas')
        canvas.width = w; canvas.height = h
        canvas.getContext('2d')!.drawImage(img, 0, 0)
        canvas.toBlob(
          (blob) => resolve(blob && blob.size < file.size ? new File([blob], file.name, { type: 'image/jpeg' }) : file),
          'image/jpeg', 0.8,
        )
        return
      }
      const ratio = Math.min(MAX / w, MAX / h)
      w = Math.round(w * ratio); h = Math.round(h * ratio)
      const canvas = document.createElement('canvas')
      canvas.width = w; canvas.height = h
      canvas.getContext('2d')!.drawImage(img, 0, 0, w, h)
      canvas.toBlob(
        (blob) => resolve(blob ? new File([blob], file.name, { type: 'image/jpeg' }) : file),
        'image/jpeg', 0.8,
      )
    }
    img.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      resolve(file)
    }
    img.src = objectUrl
  })
}

export function useAiFileUpload(deps: UseAiFileUploadDeps) {
  const { loading, uploadAttachmentDirect, getCustomerId } = deps

  const pendingAttachments = ref<AiAttachment[]>([])
  const uploadingCount = ref(0)
  const fileInputRef = ref<HTMLInputElement>()
  const previewDialog = reactive({
    visible: false,
    url: '',
    title: '',
  })

  const uploadingAttachment = computed(() => uploadingCount.value > 0)

  const triggerFileInput = () => {
    if (loading.value) return
    fileInputRef.value?.click()
  }

  const addAndUploadFile = async (file: File) => {
    const customerId = getCustomerId()
    if (!customerId || loading.value) return
    if (pendingAttachments.value.length >= 3) {
      ElMessage.warning('最多同时上传 3 个附件')
      return
    }
    if (!ACCEPTED_TYPES.includes(file.type)) {
      ElMessage.warning('仅支持 JPG/PNG/WebP 图片、PDF、Word、Excel、文本文件')
      return
    }

    const isImage = file.type.startsWith('image/')
    const localUrl = isImage ? URL.createObjectURL(file) : undefined
    const tempId = 'temp_' + Date.now()
    const localAtt: AiAttachment = {
      attachment_id: tempId,
      filename: file.name,
      mime_type: file.type,
      file_size: file.size,
      url: localUrl,
      uploading: true,
      progress: 0,
    }
    pendingAttachments.value.push(localAtt)

    await new Promise<void>(r => setTimeout(r, 0))
    const contentHash = await hashFile(file)
    if (contentHash) {
      const duplicate = pendingAttachments.value.find(
        att => att.attachment_id !== tempId && att.content_hash === contentHash,
      )
      if (duplicate) {
        const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempId)
        if (idx >= 0) pendingAttachments.value.splice(idx, 1)
        if (localUrl) URL.revokeObjectURL(localUrl)
        ElMessage.info('这个文件已添加，无需重复上传')
        return
      }

      const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempId)
      if (idx >= 0) pendingAttachments.value[idx].content_hash = contentHash
    }

    const uploadFile = isImage ? await compressImage(file) : file
    uploadingCount.value++
    try {
      const att = await uploadAttachmentDirect(customerId, uploadFile, (pct: number) => {
        const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempId)
        if (idx >= 0) pendingAttachments.value[idx].progress = pct
      }, contentHash)
      att.url = localUrl || att.url
      att.content_hash = att.content_hash || contentHash || undefined
      const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempId)
      if (idx >= 0) {
        att.uploading = false
        att.progress = 100
        pendingAttachments.value[idx] = att
      }
      if (att.deduped) {
        ElMessage.success('已复用相同文件，无需重复上传')
      }
    } catch (err: any) {
      const idx = pendingAttachments.value.findIndex(a => a.attachment_id === tempId)
      if (idx >= 0) pendingAttachments.value.splice(idx, 1)
      if (localUrl) URL.revokeObjectURL(localUrl)
      ElMessage.error(err?.message || '附件上传失败')
    } finally {
      uploadingCount.value--
    }
  }

  const onFileSelected = async (e: Event) => {
    const target = e.target as HTMLInputElement
    const file = target.files?.[0]
    if (file) await addAndUploadFile(file)
    target.value = ''
  }

  const onPaste = async (e: ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of items) {
      if (item.kind === 'file') {
        const file = item.getAsFile()
        if (file) {
          e.preventDefault()
          await addAndUploadFile(file)
        }
        return
      }
    }
  }

  const removeAttachment = (idx: number) => {
    const att = pendingAttachments.value[idx]
    if (att?.url?.startsWith('blob:')) {
      URL.revokeObjectURL(att.url)
    }
    pendingAttachments.value.splice(idx, 1)
  }

  const openAttachmentPreview = (att: AiAttachment) => {
    if (!att.mime_type.startsWith('image/') || !att.url) return
    previewDialog.url = att.url
    previewDialog.title = att.filename || '图片预览'
    previewDialog.visible = true
  }

  return {
    pendingAttachments,
    uploadingAttachment,
    fileInputRef,
    previewDialog,
    triggerFileInput,
    addAndUploadFile,
    onFileSelected,
    onPaste,
    removeAttachment,
    openAttachmentPreview,
  }
}
