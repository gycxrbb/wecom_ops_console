<template>
  <div class="message-editor">
    <!-- 按消息类型切换的可视化编辑器 -->
    <div class="visual-editor">
      <TextEditor
        v-if="msgType === 'text'"
        :model-value="contentJson"
        @update:model-value="handleVisualUpdate"
      />
      <MarkdownEditor
        v-else-if="msgType === 'markdown'"
        :model-value="contentJson"
        @update:model-value="handleVisualUpdate"
      />
      <NewsEditor
        v-else-if="msgType === 'news'"
        :model-value="contentJson"
        @update:model-value="handleVisualUpdate"
      />
      <ImageEditor
        v-else-if="msgType === 'image'"
        :model-value="contentJson"
        variant="image"
        @update:model-value="handleVisualUpdate"
      />
      <ImageEditor
        v-else-if="msgType === 'emotion'"
        :model-value="contentJson"
        variant="emotion"
        @update:model-value="handleVisualUpdate"
      />
      <FileEditor
        v-else-if="msgType === 'file'"
        :model-value="contentJson"
        @update:model-value="handleVisualUpdate"
      />
      <TemplateCardEditor
        v-else-if="msgType === 'template_card'"
        :model-value="contentJson"
        @update:model-value="handleVisualUpdate"
      />
      <JsonEditor
        v-else-if="msgType === 'raw_json'"
        :model-value="contentJson"
        @update:model-value="handleVisualUpdate"
        :rows="12"
      />
      <div v-else class="unknown-type">
        <el-empty description="不支持的消息类型" />
      </div>
    </div>

    <!-- 变量编辑区（仅模板模式） -->
    <el-collapse v-if="showVariables" v-model="variableCollapse" class="variable-collapse">
      <el-collapse-item name="variables">
        <template #title>
          <div class="variable-header">
            <span class="variable-header__title">自定义变量（可选）</span>
            <el-popover placement="top-start" trigger="click" :width="320">
              <template #reference>
                <button class="variable-tip-button" type="button" @click.stop>
                  <el-icon :size="15"><QuestionFilled /></el-icon>
                </button>
              </template>
              <div class="variable-tip-content">
                <div class="variable-tip-title">什么时候需要填这里？</div>
                <div class="variable-tip-text">如果你只用了内置变量，可以不填。只有像 `course_name`、`deadline` 这种你自己写的变量，才需要补默认值。</div>
                <div class="variable-tip-text">内置变量：today、tomorrow、weekday、coach_name、group_name</div>
              </div>
            </el-popover>
          </div>
        </template>
        <VariableEditor
          :model-value="variablesJson"
          @update:model-value="$emit('update:variables', $event)"
        />
      </el-collapse-item>
    </el-collapse>

    <!-- 高级模式：JSON 折叠区 -->
    <el-collapse v-if="msgType !== 'raw_json'" class="advanced-collapse">
      <el-collapse-item title="高级模式 (JSON)" name="json">
        <JsonEditor
          :model-value="contentJson"
          @update:model-value="handleJsonUpdate"
          :rows="8"
        />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import TextEditor from './TextEditor.vue'
import MarkdownEditor from './MarkdownEditor.vue'
import NewsEditor from './NewsEditor.vue'
import ImageEditor from './ImageEditor.vue'
import FileEditor from './FileEditor.vue'
import TemplateCardEditor from './TemplateCardEditor.vue'
import JsonEditor from './JsonEditor.vue'
import VariableEditor from './VariableEditor.vue'

const props = withDefaults(defineProps<{
  modelValue: Record<string, any>
  msgType: string
  variables?: Record<string, any>
  showVariables?: boolean
}>(), {
  variables: () => ({}),
  showVariables: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', val: Record<string, any>): void
  (e: 'update:variables', val: Record<string, any>): void
}>()

const contentJson = computed(() => props.modelValue || {})
const variablesJson = computed(() => props.variables || {})
const variableCollapse = ref<string[]>([])

const handleVisualUpdate = (val: Record<string, any>) => {
  emit('update:modelValue', val)
}

const handleJsonUpdate = (val: Record<string, any>) => {
  emit('update:modelValue', val)
}
</script>

<style scoped>
.message-editor {
  padding: 0;
}
.variable-collapse {
  margin-top: 20px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}
.variable-collapse :deep(.el-collapse-item__header) {
  padding: 0 16px;
  background: var(--bg-color);
  border-bottom: none;
  font-weight: 500;
  font-size: 13px;
}
.variable-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}
.variable-collapse :deep(.el-collapse-item__content) {
  padding: 16px;
  background: #fff;
}
.variable-header {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.variable-header__title {
  color: var(--text-secondary);
}
.variable-tip-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: #64748b;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}
.variable-tip-button:hover {
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
}
.variable-tip-content {
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
}
.variable-tip-title {
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}
.variable-tip-text + .variable-tip-text {
  margin-top: 6px;
}
.unknown-type {
  padding: 24px;
}

/* Advanced Collapse */
.advanced-collapse {
  margin-top: 20px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
}
.advanced-collapse :deep(.el-collapse-item__header) {
  padding: 0 16px;
  background: var(--bg-color);
  border-bottom: none;
  font-weight: 500;
  font-size: 13px;
}
.advanced-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}
.advanced-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}
</style>
