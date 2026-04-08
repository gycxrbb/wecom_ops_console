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
          <div class="config-bar__label-row">
            <label class="config-bar__label">
              <el-icon :size="14"><ChatDotRound /></el-icon>
              发送群组 <span class="required-star">*</span>
            </label>
            <div class="config-bar__label-actions">
              <button type="button" class="config-bar__text-btn" @click="toggleSelectAllGroups">
                {{ isAllSelected ? '清空' : '全选' }}
              </button>
            </div>
          </div>
          <el-select
            v-model="form.groups"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择目标群组"
            filterable
            class="config-bar__select"
          >
            <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>
          <div class="config-bar__hint">
            <span>已选 {{ selectedGroupCount }} / {{ totalGroupCount }} 个群组</span>
            <span v-if="selectedGroupNames.length">{{ selectedGroupNames.join('、') }}</span>
          </div>
        </div>
        <div class="config-bar__item">
          <label class="config-bar__label">
            <el-icon :size="14"><Document /></el-icon>
            引用内容
          </label>
          <div class="content-ref" @click="contentSelectorVisible = true">
            <template v-if="selectedContentLabel">
              <el-tag size="small" :type="selectedContentSource === 'template' ? '' : 'warning'" class="content-ref__tag">
                {{ selectedContentSource === 'template' ? '模板' : '编排' }}
              </el-tag>
              <span class="content-ref__label">{{ selectedContentLabel }}</span>
              <el-icon class="content-ref__clear" @click.stop="$emit('clearContent')"><Close /></el-icon>
            </template>
            <span v-else class="content-ref__placeholder">点击引用模板或运营编排内容</span>
          </div>
          <ContentSelector
            v-model="contentSelectorVisible"
            :templates="templates"
            :selected-source="selectedContentSource"
            :selected-id="selectedContentId"
            @select="$emit('contentSelect', $event)"
          />
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
import { ref, computed } from 'vue'
import { EditPen, View, Position, ChatDotRound, Document, Memo, Close } from '@element-plus/icons-vue'
import MessageEditor from '@/components/message-editor/index.vue'
import ContentSelector from './ContentSelector.vue'
import type { PropType } from 'vue'

const props = defineProps({
  form: { type: Object as PropType<any>, required: true },
  groups: { type: Array as PropType<any[]>, required: true },
  templates: { type: Array as PropType<any[]>, required: true },
  selectedContentSource: { type: String as PropType<'template' | 'plan_node' | null>, default: null },
  selectedContentId: { type: Number as PropType<number | null>, default: null },
  selectedContentLabel: { type: String as PropType<string | null>, default: null },
  isPreviewing: { type: Boolean, default: false },
  isSending: { type: Boolean, default: false },
  isTestSending: { type: Boolean, default: false }
})

defineEmits(['contentSelect', 'clearContent', 'preview', 'send', 'sendTest', 'msgTypeChange', 'contentUpdate', 'variablesUpdate'])

const contentSelectorVisible = ref(false)

const variableEnabledTypes = new Set(['text', 'markdown', 'news', 'template_card'])
const supportsVariables = computed(() => !!props.selectedContentSource || variableEnabledTypes.has(props.form?.msg_type))
const totalGroupCount = computed(() => props.groups.length)
const selectedGroupCount = computed(() => Array.isArray(props.form?.groups) ? props.form.groups.length : 0)
const allGroupIds = computed(() => props.groups.map(group => group.id))
const isAllSelected = computed(() =>
  totalGroupCount.value > 0 && selectedGroupCount.value === totalGroupCount.value
)
const selectedGroupNames = computed(() =>
  props.groups
    .filter(group => props.form?.groups?.includes(group.id))
    .map(group => group.name)
    .slice(0, 3)
)

const toggleSelectAllGroups = () => {
  props.form.groups = isAllSelected.value ? [] : [...allGroupIds.value]
}
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
.config-bar__label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
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
.config-bar__label-actions {
  display: flex;
  align-items: center;
}
.config-bar__text-btn {
  appearance: none;
  border: none;
  background: none;
  padding: 0;
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.config-bar__select {
  width: 100%;
}
.config-bar__select :deep(.el-input__wrapper) {
  border-radius: 8px;
}
.config-bar__hint {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.required-star {
  color: #f56c6c;
  margin-left: 1px;
}

/* Content Reference Trigger */
.content-ref {
  width: 100%;
  min-height: 32px;
  padding: 4px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.content-ref:hover {
  border-color: var(--el-color-primary);
}
.content-ref__placeholder {
  font-size: 14px;
  color: var(--text-muted);
}
.content-ref__tag {
  flex-shrink: 0;
}
.content-ref__label {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.content-ref__clear {
  margin-left: auto;
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  font-size: 14px;
}
.content-ref__clear:hover {
  color: #f56c6c;
}

/* Responsive */
@media (max-width: 1100px) {
  .config-bar {
    flex-direction: column;
    gap: 14px;
  }
}
</style>
