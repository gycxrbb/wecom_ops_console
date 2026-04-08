<template>
  <el-dialog
    v-model="visible"
    title="引用内容"
    width="820px"
    :append-to-body="true"
    :close-on-click-modal="true"
    class="content-selector-dialog"
    @open="onOpen"
  >
    <el-tabs v-model="activeTab" class="content-selector__tabs">
      <!-- 模板库 -->
      <el-tab-pane label="模板库" name="templates">
        <el-input
          v-model="templateSearch"
          placeholder="搜索模板名称..."
          clearable
          prefix-icon="Search"
          class="content-selector__search"
        />
        <div v-if="filteredTemplates.length" class="content-selector__list">
          <div
            v-for="t in filteredTemplates"
            :key="'tpl-' + t.id"
            class="content-selector__item"
            :class="{ 'is-selected': isSelected('template', t.id) }"
            @click="selectTemplate(t)"
          >
            <div class="content-selector__item-main">
              <span class="content-selector__item-name">{{ t.name }}</span>
              <span v-if="t.category" class="content-selector__item-desc">{{ t.category }}</span>
            </div>
            <el-tag size="small" :type="tagTypeByMsgType(t.msg_type)">{{ msgTypeLabel(t.msg_type) }}</el-tag>
          </div>
        </div>
        <div v-else class="content-selector__empty">
          <span>暂无模板</span>
        </div>
      </el-tab-pane>

      <!-- 运营编排：左右分栏 -->
      <el-tab-pane label="运营编排" name="plans">
        <div class="plan-layout">
          <!-- 左栏：计划列表 -->
          <div class="plan-sidebar">
            <div class="plan-sidebar__header">运营计划</div>
            <div v-if="plansLoading" class="content-selector__loading">
              <el-icon class="is-loading"><Loading /></el-icon>
            </div>
            <div v-else-if="plans.length === 0" class="content-selector__empty" style="padding: 30px 10px">
              <span>暂无运营编排</span>
            </div>
            <div v-else class="plan-sidebar__list">
              <div
                v-for="plan in plans"
                :key="plan.id"
                class="plan-sidebar__item"
                :class="{ 'is-active': selectedPlanId === plan.id }"
                @click="selectPlan(plan)"
              >
                <div class="plan-sidebar__name">{{ plan.name }}</div>
                <div class="plan-sidebar__meta">{{ plan.day_count }}天 · {{ plan.node_count }}个节点</div>
              </div>
            </div>
          </div>

          <!-- 右栏：天数跳转 + 节点列表 -->
          <div class="plan-main">
            <template v-if="selectedPlanDetail">
              <!-- 搜索 -->
              <el-input
                v-model="nodeSearch"
                placeholder="搜索节点标题..."
                clearable
                prefix-icon="Search"
                size="default"
                class="content-selector__search"
              />

              <!-- 天数快速跳转（搜索时隐藏） -->
              <div v-if="!nodeSearch.trim()" class="day-chips">
                <button
                  class="day-chip"
                  :class="{ 'is-active': selectedDayNumber === day.day_number }"
                  v-for="day in currentDays"
                  :key="day.id"
                  @click="selectedDayNumber = day.day_number"
                >{{ day.day_number }}</button>
              </div>

              <!-- 节点列表 -->
              <div class="node-list">
                <template v-if="nodeSearch.trim()">
                  <div v-if="searchResults.length === 0" class="content-selector__empty" style="padding: 30px 10px">
                    <span>未找到匹配节点</span>
                  </div>
                  <template v-for="group in searchResults" :key="group.day.id">
                    <div class="node-list__day-label">
                      第{{ group.day.day_number }}天
                      <span v-if="group.day.title && group.day.title !== `第${group.day.day_number}天`"> · {{ group.day.title }}</span>
                    </div>
                    <div
                      v-for="node in group.nodes"
                      :key="node.id"
                      class="content-selector__item"
                      :class="{ 'is-selected': isSelected('plan_node', node.id) }"
                      @click="selectNode(selectedPlan!, group.day, node)"
                    >
                      <div class="content-selector__item-main">
                        <span class="content-selector__item-name">{{ node.title }}</span>
                      </div>
                      <el-tag size="small" :type="tagTypeByMsgType(node.msg_type)">{{ msgTypeLabel(node.msg_type) }}</el-tag>
                    </div>
                  </template>
                </template>
                <template v-else>
                  <div v-if="selectedDay" class="node-list__day-title">
                    第{{ selectedDay.day_number }}天
                    <span v-if="selectedDay.title && selectedDay.title !== `第${selectedDay.day_number}天`"> · {{ selectedDay.title }}</span>
                  </div>
                  <div v-if="selectedDayNodes.length === 0" class="content-selector__empty" style="padding: 30px 10px">
                    <span>该天暂无节点</span>
                  </div>
                  <div
                    v-for="node in selectedDayNodes"
                    :key="node.id"
                    class="content-selector__item"
                    :class="{ 'is-selected': isSelected('plan_node', node.id) }"
                    @click="selectNode(selectedPlan!, selectedDay!, node)"
                  >
                    <div class="content-selector__item-main">
                      <span class="content-selector__item-name">{{ node.title }}</span>
                      <span v-if="node.description" class="content-selector__item-desc">{{ node.description }}</span>
                    </div>
                    <el-tag size="small" :type="tagTypeByMsgType(node.msg_type)">{{ msgTypeLabel(node.msg_type) }}</el-tag>
                  </div>
                </template>
              </div>
            </template>

            <div v-else-if="loadingPlanDetail" class="content-selector__loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>加载中...</span>
            </div>

            <div v-else class="content-selector__empty">
              <span>请先选择左侧的运营计划</span>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { msgTypeLabel } from '@/views/Templates/composables/useTemplates'
