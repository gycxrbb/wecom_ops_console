<template>
  <div class="wb-left-nav">
    <div class="wb-left-nav__plan-section">
      <el-select
        :model-value="currentPlanId"
        placeholder="选择主题"
        filterable
        size="small"
        @change="handlePlanChange"
      >
        <el-option v-for="plan in plans" :key="plan.id" :label="plan.name" :value="plan.id" />
      </el-select>
      <div v-if="currentPlan" class="wb-left-nav__plan-meta">
        <span>{{ currentPlan.stage || '未分阶段' }}</span>
        <span>{{ currentPlan.day_count }}天 · {{ currentPlan.node_count }}个节点</span>
      </div>
      <div v-if="currentPlan" class="wb-left-nav__plan-name-row">
        <template v-if="!isRenaming">
          <span class="wb-left-nav__plan-name" :title="currentPlan.name">{{ currentPlan.name }}</span>
          <el-button text size="small" @click="startRename">
            <el-icon :size="14"><Edit /></el-icon>
          </el-button>
        </template>
        <template v-else>
          <el-input
            ref="renameInputRef"
            v-model="renameValue"
            size="small"
            maxlength="50"
            @keyup.enter="confirmRename"
            @keyup.escape="cancelRename"
            @blur="confirmRename"
          />
        </template>
      </div>
      <div class="wb-left-nav__plan-actions">
        <el-dropdown v-if="currentPlanId" trigger="click" @command="handleExport">
          <el-button text size="small" type="primary">导出</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="json">导出 JSON</el-dropdown-item>
              <el-dropdown-item command="excel">导出 Excel</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button text size="small" type="danger" @click="$emit('remove-plan', currentPlan)">删除主题</el-button>
      </div>
    </div>

    <div class="wb-left-nav__toolbar">
      <label class="wb-left-nav__filter">
        <input type="checkbox" v-model="showPendingOnly" />
        <span>只看未完成</span>
      </label>
      <div class="wb-left-nav__toolbar-right">
        <button class="wb-left-nav__action" @click="$emit('jump-pending')">回到待完善</button>
        <button class="wb-left-nav__action wb-left-nav__action--add" @click="$emit('add-day')">+ 新增天数</button>
      </div>
    </div>

    <div class="wb-left-nav__day-list">
      <button
        v-for="day in filteredDays"
        :key="day.id"
        class="wb-day-item"
        :class="{ 'is-active': currentDayId === day.id }"
        @click="$emit('select-day', day.id)"
      >
        <div class="wb-day-item__label">
          <strong>Day {{ day.day_number }}</strong>
          <span>{{ day.title }}</span>
        </div>
        <div class="wb-day-item__progress">
          <div class="wb-day-item__bar-track">
            <div class="wb-day-item__bar" :style="{ width: completionPercent(day) + '%' }" />
          </div>
          <span class="wb-day-item__count">{{ completedCount(day) }}/{{ day.nodes?.length || 0 }}</span>
        </div>
        <el-icon
          class="wb-day-item__delete"
          @click.stop="$emit('remove-day', day.id)"
          :size="14"
        ><Close /></el-icon>
      </button>
      <el-empty v-if="!filteredDays.length" description="没有天数数据" :image-size="40" />
    </div>

    <div class="wb-left-nav__footer">
      <el-button type="primary" size="small" style="width: 100%" @click="$emit('create-plan')">新建主题</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { Edit, Close } from '@element-plus/icons-vue'
import type { PlanDay } from '../composables/useOperationPlans'

interface Plan {
  id: number
  name: string
  stage?: string
  topic?: string
  day_count: number
  node_count: number
}

const props = defineProps<{
  plans: Plan[]
  currentPlanId: number | null
  days: PlanDay[]
  currentDayId: number | null
  completedCount: (day: PlanDay) => number
  completionPercent: (day: PlanDay) => number
}>()

const emit = defineEmits<{
  'select-plan': [planId: number]
  'select-day': [dayId: number]
  'create-plan': []
  'remove-plan': [plan: Plan | null]
  'rename-plan': [planId: number, newName: string]
  'jump-pending': []
  'add-day': []
  'remove-day': [dayId: number]
  'export-plan': [planId: number, format: 'json' | 'excel']
}>()

