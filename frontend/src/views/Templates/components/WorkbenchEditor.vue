<template>
  <div class="wb-editor">
    <template v-if="currentNode">
      <!-- 顶部导航 -->
      <div class="wb-editor__nav">
        <el-button text :disabled="!hasPrev" @click="$emit('prev-node')">
          <el-icon><ArrowLeft /></el-icon> 上一个
        </el-button>
        <span class="wb-editor__title">{{ currentNode.title }}</span>
        <el-button text :disabled="!hasNext" @click="$emit('next-node')">
          下一个 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>

      <!-- 状态 + 操作 -->
      <div class="wb-editor__toolbar">
        <span class="wb-status-dot" :class="{ 'is-dirty': nodeDirty }">
          {{ nodeDirty ? '草稿待保存' : '已同步' }}
        </span>
        <div class="wb-editor__toolbar-actions">
          <el-button text size="small" @click="$emit('copy-node')">
            <el-icon><CopyDocument /></el-icon> 复制
          </el-button>
          <el-dropdown trigger="click">
            <el-button text size="small">更多操作</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="$emit('sync-node')">同步同类节点到其他天</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- 套模板 -->
      <div class="wb-editor__template-apply">
        <el-select
          :model-value="selectedTemplateId"
          @update:model-value="$emit('update:selected-template-id', $event as number)"
          placeholder="从模板库套用"
          clearable
          filterable
          size="small"
          style="flex: 1"
        >
          <el-option v-for="item in templateOptions" :key="item.id" :label="item.label" :value="item.id" />
        </el-select>
        <el-button size="small" :disabled="!selectedTemplateId" @click="$emit('apply-template')">套用</el-button>
      </div>

      <!-- 编辑表单 -->
      <el-form label-width="76px" class="wb-editor__form" size="small">
        <el-form-item label="节点标题">
          <el-input
            :model-value="nodeDraft?.title"
            @update:model-value="$emit('patch-draft', { title: $event })"
          />
        </el-form-item>
        <el-form-item label="消息类型">
          <el-select
            :model-value="nodeDraft?.msg_type"
            @update:model-value="$emit('patch-draft', { msg_type: $event })"
            style="width: 100%"
          >
            <el-option v-for="item in msgTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="节点说明">
          <div class="wb-expandable-field" @click="openDescDialog">
            <el-input
              :model-value="nodeDraft?.description"
              type="textarea"
              :rows="2"
              readonly
              class="wb-expandable-field__input"
            />
            <div class="wb-expandable-field__hint">
              <el-icon :size="14"><FullScreen /></el-icon>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="发送内容">
          <MessageEditor
            :model-value="nodeDraft?.content_json || {}"
            @update:model-value="$emit('patch-draft', { content_json: $event })"
            :msg-type="nodeDraft?.msg_type || currentNode.msg_type"
            :variables="nodeDraft?.variables_json || {}"
            @update:variables="$emit('patch-draft', { variables_json: $event })"
            :show-variables="supportsVariables(nodeDraft?.msg_type || currentNode.msg_type)"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>

      <!-- 底部操作栏 -->
      <div class="wb-editor__actions">
        <el-button :disabled="!nodeDirty" @click="$emit('reset')">重置</el-button>
        <el-button type="primary" :loading="nodeSaving" :disabled="!nodeDirty" @click="$emit('save')">保存</el-button>
        <el-button type="success" :loading="nodeSaving" :disabled="!nodeDirty" @click="$emit('save-and-next')">
          保存并下一条
        </el-button>
      </div>

      <!-- 节点说明展开编辑弹窗 -->
      <el-dialog
        v-model="descDialogVisible"
        title="节点说明"
        width="600px"
        :close-on-click-modal="false"
        append-to-body
        destroy-on-close
      >
        <el-input
          v-model="descDialogValue"
          type="textarea"
          :rows="10"
          placeholder="输入节点说明"
        />
        <template #footer>
          <el-button @click="descDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmDescDialog">确定</el-button>
        </template>
      </el-dialog>
    </template>
    <el-empty v-else description="选择一个节点开始编辑" :image-size="64" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ArrowLeft, ArrowRight, FullScreen, CopyDocument } from '@element-plus/icons-vue'
import MessageEditor from '@/components/message-editor/index.vue'
import { msgTypeOptions, supportsVariables } from '../composables/useTemplates'

interface CurrentNode {
  id: number
  title: string
  msg_type: string
  status: string
}

const props = defineProps<{
  currentNode: CurrentNode | null
  nodeDraft: Record<string, any> | null
  nodeDirty: boolean
  nodeSaving: boolean
  templateOptions: Array<{ id: number; label: string }>
  selectedTemplateId: number | null
  hasPrev: boolean
  hasNext: boolean
}>()

const emit = defineEmits<{
  'patch-draft': [patch: Record<string, any>]
  'save': []
  'save-and-next': []
  'reset': []
  'apply-template': []
  'sync-node': []
  'copy-node': []
  'prev-node': []
  'next-node': []
  'update:selected-template-id': [id: number]
}>()

const descDialogVisible = ref(false)
const descDialogValue = ref('')

const openDescDialog = () => {
  descDialogValue.value = props.nodeDraft?.description || ''
  descDialogVisible.value = true
}

const confirmDescDialog = () => {
  emit('patch-draft', { description: descDialogValue.value })
  descDialogVisible.value = false
}
</script>

<style scoped>
.wb-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  position: sticky;
  top: 0;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
  overscroll-behavior: contain;
}

@media (max-width: 767px) {
  .wb-editor {
    position: static;
    max-height: none;
    overflow-y: visible;
    overscroll-behavior: auto;
  }
}

.wb-editor__nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.wb-editor__title {
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 700;
  text-align: center;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-editor__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.wb-editor__toolbar-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.wb-editor__template-apply {
  display: flex;
  gap: 8px;
  align-items: center;
}

.wb-editor__form {
  flex: 1;
}

.wb-editor__actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.wb-status-dot {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.08);
  color: var(--text-muted);
  font-size: 12px;
}

.wb-status-dot.is-dirty {
  background: rgba(34, 197, 94, 0.1);
  color: var(--primary-color);
}

:global(html.dark) .wb-status-dot {
  background: rgba(148, 163, 184, 0.06);
}

:global(html.dark) .wb-status-dot.is-dirty {
  background: rgba(74, 222, 128, 0.14);
  color: #4ade80;
}

.wb-expandable-field {
  position: relative;
  cursor: pointer;
  border-radius: 4px;
  overflow: hidden;
}

.wb-expandable-field:hover {
  box-shadow: 0 0 0 1px var(--el-color-primary-light-5);
}

.wb-expandable-field__input :deep(.el-textarea__inner) {
  cursor: pointer;
  padding-right: 28px;
}

.wb-expandable-field__hint {
  position: absolute;
  right: 6px;
  bottom: 6px;
  color: var(--text-muted);
  opacity: 0;
  transition: opacity 0.2s ease;
  pointer-events: none;
}

.wb-expandable-field:hover .wb-expandable-field__hint {
  opacity: 1;
}
</style>

<style>
html.dark .wb-status-dot {
  background: rgba(148, 163, 184, 0.06);
}

html.dark .wb-status-dot.is-dirty {
  background: rgba(74, 222, 128, 0.14);
  color: #4ade80;
}
</style>
