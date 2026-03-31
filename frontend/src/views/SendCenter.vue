<template>
  <div class="view-container">
    <h2>发送中心</h2>
    <el-row :gutter="20">
      <!-- Left side: Compose -->
      <el-col :span="12">
        <el-card>
          <template #header>消息内容</template>
          <el-form label-width="100px">
            <el-form-item label="群组">
              <el-select v-model="form.groups" multiple placeholder="选择群组" style="width: 100%">
                <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="模板">
              <el-select v-model="selectedTemplate" @change="handleTemplateChange" placeholder="使用模板" clearable style="width: 100%">
                <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="消息类型">
              <el-select v-model="form.msg_type" @change="handleMsgTypeChange" style="width: 100%">
                <el-option label="文本" value="text"></el-option>
                <el-option label="Markdown" value="markdown"></el-option>
                <el-option label="图片" value="image"></el-option>
                <el-option label="图文 (News)" value="news"></el-option>
                <el-option label="文件" value="file"></el-option>
                <el-option label="模板卡片" value="template_card"></el-option>
              </el-select>
            </el-form-item>

            <!-- 可视化编辑器 -->
            <el-form-item label="消息内容">
              <MessageEditor
                v-model="form.contentJson"
                :msg-type="form.msg_type"
                v-model:variables="form.variables"
                :show-variables="!!selectedTemplate"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="info" @click="handlePreview">预览</el-button>
              <el-button type="primary" @click="handleSend">立即发送</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- Right side: Preview & Schedule -->
      <el-col :span="12">
        <el-card style="margin-bottom: 20px">
          <template #header>预览结果</template>
          <pre class="preview-box">{{ previewResult }}</pre>
        </el-card>

        <el-card>
          <template #header>定时发送</template>
          <el-form label-width="100px">
            <el-form-item label="任务标题">
              <el-input v-model="scheduleForm.title" />
            </el-form-item>
            <el-form-item label="任务类型">
              <el-radio-group v-model="scheduleForm.schedule_type">
                <el-radio label="once">一次性</el-radio>
                <el-radio label="cron">周期性</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="执行时间" v-if="scheduleForm.schedule_type === 'once'">
              <el-date-picker v-model="scheduleForm.run_at" type="datetime" placeholder="选择时间" value-format="YYYY-MM-DDTHH:mm:ss" />
            </el-form-item>
            <el-form-item label="Cron表达式" v-if="scheduleForm.schedule_type === 'cron'">
              <el-input v-model="scheduleForm.cron_expr" placeholder="* * * * *" />
            </el-form-item>
            <el-form-item>
              <el-button type="success" @click="handleSchedule">创建定时任务</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import MessageEditor from '@/components/message-editor/index.vue'

const groups = ref<any[]>([])
const templates = ref<any[]>([])
const selectedTemplate = ref<any>(null)
const previewResult = ref('暂无预览')

// 默认内容按类型初始化
const defaultContentByType: Record<string, any> = {
  text: { content: '', mentioned_list: [], mentioned_mobile_list: [] },
  markdown: { content: '' },
  news: { articles: [] },
  image: {},
  file: {},
  template_card: { card_type: 'text_notice', main_title: { title: '' } },
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
  cron_expr: ''
})

const fetchBaseData = async () => {
  try {
    const res1 = await request.get('/v1/groups')
    const res2 = await request.get('/v1/templates')
    groups.value = res1.list || res1
    templates.value = res2.list || res2
  } catch (e) { console.error(e) }
}

const handleMsgTypeChange = (type: string) => {
  form.contentJson = { ...(defaultContentByType[type] || {}) }
}

const handleTemplateChange = (val: any) => {
  const t = templates.value.find((x: any) => x.id === val)
  if (t) {
    form.msg_type = t.msg_type
    form.template_id = t.id
    // 解析模板 content JSON
    try {
      const content = typeof t.content === 'string' ? JSON.parse(t.content) : (t.content || {})
      form.contentJson = { ...content }
    } catch {
      form.contentJson = { ...(defaultContentByType[t.msg_type] || {}) }
    }
    // 解析变量
    try {
      const vars = typeof t.variable_schema === 'string' ? JSON.parse(t.variable_schema) : (t.variable_schema || {})
      form.variables = { ...vars }
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
  }
}

const handleSend = async () => {
  if (form.groups.length === 0) {
    return ElMessage.warning('请选择群组')
  }
  try {
    await request.post('/v1/send', {
      group_ids: form.groups,
      msg_type: form.msg_type,
      content_json: form.contentJson,
      variables_json: form.variables
    })
    ElMessage.success('已触发发送任务')
  } catch (e) {
    console.error(e)
  }
}

const handleSchedule = async () => {
  if (form.groups.length === 0) {
    return ElMessage.warning('请选择群组')
  }
  try {
    await request.post('/v1/schedules', {
      title: scheduleForm.title,
      group_ids: form.groups.join(','),
      schedule_type: scheduleForm.schedule_type,
      run_at: scheduleForm.run_at || null,
      cron_expr: scheduleForm.cron_expr || null,
      msg_type: form.msg_type,
      content_json: form.contentJson,
      variables_json: form.variables
    })
    ElMessage.success('定时任务创建成功')
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  fetchBaseData()
})
</script>

<style scoped>
.view-container {
  padding: 20px;
}
.preview-box {
  background: var(--bg-color, #f5f7fa);
  padding: 10px;
  border-radius: 4px;
  min-height: 100px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
}
</style>
