<template>
  <div class="card-panel">
    <div class="card-header">
      <div class="card-header-icon card-header-icon--green">
        <el-icon :size="16"><EditPen /></el-icon>
      </div>
      <h3 class="card-header-title">消息内容</h3>
      <el-tag v-if="isBatchMode" size="small" type="warning" class="card-header__batch-tag">
        批量模式 ({{ batchQueue.length }} 项)
      </el-tag>
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

        <!-- 引用内容 / 批量选择状态 -->
        <div class="config-bar__item">
          <label class="config-bar__label">
            <el-icon :size="14"><Document /></el-icon>
            引用内容
          </label>
          <template v-if="isBatchMode">
            <div class="content-ref" @click="contentSelectorVisible = true">
              <el-tag size="small" type="warning" class="content-ref__tag">批量</el-tag>
              <span class="content-ref__label">已选 {{ batchQueue.length }} 条编排内容</span>
              <el-icon class="content-ref__clear" @click.stop="$emit('clearBatch')"><Close /></el-icon>
            </div>
          </template>
          <template v-else>
            <div class="content-ref" @click="contentSelectorVisible = true">
              <template v-if="selectedContentLabel">
                <el-tag size="small" :type="selectedContentSource === 'template' ? '' : 'warning'" class="content-ref__tag">
                  {{ selectedContentSource === 'template' ? '模板' : '编排' }}
                </el-tag>
                <span class="content-ref__label">{{ selectedContentLabel }}</span>
                <el-icon class="content-ref__clear" @click.stop="$emit('clearContent')"><Close /></el-icon>
              </template>
              <span v-else class="content-ref__placeholder">引用模板或运营编排</span>
            </div>
          </template>
          <ContentSelector
            v-model="contentSelectorVisible"
            :templates="templates"
            :selected-source="selectedContentSource"
            :selected-id="selectedContentId"
            @select="$emit('contentSelect', $event)"
            @select-batch="$emit('batchSelect', $event)"
          />
        </div>

        <!-- 消息类型（仅单条模式显示） -->
        <div v-if="!isBatchMode" class="config-bar__item">
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
            <el-option label="表情包" value="emotion" />
            <el-option label="图文" value="news" />
            <el-option label="文件" value="file" />
            <el-option label="模板卡片" value="template_card" />
          </el-select>
        </div>
      </div>

      <!-- 批量发送队列 -->
      <div v-if="isBatchMode" class="batch-queue">
        <div class="batch-queue__header">
          <span>发送队列</span>
          <span class="batch-queue__progress" v-if="isBatchSending">
            {{ batchProgress.done + (notifyEnabled && (notifySendStatus === 'success' || notifySendStatus === 'failed') ? 1 : 0) + 1 }} / {{ batchQueue.length + (notifyEnabled ? 1 : 0) }}
          </span>
          <span v-if="!isBatchSending" class="batch-queue__hint">点击查看详情</span>
        </div>
        <div class="batch-queue__list">
          <!-- 推送预告项 -->
          <div v-if="notifyEnabled && isBatchMode" class="batch-queue__item batch-queue__item--notify"
            :class="{
              'is-active': activeBatchIndex === -1,
              'is-sending': notifySendStatus === 'sending',
              'is-success': notifySendStatus === 'success',
              'is-failed': notifySendStatus === 'failed'
            }"
            @click="$emit('selectBatchItem', -1)"
          >
            <div class="batch-queue__item-index batch-queue__item-index--notify">📢</div>
            <div class="batch-queue__item-info">
              <span class="batch-queue__item-title">推送预告</span>
            </div>
            <el-tag size="small" type="success">Markdown</el-tag>
            <div class="batch-queue__item-status">
              <el-icon v-if="notifySendStatus === 'sending'" class="is-loading"><Loading /></el-icon>
              <el-icon v-else-if="notifySendStatus === 'success'" color="#67c23a"><CircleCheckFilled /></el-icon>
              <el-icon v-else-if="notifySendStatus === 'failed'" color="#f56c6c"><CircleCloseFilled /></el-icon>
            </div>
          </div>
          <div
            v-for="(item, index) in batchQueue"
            :key="item.id"
            class="batch-queue__item-wrapper"
          >
            <div
              class="batch-queue__item"
              :class="{
                'is-active': activeBatchIndex === index,
                'is-sending': item.status === 'sending',
                'is-success': item.status === 'success',
                'is-failed': item.status === 'failed'
              }"
              @click="$emit('selectBatchItem', index)"
            >
              <div class="batch-queue__item-index">{{ index + 1 }}</div>
              <div class="batch-queue__item-info">
                <span class="batch-queue__item-title">{{ item.title }}</span>
              </div>
              <el-tag size="small" :type="tagTypeByMsgType(item.msg_type)">{{ msgTypeLabel(item.msg_type) }}</el-tag>
              <div class="batch-queue__item-status">
                <el-icon v-if="item.status === 'sending'" class="is-loading"><Loading /></el-icon>
                <el-icon v-else-if="item.status === 'success'" color="#67c23a"><CircleCheckFilled /></el-icon>
                <el-icon v-else-if="item.status === 'failed'" color="#f56c6c"><CircleCloseFilled /></el-icon>
              </div>
              <button
                v-if="!isBatchSending"
                type="button"
                class="batch-queue__item-remark-btn"
                :class="{ 'is-active': item.remarkEnabled }"
                @click.stop="$emit('toggleRemark', index)"
                title="添加备注"
              >备注</button>
              <el-icon
                v-if="!isBatchSending"
                class="batch-queue__item-remove"
                @click.stop="$emit('removeBatchItem', index)"
              ><Close /></el-icon>
            </div>
            <transition name="el-zoom-in-top">
              <div v-if="item.remarkEnabled" class="batch-queue__remark" @click.stop>
                <el-input
                  type="textarea"
                  :rows="3"
                  :model-value="item.remark"
                  @update:model-value="$emit('updateRemark', index, $event)"
                  placeholder="备注内容（Markdown 格式）..."
                  class="batch-queue__remark-input"
                />
              </div>
            </transition>
          </div>
        </div>
        <div v-if="batchProgress.done > 0" class="batch-queue__summary">
          <span v-if="batchProgress.failed === 0" class="batch-queue__summary--success">
            全部 {{ batchProgress.total }} 条发送成功
          </span>
          <span v-else class="batch-queue__summary--partial">
            {{ batchProgress.success }} 成功 / {{ batchProgress.failed }} 失败
          </span>
        </div>
      </div>

      <!-- 单条消息编辑器 -->
      <MessageEditor
        v-if="!isBatchMode"
        :model-value="form.contentJson"
        @update:model-value="$emit('contentUpdate', $event)"
        :msg-type="form.msg_type"
        :variables="form.variables"
        @update:variables="$emit('variablesUpdate', $event)"
        :show-variables="supportsVariables"
        style="width: 100%"
      />

      <!-- Push Notification Preview -->
      <div v-if="showNotifySection" class="notify-section">
        <div class="notify-header">
          <el-switch :model-value="notifyEnabled" size="small" @update:model-value="$emit('update:notifyEnabled', $event)" />
          <span class="notify-label">发送推送预告</span>
          <span class="notify-hint">在正式内容前发送一条预告通知</span>
        </div>
        <div v-if="notifyEnabled" class="notify-body">
          <el-input
            type="textarea"
            :rows="4"
            :model-value="notifyCustomText"
            @update:model-value="$emit('update:notifyCustomText', $event)"
            placeholder="自动生成的预告文本，可手动编辑..."
            class="notify-textarea"
          />
        </div>
      </div>

      <!-- Action Footer -->
      <div class="action-footer">
        <template v-if="isBatchMode">
          <div class="action-footer__row">
            <el-button
              size="large"
              type="primary"
              @click="$emit('batchSend')"
              :loading="isBatchSending"
              :disabled="isBatchSending"
            >
              <template #icon><el-icon><Position /></el-icon></template>
              批量发送 ({{ batchQueue.length }})
            </el-button>
            <el-button
              size="large"
              type="warning"
              plain
              @click="$emit('batchSend', true)"
              :loading="isBatchSending"
              :disabled="isBatchSending"
            >
              测试群发送
            </el-button>
          </div>
          <div class="action-footer__sub" v-if="isBatchSending">
            <el-button size="small" type="danger" text @click="$emit('cancelBatchSend')">
              <el-icon><Close /></el-icon> 取消发送
            </el-button>
          </div>
        </template>
        <template v-else>
          <div class="action-footer__row">
            <el-button size="large" type="primary" @click="$emit('send')" :loading="isSending">
              <template #icon><el-icon><Position /></el-icon></template>
              立即发送
            </el-button>
            <el-button size="large" type="warning" plain @click="$emit('sendTest')" :loading="isTestSending">
              测试群发送
            </el-button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { EditPen, View, Position, ChatDotRound, Document, Memo, Close, Loading, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import MessageEditor from '@/components/message-editor/index.vue'
import ContentSelector from './ContentSelector.vue'
import { msgTypeLabel } from '@/views/Templates/composables/useTemplates'
import type { PropType } from 'vue'
import type { BatchQueueItem } from '../composables/useSendLogic'

const props = defineProps({
  form: { type: Object as PropType<any>, required: true },
  groups: { type: Array as PropType<any[]>, required: true },
  templates: { type: Array as PropType<any[]>, required: true },
  selectedContentSource: { type: String as PropType<'template' | 'plan_node' | null>, default: null },
  selectedContentId: { type: Number as PropType<number | null>, default: null },
  selectedContentLabel: { type: String as PropType<string | null>, default: null },
  isPreviewing: { type: Boolean, default: false },
  isSending: { type: Boolean, default: false },
  isTestSending: { type: Boolean, default: false },
  // 批量模式
  isBatchMode: { type: Boolean, default: false },
  batchQueue: { type: Array as PropType<BatchQueueItem[]>, default: () => [] },
  isBatchSending: { type: Boolean, default: false },
  batchProgress: { type: Object as PropType<{ total: number; done: number; success: number; failed: number }>, default: () => ({ total: 0, done: 0, success: 0, failed: 0 }) },
  activeBatchIndex: { type: Number as PropType<number | null>, default: null },
  notifyEnabled: { type: Boolean, default: false },
  notifyCustomText: { type: String, default: '' },
  notifyAutoText: { type: String, default: '' },
  notifySendStatus: { type: String as PropType<'hidden' | 'pending' | 'sending' | 'success' | 'failed'>, default: 'hidden' }
})

defineEmits([
  'contentSelect', 'clearContent', 'preview', 'send', 'sendTest',
  'msgTypeChange', 'contentUpdate', 'variablesUpdate',
  // 批量模式
  'batchSelect', 'batchSend', 'removeBatchItem', 'clearBatch', 'cancelBatchSend', 'selectBatchItem',
  'toggleRemark', 'updateRemark',
  // 预告通知
  'update:notifyEnabled', 'update:notifyCustomText'
])

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

const showNotifySection = computed(() => {
  if (props.isBatchMode && props.batchQueue.length > 0) return true
  if (!props.isBatchMode && props.selectedContentLabel) return true
  return false
})

const tagTypeByMsgType = (msgType: string) => {
  const map: Record<string, string> = {
    text: '', markdown: 'success', image: 'warning', emotion: 'warning', news: 'danger', file: 'info', template_card: ''
  }
  return map[msgType] || ''
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

.card-header__batch-tag {
  margin-left: 8px;
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

/* Batch Queue */
.batch-queue {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-color);
  margin-bottom: 20px;
  overflow: hidden;
}
.batch-queue__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border-color);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}
.batch-queue__progress {
  font-size: 12px;
  color: var(--el-color-primary);
}
.batch-queue__hint {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 400;
}
.batch-queue__list {
  max-height: 320px;
  overflow-y: auto;
}
.batch-queue__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 18px;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
}
.batch-queue__item:last-child {
  border-bottom: none;
}
.batch-queue__item.is-sending {
  background: rgba(var(--el-color-primary-rgb), 0.05);
}
.batch-queue__item.is-success {
  background: rgba(103, 194, 58, 0.05);
}
.batch-queue__item.is-failed {
  background: rgba(245, 108, 108, 0.05);
}
.batch-queue__item.is-active {
  outline: 2px solid var(--el-color-primary);
  background: rgba(var(--el-color-primary-rgb), 0.04);
}
.batch-queue__item-index {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--fill-color-light, #f5f7fa);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  flex-shrink: 0;
}
.batch-queue__item-info {
  flex: 1;
  min-width: 0;
}
.batch-queue__item-title {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.batch-queue__item-status {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.batch-queue__item-remove {
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  font-size: 14px;
  transition: color 0.15s;
}
.batch-queue__item-remove:hover {
  color: #f56c6c;
}
.batch-queue__item-wrapper {
  display: flex;
  flex-direction: column;
}
.batch-queue__item-remark-btn {
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 11px;
  padding: 1px 6px;
  flex-shrink: 0;
  transition: all 0.15s;
}
.batch-queue__item-remark-btn:hover {
  border-color: var(--el-color-primary, #409eff);
  color: var(--el-color-primary, #409eff);
}
.batch-queue__item-remark-btn.is-active {
  border-color: var(--el-color-primary, #409eff);
  background: rgba(64, 158, 255, 0.08);
  color: var(--el-color-primary, #409eff);
}
.batch-queue__remark {
  padding: 6px 12px 8px 36px;
}
.batch-queue__remark-input :deep(.el-textarea__inner) {
  font-size: 12px;
  border-radius: 8px;
}
.batch-queue__item--notify {
  border-left: 3px solid #67c23a;
}
.batch-queue__item-index--notify {
  font-size: 14px;
  background: rgba(103, 194, 58, 0.1);
}
.batch-queue__summary {
  padding: 10px 18px;
  font-size: 13px;
  font-weight: 500;
  text-align: center;
}
.batch-queue__summary--success {
  color: #67c23a;
}
.batch-queue__summary--partial {
  color: #e6a23c;
}

.action-footer__row {
  display: flex;
  gap: 10px;
}
.action-footer__sub {
  display: flex;
  justify-content: center;
  margin-top: 6px;
}

/* Notify Section */
.notify-section {
  margin-top: 16px;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--bg-color);
}
.notify-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.notify-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.notify-hint {
  font-size: 12px;
  color: var(--text-muted);
}
.notify-body {
  margin-top: 10px;
}
.notify-textarea :deep(.el-textarea__inner) {
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.7;
}

/* Responsive */
@media (max-width: 1100px) {
  .config-bar {
    flex-direction: column;
    gap: 14px;
  }
}
@media (max-width: 767px) {
  .action-footer__row {
    flex-direction: column;
    width: 100%;
  }
  .notify-header {
    flex-wrap: wrap;
  }
}
</style>
