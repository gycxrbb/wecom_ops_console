import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import request from '@/utils/request'
import { buildAssetAuthUrl } from '@/utils/assets'
import { ElMessage } from 'element-plus'
import { msgTypeLabel, supportsVariables } from '@/views/Templates/composables/useTemplates'
import { CRM_DEMO_URL, createTemplateCardExample, templateCardExampleVariables } from '@/components/message-editor/templateCardPresets'

// 每种消息类型的默认 content_json 结构
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

export type BatchQueueItem = {
  id: number
  title: string
  msg_type: string
  description?: string
  contentJson: Record<string, any>
  variablesJson: Record<string, any>
  status: 'pending' | 'sending' | 'success' | 'failed'
  error?: string
  remarkEnabled?: boolean
  remark?: string
  targetGroupIds?: number[]  // 积分排行时每条消息发送到不同群组
}

const DRAFT_KEY = 'send-center-draft'

function saveDraft(state: {
  form: { groups: number[]; msg_type: string; contentJson: any; variables: any; template_id: number | null }
  scheduleForm: { title: string; schedule_type: string; run_at: string; cron_expr: string; timezone: string; approval_required: boolean; skip_weekends: boolean; skip_dates: string[] }
  selectedContentSource: 'template' | 'plan_node' | null
  selectedContentId: number | null
  selectedContentLabel: string | null
  batchQueue: BatchQueueItem[]
  activeBatchIndex: number | null
}) {
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(state))
  } catch { /* quota exceeded — ignore */ }
}

function loadDraft(): {
  form: { groups: number[]; msg_type: string; contentJson: any; variables: any; template_id: number | null }
  scheduleForm: { title: string; schedule_type: string; run_at: string; cron_expr: string; timezone: string; approval_required: boolean; skip_weekends: boolean; skip_dates: string[] }
  selectedContentSource: 'template' | 'plan_node' | null
  selectedContentId: number | null
  selectedContentLabel: string | null
  batchQueue: BatchQueueItem[]
  activeBatchIndex: number | null
} | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

export function clearSendCenterDraft() {
  sessionStorage.removeItem(DRAFT_KEY)
}

