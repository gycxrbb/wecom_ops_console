<template>
  <div class="markdown-editor">
    <div class="toolbar">
      <div class="toolbar__group">
        <button type="button" class="toolbar__btn" @click="insert('bold')" title="加粗"><strong>B</strong></button>
        <button type="button" class="toolbar__btn" @click="insert('h1')" title="一级标题">H1</button>
        <button type="button" class="toolbar__btn" @click="insert('h2')" title="二级标题">H2</button>
        <button type="button" class="toolbar__btn" @click="insert('h3')" title="三级标题">H3</button>
      </div>
      <div class="toolbar__sep" />
      <div class="toolbar__group">
        <button type="button" class="toolbar__btn" @click="insert('link')" title="链接">
          <el-icon :size="14"><Link /></el-icon>
        </button>
        <button type="button" class="toolbar__btn" @click="insert('image')" title="图片">
          <el-icon :size="14"><Picture /></el-icon>
        </button>
        <button type="button" class="toolbar__btn" @click="insert('quote')" title="引用">
          <el-icon :size="14"><ChatLineSquare /></el-icon>
        </button>
        <button type="button" class="toolbar__btn" @click="insert('code')" title="代码">
          <el-icon :size="14"><Document /></el-icon>
        </button>
        <button type="button" class="toolbar__btn" @click="insert('list')" title="列表">
          <el-icon :size="14"><List /></el-icon>
        </button>
      </div>
      <div class="toolbar__sep" />
      <div class="toolbar__group">
        <button type="button" class="toolbar__btn" @click="insert('time')" title="插入当前时间">
          <el-icon :size="14"><Clock /></el-icon>
        </button>
        <button type="button" class="toolbar__btn toolbar__btn--ai" @click="openAiDialog" title="AI 润色">
          <el-icon :size="14"><MagicStick /></el-icon>
        </button>
      </div>
    </div>
    <el-input
      ref="textareaRef"
      type="textarea"
      :rows="12"
      :model-value="modelValue.content || ''"
      @update:model-value="updateContent"
      placeholder="输入 Markdown 内容...&#10;&#10;支持格式:&#10;# 标题&#10;**加粗**&#10;[链接文字](url)&#10;> 引用"
      class="md-textarea"
    />
  </div>

  <!-- 链接插入弹窗 -->
  <el-dialog v-model="linkDialogVisible" title="插入链接" width="400px" append-to-body>
    <el-form label-width="80px">
      <el-form-item label="链接文字">
        <el-input v-model="linkText" placeholder="显示的文字" />
      </el-form-item>
      <el-form-item label="链接地址">
        <el-input v-model="linkUrl" placeholder="https://" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="linkDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="confirmInsertLink">插入</el-button>
    </template>
  </el-dialog>

  <!-- 图片插入弹窗 -->
  <el-dialog v-model="imageDialogVisible" title="插入图片" width="400px" append-to-body>
    <el-form label-width="80px">
      <el-form-item label="图片地址">
        <el-input v-model="imageUrl" placeholder="https://" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" link @click="showAssetPicker = true">从素材库选择</el-button>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="imageDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="confirmInsertImage">插入</el-button>
    </template>
  </el-dialog>

  <AssetPicker
    v-model:visible="showAssetPicker"
    accept-type="image"
    @select="handleAssetSelect"
  />

  <el-dialog v-model="aiDialogVisible" title="AI 润色" width="500px" append-to-body destroy-on-close>
    <el-input
      v-model="aiInstruction"
      type="textarea"
      :rows="3"
      placeholder="输入修改指令，例如：语气更正式一些 / 缩短到两句话 / 从零写一个早安问候"
    />
    <template #footer>
      <el-button @click="aiDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="aiLoading" @click="handleAiPolish">
        {{ (modelValue.content || '').trim() ? '润色' : '从零撰写' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Link, Picture, ChatLineSquare, Document, List, Clock, MagicStick } from '@element-plus/icons-vue'
import AssetPicker from './AssetPicker.vue'
import { useAiPolish } from './useAiPolish'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const textareaRef = ref<any>(null)
const linkDialogVisible = ref(false)
const imageDialogVisible = ref(false)
const showAssetPicker = ref(false)
const linkText = ref('')
const linkUrl = ref('')
const imageUrl = ref('')

// 记住插入位置
let insertType = ''

const updateContent = (val: string) => {
  emit('update:modelValue', { ...props.modelValue, content: val })
}

const insert = (type: string) => {
  insertType = type
  const textarea = textareaRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement | undefined
  const selected = textarea ? textarea.value.substring(textarea.selectionStart, textarea.selectionEnd) : ''

  if (type === 'link') {
    linkText.value = selected
    linkUrl.value = ''
    linkDialogVisible.value = true
    return
  }

  if (type === 'image') {
    imageUrl.value = ''
    imageDialogVisible.value = true
    return
  }

  let insertion = ''
  switch (type) {
    case 'bold':
      insertion = selected ? `**${selected}**` : '**加粗文字**'
      break
    case 'h1':
      insertion = `\n# ${selected || '标题'}\n`
      break
    case 'h2':
      insertion = `\n## ${selected || '标题'}\n`
      break
    case 'h3':
      insertion = `\n### ${selected || '标题'}\n`
      break
    case 'quote':
      insertion = `\n> ${selected || '引用内容'}\n`
      break
    case 'code':
      insertion = selected.includes('\n') ? `\n\`\`\`\n${selected}\n\`\`\`\n` : `\`${selected || '代码'}\``
      break
    case 'list':
      insertion = `\n- ${selected || '列表项'}\n- 列表项\n`
      break
    case 'time': {
      const now = new Date()
      const pad = (n: number) => String(n).padStart(2, '0')
      insertion = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
      break
    }
  }
  replaceSelection(textarea, insertion)
}

const confirmInsertLink = () => {
  if (!linkUrl.value) return
  const text = `[${linkText.value || '链接'}](${linkUrl.value})`
  const textarea = textareaRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement | undefined
  replaceSelection(textarea, text)
  linkDialogVisible.value = false
}

const confirmInsertImage = () => {
  if (!imageUrl.value) return
  const text = `![图片](${imageUrl.value})`
  const textarea = textareaRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement | undefined
  replaceSelection(textarea, text)
  imageDialogVisible.value = false
}

const handleAssetSelect = (asset: any) => {
  imageUrl.value = asset.preview_url || asset.url || ''
  confirmInsertImage()
}

const replaceSelection = (textarea: HTMLTextAreaElement | undefined, text: string) => {
  if (!textarea) {
    // fallback: append
    updateContent((props.modelValue.content || '') + text)
    return
  }
  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const original = props.modelValue.content || ''
  const newVal = original.substring(0, start) + text + original.substring(end)
  updateContent(newVal)
  nextTick(() => {
    textarea.focus()
    const pos = start + text.length
    textarea.setSelectionRange(pos, pos)
  })
}

const { aiDialogVisible, aiInstruction, aiLoading, openAiDialog, doPolish } = useAiPolish()

const handleAiPolish = async () => {
  const result = await doPolish(props.modelValue.content || '', 'markdown')
  if (result !== null) {
    emit('update:modelValue', { ...props.modelValue, content: result })
  }
}
</script>

<style scoped>
.markdown-editor {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}
.toolbar {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  gap: 0;
  background: var(--bg-color);
  border-bottom: 1px solid var(--border-color);
}
.toolbar__group {
  display: flex;
  align-items: center;
  gap: 2px;
}
.toolbar__sep {
  width: 1px;
  height: 18px;
  margin: 0 6px;
  background: var(--border-color);
}
.toolbar__btn {
  appearance: none;
  border: none;
  background: transparent;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 26px;
  transition: background 0.15s, color 0.15s;
}
.toolbar__btn:hover {
  background: rgba(34, 197, 94, 0.1);
  color: var(--primary-color);
}
.toolbar__btn--ai:hover {
  background: rgba(139, 92, 246, 0.1);
  color: #7c3aed;
}
.md-textarea :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  padding: 16px;
  font-size: 14px;
  line-height: 1.7;
  min-height: 260px !important;
  box-shadow: none !important;
}
</style>
