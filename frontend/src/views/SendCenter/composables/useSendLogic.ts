import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

// 每种消息类型的默认 content_json 结构
const defaultContentByType: Record<string, any> = {
  text: { content: '', mentioned_list: [], mentioned_mobile_list: [] },
  markdown: { content: '' },
  news: { articles: [] },
  image: {},
  file: {},
  template_card: { card_type: 'text_notice', main_title: { title: '' } },
}

export function useSendLogic() {
  const groups = ref<any[]>([])
  const templates = ref<any[]>([])
  const selectedTemplate = ref<any>(null)
  const previewResult = ref('暂无预览...')
  const isPreviewing = ref(false)
  const isSending = ref(false)
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
    cron_expr: ''
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
    form.contentJson = { ...(defaultContentByType[type] || {}) }
  }

  const handleTemplateChange = (val: any) => {
    const t = templates.value.find(x => x.id === val)
    if (t) {
      form.msg_type = t.msg_type
      form.template_id = t.id
      // 解析模板 content JSON — 后端返回 content_json
      const rawContent = t.content_json ?? t.content
      try {
        form.contentJson = typeof rawContent === 'string'
          ? JSON.parse(rawContent)
          : (rawContent || {})
      } catch {
        form.contentJson = { ...(defaultContentByType[t.msg_type] || {}) }
      }
      // 解析变量 — 后端返回 variables_json
      const rawVars = t.variables_json ?? t.variable_schema
      try {
        form.variables = typeof rawVars === 'string'
          ? JSON.parse(rawVars)
          : (rawVars || {})
      } catch {
        form.variables = {}
      }
    } else {
      form.template_id = null
      form.variables = {}
      handleMsgTypeChange(form.msg_type)
    }
  }

  const handlePreview = async () => {
    isPreviewing.value = true
    try {
      const res = await request.post('/v1/preview', {
        msg_type: form.msg_type,
        content_json: form.contentJson,
        variables_json: form.variables,
        group_ids: form.groups.length > 0 ? [form.groups[0]] : undefined
      })
      previewResult.value = JSON.stringify(res, null, 2)
    } catch (e: any) {
      previewResult.value = '预览失败: ' + String(e)
    } finally {
      isPreviewing.value = false
    }
  }

  const handleSend = async () => {
    if (form.groups.length === 0) {
      return ElMessage.warning('请至少选择一个群组')
    }
    isSending.value = true
    try {
      await request.post('/v1/send', {
        group_ids: form.groups,
        msg_type: form.msg_type,
        content_json: form.contentJson,
        variables_json: form.variables
      })
      ElMessage.success('已触发发送任务')
    } catch (e: any) {
      ElMessage.error('发送失败: ' + String(e))
    } finally {
      isSending.value = false
    }
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
    selectedTemplate,
    previewResult,
    form,
    scheduleForm,
    isPreviewing,
    isSending,
    isScheduling,
    handleMsgTypeChange,
    handleTemplateChange,
    handlePreview,
    handleSend,
    handleSchedule
  }
}
