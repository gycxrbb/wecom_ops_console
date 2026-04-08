<template>
  <div class="text-editor">
    <!-- <div class="intro-card">
      <div class="intro-card__title">发送给群成员的正文</div>
      <div class="intro-card__desc">适合通知、提醒、简单公告。直接输入用户最终会在企微里看到的内容即可。</div>
    </div> -->

    <el-form-item label="文本内容" class="text-editor__form-item">
      <div class="text-editor__surface">
        <div class="text-editor__surface-bar">
          <span class="text-editor__surface-label">消息正文</span>
          <div class="text-editor__surface-actions">
            <button type="button" class="text-editor__insert-btn" @click="insertCurrentTime" title="插入当前时间">
              <el-icon :size="13"><Clock /></el-icon>
              <span>插入时间</span>
            </button>
            <button type="button" class="text-editor__insert-btn text-editor__insert-btn--ai" @click="openAiDialog" title="AI 润色">
              <el-icon :size="13"><MagicStick /></el-icon>
              <span>AI 润色</span>
            </button>
          </div>
        </div>
        <el-input
          type="textarea"
          :rows="8"
          :model-value="modelValue.content || ''"
          @update:model-value="updateField('content', $event)"
          placeholder="示例：&#10;今日打卡提醒&#10;请在今晚 20:00 前完成打卡并提交反馈。"
          class="text-editor__textarea"
        />
      </div>
    </el-form-item>
    <div class="text-editor__meta">
      <span>建议直接填写最终发送文案，不需要再写 JSON。</span>
      <span>{{ contentLength }} 字</span>
    </div>

    <div class="mention-section">
      <div class="mention-row">
        <span class="mention-row__label">
          <el-icon :size="14"><User /></el-icon>
          @指定人
        </span>
        <div class="mention-row__input">
          <el-input
            v-model="mentionInput"
            placeholder="输入 userid，举例：如果想@张三 那么就输入 zhangsan"
            @keyup.enter="addMention"
          />
          <el-button @click="addMention">添加</el-button>
          <el-button type="warning" plain @click="addMentionAll">@所有人</el-button>
        </div>
      </div>
      <div class="tag-list" v-if="(modelValue.mentioned_list || []).length">
        <el-tag
          v-for="(item, idx) in modelValue.mentioned_list"
          :key="idx"
          closable
          size="small"
          @close="removeMention(idx)"
          class="mention-tag"
        >
          {{ item }}
        </el-tag>
      </div>
    </div>

    <div class="mention-section">
      <div class="mention-row">
        <span class="mention-row__label">
          <el-icon :size="14"><Phone /></el-icon>
          @手机号
        </span>
        <div class="mention-row__input">
          <el-input
            v-model="phoneInput"
            placeholder="输入手机号"
            @keyup.enter="addPhone"
          />
          <el-button @click="addPhone">添加</el-button>
        </div>
      </div>
      <div class="tag-list" v-if="(modelValue.mentioned_mobile_list || []).length">
        <el-tag
          v-for="(item, idx) in modelValue.mentioned_mobile_list"
          :key="idx"
          type="success"
          closable
          size="small"
          @close="removePhone(idx)"
          class="mention-tag"
        >
          {{ item }}
        </el-tag>
      </div>
    </div>

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
  </div>
</template>

<script setup lang="ts">
import { computed, ref, toRefs } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Phone, Clock, MagicStick } from '@element-plus/icons-vue'
import { useAiPolish } from './useAiPolish'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()
const { modelValue } = toRefs(props)

const mentionInput = ref('')
const phoneInput = ref('')
const contentLength = computed(() => String(modelValue.value.content || '').trim().length)

const updateField = (field: string, value: any) => {
  emit('update:modelValue', { ...modelValue.value, [field]: value })
}

