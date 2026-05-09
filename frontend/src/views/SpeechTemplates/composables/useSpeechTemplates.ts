import { ref, computed, reactive, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '#/utils/request'
import type { Template, Scene, CategoryL1Node, CategoryL2Node, CategoryL3Node } from '../types'

export function useSpeechTemplates() {
  const loading = ref(true)
  const scenes = ref<Scene[]>([])
  const categories = ref<CategoryL1Node[]>([])
  const templatesMap = ref<Record<string, Template[]>>({})
  const activeScene = ref('')
  const activeStyle = ref('')
  const expandedState = reactive<Record<string, boolean>>({})

  // Category editing state
  const hoveredL1 = ref<number | null>(null)
  const hoveredL2 = ref<number | null>(null)
  const hoveredL3 = ref<number | null>(null)
  const hoveredScene = ref<string | null>(null)
  const renamingId = ref<number | null>(null)
  const renamingName = ref('')
  const renameInputRef = ref<any>(null)

  // Dialogs
  const createL1DialogVisible = ref(false)
  const createL1Name = ref('')
  const moveDialogVisible = ref(false)
  const moveTargetNode = ref<CategoryL2Node | CategoryL3Node | null>(null)
  const moveTargetParentId = ref<number | null>(null)
  const categorizeDialogVisible = ref(false)
  const categorizeSceneKey = ref('')
  const categorizeTargetId = ref<number | null>(null)
  const createTemplateDialogVisible = ref(false)
  const createTemplateCategoryId = ref<number | null>(null)
  const createTemplateSceneKey = ref('')
  const createTemplateStyle = ref('professional')
  const createTemplateLabel = ref('')
  const createTemplateContent = ref('')
  const createTemplateSaving = ref(false)

  const sidebarTree = computed<CategoryL1Node[]>(() => {
    const sceneByL3 = new Map<number, Scene[]>()
    for (const s of scenes.value) {
      if (s.category_id) {
        if (!sceneByL3.has(s.category_id)) sceneByL3.set(s.category_id, [])
        sceneByL3.get(s.category_id)!.push(s)
      }
    }
    return categories.value.map(l1 => ({
      ...l1,
      children: l1.children.map(l2 => ({
        ...l2,
        children: l2.children.map(l3 => ({
          ...l3,
          scenes: sceneByL3.get(l3.id) || [],
        })),
      })),
    }))
  })

  const uncategorizedScenes = computed(() =>
    scenes.value.filter(s => !s.category_l1 || !s.category_l2 || !s.category_l3)
  )

  const currentSceneLabel = computed(() => {
    const s = scenes.value.find(s => s.key === activeScene.value)
    return s?.label || activeScene.value
  })

  const currentTemplates = computed(() =>
    templatesMap.value[activeScene.value] || []
  )

  const currentEditingTpl = computed(() =>
    currentTemplates.value.find(t => t.style === activeStyle.value) || currentTemplates.value[0] || null
  )

  const isPointsScene = computed(() => {
    const scene = scenes.value.find(s => s.key === activeScene.value)
    return scene?.category_l2 === '积分管理'
  })

  const categorizeOptions = computed(() =>
    categories.value.map(l1 => ({
      id: l1.id,
      name: l1.name,
      children: l1.children.map(l2 => ({
        id: l2.id,
        name: l2.name,
        children: l2.children.map(l3 => ({ id: l3.id, name: l3.name })),
      })),
    }))
  )

  // ── Actions ──

  const selectScene = (key: string) => {
    activeScene.value = key
    const tpls = templatesMap.value[key]
    if (tpls?.length) activeStyle.value = tpls[0].style
  }

  const toggleNode = (key: string) => {
    expandedState[key] = !expandedState[key]
  }

  const styleLabel = (style: string) => {
    const map: Record<string, string> = { professional: '专业风格', encouraging: '鼓励风格', competitive: '竞争风格' }
    return map[style] || style
  }

  const getCategoryIcon = (name: string): string => {
    const svg = (paths: string) =>
      `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`
    if (name.includes('健康')) return svg('<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78z"/>')
    if (name.includes('社区')) return svg('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>')
    if (name.includes('服务') || name.includes('支持')) return svg('<path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>')
    if (name.includes('系统')) return svg('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>')
    return svg('<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>')
  }

  function expandAllNodes() {
    for (const l1 of sidebarTree.value) {
      expandedState[`l1-${l1.id}`] = true
      for (const l2 of l1.children) {
        expandedState[`l2-${l2.id}`] = true
        for (const l3 of l2.children) expandedState[`l3-${l3.id}`] = true
      }
    }
    if (uncategorizedScenes.value.length) expandedState['uncategorized'] = true
  }

  // ── Data loading ──

  const loadCategories = async () => {
    categories.value = await request.get('/v1/speech-templates/categories')
  }

  const fetchData = async () => {
    loading.value = true
    try {
      const [scenesData, templatesData, categoriesData]: [any[], any, any[]] = await Promise.all([
        request.get('/v1/speech-templates/scenes'),
        request.get('/v1/speech-templates'),
        request.get('/v1/speech-templates/categories'),
      ])
      categories.value = categoriesData
      scenes.value = scenesData
      const map: Record<string, Template[]> = {}
      for (const [key, list] of Object.entries(templatesData as Record<string, any[]>)) {
        map[key] = list.map((t: any) => ({
          ...t,
          metadata_json: t.metadata_json || null,
          _editContent: t.content,
          _saving: false,
        }))
      }
      templatesMap.value = map
      if (scenes.value.length && (!activeScene.value || !scenes.value.some(s => s.key === activeScene.value))) {
        const first = scenes.value.find(s => map[s.key]?.length)
        activeScene.value = first?.key || scenes.value[0].key
      }
      const tpls = map[activeScene.value]
      if (tpls?.length && !tpls.some(t => t.style === activeStyle.value)) {
        activeStyle.value = tpls[0].style
      }
      expandAllNodes()
    } catch (e) {
      console.error(e)
      ElMessage.error('加载话术模板失败')
    } finally {
      loading.value = false
    }
  }

  // ── Template CRUD ──

  const saveTemplate = async (tpl: Template) => {
    if (!tpl.id) return
    tpl._saving = true
    try {
      const res: any = await request.put(`/v1/speech-templates/${tpl.id}`, {
        content: tpl._editContent,
        label: tpl.label,
      })
      tpl.content = tpl._editContent
      if (res.metadata_json) tpl.metadata_json = res.metadata_json
      ElMessage.success('话术已保存')
    } catch (e) {
      console.error(e)
      ElMessage.error('保存失败')
    } finally {
      tpl._saving = false
    }
  }

  const openCreateTemplate = (categoryId: number) => {
    createTemplateCategoryId.value = categoryId
    createTemplateSceneKey.value = ''
    createTemplateStyle.value = 'professional'
    createTemplateLabel.value = ''
    createTemplateContent.value = ''
    createTemplateDialogVisible.value = true
  }

  const handleCreateTemplate = async () => {
    if (!createTemplateSceneKey.value.trim() || !createTemplateContent.value.trim()) {
      ElMessage.warning('请填写场景标识和内容')
      return
    }
    createTemplateSaving.value = true
    try {
      await request.post('/v1/speech-templates', {
        scene_key: createTemplateSceneKey.value.trim(),
        style: createTemplateStyle.value,
        label: createTemplateLabel.value.trim() || createTemplateSceneKey.value.trim(),
        content: createTemplateContent.value,
        category_id: createTemplateCategoryId.value,
      })
      ElMessage.success('话术已创建')
      createTemplateDialogVisible.value = false
      await fetchData()
    } catch (e: any) {
      ElMessage.warning(e?.response?.data?.detail || '创建失败')
    } finally {
      createTemplateSaving.value = false
    }
  }

  // ── Category management ──

  type AnyCategoryNode = CategoryL1Node | CategoryL2Node | CategoryL3Node

  const startRename = (node: AnyCategoryNode) => {
    renamingId.value = node.id
    renamingName.value = node.name
    nextTick(() => renameInputRef.value?.focus())
  }

  const saveRename = async (node: AnyCategoryNode) => {
    if (!renamingName.value.trim() || renamingName.value.trim() === node.name) {
      renamingId.value = null
      return
    }
    await request.put(`/v1/speech-templates/categories/${node.id}`, {
      name: renamingName.value.trim(),
      sort_order: node.sort_order,
    })
    node.name = renamingName.value.trim()
    renamingId.value = null
    ElMessage.success('已重命名')
  }

  const handleDeleteCategory = async (node: AnyCategoryNode) => {
    const hasChildren = 'children' in node && (node as any).children?.length > 0
    await ElMessageBox.confirm(
      `确定删除分类「${node.name}」？` + (hasChildren ? '下有子分类时无法删除。' : '下有模板时无法删除。'),
      '确认删除',
      { type: 'warning' },
    )
    try {
      await request.delete(`/v1/speech-templates/categories/${node.id}`)
      ElMessage.success('已删除')
      await loadCategories()
    } catch (e: any) {
      ElMessage.warning(e?.response?.data?.detail || '删除失败')
    }
  }

  const openMoveDialog = (node: CategoryL2Node | CategoryL3Node) => {
    moveTargetNode.value = node
    moveTargetParentId.value = null
    moveDialogVisible.value = true
  }

  const handleMoveCategory = async () => {
    if (!moveTargetNode.value || !moveTargetParentId.value) return
    await request.put(`/v1/speech-templates/categories/${moveTargetNode.value.id}/move`, {
      new_parent_id: moveTargetParentId.value,
    })
    ElMessage.success('已移动')
    moveDialogVisible.value = false
    await loadCategories()
  }

  const openCreateL2 = (parentId: number) => {
    ElMessageBox.prompt('请输入子类名称', '新建子类', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空',
    }).then(async ({ value }) => {
      await request.post('/v1/speech-templates/categories', { name: value, parent_id: parentId })
      ElMessage.success('已创建')
      await loadCategories()
    }).catch(() => {})
  }

  const openCreateL3 = (parentId: number) => {
    ElMessageBox.prompt('请输入三级分类名称', '新建三级分类', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空',
    }).then(async ({ value }) => {
      await request.post('/v1/speech-templates/categories', { name: value, parent_id: parentId })
      ElMessage.success('已创建')
      await loadCategories()
    }).catch(() => {})
  }

  const handleCreateL1 = async () => {
    if (!createL1Name.value.trim()) return
    await request.post('/v1/speech-templates/categories', { name: createL1Name.value.trim() })
    ElMessage.success('已创建')
    createL1DialogVisible.value = false
    await loadCategories()
  }

  const openCategorizeDialog = (sceneKey: string) => {
    categorizeSceneKey.value = sceneKey
    categorizeTargetId.value = null
    categorizeDialogVisible.value = true
  }

  const handleCategorizeScene = async () => {
    if (!categorizeTargetId.value) return
    await request.post('/v1/speech-templates/assign-category', {
      assignments: [{ scene_key: categorizeSceneKey.value, category_id: categorizeTargetId.value }],
    })
    ElMessage.success('已归类')
    categorizeDialogVisible.value = false
    await fetchData()
  }

  // ── RAG metadata ──

  const ragMetaDialogVisible = ref(false)
  const ragMetaTarget = ref<Template | null>(null)
  const ragMetaOriginal = ref<Record<string, any> | null>(null)
  const ragMetaForm = reactive<Record<string, any>>({
    summary: '', customer_goal: [], intervention_scene: [],
    question_type: [], safety_level: '', visibility: '',
    tags: [], usage_note: '',
  })
  const ragMetaSaving = ref(false)

  const openRagMetaDialog = (tpl: Template) => {
    ragMetaTarget.value = tpl
    const meta = tpl.metadata_json || {}
    ragMetaOriginal.value = JSON.parse(JSON.stringify(meta))
    ragMetaForm.summary = meta.summary || ''
    ragMetaForm.customer_goal = meta.customer_goal || []
    ragMetaForm.intervention_scene = meta.intervention_scene || []
    ragMetaForm.question_type = meta.question_type || []
    ragMetaForm.safety_level = meta.safety_level || ''
    ragMetaForm.visibility = meta.visibility || ''
    ragMetaForm.tags = meta.tags || []
    ragMetaForm.usage_note = meta.usage_note || ''
    ragMetaDialogVisible.value = true
  }

  const handleSaveRagMeta = async () => {
    if (!ragMetaTarget.value) return
    // Compute diff
    const changes: string[] = []
    const orig = ragMetaOriginal.value || {}
    const fields = ['summary', 'safety_level', 'visibility', 'usage_note'] as const
    for (const f of fields) {
      if (ragMetaForm[f] !== (orig[f] || '')) changes.push(f)
    }
    const arrayFields = ['customer_goal', 'intervention_scene', 'question_type', 'tags'] as const
    for (const f of arrayFields) {
      const newVal = JSON.stringify([...(ragMetaForm[f] || [])].sort())
      const oldVal = JSON.stringify([...(orig[f] || [])].sort())
      if (newVal !== oldVal) changes.push(f)
    }
    if (changes.length === 0) {
      ElMessage.info('配置未变更')
      return
    }
    try {
      await ElMessageBox.confirm(
        `以下 ${changes.length} 个字段将被更新：${changes.join('、')}`,
        '确认保存 RAG 配置',
        { type: 'info', confirmButtonText: '保存', cancelButtonText: '取消' },
      )
    } catch { return }

    ragMetaSaving.value = true
    try {
      const res: any = await request.patch(
        `/v1/speech-templates/${ragMetaTarget.value.id}/rag-meta`,
        ragMetaForm,
      )
      ragMetaTarget.value.metadata_json = res.metadata_json || null
      ElMessage.success('RAG 配置已保存并重新索引')
      ragMetaDialogVisible.value = false
    } catch (e) {
      console.error(e)
      ElMessage.error('RAG 配置保存失败')
    } finally {
      ragMetaSaving.value = false
    }
  }

  // Move dialog: target parent options depend on node level
  const moveTargetOptions = computed(() => {
    if (!moveTargetNode.value) return []
    // L2 can be moved to L1, L3 can be moved to L2
    return categories.value.map(l1 => ({
      id: l1.id,
      name: l1.name,
      children: l1.children.map(l2 => ({ id: l2.id, name: l2.name })),
    }))
  })

  return {
    // State
    loading, scenes, categories, templatesMap, activeScene, activeStyle, expandedState,
    hoveredL1, hoveredL2, hoveredL3, hoveredScene, renamingId, renamingName, renameInputRef,
    createL1DialogVisible, createL1Name,
    moveDialogVisible, moveTargetNode, moveTargetParentId, moveTargetOptions,
    categorizeDialogVisible, categorizeSceneKey, categorizeTargetId, categorizeOptions,
    createTemplateDialogVisible, createTemplateCategoryId, createTemplateSceneKey,
    createTemplateStyle, createTemplateLabel, createTemplateContent, createTemplateSaving,
    ragMetaDialogVisible, ragMetaTarget, ragMetaForm, ragMetaOriginal, ragMetaSaving,
    // Computed
    sidebarTree, uncategorizedScenes, currentSceneLabel, currentTemplates,
    currentEditingTpl, isPointsScene,
    // Actions
    selectScene, toggleNode, styleLabel, getCategoryIcon, fetchData,
    saveTemplate, openCreateTemplate, handleCreateTemplate,
    startRename, saveRename, handleDeleteCategory, openMoveDialog, handleMoveCategory,
    openCreateL2, openCreateL3, handleCreateL1, openCategorizeDialog, handleCategorizeScene,
    openRagMetaDialog, handleSaveRagMeta,
    loadCategories,
  }
}
