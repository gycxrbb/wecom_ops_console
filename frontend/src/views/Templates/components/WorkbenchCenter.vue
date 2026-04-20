<template>
  <div class="wb-center">
    <!-- 当天概览卡 -->
    <div v-if="currentDay" class="wb-day-overview">
      <div class="wb-day-overview__header">
        <div>
          <div class="wb-day-overview__badge">{{ isCampaignMode ? 'Stage' : 'Day' }} {{ currentDay.day_number }}</div>
          <h3>{{ currentDay.title }}</h3>
        </div>
        <div class="wb-day-overview__actions">
          <span class="wb-status-dot" :class="{ 'is-dirty': dayDirty }">
            {{ dayDirty ? '待保存' : '已同步' }}
          </span>
          <el-button text size="small" :disabled="!dayDirty" @click="$emit('reset-day')">重置</el-button>
          <el-button type="primary" size="small" :disabled="!dayDirty" :loading="daySaving" @click="$emit('save-day')">保存</el-button>
        </div>
      </div>
      <div class="wb-day-overview__fields">
        <el-input
          :model-value="dayDraft?.title"
          @update:model-value="$emit('patch-day', { title: $event })"
          :placeholder="isCampaignMode ? '阶段标题' : '天标题'"
          size="small"
        />
        <div class="wb-expandable-field" @click="openFocusDialog">
          <el-input
            :model-value="dayDraft?.focus"
            type="textarea"
            :rows="2"
            :placeholder="isCampaignMode ? '阶段目标，例如：冲刺激励，带动群氛围' : '今日重点，例如：今天聚焦早餐结构与餐后反馈记录'"
            size="small"
            readonly
            class="wb-expandable-field__input"
          />
          <div class="wb-expandable-field__hint">
            <el-icon :size="14"><FullScreen /></el-icon>
          </div>
        </div>
      </div>

      <!-- 触发规则编辑（积分运营模式） -->
      <div v-if="isCampaignMode && currentDay" class="wb-day-overview__trigger">
        <label class="wb-trigger-label">触发规则</label>
        <div class="wb-trigger-row">
          <el-select
            :model-value="triggerType"
            @update:model-value="updateTriggerType"
            size="small"
            style="width: 140px"
          >
            <el-option label="每日触发" value="daily" />
            <el-option label="每周触发" value="weekly" />
            <el-option label="倒计时范围" value="countdown_range" />
            <el-option label="倒数第N天" value="final_day" />
            <el-option label="手动触发" value="manual" />
          </el-select>
          <el-time-select
            v-if="triggerType !== 'manual'"
            :model-value="triggerTime"
            @update:model-value="updateTriggerTime"
            :start="'06:00'"
            :step="'00:15'"
            :end="'23:00'"
            placeholder="发送时间"
            size="small"
            style="width: 120px"
          />
        </div>
      </div>

      <!-- 运营焦点展开编辑弹窗 -->
      <el-dialog
        v-model="focusDialogVisible"
        :title="isCampaignMode ? '阶段目标' : '运营焦点'"
        width="600px"
        :close-on-click-modal="false"
        append-to-body
        destroy-on-close
      >
        <el-input
          v-model="focusDialogValue"
          type="textarea"
          :rows="8"
          :placeholder="isCampaignMode ? '阶段目标' : '今日重点，例如：今天聚焦早餐结构与餐后反馈记录'"
        />
        <template #footer>
          <el-button @click="focusDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmFocusDialog">确定</el-button>
        </template>
      </el-dialog>
    </div>

    <!-- 节点时间线 -->
    <div class="wb-center__timeline-section">
      <div class="wb-center__timeline-header">
        <h4>流程节点</h4>
        <div class="wb-center__timeline-actions">
          <span v-if="pendingCount" class="wb-center__pending-badge">还差 {{ pendingCount }} 个</span>
          <el-button size="small" @click="$emit('add-node')">+ 新增节点</el-button>
        </div>
      </div>
      <el-timeline v-if="nodes.length">
        <el-timeline-item
          v-for="node in nodes"
          :key="node.id"
          :type="node.status === 'draft' ? 'warning' : 'success'"
          :hollow="node.status === 'draft'"
          :timestamp="`Step ${node.sort_order}`"
        >
          <button
            class="wb-node-item"
            :class="{ 'is-active': currentNodeId === node.id }"
            @click="$emit('select-node', node.id)"
          >
            <div class="wb-node-item__head">
              <strong>{{ node.title }}</strong>
              <div class="wb-node-item__head-right">
                <span class="wb-node-item__type">{{ msgTypeLabel(node.msg_type) }}</span>
                <el-tooltip v-if="currentNodeId === node.id" content="新增节点" placement="top" :show-after="400">
                  <el-icon
                    class="wb-node-item__add"
                    :size="14"
                    @click.stop="$emit('add-node-after', node.id)"
                  ><Plus /></el-icon>
                </el-tooltip>
                <el-icon
                  class="wb-node-item__delete"
                  :size="14"
                  @click.stop="$emit('remove-node', node.id)"
                ><Close /></el-icon>
              </div>
            </div>
            <div v-if="node.description" class="wb-node-item__desc">{{ node.description }}</div>
          </button>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else :description="`当前${isCampaignMode ? '阶段' : '天'}没有流程节点`" :image-size="48" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { FullScreen, Close, Plus } from '@element-plus/icons-vue'
