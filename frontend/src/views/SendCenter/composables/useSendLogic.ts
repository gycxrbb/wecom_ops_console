import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import request from '@/utils/request'
import { buildAssetAuthUrl } from '@/utils/assets'
import { ElMessage } from 'element-plus'
import { msgTypeLabel } from '@/views/Templates/composables/useTemplates'

// 每种消息类型的默认 content_json 结构
const defaultContentByType: Record<string, any> = {
  text: { content: '', mentioned_list: [], mentioned_mobile_list: [] },
  markdown: { content: '' },
  news: { articles: [] },
  image: { asset_id: undefined, asset_name: '', asset_url: '', image_path: '' },
  file: { asset_id: undefined, asset_name: '', media_id: '' },
  template_card: { template_card: { card_type: 'text_notice', main_title: { title: '' } } },
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

  const notifyAutoText = computed(() => {
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
      if (form.msg_type === 'image') {
        nextPreview.rendered_content = {
          ...(nextPreview.rendered_content || {}),
          asset_url: buildAssetAuthUrl(form.contentJson?.asset_url || '')
        }
      }
      if (form.msg_type === 'file') {
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
    if (form.msg_type === 'image') return !!c.asset_id
    if (form.msg_type === 'file') return !!c.asset_id
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
    autoPreview,
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
    }))
    // 进入批量模式时清除单条选中状态
    selectedContentSource.value = null
    selectedContentId.value = null
    selectedContentLabel.value = `批量发送 (${items.length} 项)`
  }

  const removeBatchItem = (index: number) => {
    batchQueue.value.splice(index, 1)
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
    if (form.groups.length === 0) {
      return ElMessage.warning('请至少选择一个群组')
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

    // 构建实际发送列表（预告可选插入头部）
    const sendQueue: Array<{ item: BatchQueueItem; index: number }> = []
    if (notifyEnabled.value && notifyCustomText.value.trim()) {
      sendQueue.push({
        item: { id: -1, title: '📢 推送预告', msg_type: 'markdown', contentJson: { content: notifyCustomText.value }, variablesJson: {}, status: 'pending' as const },
        index: -1,
      })
    }
    for (let i = 0; i < batchQueue.value.length; i++) {
      sendQueue.push({ item: batchQueue.value[i], index: i })
    }

    for (const entry of sendQueue) {
      if (batchCancelled.value) break
      const item = entry.item
      item.status = 'sending'
      if (entry.index === -1) notifySendStatus.value = 'sending'
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
          if (entry.index === -1) notifySendStatus.value = 'failed'
        } else {
          item.status = 'success'
          if (entry.index === -1) notifySendStatus.value = 'success'
        }
      } catch (e: any) {
        item.status = 'failed'
        item.error = String(e)
        if (entry.index === -1) notifySendStatus.value = 'failed'
      }
    }

    isBatchSending.value = false

    const { success, failed: failCount, total } = batchProgress.value
    if (batchCancelled.value) {
      ElMessage.warning(`批量发送已中断：${success}/${total} 成功`)
    } else if (failCount === 0) {
      ElMessage.success(`批量发送完成：${total} 条全部成功`)
    } else if (success === 0) {
      ElMessage.error(`批量发送失败：全部 ${total} 条发送失败`)
    } else {
      ElMessage.warning(`批量发送完成：${success} 成功，${failCount} 失败`)
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
    removeBatchItem,
    clearBatch,
    cancelBatchSend,
    handleBatchSend,
    handleBatchItemContentUpdate,
    handleBatchItemVariablesUpdate,
    handleBatchItemPreview,
    handleBatchItemSchedule,
    // 单条操作
    handleMsgTypeChange,
    handleContentSelect,
    handleClearContent,
    handlePreview,
    handleSend,
    handleTestSend,
    handleSchedule,
    // 草稿管理
    clearSendCenterDraft
  }
}
