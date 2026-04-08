import { computed, onBeforeUnmount, onMounted, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
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
  saveNodeDraft: () => Promise<boolean>
  confirmDiscardDraft: () => Promise<boolean>
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
    if (deps.nodeDirty.value) {
      const saved = await deps.saveNodeDraft()
      if (!saved) return
    }

    const idx = currentNodeIndex.value
    const nextDraft = deps.nodes.value.slice(idx + 1).find(n => n.status === 'draft')
    if (nextDraft) {
      deps.selectNode(nextDraft.id)
      return
    }

    const currentDayIdx = deps.days.value.findIndex(d => d.id === deps.currentDay.value?.id)
    const nextPendingDay = deps.days.value.slice(currentDayIdx + 1).find(
      d => d.nodes?.some(n => n.status === 'draft')
    )
    if (nextPendingDay) {
      deps.selectDay(nextPendingDay.id)
      ElMessage.success(`已跳转到 Day ${nextPendingDay.day_number}`)
      return
    }

    ElMessage.success('所有节点已配置完成！')
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
    currentDayProgress,
    overallProgress,
    completedCount,
    completionPercent,
  }
}
