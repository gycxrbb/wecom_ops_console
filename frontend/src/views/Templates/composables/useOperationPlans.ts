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
  trigger_rule_json: Record<string, any>
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
  plan_mode: string
  status: string
  updated_at: string
  day_count: number
  node_count: number
  days?: PlanDay[]
}

export function useOperationPlans() {
  const plans = ref<OperationPlan[]>([])
  const presets = ref<Array<{ node_type: string; title: string; description: string; sort_order: number; msg_type: string }>>([])
  const campaignStages = ref<any[]>([])
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
    plan_mode: 'day_flow' as 'day_flow' | 'points_campaign',
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
  const isCampaignMode = computed(() => currentPlan.value?.plan_mode === 'points_campaign')
  const dayLabel = computed(() => isCampaignMode.value ? '阶段' : '天')
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
      const [planRes, presetRes, stagesRes]: any = await Promise.all([
        request.get('/v1/operation-plans'),
        request.get('/v1/operation-plans/meta/node-presets'),
        request.get('/v1/operation-plans/meta/campaign-stages').catch(() => []),
      ])
      presets.value = presetRes || []
      campaignStages.value = Array.isArray(stagesRes) ? stagesRes : []
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

  const renamePlan = async (planId: number, newName: string) => {
    if (!newName.trim()) {
      ElMessage.warning('主题名称不能为空')
      return
    }
    const plan = plans.value.find(p => p.id === planId)
    if (!plan) return
    try {
      await request.put(`/v1/operation-plans/${planId}`, {
        name: newName.trim(),
        topic: plan.topic,
        stage: plan.stage,
        description: plan.description,
        plan_mode: plan.plan_mode,
        status: plan.status
      })
      plan.name = newName.trim()
      ElMessage.success('主题已重命名')
    } catch (error) {
      console.error(error)
      ElMessage.error('重命名失败')
    }
  }

  const openCreatePlan = () => {
    planForm.id = null
    planForm.name = ''
    planForm.topic = ''
    planForm.stage = ''
    planForm.description = ''
    planForm.plan_mode = 'day_flow'
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
        plan_mode: planForm.plan_mode,
        day_count: planForm.plan_mode === 'points_campaign' ? 0 : planForm.day_count,
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
        trigger_rule_json: payload.trigger_rule_json ?? currentDay.value.trigger_rule_json,
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

  const addDay = async (dayNumber?: number) => {
    if (!currentPlan.value) return
    const plan = currentPlan.value
    const maxDay = plan.days?.length ? Math.max(...plan.days.map(d => d.day_number)) : 0
    const nextDay = dayNumber ?? (maxDay + 1)
    try {
      const saved = await request.post(`/v1/operation-plans/${plan.id}/days`, {
        day_number: nextDay,
        title: `第${nextDay}天`,
        focus: '',
        auto_init_nodes: true
      })
      if (plan.days) {
        plan.days.push(saved)
        plan.day_count = plan.days.length
        plan.node_count = plan.days.reduce((sum, d) => sum + (d.nodes?.length || 0), 0)
      }
      activeDayId.value = saved.id
      activeNodeId.value = saved.nodes?.[0]?.id || null
      ElMessage.success(`第${nextDay}天已添加`)
    } catch (error: any) {
      console.error(error)
      ElMessage.error(error?.response?.data?.detail || '添加天数失败')
    }
  }

  const removeDay = async (dayId: number) => {
    const plan = currentPlan.value
    if (!plan?.days) return
    const day = plan.days.find(d => d.id === dayId)
    if (!day) return
    try {
      await ElMessageBox.confirm(`确认删除第${day.day_number}天及其所有节点吗？`, '删除天数', { type: 'warning' })
      await request.delete(`/v1/operation-plans/days/${dayId}`)
      plan.days = plan.days.filter(d => d.id !== dayId)
      plan.day_count = plan.days.length
      plan.node_count = plan.days.reduce((sum, d) => sum + (d.nodes?.length || 0), 0)
      if (activeDayId.value === dayId) {
        const remaining = plan.days.sort((a, b) => a.day_number - b.day_number)
        const fallback = remaining[0]
        activeDayId.value = fallback?.id || null
        activeNodeId.value = fallback?.nodes?.[0]?.id || null
      }
      ElMessage.success('天数已删除')
    } catch {
      // cancel
    }
  }

  const addNode = async (afterNodeId?: number | null, overrides?: Partial<PlanNode>) => {
    if (!currentDay.value) return
    const day = currentDay.value
    // 计算插入位置的 sort_order
    let sortOrder: number
    const refId = afterNodeId ?? activeNodeId.value
    if (refId) {
      const refIdx = day.nodes?.findIndex(n => n.id === refId)
      if (refIdx >= 0 && refIdx < (day.nodes?.length || 0) - 1) {
        const prev = day.nodes[refIdx].sort_order
        const next = day.nodes[refIdx + 1].sort_order
        sortOrder = Math.round((prev + next) / 2)
      } else {
        const maxSort = day.nodes?.length ? Math.max(...day.nodes.map(n => n.sort_order)) : 0
        sortOrder = maxSort + 10
      }
    } else {
      const maxSort = day.nodes?.length ? Math.max(...day.nodes.map(n => n.sort_order)) : 0
      sortOrder = maxSort + 10
    }
    try {
      const saved = await request.post(`/v1/operation-plans/days/${day.id}/nodes`, {
        node_type: overrides?.node_type || 'custom',
        title: overrides?.title || '新节点',
        description: overrides?.description || '',
        sort_order: sortOrder,
        msg_type: overrides?.msg_type || 'markdown',
        content_json: overrides?.content_json || { content: '' },
        variables_json: overrides?.variables_json || {},
        status: 'draft',
        enabled: true
      })
      if (day.nodes) {
        day.nodes.push(saved)
        day.nodes.sort((a, b) => a.sort_order - b.sort_order)
        day.node_count = day.nodes.length
      }
      activeNodeId.value = saved.id
      ElMessage.success('节点已添加')
    } catch (error: any) {
      console.error(error)
      ElMessage.error(error?.response?.data?.detail || '添加节点失败')
    }
  }

  const removeNode = async (nodeId: number) => {
    const day = currentDay.value
    if (!day?.nodes) return
    const node = day.nodes.find(n => n.id === nodeId)
    if (!node) return
    try {
      await ElMessageBox.confirm(`确认删除节点「${node.title}」吗？`, '删除节点', { type: 'warning' })
      await request.delete(`/v1/operation-plans/nodes/${nodeId}`)
      day.nodes = day.nodes.filter(n => n.id !== nodeId)
      day.node_count = day.nodes.length
      if (activeNodeId.value === nodeId) {
        activeNodeId.value = day.nodes[0]?.id || null
      }
      if (currentPlan.value) {
        currentPlan.value.node_count = currentPlan.value.days?.reduce((sum, d) => sum + (d.nodes?.length || 0), 0) || 0
      }
      ElMessage.success('节点已删除')
    } catch {
      // cancel
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

  const exportPlan = async (planId: number, format: 'json' | 'excel') => {
    try {
      const token = localStorage.getItem('access_token') || ''
      const url = `/api/v1/operation-plans/${planId}/export?format=${format}`
      const resp = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!resp.ok) throw new Error('导出失败')
      const blob = await resp.blob()
      const disposition = resp.headers.get('Content-Disposition') || ''
      const match = disposition.match(/filename="?(.+?)"?$/)
      const filename = match ? match[1] : `plan-${planId}.${format === 'excel' ? 'xlsx' : 'json'}`
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = filename
      a.click()
      URL.revokeObjectURL(a.href)
      ElMessage.success('导出成功')
    } catch (e: any) {
      ElMessage.error('导出失败: ' + (e?.message || String(e)))
    }
  }

  return {
    plans,
    presets,
    campaignStages,
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
    isCampaignMode,
    dayLabel,
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
    addDay,
    removeDay,
    addNode,
    removeNode,
    openCreatePlan,
    openCopyDay,
    openBatchCopyDay,
    openSyncNode,
    savePlan,
    updateNode,
    applyTemplateToNode,
    updateDayMeta,
    removePlan,
    renamePlan,
    copyDayContent,
    batchCopyDayContent,
    syncNodeToPeerDays,
    exportPlan
  }
}
