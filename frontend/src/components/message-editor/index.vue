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
    <div v-if="showVariables" class="variable-section">
      <el-divider content-position="left">自定义变量（可选）</el-divider>
      <div class="var-intro">
        <div class="var-title">这里是给模板占位符填写默认值的地方。</div>
        <div class="var-desc">如果你只使用内置变量，保持 `{}` 就可以，不需要额外填写。</div>
      </div>
      <JsonEditor
        :model-value="variablesJson"
        @update:model-value="$emit('update:variables', $event)"
        :rows="4"
      />
      <div class="var-example">
        <span class="var-example-label">示例：</span>
        <code>{ "course_name": "减脂营", "deadline": "今晚 20:00" }</code>
      </div>
      <div class="var-hint">
        内置变量：today、tomorrow、weekday、coach_name、group_name
      </div>
    </div>

    <!-- 高级模式：JSON 折叠区 -->
    <el-collapse v-if="msgType !== 'raw_json'" style="margin-top: 16px">
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
import { computed } from 'vue'
import TextEditor from './TextEditor.vue'
import MarkdownEditor from './MarkdownEditor.vue'
import NewsEditor from './NewsEditor.vue'
import ImageEditor from './ImageEditor.vue'
import FileEditor from './FileEditor.vue'
import TemplateCardEditor from './TemplateCardEditor.vue'
import JsonEditor from './JsonEditor.vue'

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
.variable-section {
  margin-top: 16px;
}
.var-intro {
  margin-bottom: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}
.var-title {
  margin-bottom: 4px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}
.var-desc {
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}
.var-example {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}
.var-example-label {
  margin-right: 6px;
  color: #475569;
}
.var-example code {
  padding: 2px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #0f172a;
}
.var-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}
.unknown-type {
  padding: 24px;
}
</style>
