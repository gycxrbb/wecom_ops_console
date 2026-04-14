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
        <div class="tpl-filter-bar">
          <div class="tpl-type-chips">
            <button
              type="button"
              class="tpl-type-chip"
              :class="{ 'is-active': templateTypeFilter === '' }"
              @click="templateTypeFilter = ''"
            >全部</button>
            <button
              v-for="opt in templateTypeOptions"
              :key="opt.value"
              type="button"
              class="tpl-type-chip"
              :class="{ 'is-active': templateTypeFilter === opt.value }"
              @click="templateTypeFilter = opt.value"
            >{{ opt.label }}</button>
          </div>
          <el-input
            v-model="templateSearch"
            placeholder="搜索模板..."
            clearable
            prefix-icon="Search"
            size="small"
            class="tpl-filter-bar__search"
          />
        </div>
        <div v-if="filteredTemplates.length" class="content-selector__list">
          <template v-for="group in templateGroups" :key="group.type">
            <div v-if="group.items.length" class="tpl-group">
              <div class="tpl-group__header">{{ group.label }} <span class="tpl-group__count">{{ group.items.length }}</span></div>
              <div
                v-for="t in group.items"
                :key="'tpl-' + t.id"
                class="content-selector__item"
                :class="{ 'is-selected': isSelected('template', t.id) }"
                @click="selectTemplate(t)"
              >
                <div class="content-selector__item-main">
                  <span class="content-selector__item-name">{{ t.name }}</span>
                  <span v-if="t.category" class="content-selector__item-desc">{{ t.category }}</span>
                </div>
              </div>
            </div>
          </template>
        </div>
        <div v-else class="content-selector__empty">
          <span>{{ templateTypeFilter ? '该类型暂无模板' : '暂无模板' }}</span>
        </div>
      </el-tab-pane>

      <!-- 运营编排：左右分栏 -->
      <el-tab-pane label="运营编排" name="plans">
        <!-- 移动端 Tab 切换 -->
        <div v-if="isMobile" class="mobile-plan-tabs">
          <button type="button" :class="{ 'is-active': mobilePlanTab === 'list' }" @click="mobilePlanTab = 'list'">计划列表</button>
          <button type="button" :class="{ 'is-active': mobilePlanTab === 'nodes' }" @click="mobilePlanTab = 'nodes'">节点</button>
        </div>

        <div class="plan-layout" :class="{ 'is-mobile': isMobile }">
          <!-- 左栏：计划列表 -->
          <div v-show="!isMobile || mobilePlanTab === 'list'" class="plan-sidebar">
            <div class="plan-sidebar__header">运营计划</div>
            <el-input
              v-model="planSearch"
              placeholder="搜索计划..."
              clearable
              size="small"
              class="plan-sidebar__search"
            />
            <div v-if="plansLoading" class="content-selector__loading">
              <el-icon class="is-loading"><Loading /></el-icon>
            </div>
            <div v-else-if="plans.length === 0" class="content-selector__empty" style="padding: 30px 10px">
              <span>暂无运营编排</span>
            </div>
            <div v-else-if="filteredPlans.length === 0" class="content-selector__empty" style="padding: 20px 10px">
              <span>无匹配计划</span>
            </div>
            <div v-else class="plan-sidebar__list">
              <div
                v-for="plan in filteredPlans"
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
          <div v-show="!isMobile || mobilePlanTab === 'nodes'" class="plan-main">
            <template v-if="selectedPlanDetail">
              <!-- 搜索 -->
              <el-input
                v-model="nodeSearch"
                placeholder="搜索节点（跨全部计划）..."
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

              <!-- 批量选择工具栏 -->
              <div v-if="!nodeSearch.trim() && selectedDayNodes.length > 0" class="batch-toolbar">
                <el-checkbox
                  :model-value="currentDayCheckedAll"
                  :indeterminate="currentDayIndeterminate"
                  @change="toggleDayAll"
                >全选当天</el-checkbox>
                <span v-if="checkedCount > 0" class="batch-toolbar__count">已选 {{ checkedCount }} 项</span>
              </div>

              <!-- 节点列表 -->
              <div class="node-list">
                <template v-if="nodeSearch.trim()">
                  <div v-if="searchResults.length === 0" class="content-selector__empty" style="padding: 30px 10px">
                    <span>未找到匹配节点</span>
                  </div>
                  <template v-for="group in searchResults" :key="`${group.plan.id}-${group.day.id}`">
                    <div class="node-list__day-label">
                      {{ group.plan.name }}
                      <span class="node-list__day-sub"> · 第{{ group.day.day_number }}天
                        <template v-if="group.day.title && group.day.title !== `第${group.day.day_number}天`"> · {{ group.day.title }}</template>
                      </span>
                    </div>
                    <div
                      v-for="node in group.nodes"
                      :key="node.id"
                      class="content-selector__item"
                      :class="{ 'is-selected': isSelected('plan_node', node.id) }"
                      @click="selectNode(group.plan, group.day, node)"
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
                    class="content-selector__item content-selector__item--checkable"
                    :class="{ 'is-checked': checkedNodeIds.has(node.id) }"
                  >
                    <el-checkbox
                      :model-value="checkedNodeIds.has(node.id)"
                      @change="toggleNodeCheck(node.id)"
                      @click.stop
                    />
                    <div class="content-selector__item-main" @click="selectNode(selectedPlan!, selectedDay!, node)">
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
      <div class="dialog-footer">
        <div v-if="checkedCount > 0 && activeTab === 'plans'" class="dialog-footer__batch">
          <el-button type="primary" @click="confirmBatchSelect">
            确认选择 ({{ checkedCount }} 项)
          </el-button>
        </div>
        <el-button @click="visible = false">取消</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { msgTypeLabel, msgTypeOptions } from '@/views/Templates/composables/useTemplates'
