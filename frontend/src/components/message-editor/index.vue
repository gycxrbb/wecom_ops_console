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
    <div v-if="showVariables" style="margin-top: 16px">
      <el-divider content-position="left">模板变量</el-divider>
      <JsonEditor
        :model-value="variablesJson"
        @update:model-value="$emit('update:variables', $event)"
        :rows="4"
      />
      <div class="var-hint">
        内置变量: today, tomorrow, weekday, coach_name, group_name
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
.var-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}
.unknown-type {
  padding: 24px;
}
</style>
