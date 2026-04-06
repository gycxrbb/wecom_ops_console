import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'
import type { TemplateItem } from './useTemplates'

export type PlanNode = {
  id: number
  plan_day_id: number
  node_type: string
  title: string
  description: string
  sort_order: number
  template_id: number | null
  msg_type: string
  content_json: Record<string, any>
  variables_json: Record<string, any>
  status: string
  enabled: boolean
  updated_at: string
}

export type PlanDay = {
  id: number
  plan_id: number
  day_number: number
  title: string
  focus: string
  status: string
  updated_at: string
  node_count: number
  nodes: PlanNode[]
}

export type OperationPlan = {
  id: number
  name: string
  topic: string
  stage: string
  description: string
  status: string
  updated_at: string
  day_count: number
  node_count: number
  days?: PlanDay[]
}

export function useOperationPlans() {
  const plans = ref<OperationPlan[]>([])
  const presets = ref<Array<{ node_type: string; title: string; description: string; sort_order: number; msg_type: string }>>([])
  const loading = ref(false)
  const activePlanId = ref<number | null>(null)
  const activeDayId = ref<number | null>(null)
  const activeNodeId = ref<number | null>(null)
  const planDialogVisible = ref(false)
  const copyDialogVisible = ref(false)
  const batchCopyDialogVisible = ref(false)
  const syncNodeDialogVisible = ref(false)
  const planForm = reactive({
    id: null as number | null,
    name: '',
    topic: '',
    stage: '',
    description: '',
    day_count: 30,
    status: 'draft'
  })
  const copyForm = reactive({
    sourceDayId: null as number | null
  })
  const batchCopyForm = reactive({
    targetDayIds: [] as number[]
  })
  const syncNodeForm = reactive({
    targetDayIds: [] as number[]
  })

  const currentPlan = computed(() => plans.value.find(plan => plan.id === activePlanId.value) || null)
  const days = computed(() => currentPlan.value?.days || [])
  const currentDay = computed(() => days.value.find(day => day.id === activeDayId.value) || null)
  const nodes = computed(() => currentDay.value?.nodes || [])
  const currentNode = computed(() => nodes.value.find(node => node.id === activeNodeId.value) || null)
  const completionSummary = computed(() => {
    const total = days.value.length
    const completed = days.value.filter(day => day.nodes?.every(node => node.status !== 'draft')).length
    return { total, completed }
  })
  const availableSourceDays = computed(() =>
    days.value.filter(day => day.id !== currentDay.value?.id)
  )
  const availableTargetDays = computed(() =>
    days.value.filter(day => day.id !== currentDay.value?.id)
  )

  const setDefaultSelection = () => {
    const firstPlan = plans.value[0] || null
    if (!firstPlan) {
      activePlanId.value = null
      activeDayId.value = null
      activeNodeId.value = null
      return
    }
    if (!activePlanId.value || !plans.value.some(plan => plan.id === activePlanId.value)) {
      activePlanId.value = firstPlan.id
    }
    const plan = plans.value.find(item => item.id === activePlanId.value) || firstPlan
    const firstDay = plan.days?.[0] || null
    if (!firstDay) {
      activeDayId.value = null
      activeNodeId.value = null
      return
    }
    if (!activeDayId.value || !plan.days?.some(day => day.id === activeDayId.value)) {
      activeDayId.value = firstDay.id
    }
    const day = plan.days?.find(item => item.id === activeDayId.value) || firstDay
    const firstNode = day.nodes?.[0] || null
    if (!firstNode) {
      activeNodeId.value = null
      return
    }
    if (!activeNodeId.value || !day.nodes?.some(node => node.id === activeNodeId.value)) {
      activeNodeId.value = firstNode.id
    }
  }

  const fetchPlans = async () => {
    loading.value = true
    try {
      const [planRes, presetRes]: any = await Promise.all([
        request.get('/v1/operation-plans'),
        request.get('/v1/operation-plans/meta/node-presets')
      ])
      presets.value = presetRes || []
      const list = Array.isArray(planRes) ? planRes : (planRes.list || [])
      const details = await Promise.all(list.map((plan: OperationPlan) => request.get(`/v1/operation-plans/${plan.id}`)))
      plans.value = details
      setDefaultSelection()
    } catch (error) {
      console.error(error)
      ElMessage.error('加载运营编排失败')
    } finally {
      loading.value = false
    }
  }

  const selectPlan = (planId: number) => {
    activePlanId.value = planId
    const plan = plans.value.find(item => item.id === planId)
    const firstDay = plan?.days?.[0]
    activeDayId.value = firstDay?.id || null
    activeNodeId.value = firstDay?.nodes?.[0]?.id || null
  }

  const selectDay = (dayId: number) => {
    activeDayId.value = dayId
    const day = days.value.find(item => item.id === dayId)
    activeNodeId.value = day?.nodes?.[0]?.id || null
  }

  const selectNode = (nodeId: number) => {
    activeNodeId.value = nodeId
  }

  const openCreatePlan = () => {
    planForm.id = null
    planForm.name = ''
    planForm.topic = ''
    planForm.stage = ''
    planForm.description = ''
    planForm.day_count = 30
    planForm.status = 'draft'
    planDialogVisible.value = true
  }

  const openCopyDay = () => {
    if (!currentDay.value) return
    copyForm.sourceDayId = availableSourceDays.value[0]?.id || null
    copyDialogVisible.value = true
  }

  const openBatchCopyDay = () => {
    if (!currentDay.value) return
    batchCopyForm.targetDayIds = []
    batchCopyDialogVisible.value = true
  }

  const openSyncNode = () => {
    if (!currentNode.value) return
    syncNodeForm.targetDayIds = []
    syncNodeDialogVisible.value = true
  }

  const savePlan = async () => {
    if (!planForm.name.trim()) {
      ElMessage.warning('请输入运营主题名称')
      return
    }
    try {
      const payload = {
        name: planForm.name,
        topic: planForm.topic,
        stage: planForm.stage,
        description: planForm.description,
        day_count: planForm.day_count,
        status: planForm.status
      }
      if (planForm.id) {
        await request.put(`/v1/operation-plans/${planForm.id}`, payload)
      } else {
        await request.post('/v1/operation-plans', payload)
      }
      planDialogVisible.value = false
      await fetchPlans()
      ElMessage.success('运营计划已保存')
    } catch (error) {
      console.error(error)
      ElMessage.error('保存运营计划失败')
    }
  }

  const updateNode = async (payload: Partial<PlanNode>) => {
    if (!currentNode.value) return null
    try {
      const nextPayload = {
        node_type: payload.node_type ?? currentNode.value.node_type,
        title: payload.title ?? currentNode.value.title,
        description: payload.description ?? currentNode.value.description,
        sort_order: payload.sort_order ?? currentNode.value.sort_order,
        template_id: payload.template_id ?? currentNode.value.template_id,
        msg_type: payload.msg_type ?? currentNode.value.msg_type,
        content_json: payload.content_json ?? currentNode.value.content_json,
        variables_json: payload.variables_json ?? currentNode.value.variables_json,
        status: payload.status ?? currentNode.value.status,
        enabled: payload.enabled ?? currentNode.value.enabled
      }
      const saved = await request.put(`/v1/operation-plans/nodes/${currentNode.value.id}`, nextPayload)
      const day = currentDay.value
      if (!day) return
      const nodeIndex = day.nodes.findIndex(node => node.id === saved.id)
      if (nodeIndex >= 0) {
        day.nodes.splice(nodeIndex, 1, saved)
      }
      ElMessage.success('流程节点已更新')
      return saved
    } catch (error) {
      console.error(error)
      ElMessage.error('更新流程节点失败')
      return null
    }
  }

  const applyTemplateToNode = async (template: TemplateItem) => {
    if (!currentNode.value) return
    const rawContent = template.content_json ?? template.content
    const rawVariables = template.variables_json ?? template.variable_schema
    let contentJson: Record<string, any> = {}
    let variablesJson: Record<string, any> = {}
    try {
      contentJson = typeof rawContent === 'string' ? JSON.parse(rawContent) : (rawContent || {})
    } catch {
      contentJson = {}
    }
    try {
      variablesJson = typeof rawVariables === 'string' ? JSON.parse(rawVariables) : (rawVariables || {})
    } catch {
      variablesJson = {}
    }
    await updateNode({
      template_id: template.id,
      title: currentNode.value.title || template.name,
      description: template.description || currentNode.value.description,
      msg_type: template.msg_type,
      content_json: contentJson,
      variables_json: variablesJson,
      status: 'ready'
    })
  }

  const updateDayMeta = async (payload: Partial<PlanDay>) => {
    if (!currentDay.value) return null
    try {
      const saved = await request.put(`/v1/operation-plans/days/${currentDay.value.id}`, {
        day_number: payload.day_number ?? currentDay.value.day_number,
        title: payload.title ?? currentDay.value.title,
        focus: payload.focus ?? currentDay.value.focus,
        status: payload.status ?? currentDay.value.status
      })
      const plan = currentPlan.value
      if (!plan?.days) return
      const index = plan.days.findIndex(day => day.id === saved.id)
      if (index >= 0) {
        plan.days.splice(index, 1, saved)
      }
      ElMessage.success('当天信息已更新')
      return saved
    } catch (error) {
      console.error(error)
      ElMessage.error('更新当天信息失败')
      return null
    }
  }

  const removePlan = async (plan: OperationPlan) => {
    try {
      await ElMessageBox.confirm(`确认删除运营计划「${plan.name}」吗？`, '删除运营计划', { type: 'warning' })
      await request.delete(`/v1/operation-plans/${plan.id}`)
      await fetchPlans()
      ElMessage.success('运营计划已删除')
    } catch {
      // ignore cancel
    }
  }

  const copyDayContent = async () => {
    if (!currentDay.value || !copyForm.sourceDayId) {
      ElMessage.warning('请选择要复制的来源天')
      return
    }
    try {
      const saved = await request.post(`/v1/operation-plans/days/${currentDay.value.id}/copy`, {
        source_day_id: copyForm.sourceDayId
      })
      const plan = currentPlan.value
      if (plan?.days) {
        const index = plan.days.findIndex(day => day.id === saved.id)
        if (index >= 0) {
          plan.days.splice(index, 1, saved)
        }
      }
      activeNodeId.value = saved.nodes?.[0]?.id || null
      copyDialogVisible.value = false
      ElMessage.success('已复制当天编排内容')
    } catch (error) {
      console.error(error)
      ElMessage.error('复制当天内容失败')
    }
  }

  const buildNodePayload = (node: PlanNode) => ({
    node_type: node.node_type,
    title: node.title,
    description: node.description,
    sort_order: node.sort_order,
    template_id: node.template_id,
    msg_type: node.msg_type,
    content_json: node.content_json,
    variables_json: node.variables_json,
    status: node.status,
    enabled: node.enabled
  })

  const batchCopyDayContent = async () => {
    if (!currentDay.value || !batchCopyForm.targetDayIds.length) {
      ElMessage.warning('请选择要覆盖的目标天')
      return
    }
    try {
      for (const targetDayId of batchCopyForm.targetDayIds) {
        await request.post(`/v1/operation-plans/days/${targetDayId}/copy`, {
          source_day_id: currentDay.value.id
        })
      }
      const currentPlanId = activePlanId.value
      const currentDayId = activeDayId.value
      const currentNodeId = activeNodeId.value
      await fetchPlans()
      if (currentPlanId) activePlanId.value = currentPlanId
      if (currentDayId) activeDayId.value = currentDayId
      if (currentNodeId) activeNodeId.value = currentNodeId
      batchCopyDialogVisible.value = false
      ElMessage.success(`已复制到 ${batchCopyForm.targetDayIds.length} 天`)
    } catch (error) {
      console.error(error)
      ElMessage.error('批量复制失败')
    }
  }

  const syncNodeToPeerDays = async () => {
    if (!currentNode.value || !syncNodeForm.targetDayIds.length) {
      ElMessage.warning('请选择要同步的目标天')
      return
    }
    const payload = buildNodePayload(currentNode.value)
    try {
      for (const targetDayId of syncNodeForm.targetDayIds) {
        const targetDay = days.value.find(day => day.id === targetDayId)
        const targetNode = targetDay?.nodes?.find(node => node.node_type === currentNode.value?.node_type)
        if (!targetNode) continue
        await request.put(`/v1/operation-plans/nodes/${targetNode.id}`, payload)
      }
      const currentPlanId = activePlanId.value
      const currentDayId = activeDayId.value
      const currentNodeId = activeNodeId.value
      await fetchPlans()
      if (currentPlanId) activePlanId.value = currentPlanId
      if (currentDayId) activeDayId.value = currentDayId
      if (currentNodeId) activeNodeId.value = currentNodeId
      syncNodeDialogVisible.value = false
      ElMessage.success(`已同步到 ${syncNodeForm.targetDayIds.length} 个同类节点`)
    } catch (error) {
      console.error(error)
      ElMessage.error('同步同类节点失败')
    }
  }

  onMounted(fetchPlans)

  return {
    plans,
    presets,
    loading,
    activePlanId,
    activeDayId,
    activeNodeId,
    currentPlan,
    currentDay,
    currentNode,
    days,
    nodes,
    completionSummary,
    planDialogVisible,
    copyDialogVisible,
    batchCopyDialogVisible,
    syncNodeDialogVisible,
    planForm,
    copyForm,
    batchCopyForm,
    syncNodeForm,
    availableSourceDays,
    availableTargetDays,
    fetchPlans,
    selectPlan,
    selectDay,
    selectNode,
    openCreatePlan,
    openCopyDay,
    openBatchCopyDay,
    openSyncNode,
    savePlan,
    updateNode,
    applyTemplateToNode,
    updateDayMeta,
    removePlan,
    copyDayContent,
    batchCopyDayContent,
    syncNodeToPeerDays
  }
}
