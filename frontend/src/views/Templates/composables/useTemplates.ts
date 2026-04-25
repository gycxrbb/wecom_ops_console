import { ref, computed, reactive, onMounted } from 'vue'
import request from '#/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { nextTick } from 'vue'
import { CRM_DEMO_URL, createTemplateCardExample, templateCardExampleVariables } from '#/components/message-editor/templateCardPresets'

export type TemplateItem = {
  id: number
  name: string
  category?: string
  msg_type: string
  description?: string
  content_json?: Record<string, any>
  content?: Record<string, any> | string
  variables_json?: Record<string, any>
  variable_schema?: Record<string, any> | string
  is_system?: boolean
  updated_at?: string
}

const defaultContentByType: Record<string, any> = {
  text: { content: '', mentioned_list: [], mentioned_mobile_list: [] },
  markdown: { content: '' },
  news: {
    articles: [
      {
        title: '惯能 H5 · 今日内容导读',
        description: '打开 CRM 内容页查看今天的 H5 讲解示例，运营同学可直接改标题、描述和封面图。',
        url: CRM_DEMO_URL,
        picurl: 'https://picsum.photos/seed/guanneng-h5-news/640/360',
      },
    ],
  },
  image: { asset_id: undefined, asset_name: '', asset_url: '', image_path: '' },
  emotion: { asset_id: undefined, asset_name: '', asset_url: '', image_path: '' },
  file: { asset_id: undefined, asset_name: '', media_id: '' },
  voice: { asset_id: undefined, asset_name: '', media_id: '' },
  template_card: createTemplateCardExample('text_notice'),
}

const defaultVariablesByType: Record<string, any> = {
  template_card: { ...templateCardExampleVariables.text_notice },
}

const variableEnabledTypes = new Set(['text', 'markdown', 'news', 'template_card'])

export const msgTypeOptions = [
  { value: 'text', label: '文本' },
  { value: 'markdown', label: 'Markdown' },
  { value: 'image', label: '图片' },
  { value: 'emotion', label: '表情包' },
  { value: 'news', label: '图文' },
  { value: 'file', label: '文件' },
  { value: 'voice', label: '语音' },
  { value: 'template_card', label: '模板卡片' }
]

export const msgTypeLabel = (type: string) => {
  const match = msgTypeOptions.find(item => item.value === type)
  return match?.label || type
}

export const supportsVariables = (msgType: string) => variableEnabledTypes.has(msgType)

