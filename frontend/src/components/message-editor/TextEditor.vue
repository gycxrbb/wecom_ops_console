<template>
  <div class="text-editor">
    <div class="intro-card">
      <div class="intro-card__title">发送给群成员的正文</div>
      <div class="intro-card__desc">适合通知、提醒、简单公告。直接输入用户最终会在企微里看到的内容即可。</div>
    </div>

    <el-form-item label="文本内容" class="text-editor__form-item">
      <div class="text-editor__surface">
        <div class="text-editor__surface-bar">
          <span class="text-editor__surface-label">消息正文</span>
          <span class="text-editor__surface-tip">群成员收到的就是这里的内容</span>
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
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Phone } from '@element-plus/icons-vue'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const mentionInput = ref('')
const phoneInput = ref('')
const contentLength = computed(() => String(props.modelValue.content || '').trim().length)

const updateField = (field: string, value: any) => {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}

const addMention = () => {
  const val = mentionInput.value.trim()
  if (!val) return
  const list = [...(props.modelValue.mentioned_list || [])]
  if (list.includes(val)) {
    ElMessage.warning('已存在该用户')
    return
  }
  list.push(val)
  emit('update:modelValue', { ...props.modelValue, mentioned_list: list })
  mentionInput.value = ''
}

const addMentionAll = () => {
  const list = [...(props.modelValue.mentioned_list || [])]
  if (list.includes('@all')) {
    ElMessage.warning('已添加@所有人')
    return
  }
  list.push('@all')
  emit('update:modelValue', { ...props.modelValue, mentioned_list: list })
}

const removeMention = (idx: number) => {
  const list = [...(props.modelValue.mentioned_list || [])]
  list.splice(idx, 1)
  emit('update:modelValue', { ...props.modelValue, mentioned_list: list })
}

const addPhone = () => {
  const val = phoneInput.value.trim()
  if (!val) return
  if (!/^1\d{10}$/.test(val)) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  const list = [...(props.modelValue.mentioned_mobile_list || [])]
  if (list.includes(val)) {
    ElMessage.warning('已存在该手机号')
    return
  }
  list.push(val)
  emit('update:modelValue', { ...props.modelValue, mentioned_mobile_list: list })
  phoneInput.value = ''
}

const removePhone = (idx: number) => {
  const list = [...(props.modelValue.mentioned_mobile_list || [])]
  list.splice(idx, 1)
  emit('update:modelValue', { ...props.modelValue, mentioned_mobile_list: list })
}
</script>

<style scoped>
.text-editor {
  padding: 0;
}
.intro-card {
  margin-bottom: 12px;
  padding: 12px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #f8fafc;
}
.intro-card__title {
  margin-bottom: 4px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
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
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}
.text-editor__surface:focus-within {
  border-color: rgba(34, 197, 94, 0.34);
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.08);
  background: #ffffff;
}
.text-editor__surface-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px 8px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.9);
  background: #ffffff;
}
.text-editor__surface-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  letter-spacing: 0.02em;
}
.text-editor__surface-tip {
  font-size: 12px;
  color: #cbd5e1;
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
  color: #0f172a;
  resize: vertical;
}
.text-editor__textarea :deep(.el-textarea__inner::placeholder) {
  color: #a8b3c2;
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
  color: #64748b;
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