const addMention = () => {
  const val = mentionInput.value.trim()
  if (!val) return
  const list = [...(modelValue.value.mentioned_list || [])]
  if (list.includes(val)) {
    ElMessage.warning('已存在该用户')
    return
  }
  list.push(val)
  emit('update:modelValue', { ...modelValue.value, mentioned_list: list })
  mentionInput.value = ''
}

const addMentionAll = () => {
  const list = [...(modelValue.value.mentioned_list || [])]
  if (list.includes('@all')) {
    ElMessage.warning('已添加@所有人')
    return
  }
  list.push('@all')
  emit('update:modelValue', { ...modelValue.value, mentioned_list: list })
}

const removeMention = (idx: string | number) => {
  const list = [...(modelValue.value.mentioned_list || [])]
  list.splice(Number(idx), 1)
  emit('update:modelValue', { ...modelValue.value, mentioned_list: list })
}

const addPhone = () => {
  const val = phoneInput.value.trim()
  if (!val) return
  if (!/^1\d{10}$/.test(val)) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  const list = [...(modelValue.value.mentioned_mobile_list || [])]
  if (list.includes(val)) {
    ElMessage.warning('已存在该手机号')
    return
  }
  list.push(val)
  emit('update:modelValue', { ...modelValue.value, mentioned_mobile_list: list })
  phoneInput.value = ''
}

const removePhone = (idx: string | number) => {
  const list = [...(modelValue.value.mentioned_mobile_list || [])]
  list.splice(Number(idx), 1)
  emit('update:modelValue', { ...modelValue.value, mentioned_mobile_list: list })
}

const insertCurrentTime = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const timeStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
  const current = modelValue.value.content || ''
  emit('update:modelValue', { ...modelValue.value, content: current + timeStr })
}

const { aiDialogVisible, aiInstruction, aiLoading, openAiDialog, doPolish } = useAiPolish()

const handleAiPolish = async () => {
  const result = await doPolish(modelValue.value.content || '', 'text')
  if (result !== null) {
    emit('update:modelValue', { ...modelValue.value, content: result })
  }
}
</script>

<style scoped>
.text-editor {
  padding: 0;
}
.intro-card {
  margin-bottom: 12px;
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-color);
}
.intro-card__title {
  margin-bottom: 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.intro-card__desc {
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}
.text-editor__form-item {
  margin-bottom: 10px;
}
.text-editor__surface {
  width: 100%;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}
.text-editor__surface:focus-within {
  border-color: rgba(34, 197, 94, 0.34);
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.08);
}
.text-editor__surface-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px 8px;
  border-bottom: 1px solid var(--border-color);
  background: var(--card-bg);
}
.text-editor__surface-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.02em;
}
.text-editor__surface-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.text-editor__insert-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  appearance: none;
  border: none;
  border-radius: 6px;
  padding: 3px 8px;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.text-editor__insert-btn:hover {
  background: rgba(34, 197, 94, 0.1);
  color: var(--primary-color);
}
.text-editor__insert-btn--ai:hover {
  background: rgba(139, 92, 246, 0.1);
  color: #7c3aed;
}
.text-editor__textarea :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  border-radius: 0 0 16px 16px;
  padding: 16px 18px 18px;
  font-size: 14px;
  line-height: 1.8;
  min-height: 180px !important;
  background: transparent;
  color: var(--text-primary);
  resize: vertical;
}
.text-editor__textarea :deep(.el-textarea__inner::placeholder) {
  color: var(--text-muted);
  line-height: 1.9;
}
.text-editor__textarea :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}
.text-editor__meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: -4px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.mention-section {
  margin-top: 16px;
  padding: 14px 16px;
  background: var(--bg-color);
  border-radius: 10px;
  border: 1px solid var(--border-color);
}
.mention-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.mention-row__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  min-width: 72px;
}
.mention-row__input {
  display: flex;
  gap: 8px;
  flex: 1;
}
.mention-row__input .el-input {
  flex: 1;
}
.tag-list {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.mention-tag {
  margin: 0;
}
</style>