export function useSendLogic() {
  // ---- 尝试从 sessionStorage 恢复草稿 ----
  const draft = loadDraft()

  const groups = ref<any[]>([])
  const templates = ref<any[]>([])
  const selectedContentSource = ref<'template' | 'plan_node' | null>(
    draft?.selectedContentSource === 'template' || draft?.selectedContentSource === 'plan_node'
      ? draft.selectedContentSource
      : null
  )
  const selectedContentId = ref<number | null>(draft?.selectedContentId ?? null)
  const selectedContentLabel = ref<string | null>(draft?.selectedContentLabel ?? null)
  const previewData = ref<any | null>(null)
  const previewError = ref('')
  const isPreviewing = ref(false)
  const isSending = ref(false)
  const isTestSending = ref(false)
  const isScheduling = ref(false)

  // ---- 批量发送状态 ----
  const batchQueue = ref<BatchQueueItem[]>(
    draft?.batchQueue?.map(item => ({ ...item, status: 'pending' as const })) ?? []
  )
  const isBatchMode = computed(() => batchQueue.value.length > 0)
  const isBatchSending = ref(false)
  const batchCancelled = ref(false)
  const batchProgress = computed(() => {
    const total = batchQueue.value.length
    const done = batchQueue.value.filter(i => i.status === 'success' || i.status === 'failed').length
    const success = batchQueue.value.filter(i => i.status === 'success').length
    const failed = batchQueue.value.filter(i => i.status === 'failed').length
    return { total, done, success, failed }
  })

  // 批量项选中态
  const activeBatchIndex = ref<number | null>(draft?.activeBatchIndex ?? null)
  // 推送预告项的虚拟 BatchQueueItem（仅在 index === -1 时使用）
  const notifyBatchItem = computed<BatchQueueItem>(() => ({
    id: -1,
    title: '📢 推送预告',
    msg_type: 'markdown',
    description: '',
    contentJson: { content: notifyCustomText.value },
    variablesJson: {},
    status: (notifySendStatus.value !== 'hidden' ? notifySendStatus.value : 'pending') as BatchQueueItem['status'],
  }))
  const activeBatchItem = computed<BatchQueueItem | null>(() => {
    if (activeBatchIndex.value === -1) return notifyBatchItem.value
    if (activeBatchIndex.value != null && activeBatchIndex.value < batchQueue.value.length)
      return batchQueue.value[activeBatchIndex.value]
    return null
  })
  const batchItemPreviewData = ref<any | null>(null)
  const batchItemPreviewError = ref('')
  const isBatchItemPreviewing = ref(false)

  // ---- 推送预告 ----
  const notifyEnabled = ref(false)
  const notifyCustomText = ref('')
  const notifySendStatus = ref<'hidden' | 'pending' | 'sending' | 'success' | 'failed'>('hidden')
  const previewingNotify = ref(false)

  const notifyAutoText = computed(() => {
    // 手动队列模式
    if (!isBatchMode.value && manualQueue.value.length > 0) {
      const rows = manualQueue.value.map((item, i) => {
        return `**${i + 1}.** ${item.title} \`${msgTypeLabel(item.msg_type)}\``
      })
      return [
        '📢 **推送预告**',
        '',
        '接下来将发送以下内容：',
        '',
        ...rows,
        '',
        '请留意查收！',
      ].join('\n')
    }
    if (isBatchMode.value) {
      const rows = batchQueue.value.map((item, i) => {
        const desc = item.description ? ` — ${item.description}` : ''
        return `**${i + 1}.** ${item.title} \`${msgTypeLabel(item.msg_type)}\`${desc}`
      })
      return [
        '📢 **推送预告**',
        '',
        '接下来将发送以下内容：',
        '',
        ...rows,
        '',
        '请留意查收！',
      ].join('\n')
    }
    const label = selectedContentLabel.value || form.msg_type
    return `📢 **推送预告**\n即将发送：**${label}** \`${msgTypeLabel(form.msg_type)}消息\``
  })

  // 开启预告时自动填入生成的文本
  watch(notifyEnabled, (val) => {
    if (val) {
      notifyCustomText.value = notifyAutoText.value
      if (isBatchMode.value) notifySendStatus.value = 'pending'
    } else {
      notifySendStatus.value = 'hidden'
    }
  })

  // 队列或内容变化时重新生成预告文本（仅当预告开启时）
  watch(
    () => [batchQueue.value.length, JSON.stringify(batchQueue.value.map(i => i.title + i.msg_type + (i.description || ''))), selectedContentLabel.value, form.msg_type],
    () => {
      if (notifyEnabled.value) {
        notifyCustomText.value = notifyAutoText.value
        if (isBatchMode.value && notifySendStatus.value === 'hidden') notifySendStatus.value = 'pending'
      }
      if (!isBatchMode.value) notifySendStatus.value = 'hidden'
    },
  )

  const selectBatchItem = (index: number | null) => {
    activeBatchIndex.value = index
    batchItemPreviewData.value = null
    batchItemPreviewError.value = ''
  }

  const handleNotifyPreview = async () => {
    previewingNotify.value = true
    isPreviewing.value = true
    previewError.value = ''
    try {
      const res = await request.post('/v1/preview', {
        msg_type: 'markdown',
        content_json: { content: notifyCustomText.value },
        variables_json: {},
        group_ids: form.groups.length > 0 ? [...form.groups] : undefined
      })
      previewData.value = res
    } catch (e: any) {
      previewData.value = null
      previewError.value = '预览失败: ' + String(e)
    } finally {
      isPreviewing.value = false
    }
  }

  const handleBatchItemContentUpdate = (val: Record<string, any>) => {
    if (activeBatchIndex.value === -1) {
      notifyCustomText.value = val.content || ''
    } else if (activeBatchItem.value) {
      activeBatchItem.value.contentJson = val
    }
  }

  const handleBatchItemVariablesUpdate = (val: Record<string, any>) => {
    if (activeBatchIndex.value !== -1 && activeBatchItem.value) {
      activeBatchItem.value.variablesJson = val
    }
  }

  const handleBatchItemPreview = async () => {
    const item = activeBatchItem.value
    if (!item) return
    isBatchItemPreviewing.value = true
    batchItemPreviewError.value = ''
    try {
      const res = await request.post('/v1/preview', {
        msg_type: item.msg_type,
        content_json: item.contentJson,
        variables_json: item.variablesJson,
        group_ids: form.groups.length > 0 ? [...form.groups] : undefined
      })
      batchItemPreviewData.value = res
    } catch (e: any) {
      batchItemPreviewData.value = null
      batchItemPreviewError.value = '预览失败: ' + String(e)
    } finally {
      isBatchItemPreviewing.value = false
    }
  }

  const handleBatchItemSchedule = async () => {
    const item = activeBatchItem.value
    if (!item) return
    if (form.groups.length === 0) {
      return ElMessage.warning('请至少选择一个群组')
    }
    if (!scheduleForm.title) {
      return ElMessage.warning('请填写任务标题')
    }
    isScheduling.value = true
    try {
      await request.post('/v1/schedules', {
        title: scheduleForm.title,
        group_ids: [...form.groups],
        schedule_type: scheduleForm.schedule_type,
        run_at: scheduleForm.run_at || null,
        cron_expr: scheduleForm.cron_expr || null,
        timezone: scheduleForm.timezone || 'Asia/Shanghai',
        approval_required: scheduleForm.approval_required,
        skip_weekends: scheduleForm.skip_weekends,
        skip_dates: [...scheduleForm.skip_dates],
        msg_type: item.msg_type,
        content_json: item.contentJson,
        variables_json: item.variablesJson
      })
      ElMessage.success('定时任务创建成功')
    } catch (e: any) {
      ElMessage.error('创建定时任务失败: ' + String(e))
    } finally {
      isScheduling.value = false
    }
  }

  const form = reactive({
    groups: draft?.form?.groups ?? ([] as number[]),
    msg_type: draft?.form?.msg_type ?? 'text',
    contentJson: draft?.form?.contentJson ?? { ...defaultContentByType.text },
    variables: draft?.form?.variables ?? ({} as Record<string, any>),
    template_id: draft?.form?.template_id ?? (null as number | null)
  })

  const scheduleForm = reactive({
    title: draft?.scheduleForm?.title ?? '',
    schedule_type: draft?.scheduleForm?.schedule_type ?? 'once',
    run_at: draft?.scheduleForm?.run_at ?? '',
    cron_expr: draft?.scheduleForm?.cron_expr ?? '',
    timezone: draft?.scheduleForm?.timezone ?? 'Asia/Shanghai',
    approval_required: draft?.scheduleForm?.approval_required ?? false,
    skip_weekends: draft?.scheduleForm?.skip_weekends ?? false,
    skip_dates: draft?.scheduleForm?.skip_dates ?? ([] as string[])
  })

  const fetchBaseData = async () => {
    try {
      const [resGroups, resTemplates] = await Promise.all([
        request.get('/v1/groups'),
        request.get('/v1/templates')
      ])
      groups.value = resGroups.list || resGroups
      templates.value = resTemplates.list || resTemplates
    } catch (e: any) {
      ElMessage.error('加载基础数据失败: ' + (e.message || String(e)))
    }
  }

  const handleMsgTypeChange = (type: string) => {
    form.msg_type = type
    form.contentJson = { ...(defaultContentByType[type] || {}) }
    form.variables = supportsVariables(type) ? { ...(defaultVariablesByType[type] || {}) } : {}
  }

  const handleContentSelect = (data: { source: string; id: number; label: string; msg_type: string; contentJson: any; variablesJson: any }) => {
    // 切换到单条模式
    clearBatch()
    selectedContentSource.value = data.source as 'template' | 'plan_node'
    selectedContentId.value = data.id
    selectedContentLabel.value = data.label
    form.msg_type = data.msg_type
    form.template_id = data.source === 'template' ? data.id : null
    form.contentJson = data.contentJson || { ...(defaultContentByType[data.msg_type] || {}) }
    form.variables = data.variablesJson || {}
  }

  const handleClearContent = () => {
    selectedContentSource.value = null
    selectedContentId.value = null
    selectedContentLabel.value = null
    form.template_id = null
    form.variables = {}
    handleMsgTypeChange(form.msg_type)
  }

  const handlePreview = async () => {
    isPreviewing.value = true
    previewError.value = ''
    try {
      const res = await request.post('/v1/preview', {
        msg_type: form.msg_type,
        content_json: form.contentJson,
        variables_json: form.variables,
        group_ids: form.groups.length > 0 ? [...form.groups] : undefined
      })
      const nextPreview = { ...res }
      if (form.msg_type === 'image' || form.msg_type === 'emotion') {
        nextPreview.rendered_content = {
          ...(nextPreview.rendered_content || {}),
          asset_url: buildAssetAuthUrl(form.contentJson?.asset_url || '')
        }
      }
      if (form.msg_type === 'file' || form.msg_type === 'voice') {
        nextPreview.rendered_content = {
          ...(nextPreview.rendered_content || {}),
          asset_name: form.contentJson?.asset_name || ''
        }
      }
      previewData.value = nextPreview
    } catch (e: any) {
      previewData.value = null
      previewError.value = '预览失败: ' + String(e)
    } finally {
      isPreviewing.value = false
    }
  }

  // ---- 自动实时预览（防抖 800ms）----
  let previewTimer: ReturnType<typeof setTimeout> | null = null
  const hasContent = computed(() => {
    const c = form.contentJson
    if (!c) return false
    if (form.msg_type === 'text' || form.msg_type === 'markdown') return !!(c.content || '').trim()
    if (form.msg_type === 'image' || form.msg_type === 'emotion') return !!c.asset_id
    if (form.msg_type === 'file') return !!c.asset_id
    if (form.msg_type === 'voice') return !!c.asset_id
    if (form.msg_type === 'news') return Array.isArray(c.articles) && c.articles.length > 0
    if (form.msg_type === 'template_card') return !!c.template_card
    return JSON.stringify(c) !== '{}'
  })

  const autoPreview = () => {
    if (previewTimer) clearTimeout(previewTimer)
    if (!hasContent.value) {
      previewData.value = null
      previewError.value = ''
      return
    }
    previewTimer = setTimeout(() => {
      handlePreview()
    }, 800)
  }

  watch(
    () => [form.msg_type, JSON.stringify(form.contentJson), JSON.stringify(form.variables)],
    () => {
      previewingNotify.value = false
      autoPreview()
    },
  )

  // ---- 批量项自动实时预览 ----
  let batchPreviewTimer: ReturnType<typeof setTimeout> | null = null

  const autoBatchItemPreview = () => {
    if (batchPreviewTimer) clearTimeout(batchPreviewTimer)
    const item = activeBatchItem.value
    if (!item) {
      batchItemPreviewData.value = null
      batchItemPreviewError.value = ''
      return
    }
    batchPreviewTimer = setTimeout(() => {
      handleBatchItemPreview()
    }, 800)
  }

  watch(activeBatchItem, () => {
    autoBatchItemPreview()
  })

  watch(
    () => activeBatchItem.value ? JSON.stringify(activeBatchItem.value.contentJson) : '',
    () => { if (activeBatchItem.value) autoBatchItemPreview() },
  )

  const handleSend = async (testGroupOnly = false) => {
    if (form.groups.length === 0) {
      return ElMessage.warning('请至少选择一个群组')
    }
    if (testGroupOnly) {
      isTestSending.value = true
    } else {
      isSending.value = true
    }
    try {
      // 先发送预告通知
      if (notifyEnabled.value && notifyCustomText.value.trim()) {
        await request.post('/v1/send', {
          group_ids: form.groups,
          msg_type: 'markdown',
          content_json: { content: notifyCustomText.value },
          variables_json: {},
          test_group_only: testGroupOnly
        })
      }
      const res = await request.post('/v1/send', {
        group_ids: form.groups,
        msg_type: form.msg_type,
        content_json: form.contentJson,
        variables_json: form.variables,
        test_group_only: testGroupOnly
      })
      const failed = Array.isArray(res?.results) ? res.results.filter((item: any) => item?.success === false) : []
      if (failed.length > 0) {
        ElMessage.error(`发送失败：${failed[0]?.response || failed[0]?.error_message || '未知错误'}`)
      } else {
        ElMessage.success(testGroupOnly ? '测试群发送成功' : '已触发发送任务')
      }
    } catch (e: any) {
      ElMessage.error('发送失败: ' + String(e))
    } finally {
      if (testGroupOnly) {
        isTestSending.value = false
      } else {
        isSending.value = false
      }
    }
  }

  const handleTestSend = async () => {
    await handleSend(true)
  }

  const handleSchedule = async () => {
    if (form.groups.length === 0) {
      return ElMessage.warning('请至少选择一个群组')
    }
    if (!scheduleForm.title) {
      return ElMessage.warning('请填写任务标题')
    }
    isScheduling.value = true
    try {
      await request.post('/v1/schedules', {
        title: scheduleForm.title,
        group_ids: [...form.groups],
        schedule_type: scheduleForm.schedule_type,
        run_at: scheduleForm.run_at || null,
        cron_expr: scheduleForm.cron_expr || null,
        timezone: scheduleForm.timezone || 'Asia/Shanghai',
        approval_required: scheduleForm.approval_required,
        skip_weekends: scheduleForm.skip_weekends,
        skip_dates: [...scheduleForm.skip_dates],
        msg_type: form.msg_type,
        content_json: form.contentJson,
        variables_json: form.variables
      })
      ElMessage.success('定时任务创建成功')
    } catch (e: any) {
      ElMessage.error('创建定时任务失败: ' + String(e))
    } finally {
      isScheduling.value = false
    }
  }

  // ---- 手动队列发送（纯手写模式下管理多条消息）----
  const manualQueue = ref<BatchQueueItem[]>([])
  const isManualSending = ref(false)
  let isSwitchingManualQueueItem = false

  const activeManualQueueIndex = ref<number | null>(null)
  const activeManualQueueItem = computed<BatchQueueItem | null>(() => {
    if (activeManualQueueIndex.value != null && activeManualQueueIndex.value < manualQueue.value.length)
      return manualQueue.value[activeManualQueueIndex.value]
    return null
  })

  const extractContentTitle = (msgType: string, contentJson: any): string => {
    if (msgType === 'text' || msgType === 'markdown') {
      const content = contentJson.content || ''
      return content.substring(0, 40).replace(/\n/g, ' ') || ''
    }
    if (msgType === 'news') {
      const articles = contentJson.articles || []
      return articles.length > 0 ? (articles[0].title || '图文消息') : '图文消息'
    }
    if (msgType === 'image' || msgType === 'emotion') return contentJson.asset_name || ''
    if (msgType === 'file') return contentJson.asset_name || ''
    if (msgType === 'template_card') return contentJson.template_card?.main_title?.title || ''
    return ''
  }

  // 保存编辑器内容到当前活跃的队列项
  const saveFormToActiveManualQueueItem = () => {
    if (activeManualQueueIndex.value == null) return
    if (activeManualQueueIndex.value === -1) {
      notifyCustomText.value = form.contentJson?.content || ''
      return
    }
    const item = manualQueue.value[activeManualQueueIndex.value]
    if (!item) return
    item.msg_type = form.msg_type
    item.contentJson = JSON.parse(JSON.stringify(form.contentJson))
    item.variablesJson = JSON.parse(JSON.stringify(form.variables))
    const newTitle = extractContentTitle(item.msg_type, item.contentJson)
    if (newTitle) item.title = newTitle
  }

  // 新增一条空消息到队列，自动选中编辑
  const addToManualQueue = () => {
    // 先保存当前编辑器到之前活跃的项
    saveFormToActiveManualQueueItem()

    const idx = manualQueue.value.length
    const item: BatchQueueItem = {
      id: Date.now(),
      title: `消息 ${idx + 1}`,
      msg_type: form.msg_type,
      contentJson: { ...(defaultContentByType[form.msg_type] || {}) },
      variablesJson: {},
      status: 'pending',
      remarkEnabled: false,
      remark: '',
    }
    manualQueue.value.push(item)
    // 切换到新项
    isSwitchingManualQueueItem = true
    activeManualQueueIndex.value = idx
    form.contentJson = JSON.parse(JSON.stringify(item.contentJson))
    form.variables = JSON.parse(JSON.stringify(item.variablesJson))
    nextTick(() => { isSwitchingManualQueueItem = false })
  }

  const selectManualQueueItem = (index: number) => {
    // 点击已选中项不做任何事
    if (activeManualQueueIndex.value === index) return
    // 保存当前编辑器到之前的项
    saveFormToActiveManualQueueItem()
    // 加载新项内容到编辑器
    isSwitchingManualQueueItem = true
    activeManualQueueIndex.value = index
    if (index === -1) {
      // 预告项
      form.msg_type = 'markdown'
      form.contentJson = { content: notifyCustomText.value }
      form.variables = {}
    } else {
      const curr = manualQueue.value[index]
      if (curr) {
        form.msg_type = curr.msg_type
        form.contentJson = JSON.parse(JSON.stringify(curr.contentJson))
        form.variables = JSON.parse(JSON.stringify(curr.variablesJson))
      }
    }
    nextTick(() => { isSwitchingManualQueueItem = false })
  }

  const removeFromManualQueue = (index: number) => {
    manualQueue.value.splice(index, 1)
    if (activeManualQueueIndex.value != null) {
      if (manualQueue.value.length === 0) {
        activeManualQueueIndex.value = null
      } else if (activeManualQueueIndex.value === index) {
        // 删的是当前编辑的项，跳到相邻项
        const nextIdx = Math.min(index, manualQueue.value.length - 1)
        isSwitchingManualQueueItem = true
        activeManualQueueIndex.value = nextIdx
        const next = manualQueue.value[nextIdx]
        form.msg_type = next.msg_type
        form.contentJson = JSON.parse(JSON.stringify(next.contentJson))
        form.variables = JSON.parse(JSON.stringify(next.variablesJson))
        nextTick(() => { isSwitchingManualQueueItem = false })
      } else if (activeManualQueueIndex.value > index) {
        activeManualQueueIndex.value--
      }
    }
  }

  const clearManualQueue = () => {
    manualQueue.value = []
    activeManualQueueIndex.value = null
    form.contentJson = { ...(defaultContentByType[form.msg_type] || {}) }
    form.variables = {}
  }

  const toggleManualQueueRemark = (index: number) => {
    const item = manualQueue.value[index]
    if (!item) return
    item.remarkEnabled = !item.remarkEnabled
    if (item.remarkEnabled && !item.remark) {
      item.remark = ''
    }
  }

  const updateManualQueueRemark = (index: number, text: string) => {
    const item = manualQueue.value[index]
    if (!item) return
    item.remark = text
  }

  // 编辑器内容变化时自动保存回活跃队列项
  watch(
    () => [form.msg_type, JSON.stringify(form.contentJson), JSON.stringify(form.variables)],
    () => {
      if (isSwitchingManualQueueItem) return
      if (activeManualQueueIndex.value === -1) {
        // 预告项：同步回 notifyCustomText
        notifyCustomText.value = form.contentJson?.content || ''
      } else if (activeManualQueueIndex.value != null) {
        const item = manualQueue.value[activeManualQueueIndex.value]
        if (item) {
          item.msg_type = form.msg_type
          item.contentJson = JSON.parse(JSON.stringify(form.contentJson))
          item.variablesJson = JSON.parse(JSON.stringify(form.variables))
          const newTitle = extractContentTitle(item.msg_type, item.contentJson)
          if (newTitle) item.title = newTitle
        }
      }
    }
  )

  const sendManualQueue = async (testGroupOnly = false) => {
    if (form.groups.length === 0) {
      return ElMessage.warning('请至少选择一个群组')
    }
    if (manualQueue.value.length === 0) return

    // 发送前先保存当前编辑器
    saveFormToActiveManualQueueItem()

    isManualSending.value = true
    for (const item of manualQueue.value) {
      item.status = 'pending'
      item.error = undefined
    }

    const sendItems: BatchQueueItem[] = []
    if (notifyEnabled.value && notifyCustomText.value.trim()) {
      sendItems.push({
        id: -1, title: '📢 推送预告', msg_type: 'markdown',
        contentJson: { content: notifyCustomText.value }, variablesJson: {}, status: 'pending',
      })
    }
    for (const item of manualQueue.value) {
      sendItems.push(item)
      if (item.remarkEnabled && item.remark?.trim()) {
        sendItems.push({
          id: -(item.id + 100000), title: `备注: ${item.title}`, msg_type: 'markdown', description: '',
          contentJson: { content: item.remark }, variablesJson: {}, status: 'pending',
        })
      }
    }

    for (const item of sendItems) {
      item.status = 'sending'
      try {
        const res = await request.post('/v1/send', {
          group_ids: form.groups,
          msg_type: item.msg_type,
          content_json: item.contentJson,
          variables_json: item.variablesJson,
          test_group_only: testGroupOnly
        })
        const failed = Array.isArray(res?.results) ? res.results.filter((r: any) => r?.success === false) : []
        if (failed.length > 0) {
          item.status = 'failed'
          item.error = failed.map((r: any) => r.response || r.error_message || '未知错误').join('; ')
        } else {
          item.status = 'success'
        }
      } catch (e: any) {
        item.status = 'failed'
        item.error = String(e)
      }
    }

    isManualSending.value = false

    const success = manualQueue.value.filter(i => i.status === 'success').length
    const failedItems = manualQueue.value.filter(i => i.status === 'failed')
    const failed = failedItems.length
    const total = manualQueue.value.length
    const firstError = failedItems.length > 0 ? failedItems[0].error : ''

    if (failed === 0) {
      ElMessage.success(`队列发送完成：${total} 条全部成功`)
    } else if (success === 0) {
      ElMessage.error(`队列发送失败：全部 ${total} 条发送失败${firstError ? '，原因：' + firstError : ''}`)
    } else {
      ElMessage.warning(`队列发送完成：${success} 成功，${failed} 失败${firstError ? '，原因：' + firstError : ''}`)
    }
  }

  // ---- 批量发送方法 ----

  const handleBatchSelect = (items: Array<{ id: number; title: string; msg_type: string; description?: string; contentJson: Record<string, any>; variablesJson: Record<string, any> }>) => {
    batchQueue.value = items.map(item => ({
      id: item.id,
      title: item.title,
      msg_type: item.msg_type,
      description: item.description || '',
      contentJson: item.contentJson,
      variablesJson: item.variablesJson,
      status: 'pending' as const,
      remarkEnabled: false,
      remark: item.description || '',
    }))
    // 进入批量模式时清除单条选中状态
    selectedContentSource.value = null
    selectedContentId.value = null
    selectedContentLabel.value = `批量发送 (${items.length} 项)`
  }

  const handleRankingSelect = (items: Array<{ id: number; title: string; msg_type: string; description?: string; contentJson: Record<string, any>; variablesJson: Record<string, any>; targetGroupIds: number[] }>) => {
    batchQueue.value = items.map(item => ({
      id: item.id,
      title: item.title,
      msg_type: item.msg_type,
      description: item.description || '',
      contentJson: item.contentJson,
      variablesJson: item.variablesJson || {},
      status: 'pending' as const,
      remarkEnabled: false,
      remark: '',
      targetGroupIds: item.targetGroupIds,
    }))
    selectedContentSource.value = null
    selectedContentId.value = null
    selectedContentLabel.value = `积分排行 (${items.length} 群)`
  }

  const removeBatchItem = (index: number) => {
    batchQueue.value.splice(index, 1)
  }

  const toggleBatchItemRemark = (index: number) => {
    const item = batchQueue.value[index]
    if (!item) return
    item.remarkEnabled = !item.remarkEnabled
    if (item.remarkEnabled && !item.remark) {
      item.remark = item.description || ''
    }
  }

  const updateBatchItemRemark = (index: number, text: string) => {
    const item = batchQueue.value[index]
    if (!item) return
    item.remark = text
  }

  const clearBatch = () => {
    batchQueue.value = []
    isBatchSending.value = false
    batchCancelled.value = false
    activeBatchIndex.value = null
    batchItemPreviewData.value = null
    batchItemPreviewError.value = ''
    selectedContentLabel.value = null
    notifySendStatus.value = 'hidden'
  }

  const cancelBatchSend = () => {
    batchCancelled.value = true
  }

  const handleBatchSend = async (testGroupOnly = false) => {
    // 检查：如果有项目没有 targetGroupIds，需要 form.groups
    const needsGlobalGroups = batchQueue.value.some(item => !item.targetGroupIds?.length)
    if (needsGlobalGroups && form.groups.length === 0) {
      return ElMessage.warning('请至少选择一个群组')
    }
    const hasAnyTarget = batchQueue.value.every(item => item.targetGroupIds?.length || form.groups.length)
    if (!hasAnyTarget) {
      return ElMessage.warning('部分排行消息未绑定发送群，请先配置映射')
    }
    if (batchQueue.value.length === 0) return

    isBatchSending.value = true
    batchCancelled.value = false

    // 重置所有状态
    for (const item of batchQueue.value) {
      item.status = 'pending'
      item.error = undefined
    }
    if (notifyEnabled.value && notifyCustomText.value.trim()) {
      notifySendStatus.value = 'pending'
    }

    // 构建实际发送列表（预告可选插入头部，备注可选插入每项之后）
    const sendQueue: Array<{ item: BatchQueueItem; index: number }> = []
    if (notifyEnabled.value && notifyCustomText.value.trim()) {
      sendQueue.push({
        item: { id: -1, title: '📢 推送预告', msg_type: 'markdown', contentJson: { content: notifyCustomText.value }, variablesJson: {}, status: 'pending' as const },
        index: -1,
      })
    }
    for (let i = 0; i < batchQueue.value.length; i++) {
      sendQueue.push({ item: batchQueue.value[i], index: i })
      // 备注消息紧跟在该任务后面
      if (batchQueue.value[i].remarkEnabled && batchQueue.value[i].remark?.trim()) {
        sendQueue.push({
          item: {
            id: -(i + 100),
            title: `备注: ${batchQueue.value[i].title}`,
            msg_type: 'markdown',
            description: '',
            contentJson: { content: batchQueue.value[i].remark },
            variablesJson: {},
            status: 'pending' as const,
          },
          index: -2,
        })
      }
    }

    // 发送限速：同一群 20 条/分钟 → 每 3 秒发一条到不同群
    const BATCH_SEND_INTERVAL_MS = 2000
    const RATE_LIMIT_RETRY_MS = 65000  // 触发限速后等 65 秒重试
    const isRateLimitError = (msg: string) => /20.*分钟.*限制|rate.?limit/i.test(msg)

    for (let si = 0; si < sendQueue.length; si++) {
      if (batchCancelled.value) break
      const entry = sendQueue[si]
      const item = entry.item
      item.status = 'sending'
      if (entry.index === -1) notifySendStatus.value = 'sending'

      // 发送间隔（首条不等待）
      if (si > 0) {
        await new Promise(r => setTimeout(r, BATCH_SEND_INTERVAL_MS))
      }

      try {
        const res = await request.post('/v1/send', {
          group_ids: item.targetGroupIds?.length ? item.targetGroupIds : form.groups,
          msg_type: item.msg_type,
          content_json: item.contentJson,
          variables_json: item.variablesJson,
          test_group_only: testGroupOnly
        })
        const failed = Array.isArray(res?.results) ? res.results.filter((r: any) => r?.success === false) : []
        if (failed.length > 0) {
          const errMsg = failed.map((r: any) => r.response || r.error_message || '未知错误').join('; ')
          // 触发限速 → 等待后重试一次
          if (isRateLimitError(errMsg)) {
            item.status = 'sending'
            await new Promise(r => setTimeout(r, RATE_LIMIT_RETRY_MS))
            if (batchCancelled.value) { item.status = 'failed'; item.error = '已取消'; break }
            try {
              const retryRes = await request.post('/v1/send', {
                group_ids: item.targetGroupIds?.length ? item.targetGroupIds : form.groups,
                msg_type: item.msg_type,
                content_json: item.contentJson,
                variables_json: item.variablesJson,
                test_group_only: testGroupOnly
              })
              const retryFailed = Array.isArray(retryRes?.results) ? retryRes.results.filter((r: any) => r?.success === false) : []
              if (retryFailed.length > 0) {
                item.status = 'failed'
                item.error = retryFailed.map((r: any) => r.response || r.error_message || '未知错误').join('; ')
                if (entry.index === -1) notifySendStatus.value = 'failed'
              } else {
                item.status = 'success'
                if (entry.index === -1) notifySendStatus.value = 'success'
              }
            } catch {
              item.status = 'failed'
              item.error = '重试仍失败：触发限速'
              if (entry.index === -1) notifySendStatus.value = 'failed'
            }
          } else {
            item.status = 'failed'
            item.error = errMsg
            if (entry.index === -1) notifySendStatus.value = 'failed'
          }
        } else {
          item.status = 'success'
          if (entry.index === -1) notifySendStatus.value = 'success'
        }
      } catch (e: any) {
        const errMsg = String(e)
        // 触发限速 → 等待后重试一次
        if (isRateLimitError(errMsg)) {
          item.status = 'sending'
          await new Promise(r => setTimeout(r, RATE_LIMIT_RETRY_MS))
          if (batchCancelled.value) { item.status = 'failed'; item.error = '已取消'; break }
          try {
            const retryRes = await request.post('/v1/send', {
              group_ids: item.targetGroupIds?.length ? item.targetGroupIds : form.groups,
              msg_type: item.msg_type,
              content_json: item.contentJson,
              variables_json: item.variablesJson,
              test_group_only: testGroupOnly
            })
            const retryFailed = Array.isArray(retryRes?.results) ? retryRes.results.filter((r: any) => r?.success === false) : []
            if (retryFailed.length > 0) {
              item.status = 'failed'
              item.error = '重试仍失败'
              if (entry.index === -1) notifySendStatus.value = 'failed'
            } else {
              item.status = 'success'
              if (entry.index === -1) notifySendStatus.value = 'success'
            }
          } catch {
            item.status = 'failed'
            item.error = '重试仍失败：触发限速'
            if (entry.index === -1) notifySendStatus.value = 'failed'
          }
        } else {
          item.status = 'failed'
          item.error = errMsg
          if (entry.index === -1) notifySendStatus.value = 'failed'
        }
      }
    }

    isBatchSending.value = false

    const { success, failed: failCount, total } = batchProgress.value
    const firstBatchError = batchQueue.value.find(i => i.status === 'failed' && i.error)?.error || ''
    if (batchCancelled.value) {
      ElMessage.warning(`批量发送已中断：${success}/${total} 成功`)
    } else if (failCount === 0) {
      ElMessage.success(`批量发送完成：${total} 条全部成功`)
    } else if (success === 0) {
      ElMessage.error(`批量发送失败：全部 ${total} 条发送失败${firstBatchError ? '，原因：' + firstBatchError : ''}`)
    } else {
      ElMessage.warning(`批量发送完成：${success} 成功，${failCount} 失败${firstBatchError ? '，原因：' + firstBatchError : ''}`)
    }
  }

  // ---- 草稿自动保存（防抖 1s）----
  let draftTimer: ReturnType<typeof setTimeout> | null = null
  const autoSaveDraft = () => {
    if (draftTimer) clearTimeout(draftTimer)
    draftTimer = setTimeout(() => {
      saveDraft({
        form: { groups: form.groups, msg_type: form.msg_type, contentJson: form.contentJson, variables: form.variables, template_id: form.template_id },
        scheduleForm: { title: scheduleForm.title, schedule_type: scheduleForm.schedule_type, run_at: scheduleForm.run_at, cron_expr: scheduleForm.cron_expr, timezone: scheduleForm.timezone, approval_required: scheduleForm.approval_required, skip_weekends: scheduleForm.skip_weekends, skip_dates: scheduleForm.skip_dates },
        selectedContentSource: selectedContentSource.value,
        selectedContentId: selectedContentId.value,
        selectedContentLabel: selectedContentLabel.value,
        batchQueue: batchQueue.value.map(item => ({ ...item })),
        activeBatchIndex: activeBatchIndex.value
      })
    }, 1000)
  }

  watch(
    () => [
      form.groups, form.msg_type, JSON.stringify(form.contentJson), JSON.stringify(form.variables), form.template_id,
      scheduleForm.title, scheduleForm.schedule_type, scheduleForm.run_at, scheduleForm.cron_expr,
      scheduleForm.timezone, scheduleForm.approval_required, scheduleForm.skip_weekends, JSON.stringify(scheduleForm.skip_dates),
      selectedContentSource.value, selectedContentId.value, selectedContentLabel.value,
      batchQueue.value.length, activeBatchIndex.value
    ],
    autoSaveDraft,
  )

  onMounted(() => {
    fetchBaseData()
  })

  onBeforeUnmount(() => {
    if (draftTimer) clearTimeout(draftTimer)
    // 立即保存一次，确保最新状态写入
    saveDraft({
      form: { groups: form.groups, msg_type: form.msg_type, contentJson: form.contentJson, variables: form.variables, template_id: form.template_id },
      scheduleForm: { title: scheduleForm.title, schedule_type: scheduleForm.schedule_type, run_at: scheduleForm.run_at, cron_expr: scheduleForm.cron_expr, timezone: scheduleForm.timezone, approval_required: scheduleForm.approval_required, skip_weekends: scheduleForm.skip_weekends, skip_dates: scheduleForm.skip_dates },
      selectedContentSource: selectedContentSource.value,
      selectedContentId: selectedContentId.value,
      selectedContentLabel: selectedContentLabel.value,
      batchQueue: batchQueue.value.map(item => ({ ...item })),
      activeBatchIndex: activeBatchIndex.value
    })
  })

  // ---- 队列定时发送 ----
  const handleBatchQueueSchedule = async () => {
    if (batchQueue.value.length === 0) {
      return ElMessage.warning('发送队列为空')
    }
    if (!scheduleForm.title) {
      return ElMessage.warning('请填写任务标题')
    }
    // 检查群组：如果所有 item 都有 targetGroupIds 则不需要全局 groups
    const allHaveTargets = batchQueue.value.every(item => item.targetGroupIds?.length)
    if (!allHaveTargets && form.groups.length === 0) {
      return ElMessage.warning('请至少选择一个群组')
    }

    isScheduling.value = true
    try {
      // 构建 batch_items
      const batchItems: Array<{ msg_type: string; content_json: any; variables_json: any; group_ids: number[] | null }> = []

      // 推送预告（可选）
      if (notifyEnabled.value && notifyCustomText.value.trim()) {
        batchItems.push({
          msg_type: 'markdown',
          content_json: { content: notifyCustomText.value },
          variables_json: {},
          group_ids: allHaveTargets ? null : [...form.groups],
        })
      }

      // 消息 + 备注
      for (const item of batchQueue.value) {
        batchItems.push({
          msg_type: item.msg_type,
          content_json: item.contentJson,
          variables_json: item.variablesJson,
          group_ids: item.targetGroupIds?.length ? [...item.targetGroupIds] : (allHaveTargets ? null : [...form.groups]),
        })
        if (item.remarkEnabled && item.remark?.trim()) {
          batchItems.push({
            msg_type: 'markdown',
            content_json: { content: item.remark },
            variables_json: {},
            group_ids: item.targetGroupIds?.length ? [...item.targetGroupIds] : (allHaveTargets ? null : [...form.groups]),
          })
        }
      }

      await request.post('/v1/schedules', {
        title: scheduleForm.title,
        group_ids: allHaveTargets ? [0] : [...form.groups],  // 全局占位避免后端校验报错
        schedule_type: scheduleForm.schedule_type,
        run_at: scheduleForm.run_at || null,
        cron_expr: scheduleForm.cron_expr || null,
        timezone: scheduleForm.timezone || 'Asia/Shanghai',
        approval_required: scheduleForm.approval_required,
        skip_weekends: scheduleForm.skip_weekends,
        skip_dates: [...scheduleForm.skip_dates],
        msg_type: batchQueue.value[0]?.msg_type || 'markdown',
        content_json: batchQueue.value[0]?.contentJson || {},
        variables_json: batchQueue.value[0]?.variablesJson || {},
        batch_items_json: batchItems,
      })
      ElMessage.success(`定时任务创建成功，包含 ${batchItems.length} 条消息`)
    } catch (e: any) {
      ElMessage.error('创建定时任务失败: ' + String(e))
    } finally {
      isScheduling.value = false
    }
  }

  return {
    groups,
    templates,
    selectedContentSource,
    selectedContentId,
    selectedContentLabel,
    previewData,
    previewError,
    form,
    scheduleForm,
    isPreviewing,
    isSending,
    isTestSending,
    isScheduling,
    // 批量发送
    batchQueue,
    notifyEnabled,
    notifyCustomText,
    notifyAutoText,
    notifySendStatus,
    previewingNotify,
    isBatchMode,
    isBatchSending,
    batchProgress,
    activeBatchIndex,
    activeBatchItem,
    batchItemPreviewData,
    batchItemPreviewError,
    isBatchItemPreviewing,
    selectBatchItem,
    handleBatchSelect,
    handleRankingSelect,
    removeBatchItem,
    toggleBatchItemRemark,
    updateBatchItemRemark,
    clearBatch,
    cancelBatchSend,
    handleBatchSend,
    handleBatchItemContentUpdate,
    handleBatchItemVariablesUpdate,
    handleBatchItemPreview,
    handleBatchItemSchedule,
    handleBatchQueueSchedule,
    handleNotifyPreview,
    // 单条操作
    handleMsgTypeChange,
    handleContentSelect,
    handleClearContent,
    handlePreview,
    handleSend,
    handleTestSend,
    handleSchedule,
    // 手动队列
    manualQueue,
    isManualSending,
    addToManualQueue,
    removeFromManualQueue,
    clearManualQueue,
    sendManualQueue,
    toggleManualQueueRemark,
    updateManualQueueRemark,
    activeManualQueueIndex,
    activeManualQueueItem,
    selectManualQueueItem,
    // 草稿管理
    clearSendCenterDraft
  }
}
