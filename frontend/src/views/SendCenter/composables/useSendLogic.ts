import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

export function useSendLogic() {
  const groups = ref<any[]>([])
  const templates = ref<any[]>([])
  const selectedTemplate = ref(null)
  const previewResult = ref('暂无预览...')
  const isPreviewing = ref(false)
  const isSending = ref(false)
  const isScheduling = ref(false)

  const form = reactive({
    groups: [] as number[],
    msg_type: 'text',
    content: '',
    variables: '{}',
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

  const handleTemplateChange = (val: any) => {
    const t = templates.value.find(x => x.id === val)
    if (t) {
      form.content = t.content
      form.msg_type = t.msg_type
      form.variables = t.variables_schema ? JSON.stringify(t.variables_schema, null, 2) : '{}'
      form.template_id = t.id
    } else {
      form.template_id = null
    }
  }

  const handlePreview = async () => {
    if (!form.content) {
      return ElMessage.warning('内容不能为空')
    }
    
    isPreviewing.value = true
    try {
      let parsedVars = {}
      try {
        parsedVars = JSON.parse(form.variables || '{}')
      } catch (err) {
        ElMessage.warning('变量 JSON 格式错误')
        isPreviewing.value = false
        return
      }

      const res = await request.post('/v1/preview', {
        template_id: form.template_id,
        content: form.content,
        variables: parsedVars
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
    if (!form.content) {
      return ElMessage.warning('内容不能为空')
    }

    isSending.value = true
    try {
      let parsedVars = {}
      try {
        parsedVars = JSON.parse(form.variables || '{}')
      } catch (err) {
        ElMessage.warning('变量 JSON 格式错误')
        isSending.value = false
        return
      }

      await request.post('/v1/send', {
        group_ids: form.groups,
        msg_type: form.msg_type,
        content: form.content,
        variables: parsedVars
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
        group_ids: form.groups.join(','),
        schedule_type: scheduleForm.schedule_type,
        run_at: scheduleForm.run_at || null,
        cron_expr: scheduleForm.cron_expr || null,
        msg_type: form.msg_type,
        content: form.content,
        variables: form.variables
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
    handleTemplateChange,
    handlePreview,
    handleSend,
    handleSchedule
  }
}