import { msgTypeLabel } from '../composables/useTemplates'

interface Day {
  id: number
  day_number: number
  title: string
  focus?: string
  trigger_rule_json?: Record<string, any>
  status: string
}

interface Node {
  id: number
  sort_order: number
  title: string
  description?: string
  msg_type: string
  status: string
}

const props = defineProps<{
  currentDay: Day | null
  nodes: Node[]
  currentNodeId: number | null
  pendingCount: number
  isCampaignMode: boolean
  dayDraft: { title?: string; focus?: string; trigger_rule_json?: Record<string, any> } | null
  dayDirty: boolean
  daySaving: boolean
}>()

const emit = defineEmits<{
  'select-node': [nodeId: number]
  'patch-day': [patch: Record<string, any>]
  'save-day': []
  'reset-day': []
  'add-node': []
  'add-node-after': [nodeId: number]
  'remove-node': [nodeId: number]
}>()

const focusDialogVisible = ref(false)
const focusDialogValue = ref('')

watch(
  () => props.dayDraft?.focus,
  value => {
    focusDialogValue.value = value || ''
  },
  { immediate: true }
)

const openFocusDialog = () => {
  focusDialogValue.value = props.dayDraft?.focus || ''
  focusDialogVisible.value = true
}

const confirmFocusDialog = () => {
  emit('patch-day', { focus: focusDialogValue.value })
  focusDialogVisible.value = false
}

// ── 触发规则逻辑（积分运营模式） ──
const triggerRule = computed(() => props.dayDraft?.trigger_rule_json || props.currentDay?.trigger_rule_json || {})
const triggerType = computed(() => (triggerRule.value as any).trigger_type || 'daily')
const triggerTime = computed(() => (triggerRule.value as any).time || '09:00')

const updateTriggerType = (val: string) => {
  const rule = { ...triggerRule.value, trigger_type: val }
  emit('patch-day', { trigger_rule_json: rule })
}

const updateTriggerTime = (val: string) => {
  const rule = { ...triggerRule.value, time: val }
  emit('patch-day', { trigger_rule_json: rule })
}
</script>

<style scoped>
.wb-center {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}

.wb-day-overview {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.wb-day-overview__badge {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.1);
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
}

.wb-day-overview__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.wb-day-overview__header h3 {
  margin: 8px 0 0;
  color: var(--text-primary);
  font-size: 18px;
}

.wb-day-overview__actions {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-shrink: 0;
}

