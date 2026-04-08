import { ref, reactive, computed, onMounted } from 'vue'
import request from '@/utils/request'
import { buildAssetAuthUrl } from '@/utils/assets'
import { ElMessage } from 'element-plus'

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
  contentJson: Record<string, any>
  variablesJson: Record<string, any>
  status: 'pending' | 'sending' | 'success' | 'failed'
  error?: string
}

export function useSendLogic() {
  const groups = ref<any[]>([])
  const templates = ref<any[]>([])
  const selectedContentSource = ref<'template' | 'plan_node' | null>(null)
  const selectedContentId = ref<number | null>(null)
  const selectedContentLabel = ref<string | null>(null)
  const previewData = ref<any | null>(null)
  const previewError = ref('')
  const isPreviewing = ref(false)
  const isSending = ref(false)
  const isTestSending = ref(false)
  const isScheduling = ref(false)

  // ---- 批量发送状态 ----
  const batchQueue = ref<BatchQueueItem[]>([])
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
  const activeBatchIndex = ref<number | null>(null)
  const activeBatchItem = computed(() =>
    activeBatchIndex.value != null && activeBatchIndex.value < batchQueue.value.length
      ? batchQueue.value[activeBatchIndex.value] : null
  )
  const batchItemPreviewData = ref<any | null>(null)
  const batchItemPreviewError = ref('')
  const isBatchItemPreviewing = ref(false)

  const selectBatchItem = (index: number | null) => {
    activeBatchIndex.value = index
    batchItemPreviewData.value = null
    batchItemPreviewError.value = ''
  }

  const handleBatchItemContentUpdate = (val: Record<string, any>) => {
    if (activeBatchItem.value) activeBatchItem.value.contentJson = val
  }

  const handleBatchItemVariablesUpdate = (val: Record<string, any>) => {
    if (activeBatchItem.value) activeBatchItem.value.variablesJson = val
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
    groups: [] as number[],
    msg_type: 'text',
    contentJson: { ...defaultContentByType.text },
    variables: {} as Record<string, any>,
    template_id: null as number | null
  })

  const scheduleForm = reactive({
    title: '',
    schedule_type: 'once',
    run_at: '',
    cron_expr: '',
    timezone: 'Asia/Shanghai',
    approval_required: false,
    skip_weekends: false,
    skip_dates: [] as string[]
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

  const handleBatchSelect = (items: Array<{ id: number; title: string; msg_type: string; contentJson: Record<string, any>; variablesJson: Record<string, any> }>) => {
    batchQueue.value = items.map(item => ({
      id: item.id,
      title: item.title,
      msg_type: item.msg_type,
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

    for (let i = 0; i < batchQueue.value.length; i++) {
      if (batchCancelled.value) break
      const item = batchQueue.value[i]
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

  onMounted(() => {
    fetchBaseData()
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
    handleSchedule
  }
}
