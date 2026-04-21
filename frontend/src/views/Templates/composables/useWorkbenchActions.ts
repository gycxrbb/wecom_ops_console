import { computed, onBeforeUnmount, onMounted, ref, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { PlanDay, PlanNode } from './useOperationPlans'

interface WorkbenchDeps {
  nodes: Ref<PlanNode[]>
  days: Ref<PlanDay[]>
  currentNode: Ref<PlanNode | null>
  currentDay: Ref<PlanDay | null>
  nodeDirty: Ref<boolean>
  nodeSaving: Ref<boolean>
  selectNode: (nodeId: number) => void
  selectDay: (dayId: number) => void
  addNode: (afterNodeId?: number | null, overrides?: Partial<PlanNode>) => Promise<void>
  saveNodeDraft: () => Promise<boolean>
  confirmDiscardDraft: () => Promise<boolean>
  pasteDayContent: (sourceDay: PlanDay, targetDay: PlanDay) => Promise<void>
}

export function useWorkbenchActions(deps: WorkbenchDeps) {
  // ===== 前后节点切换 =====

  const currentNodeIndex = computed(() =>
    deps.nodes.value.findIndex(n => n.id === deps.currentNode.value?.id)
  )

  const hasPrevNode = computed(() => currentNodeIndex.value > 0)
  const hasNextNode = computed(() =>
    currentNodeIndex.value >= 0 && currentNodeIndex.value < deps.nodes.value.length - 1
  )

  const goToPrevNode = async () => {
    if (!hasPrevNode.value) return
    if (!(await deps.confirmDiscardDraft())) return
    deps.selectNode(deps.nodes.value[currentNodeIndex.value - 1].id)
  }

  const goToNextNode = async () => {
    if (!hasNextNode.value) return
    if (!(await deps.confirmDiscardDraft())) return
    deps.selectNode(deps.nodes.value[currentNodeIndex.value + 1].id)
  }

  // ===== 保存并下一条 =====

  const saveAndNext = async () => {
    const idx = currentNodeIndex.value
    if (idx < 0 || !deps.currentNode.value || !deps.currentDay.value) return

    if (deps.nodeDirty.value) {
      const saved = await deps.saveNodeDraft()
      if (!saved) return
    }

    const nextNode = deps.nodes.value[idx + 1]
    if (nextNode) {
      deps.selectNode(nextNode.id)
      return
    }

    try {
      await ElMessageBox.confirm(
        `已经是第${deps.currentDay.value.day_number}天最后一个节点了，您是否需要新增一个节点？`,
        '最后一个节点',
        {
          confirmButtonText: '新增节点',
          cancelButtonText: '仅保存',
          distinguishCancelAndClose: true,
          closeOnClickModal: false,
          closeOnPressEscape: false,
          type: 'warning',
        }
      )
      await deps.addNode(deps.currentNode.value.id)
      return
    } catch (error) {
      if (error === 'cancel') {
        ElMessage.success('当前节点已保存')
      }
    }
  }

  // ===== 复制/粘贴节点 =====

  const copiedNode = ref<PlanNode | null>(null)

  const copiedDay = ref<PlanDay | null>(null)

  const copyNode = () => {
    const node = deps.currentNode.value
    if (!node) return
    copiedNode.value = { ...node }
    ElMessage.success(`已复制节点「${node.title}」`)
  }

  const pasteNode = async () => {
    if (!copiedNode.value) {
      ElMessage.warning('没有已复制的节点')
      return
    }
    const afterId = deps.currentNode.value?.id ?? null
    await deps.addNode(afterId, {
      title: copiedNode.value.title,
      description: copiedNode.value.description,
      msg_type: copiedNode.value.msg_type,
      content_json: copiedNode.value.content_json,
      variables_json: copiedNode.value.variables_json,
      node_type: copiedNode.value.node_type,
    })
    copiedNode.value = null
  }

  const copyDay = () => {
    const day = deps.currentDay.value
    if (!day) return
    copiedDay.value = { ...day }
    ElMessage.success(`已复制第${day.day_number}天`)
  }

  const pasteDay = async () => {
    if (!copiedDay.value) {
      ElMessage.warning('没有已复制的天')
      return
    }
    const targetDay = deps.currentDay.value
    if (!targetDay) {
      ElMessage.warning('请先选择目标天')
      return
    }
    if (targetDay.id === copiedDay.value.id) {
      ElMessage.warning('不能覆盖自己')
      return
    }
    try {
      await ElMessageBox.confirm(
        `确认将第${copiedDay.value.day_number}天内容覆盖到第${targetDay.day_number}天？目标天原有内容将被替换。`,
        '覆盖确认',
        { confirmButtonText: '确认覆盖', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
    await deps.pasteDayContent(copiedDay.value, targetDay)
    copiedDay.value = null
  }

  // ===== 键盘快捷键 =====

  const handleKeydown = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return

    if ((event.ctrlKey || event.metaKey) && event.key === 's') {
      event.preventDefault()
      if (deps.nodeDirty.value && !deps.nodeSaving.value) {
        deps.saveNodeDraft()
      }
      return
    }

    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault()
      if (deps.nodeDirty.value && !deps.nodeSaving.value) {
        saveAndNext()
      }
      return
    }

    // Ctrl+Alt+C: 复制天（必须在 Ctrl+C 之前判断）
    if ((event.ctrlKey || event.metaKey) && event.altKey && event.key.toLowerCase() === 'c') {
      event.preventDefault()
      if (deps.currentDay.value) copyDay()
      return
    }

    // Ctrl+Alt+V: 粘贴天（必须在 Ctrl+V 之前判断）
    if ((event.ctrlKey || event.metaKey) && event.altKey && event.key.toLowerCase() === 'v') {
      event.preventDefault()
      if (copiedDay.value) pasteDay()
      return
    }

    if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
      const selection = window.getSelection()
      if (selection && selection.toString().length > 0) return
      if (deps.currentNode.value) {
        event.preventDefault()
        copyNode()
      }
      return
    }

    if ((event.ctrlKey || event.metaKey) && event.key === 'v') {
      const selection = window.getSelection()
      if (selection && selection.toString().length > 0) return
      if (copiedNode.value) {
        event.preventDefault()
        pasteNode()
      }
      return
    }

    if (event.key === 'ArrowUp' && event.altKey) {
      event.preventDefault()
      goToPrevNode()
      return
    }
    if (event.key === 'ArrowDown' && event.altKey) {
      event.preventDefault()
      goToNextNode()
    }
  }

  onMounted(() => window.addEventListener('keydown', handleKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))

  // ===== 进度计算 =====

  const currentDayProgress = computed(() => {
    const total = deps.nodes.value.length
    if (!total) return { total: 0, completed: 0, percent: 0 }
    const completed = deps.nodes.value.filter(n => n.status !== 'draft').length
    return { total, completed, percent: Math.round((completed / total) * 100) }
  })

  const overallProgress = computed(() => {
    const total = deps.days.value.length
    if (!total) return { total: 0, completed: 0 }
    const completed = deps.days.value.filter(
      d => d.nodes?.length && d.nodes.every(n => n.status !== 'draft')
    ).length
    return { total, completed }
  })

  const completedCount = (day: PlanDay): number =>
    day.nodes?.filter(n => n.status !== 'draft').length || 0

  const completionPercent = (day: PlanDay): number => {
    const total = day.nodes?.length || 0
    if (!total) return 0
    return Math.round((completedCount(day) / total) * 100)
  }

  return {
    hasPrevNode,
    hasNextNode,
    goToPrevNode,
    goToNextNode,
    currentNodeIndex,
    saveAndNext,
    copyNode,
    pasteNode,
    copiedNode,
    copyDay,
    pasteDay,
    copiedDay,
    currentDayProgress,
    overallProgress,
    completedCount,
    completionPercent,
  }
}