.wb-day-overview__fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
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

.wb-day-overview__trigger {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

.wb-trigger-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.wb-trigger-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wb-center__timeline-section {
  flex: 1;
}

.wb-center__timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.wb-center__timeline-header h4 {
  margin: 0;
  color: var(--text-primary);
  font-size: 15px;
}

.wb-center__timeline-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wb-center__pending-badge {
  display: inline-flex;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
  font-size: 12px;
  font-weight: 600;
}

.wb-node-item {
  appearance: none;
  border: 1px solid transparent;
  border-radius: 10px;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
  background: transparent;
  width: 100%;
  transition: all 0.15s ease;
}

.wb-node-item:hover {
  background: rgba(34, 197, 94, 0.04);
  border-color: rgba(34, 197, 94, 0.12);
}

.wb-node-item.is-active {
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.24);
}

.wb-node-item__head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.wb-node-item__head strong {
  color: var(--text-primary);
  font-size: 14px;
}

.wb-node-item__head-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.wb-node-item__type {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 11px;
}

.wb-node-item__desc {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.wb-node-item__add {
  color: var(--primary-color);
  cursor: pointer;
  transition: color 0.15s, transform 0.15s;
}
.wb-node-item__add:hover {
  color: var(--el-color-primary);
  transform: scale(1.15);
}
.wb-node-item__delete {
  color: var(--text-muted);
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
  cursor: pointer;
}
.wb-node-item:hover .wb-node-item__delete {
  opacity: 1;
}
.wb-node-item__delete:hover {
  color: #f56c6c;
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

:global(html.dark) .wb-day-overview__badge {
  background: rgba(74, 222, 128, 0.14);
}

:global(html.dark) .wb-node-item:hover {
  background: rgba(74, 222, 128, 0.06);
  border-color: rgba(74, 222, 128, 0.18);
}

:global(html.dark) .wb-node-item.is-active {
  background: rgba(74, 222, 128, 0.1);
  border-color: rgba(74, 222, 128, 0.28);
}

:global(html.dark) .wb-node-item__type {
  background: rgba(96, 165, 250, 0.18);
  color: #93c5fd;
}

:global(html.dark) .wb-status-dot {
  background: rgba(148, 163, 184, 0.06);
}

:global(html.dark) .wb-status-dot.is-dirty {
  background: rgba(74, 222, 128, 0.14);
  color: #4ade80;
}

:global(html.dark) .wb-center__pending-badge {
  background: rgba(251, 191, 36, 0.14);
  color: #fbbf24;
}

@media (max-width: 767px) {
  .wb-center {
    padding: 12px;
    border-radius: 14px;
  }
  .wb-day-overview__header {
    flex-direction: column;
    gap: 8px;
  }
  .wb-day-overview__actions {
    flex-wrap: wrap;
  }
  .wb-center__timeline-actions {
    flex-wrap: wrap;
  }
  .wb-node-item__head {
    flex-wrap: wrap;
  }
}
</style>

<style>
html.dark .wb-day-overview__badge {
  background: rgba(74, 222, 128, 0.14);
}

html.dark .wb-node-item:hover {
  background: rgba(74, 222, 128, 0.06);
  border-color: rgba(74, 222, 128, 0.18);
}

html.dark .wb-node-item.is-active {
  background: rgba(74, 222, 128, 0.1);
  border-color: rgba(74, 222, 128, 0.28);
}

html.dark .wb-node-item__type {
  background: rgba(96, 165, 250, 0.18);
  color: #93c5fd;
}

html.dark .wb-status-dot {
  background: rgba(148, 163, 184, 0.06);
}

html.dark .wb-status-dot.is-dirty {
  background: rgba(74, 222, 128, 0.14);
  color: #4ade80;
}

html.dark .wb-center__pending-badge {
  background: rgba(251, 191, 36, 0.14);
  color: #fbbf24;
}
</style>