import request from '@/utils/request'
import type { PropType } from 'vue'
import { useMobile } from '@/composables/useMobile'

const { isMobile } = useMobile()
const mobilePlanTab = ref<'list' | 'nodes'>('list')

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  templates: { type: Array as PropType<any[]>, default: () => [] },
  selectedSource: { type: String as PropType<'template' | 'plan_node' | null>, default: null },
  selectedId: { type: Number as PropType<number | null>, default: null }
})

const emit = defineEmits(['update:modelValue', 'select', 'select-batch'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const activeTab = ref('templates')
const templateSearch = ref('')
const templateTypeFilter = ref('')
const plans = ref<any[]>([])
const plansLoading = ref(false)
const planDetailMap = ref<Record<number, any>>({})
const loadingPlanDetail = ref(false)
const selectedPlanId = ref<number | null>(null)
const selectedDayNumber = ref<number | null>(null)
const nodeSearch = ref('')
const planSearch = ref('')
const checkedNodeIds = ref<Set<number>>(new Set())

// ---------- computed ----------

const templateTypeOptions = msgTypeOptions

const filteredTemplates = computed(() => {
  let list = props.templates as any[]
  if (templateTypeFilter.value) {
    list = list.filter((t: any) => t.msg_type === templateTypeFilter.value)
  }
  const kw = templateSearch.value.trim().toLowerCase()
  if (kw) {
    list = list.filter((t: any) =>
      t.name?.toLowerCase().includes(kw) ||
      t.category?.toLowerCase().includes(kw) ||
      t.description?.toLowerCase().includes(kw)
    )
  }
  return list
})

const templateGroups = computed(() => {
  const grouped = new Map<string, any[]>()
  for (const t of filteredTemplates.value) {
    const type = t.msg_type || 'unknown'
    if (!grouped.has(type)) grouped.set(type, [])
    grouped.get(type)!.push(t)
  }
  const order = msgTypeOptions.map(o => o.value)
  const result: { type: string; label: string; items: any[] }[] = []
  for (const type of order) {
    const items = grouped.get(type)
    if (items) {
      result.push({ type, label: msgTypeLabel(type), items })
    }
  }
  // 剩余未知类型
  for (const [type, items] of grouped) {
    if (!order.includes(type)) {
      result.push({ type, label: msgTypeLabel(type), items })
    }
  }
  return result
})

const selectedPlan = computed(() =>
  plans.value.find((p: any) => p.id === selectedPlanId.value) || null
)

const filteredPlans = computed(() => {
  const kw = planSearch.value.trim().toLowerCase()
  if (!kw) return plans.value
  return plans.value.filter((p: any) =>
    p.name?.toLowerCase().includes(kw) ||
    p.topic?.toLowerCase().includes(kw) ||
    p.stage?.toLowerCase().includes(kw)
  )
})

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

const nodeMatches = (n: any, kw: string): boolean => {
  if (n.title?.toLowerCase().includes(kw)) return true
  if (n.description?.toLowerCase().includes(kw)) return true
  if (msgTypeLabel(n.msg_type)?.toLowerCase().includes(kw)) return true
  // Search inside content_json (the actual message body text)
  const contentStr = typeof n.content_json === 'string' ? n.content_json : JSON.stringify(n.content_json || {})
  if (contentStr.toLowerCase().includes(kw)) return true
  return false
}

const searchResults = computed(() => {
  const kw = nodeSearch.value.trim().toLowerCase()
  if (!kw) return []
  const results: { plan: any; day: any; nodes: any[] }[] = []
  // Search across ALL loaded plans
  for (const plan of plans.value) {
    const detail = planDetailMap.value[plan.id]
    if (!detail?.days) continue
    for (const day of detail.days) {
      const matched = (day.nodes || []).filter((n: any) => nodeMatches(n, kw))
      if (matched.length) {
        results.push({ plan, day, nodes: matched.sort((a: any, b: any) => a.sort_order - b.sort_order) })
      }
    }
  }
  return results
})

const isSelected = (source: string, id: number) =>
  props.selectedSource === source && props.selectedId === id

// When user types in node search, load all plan details for cross-plan search
watch(nodeSearch, async (kw) => {
  if (!kw.trim()) return
  const unloaded = plans.value.filter(p => !planDetailMap.value[p.id])
  if (unloaded.length === 0) return
  await Promise.all(unloaded.map(p => fetchPlanDetail(p.id)))
})

// ---------- 批量选择 ----------

const currentDayCheckedAll = computed(() => {
  const nodes = selectedDayNodes.value
  if (!nodes.length) return false
  return nodes.every((n: any) => checkedNodeIds.value.has(n.id))
})

const currentDayIndeterminate = computed(() => {
  const nodes = selectedDayNodes.value
  if (!nodes.length) return false
  const cnt = nodes.filter((n: any) => checkedNodeIds.value.has(n.id)).length
  return cnt > 0 && cnt < nodes.length
})

const checkedCount = computed(() => checkedNodeIds.value.size)

const toggleDayAll = () => {
  const nodes = selectedDayNodes.value
  if (currentDayCheckedAll.value) {
    for (const n of nodes) checkedNodeIds.value.delete(n.id)
  } else {
    for (const n of nodes) checkedNodeIds.value.add(n.id)
  }
}

const toggleNodeCheck = (nodeId: number) => {
  if (checkedNodeIds.value.has(nodeId)) {
    checkedNodeIds.value.delete(nodeId)
  } else {
    checkedNodeIds.value.add(nodeId)
  }
}

const confirmBatchSelect = () => {
  const items: Array<{ id: number; title: string; msg_type: string; description: string; contentJson: Record<string, any>; variablesJson: Record<string, any> }> = []
  for (const day of currentDays.value) {
    for (const node of (day.nodes || [])) {
      if (checkedNodeIds.value.has(node.id)) {
        items.push({
          id: node.id,
          title: `${node.title} (第${day.day_number}天)`,
          msg_type: node.msg_type,
          description: node.description || '',
          contentJson: node.content_json || {},
          variablesJson: node.variables_json || {},
        })
      }
    }
  }
  if (items.length === 0) return
  emit('select-batch', items)
  visible.value = false
}

// ---------- helpers ----------

const tagTypeByMsgType = (msgType: string) => {
  const map: Record<string, string> = {
    text: '', markdown: 'success', image: 'warning', emotion: 'warning', news: 'danger', file: 'info', template_card: ''
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
  checkedNodeIds.value.clear()
  fetchPlanDetail(plan.id)
  const detail = planDetailMap.value[plan.id]
  if (detail?.days?.length) {
    const sorted = [...detail.days].sort((a: any, b: any) => a.day_number - b.day_number)
    selectedDayNumber.value = sorted[0].day_number
  } else {
    selectedDayNumber.value = 1
  }
  if (isMobile.value) mobilePlanTab.value = 'nodes'
}

// ---------- data fetching ----------

const onOpen = () => {
  activeTab.value = 'templates'
  templateSearch.value = ''
  templateTypeFilter.value = ''
  nodeSearch.value = ''
  planSearch.value = ''
  selectedPlanId.value = null
  selectedDayNumber.value = null
  checkedNodeIds.value.clear()
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
/* ---- 模板类型筛选 ---- */
.tpl-filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.tpl-type-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  flex-shrink: 0;
}
.tpl-type-chip {
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
  white-space: nowrap;
}
.tpl-type-chip:hover {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}
.tpl-type-chip.is-active {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
  color: #fff;
}
.tpl-filter-bar__search {
  flex: 1;
  min-width: 140px;
}
.tpl-group {
  margin-bottom: 6px;
}
.tpl-group__header {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  padding: 6px 14px 4px;
  position: sticky;
  top: 0;
  background: var(--card-bg, #fff);
  z-index: 1;
}
.tpl-group__count {
  font-weight: 400;
  color: var(--text-muted);
  opacity: 0.6;
  margin-left: 2px;
}

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
.content-selector__item--checkable {
  cursor: default;
}
.content-selector__item--checkable .content-selector__item-main {
  cursor: pointer;
  flex: 1;
  min-width: 0;
}
.content-selector__item.is-checked {
  background: rgba(var(--el-color-primary-rgb), 0.06);
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

/* ---- 批量选择工具栏 ---- */
.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0 10px;
  flex-shrink: 0;
}
.batch-toolbar__count {
  font-size: 12px;
  color: var(--el-color-primary);
  font-weight: 600;
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
.plan-sidebar__search {
  margin: 0 1px 8px 0.5px;
  flex-shrink: 0;
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
  line-clamp: 2;
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
.node-list__day-sub {
  font-weight: 400;
  color: var(--text-muted);
}
.node-list__day-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 6px 0 8px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 6px;
}

/* Dialog footer */
.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}
.dialog-footer__batch {
  margin-right: auto;
}

/* Dialog tweaks */
.content-selector-dialog :deep(.el-dialog__body) {
  padding-top: 10px;
  padding-bottom: 10px;
}
.content-selector__tabs :deep(.el-tabs__content) {
  min-height: 460px;
}

@media (max-width: 768px) {
  .plan-layout {
    flex-direction: column;
    height: auto;
    max-height: 60vh;
  }
  .plan-sidebar {
    width: 100%;
    min-width: 0;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
    max-height: 160px;
  }
  .plan-main {
    padding: 12px;
  }
  .content-selector__tabs :deep(.el-tabs__content) {
    min-height: 300px;
  }
}

.mobile-plan-tabs {
  display: flex;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 10px;
}
.mobile-plan-tabs button {
  flex: 1;
  padding: 9px 8px;
  text-align: center;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}
.mobile-plan-tabs button.is-active {
  color: var(--primary-color);
  font-weight: 700;
  background: rgba(34, 197, 94, 0.1);
}
</style>