const handleExport = (format: string) => {
  if (props.currentPlanId) {
    emit('export-plan', props.currentPlanId, format as 'json' | 'excel')
  }
}

const showPendingOnly = ref(false)

const isRenaming = ref(false)
const renameValue = ref('')
const renameInputRef = ref<InstanceType<typeof import('element-plus')['ElInput']>>()

const startRename = () => {
  if (!currentPlan.value) return
  renameValue.value = currentPlan.value.name
  isRenaming.value = true
  nextTick(() => renameInputRef.value?.focus())
}

const confirmRename = () => {
  if (!isRenaming.value || !currentPlan.value) return
  const trimmed = renameValue.value.trim()
  isRenaming.value = false
  if (trimmed && trimmed !== currentPlan.value.name) {
    emit('rename-plan', currentPlan.value.id, trimmed)
  }
}

const cancelRename = () => {
  isRenaming.value = false
}

const currentPlan = computed(() => props.plans.find(p => p.id === props.currentPlanId) || null)

const filteredDays = computed(() => {
  if (!showPendingOnly.value) return props.days
  return props.days.filter(d => d.nodes?.some(n => n.status === 'draft'))
})

const handlePlanChange = (planId: number) => {
  emit('select-plan', planId)
}
</script>

<script lang="ts">
export default { name: 'WorkbenchLeftNav' }
</script>

<style scoped>
.wb-left-nav {
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
  overflow: hidden;
}

.wb-left-nav__plan-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.wb-left-nav__plan-meta {
  display: flex;
  gap: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.wb-left-nav__plan-name-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.wb-left-nav__plan-name {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-left-nav__plan-actions {
  display: flex;
  justify-content: flex-end;
}

.wb-left-nav__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
}

.wb-left-nav__toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wb-left-nav__filter {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
}

.wb-left-nav__action {
  appearance: none;
  border: none;
  background: none;
  color: var(--primary-color);
  font-size: 12px;
  cursor: pointer;
}

.wb-left-nav__action--add {
  font-weight: 600;
}

.wb-left-nav__day-list {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.wb-day-item {
  appearance: none;
  border: none;
  border-radius: 10px;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
  background: transparent;
  transition: background 0.15s ease;
  position: relative;
}

.wb-day-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 3px;
  border-radius: 2px;
  background: transparent;
  transition: background 0.15s ease;
}

.wb-day-item:hover {
  background: rgba(34, 197, 94, 0.04);
}

.wb-day-item.is-active::before {
  background: var(--primary-color);
}

.wb-day-item.is-active {
  background: rgba(34, 197, 94, 0.06);
}

.wb-day-item__label {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.wb-day-item__label strong {
  color: var(--text-primary);
  font-size: 13px;
}

.wb-day-item__label span {
  color: var(--text-muted);
  font-size: 12px;
}

.wb-day-item__progress {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}

.wb-day-item__bar-track {
  flex: 1;
  height: 3px;
  border-radius: 2px;
  background: rgba(148, 163, 184, 0.16);
}

.wb-day-item__bar {
  height: 100%;
  border-radius: 2px;
  background: var(--primary-color);
  transition: width 0.3s ease;
}

.wb-day-item__count {
  color: var(--text-muted);
  font-size: 11px;
}

.wb-day-item__delete {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
  cursor: pointer;
}
.wb-day-item:hover .wb-day-item__delete {
  opacity: 1;
}
.wb-day-item__delete:hover {
  color: #f56c6c;
}

.wb-left-nav__footer {
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
}

:global(html.dark) .wb-day-item:hover {
  background: rgba(74, 222, 128, 0.06);
}

:global(html.dark) .wb-day-item.is-active {
  background: rgba(74, 222, 128, 0.08);
}

:global(html.dark) .wb-day-item.is-active::before {
  background: #4ade80;
}

:global(html.dark) .wb-day-item__bar-track {
  background: rgba(255, 255, 255, 0.1);
}
</style>

<style>
html.dark .wb-day-item:hover {
  background: rgba(74, 222, 128, 0.06);
}

html.dark .wb-day-item.is-active {
  background: rgba(74, 222, 128, 0.08);
}

html.dark .wb-day-item.is-active::before {
  background: #4ade80;
}

html.dark .wb-day-item__bar-track {
  background: rgba(255, 255, 255, 0.1);
}
</style>
