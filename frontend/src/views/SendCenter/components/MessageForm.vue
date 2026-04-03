<template>
  <div class="card-panel">
    <div class="card-header">
      <div class="card-header-icon card-header-icon--green">
        <el-icon :size="16"><EditPen /></el-icon>
      </div>
      <h3 class="card-header-title">消息内容</h3>
    </div>
    <div class="card-body">
      <!-- Config Bar -->
      <div class="config-bar">
        <div class="config-bar__item">
          <label class="config-bar__label">
            <el-icon :size="14"><ChatDotRound /></el-icon>
            发送群组 <span class="required-star">*</span>
          </label>
          <el-select
            v-model="form.groups"
            multiple
            placeholder="选择目标群组"
            filterable
            class="config-bar__select"
          >
            <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </div>
        <div class="config-bar__item">
          <label class="config-bar__label">
            <el-icon :size="14"><Document /></el-icon>
            引用模板
          </label>
          <el-select
            :model-value="selectedTemplate"
            @update:model-value="$emit('update:selectedTemplate', $event)"
            @change="$emit('templateChange', $event)"
            placeholder="选择已有的消息模板"
            clearable
            class="config-bar__select"
          >
            <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </div>
        <div class="config-bar__item">
          <label class="config-bar__label">
            <el-icon :size="14"><Memo /></el-icon>
            消息类型 <span class="required-star">*</span>
          </label>
          <el-select
            :model-value="form.msg_type"
            @update:model-value="$emit('msgTypeChange', $event)"
            class="config-bar__select"
          >
            <el-option label="文本" value="text" />
            <el-option label="Markdown" value="markdown" />
            <el-option label="图片" value="image" />
            <el-option label="图文" value="news" />
            <el-option label="文件" value="file" />
            <el-option label="模板卡片" value="template_card" />
          </el-select>
        </div>
      </div>

      <!-- Message Editor -->
      <MessageEditor
        :model-value="form.contentJson"
        @update:model-value="$emit('contentUpdate', $event)"
        :msg-type="form.msg_type"
        :variables="form.variables"
        @update:variables="$emit('variablesUpdate', $event)"
        :show-variables="supportsVariables"
        style="width: 100%"
      />

      <!-- Action Footer -->
      <div class="action-footer">
        <el-button size="large" @click="$emit('preview')" :loading="isPreviewing">
          <template #icon><el-icon><View /></el-icon></template>
          预览消息
        </el-button>
        <el-button size="large" type="warning" @click="$emit('sendTest')" :loading="isTestSending">
          <template #icon><el-icon><Position /></el-icon></template>
          发送到测试群
        </el-button>
        <el-button size="large" type="primary" @click="$emit('send')" :loading="isSending">
          <template #icon><el-icon><Position /></el-icon></template>
          立即发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { EditPen, View, Position, ChatDotRound, Document, Memo } from '@element-plus/icons-vue'
import MessageEditor from '@/components/message-editor/index.vue'
import type { PropType } from 'vue'

const props = defineProps({
  form: { type: Object as PropType<any>, required: true },
  groups: { type: Array as PropType<any[]>, required: true },
  templates: { type: Array as PropType<any[]>, required: true },
  selectedTemplate: { type: [Number, String, null] as PropType<number | string | null> },
  isPreviewing: { type: Boolean, default: false },
  isSending: { type: Boolean, default: false },
  isTestSending: { type: Boolean, default: false }
})

defineEmits(['templateChange', 'preview', 'send', 'sendTest', 'update:selectedTemplate', 'msgTypeChange', 'contentUpdate', 'variablesUpdate'])

const variableEnabledTypes = new Set(['text', 'markdown', 'news', 'template_card'])
const supportsVariables = computed(() => !!props.selectedTemplate || variableEnabledTypes.has(props.form?.msg_type))
</script>

<style scoped>
/* Config Bar */
.config-bar {
  display: flex;
  gap: 16px;
  padding: 18px 20px;
  background: var(--bg-color);
  border-radius: 12px;
  border: 1px solid var(--border-color);
  margin-bottom: 20px;
}
.config-bar__item {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.config-bar__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  letter-spacing: 0.01em;
}
.config-bar__label .el-icon {
  color: var(--text-muted);
}
.config-bar__select {
  width: 100%;
}
.config-bar__select :deep(.el-input__wrapper) {
  border-radius: 8px;
}

.required-star {
  color: #f56c6c;
  margin-left: 1px;
}

/* Responsive */
@media (max-width: 1100px) {
  .config-bar {
    flex-direction: column;
    gap: 14px;
  }
}
</style>