export function useTemplates() {
  const templates = ref<TemplateItem[]>([])
  const loading = ref(false)
  const dialogVisible = ref(false)
  const activeType = ref('all')
  const searchKeyword = ref('')
  const highlightedTemplateId = ref<number | null>(null)

  const form = reactive({
    id: null as number | null,
    name: '',
    description: '',
    msg_type: 'text',
    category: 'general',
    contentJson: { ...defaultContentByType.text },
    variablesJson: {} as Record<string, any>
  })

  // Computed
  const mineTemplates = computed(() => templates.value.filter(tpl => !tpl.is_system))
  const systemTemplates = computed(() => templates.value.filter(tpl => !!tpl.is_system))

  const typeTabs = computed(() => {
    const items = msgTypeOptions.map(item => ({
      value: item.value,
      label: item.label,
      count: templates.value.filter(tpl => tpl.msg_type === item.value).length
    }))
    return [{ value: 'all', label: '全部', count: templates.value.length }, ...items]
  })

  const matchesKeyword = (tpl: TemplateItem) => {
    const keyword = searchKeyword.value.trim().toLowerCase()
    if (!keyword) return true
    return [tpl.name, tpl.category, tpl.description]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(keyword))
  }

  const filteredTemplates = computed(() =>
    templates.value.filter(tpl => {
      const typeMatched = activeType.value === 'all' || tpl.msg_type === activeType.value
      return typeMatched && matchesKeyword(tpl)
    })
  )

  const filteredMineTemplates = computed(() =>
    filteredTemplates.value
      .filter(tpl => !tpl.is_system)
      .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
  )

  const filteredSystemTemplates = computed(() =>
    filteredTemplates.value
      .filter(tpl => !!tpl.is_system)
      .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
  )

  const recentMineTemplates = computed(() =>
    mineTemplates.value
      .filter(tpl => matchesKeyword(tpl))
      .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
      .slice(0, 4)
  )

  // Actions
  const fetchTemplates = async () => {
    loading.value = true
    try {
      const res: any = await request.get('/v1/templates')
      templates.value = res.list || res
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  const resetForm = () => {
    form.id = null
    form.name = ''
    form.description = ''
    form.msg_type = 'text'
    form.category = 'general'
    form.contentJson = { ...defaultContentByType.text }
    form.variablesJson = {}
  }

  const openCreate = () => {
    resetForm()
    dialogVisible.value = true
  }

  const fillForm = (row: TemplateItem, nextId: number | null) => {
    form.id = nextId
    form.name = nextId ? `${row.name} - 我的版本` : row.name
    form.description = row.description || ''
    form.msg_type = row.msg_type
    form.category = row.category || 'general'
    const rawContent = row.content_json ?? row.content
    try {
      form.contentJson = typeof rawContent === 'string'
        ? JSON.parse(rawContent)
        : (rawContent || { ...(defaultContentByType[row.msg_type] || {}) })
    } catch {
      form.contentJson = { ...(defaultContentByType[row.msg_type] || {}) }
    }
    const rawVars = row.variables_json ?? row.variable_schema
    try {
      form.variablesJson = typeof rawVars === 'string' ? JSON.parse(rawVars) : (rawVars || {})
    } catch {
      form.variablesJson = {}
    }
  }

  const editTemplate = (row: TemplateItem) => {
    fillForm(row, row.id)
    dialogVisible.value = true
  }

  const createFromTemplate = (row: TemplateItem) => {
    fillForm(row, null)
    dialogVisible.value = true
  }

  const handleMsgTypeChange = (type: string) => {
    form.contentJson = { ...(defaultContentByType[type] || {}) }
    form.variablesJson = supportsVariables(type)
      ? { ...(defaultVariablesByType[type] || {}) }
      : {}
  }

  const focusTemplateCard = async (id: number, msgType: string) => {
    activeType.value = msgType
    highlightedTemplateId.value = id
    await nextTick()
    const el = document.querySelector<HTMLElement>(`[data-template-id="${id}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setTimeout(() => { if (highlightedTemplateId.value === id) highlightedTemplateId.value = null }, 2600)
  }

  const cloneTemplate = async (row: TemplateItem) => {
    try {
      const saved = await request.post(`/v1/templates/${row.id}/clone`)
      await fetchTemplates()
      ElMessage.success('已复制到我的模板')
      await focusTemplateCard(saved.id, saved.msg_type)
    } catch (e) { console.error(e) }
  }

  const deleteTemplate = (row: TemplateItem) => {
    ElMessageBox.confirm('确认删除该模板？', '警告', { type: 'warning' }).then(async () => {
      await request.delete(`/v1/templates/${row.id}`)
      ElMessage.success('删除成功')
      fetchTemplates()
    })
  }

  const saveTemplate = async () => {
    if (!form.name.trim()) {
      ElMessage.warning('请输入模板名称')
      return null
    }
    try {
      const saved = await request.post('/v1/templates', {
        id: form.id,
        name: form.name,
        description: form.description,
        category: form.category,
        msg_type: form.msg_type,
        content_json: form.contentJson,
        variables_json: form.variablesJson
      })
      dialogVisible.value = false
      await fetchTemplates()
      ElMessage.success('保存成功')
      await focusTemplateCard(saved.id, saved.msg_type)
      return saved
    } catch (e) {
      console.error(e)
      return null
    }
  }

  const contentSummary = (tpl: TemplateItem) => {
    const raw = tpl.content_json ?? tpl.content
    const content = typeof raw === 'string' ? raw : JSON.stringify(raw || {})
    const compact = content.replace(/\s+/g, ' ').trim()
    return compact.length > 88 ? `${compact.slice(0, 88)}...` : compact || '暂无描述'
  }

  const formatDate = (value?: string) => {
    if (!value) return '刚刚更新'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return '刚刚更新'
    return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  onMounted(() => { fetchTemplates() })

  return {
    templates, loading, dialogVisible, activeType, searchKeyword,
    highlightedTemplateId, form,
    mineTemplates, systemTemplates, typeTabs,
    filteredMineTemplates, filteredSystemTemplates, recentMineTemplates,
    fetchTemplates, openCreate, editTemplate, createFromTemplate,
    handleMsgTypeChange, cloneTemplate, deleteTemplate, saveTemplate,
    contentSummary, formatDate, focusTemplateCard
  }
}