import request from '@/utils/request'
import type { PropType } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  templates: { type: Array as PropType<any[]>, default: () => [] },
  selectedSource: { type: String as PropType<'template' | 'plan_node' | null>, default: null },
  selectedId: { type: Number as PropType<number | null>, default: null }
})

const emit = defineEmits(['update:modelValue', 'select'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const activeTab = ref('templates')
const templateSearch = ref('')
const plans = ref<any[]>([])
const plansLoading = ref(false)
const planDetailMap = ref<Record<number, any>>({})
const loadingPlanDetail = ref(false)
const selectedPlanId = ref<number | null>(null)
const selectedDayNumber = ref<number | null>(null)
const nodeSearch = ref('')

// ---------- computed ----------

const filteredTemplates = computed(() => {
  const kw = templateSearch.value.trim().toLowerCase()
  if (!kw) return props.templates
  return props.templates.filter((t: any) =>
    t.name?.toLowerCase().includes(kw) ||
    t.category?.toLowerCase().includes(kw)
  )
})

const selectedPlan = computed(() =>
  plans.value.find((p: any) => p.id === selectedPlanId.value) || null
)

const selectedPlanDetail = computed(() =>
  selectedPlanId.value != null ? planDetailMap.value[selectedPlanId.value] : null
)

const currentDays = computed(() => {
  const detail = selectedPlanDetail.value
  if (!detail?.days) return []
  return [...detail.days].sort((a: any, b: any) => a.day_number - b.day_number)
})

const selectedDay = computed(() => {
  if (selectedDayNumber.value == null) return null
  return currentDays.value.find((d: any) => d.day_number === selectedDayNumber.value) || null
})

const selectedDayNodes = computed(() => {
  const day = selectedDay.value
  if (!day?.nodes) return []
  return [...day.nodes].sort((a: any, b: any) => a.sort_order - b.sort_order)
})

const searchResults = computed(() => {
  const kw = nodeSearch.value.trim().toLowerCase()
  if (!kw) return []
  const results: { day: any; nodes: any[] }[] = []
  for (const day of currentDays.value) {
    const matched = (day.nodes || []).filter((n: any) =>
      n.title?.toLowerCase().includes(kw) ||
      n.description?.toLowerCase().includes(kw)
    )
    if (matched.length) {
      results.push({ day, nodes: matched.sort((a: any, b: any) => a.sort_order - b.sort_order) })
    }
  }
  return results
})

const isSelected = (source: string, id: number) =>
  props.selectedSource === source && props.selectedId === id

// ---------- helpers ----------

const tagTypeByMsgType = (msgType: string) => {
  const map: Record<string, string> = {
    text: '', markdown: 'success', image: 'warning', news: 'danger', file: 'info', template_card: ''
  }
  return map[msgType] || ''
}

const parseJsonField = (raw: any) => {
  if (!raw) return {}
  if (typeof raw === 'string') {
    try { return JSON.parse(raw) } catch { return {} }
  }
  return raw
}

// ---------- actions ----------

const selectTemplate = (t: any) => {
  emit('select', {
    source: 'template',
    id: t.id,
    label: `模板: ${t.name}`,
    msg_type: t.msg_type,
    contentJson: parseJsonField(t.content_json ?? t.content),
    variablesJson: parseJsonField(t.variables_json ?? t.variable_schema)
  })
  visible.value = false
}

const selectNode = (plan: any, day: any, node: any) => {
  emit('select', {
    source: 'plan_node',
    id: node.id,
    label: `编排: ${plan.name} > 第${day.day_number}天 > ${node.title}`,
    msg_type: node.msg_type,
    contentJson: node.content_json || {},
    variablesJson: node.variables_json || {}
  })
  visible.value = false
}

const selectPlan = (plan: any) => {
  selectedPlanId.value = plan.id
  nodeSearch.value = ''
  fetchPlanDetail(plan.id)
  // 默认选中第一天
  const detail = planDetailMap.value[plan.id]
  if (detail?.days?.length) {
    const sorted = [...detail.days].sort((a: any, b: any) => a.day_number - b.day_number)
    selectedDayNumber.value = sorted[0].day_number
  } else {
    selectedDayNumber.value = 1
  }
}

// ---------- data fetching ----------

const onOpen = () => {
  activeTab.value = 'templates'
  templateSearch.value = ''
  nodeSearch.value = ''
  selectedPlanId.value = null
  selectedDayNumber.value = null
  fetchPlans()
}

const fetchPlans = async () => {
  plansLoading.value = true
  try {
    const res = await request.get('/v1/operation-plans')
    plans.value = Array.isArray(res) ? res : (res.list || [])
  } catch {
    plans.value = []
  } finally {
    plansLoading.value = false
  }
}

const fetchPlanDetail = async (planId: number) => {
  if (planDetailMap.value[planId]) {
    // 已有数据时只更新默认天数
    const detail = planDetailMap.value[planId]
    if (detail?.days?.length && selectedDayNumber.value == null) {
      const sorted = [...detail.days].sort((a: any, b: any) => a.day_number - b.day_number)
      selectedDayNumber.value = sorted[0].day_number
    }
    return
  }
  loadingPlanDetail.value = true
  try {
    const res = await request.get(`/v1/operation-plans/${planId}`)
    planDetailMap.value[planId] = res
    if (res?.days?.length) {
      const sorted = [...res.days].sort((a: any, b: any) => a.day_number - b.day_number)
      selectedDayNumber.value = sorted[0].day_number
    }
  } catch {
    planDetailMap.value[planId] = { days: [] }
  } finally {
    loadingPlanDetail.value = false
  }
}
</script>

<style scoped>
.content-selector__search {
  margin-bottom: 12px;
}
.content-selector__list {
  max-height: 420px;
  overflow-y: auto;
}

.content-selector__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  gap: 10px;
}
.content-selector__item:hover {
  background: var(--fill-color-light, #f5f7fa);
}
html.dark .content-selector__item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.content-selector__item.is-selected {
  background: rgba(var(--el-color-primary-rgb), 0.08);
  outline: 2px solid var(--el-color-primary);
}

.content-selector__item-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.content-selector__item-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.content-selector__item-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.content-selector__empty {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 14px;
}
.content-selector__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 30px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

/* ---- 运营编排：左右分栏 ---- */
.plan-layout {
  display: flex;
  gap: 0;
  height: 460px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
}

.plan-sidebar {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  background: rgba(0, 0, 0, 0.015);
}
html.dark .plan-sidebar {
  background: rgba(255, 255, 255, 0.02);
}
.plan-sidebar__header {
  padding: 12px 16px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.plan-sidebar__list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}
.plan-sidebar__item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 4px;
}
.plan-sidebar__item:hover {
  background: var(--fill-color-light, #f5f7fa);
}
html.dark .plan-sidebar__item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.plan-sidebar__item.is-active {
  background: rgba(var(--el-color-primary-rgb), 0.1);
}
.plan-sidebar__item.is-active .plan-sidebar__name {
  color: var(--el-color-primary);
  font-weight: 600;
}
.plan-sidebar__name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.plan-sidebar__meta {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.plan-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow: hidden;
}
.plan-main > .content-selector__search {
  flex-shrink: 0;
}

/* 天数快速跳转 chips */
.day-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
  flex-shrink: 0;
  max-height: 80px;
  overflow-y: auto;
  padding: 2px 0;
}
.day-chip {
  appearance: none;
  border: 1px solid var(--border-color);
  background: var(--card-bg, #fff);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  line-height: 1.4;
}
.day-chip:hover {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}
.day-chip.is-active {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
  color: #fff;
}

/* 节点列表 */
.node-list {
  flex: 1;
  overflow-y: auto;
}
.node-list__day-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-primary);
  padding: 8px 14px 4px;
}
.node-list__day-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 6px 0 8px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 6px;
}

/* Dialog tweaks */
.content-selector-dialog :deep(.el-dialog__body) {
  padding-top: 10px;
  padding-bottom: 10px;
}
.content-selector__tabs :deep(.el-tabs__content) {
  min-height: 460px;
}
</style>
