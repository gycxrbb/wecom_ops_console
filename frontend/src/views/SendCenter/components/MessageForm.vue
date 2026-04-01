<template>
  <div class="card-panel">
    <div class="card-header">
      <el-icon color="var(--primary-color)"><EditPen /></el-icon>
      <h3 class="card-header-title">消息内容</h3>
    </div>
    <div class="card-body">
      <el-form label-width="100px" label-position="left">
        <el-form-item label="发送群组" required>
          <el-select v-model="form.groups" multiple placeholder="请选择要发送的群组" style="width: 100%" filterable>
            <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="引用模板">
          <el-select
            :model-value="selectedTemplate"
            @update:model-value="$emit('update:selectedTemplate', $event)"
            @change="$emit('templateChange', $event)"
            placeholder="选择已有的消息模板"
            clearable
            style="width: 100%"
          >
            <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="消息类型" required>
          <el-select
            :model-value="form.msg_type"
            @update:model-value="$emit('msgTypeChange', $event)"
            style="width: 100%"
          >
            <el-option label="文本 (Text)" value="text"></el-option>
            <el-option label="Markdown" value="markdown"></el-option>
            <el-option label="图片 (Image)" value="image"></el-option>
            <el-option label="图文 (News)" value="news"></el-option>
            <el-option label="文件 (File)" value="file"></el-option>
            <el-option label="模板卡片 (Template Card)" value="template_card"></el-option>
          </el-select>
        </el-form-item>

        <!-- 可视化消息编辑器 -->
        <el-form-item label="消息内容" required>
          <MessageEditor
            :model-value="form.contentJson"
            @update:model-value="$emit('contentUpdate', $event)"
            :msg-type="form.msg_type"
            :variables="form.variables"
            @update:variables="$emit('variablesUpdate', $event)"
            :show-variables="!!selectedTemplate"
            style="width: 100%"
          />
        </el-form-item>

        <div class="action-footer">
          <el-button @click="$emit('preview')" :loading="isPreviewing">
            <template #icon><el-icon><View /></el-icon></template>
            预览消息
          </el-button>
          <el-button type="warning" @click="$emit('sendTest')" :loading="isTestSending">
            <template #icon><el-icon><Position /></el-icon></template>
            发送到测试群
          </el-button>
          <el-button type="primary" @click="$emit('send')" :loading="isSending">
            <template #icon><el-icon><Position /></el-icon></template>
            立即发送
          </el-button>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { EditPen, View, Position } from '@element-plus/icons-vue'
import MessageEditor from '@/components/message-editor/index.vue'
import type { PropType } from 'vue'

defineProps({
  form: { type: Object as PropType<any>, required: true },
  groups: { type: Array as PropType<any[]>, required: true },
  templates: { type: Array as PropType<any[]>, required: true },
  selectedTemplate: { type: [Number, String, null] as PropType<number | string | null> },
  isPreviewing: { type: Boolean, default: false },
  isSending: { type: Boolean, default: false },
  isTestSending: { type: Boolean, default: false }
})

defineEmits(['templateChange', 'preview', 'send', 'sendTest', 'update:selectedTemplate', 'msgTypeChange', 'contentUpdate', 'variablesUpdate'])
</script>
