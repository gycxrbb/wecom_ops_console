import { ref, reactive, onMounted } from 'vue'
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
    handleMsgTypeChange,
    handleContentSelect,
    handleClearContent,
    handlePreview,
    handleSend,
    handleTestSend,
    handleSchedule
  }
}
