<template>
  <div class="view-container">
    <div class="header-actions">
      <h2>模板中心</h2>
      <el-button type="primary" @click="openCreate">新增模板</el-button>
    </div>

    <el-table :data="templates" style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="模板名称" />
      <el-table-column prop="msg_type" label="消息类型">
        <template #default="{ row }">
          <el-tag>{{ msgTypeLabel(row.msg_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button type="primary" link @click="editTemplate(row)">编辑</el-button>
          <el-button type="primary" link @click="cloneTemplate(row)">克隆</el-button>
          <el-button type="danger" link @click="deleteTemplate(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑模板' : '新增模板'" width="70%" top="5vh">
      <el-form label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="form.name" placeholder="输入模板名称" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="分类">
              <el-input v-model="form.category" placeholder="模板分类" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="描述">
              <el-input v-model="form.description" placeholder="模板描述" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="消息类型">
          <el-select v-model="form.msg_type" @change="handleMsgTypeChange" style="width: 200px">
            <el-option label="文本" value="text"></el-option>
            <el-option label="Markdown" value="markdown"></el-option>
            <el-option label="图片" value="image"></el-option>
            <el-option label="图文 (News)" value="news"></el-option>
            <el-option label="文件" value="file"></el-option>
            <el-option label="模板卡片" value="template_card"></el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="模板内容">
          <MessageEditor
            v-model="form.contentJson"
            :msg-type="form.msg_type"
            v-model:variables="form.variablesJson"
            :show-variables="true"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTemplate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import MessageEditor from '@/components/message-editor/index.vue'

const templates = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)

const defaultContentByType: Record<string, any> = {
  text: { content: '', mentioned_list: [], mentioned_mobile_list: [] },
  markdown: { content: '' },
  news: { articles: [] },
  image: {},
  file: {},
  template_card: { card_type: 'text_notice', main_title: { title: '' } },
}

const form = reactive({
  id: null as number | null,
  name: '',
  description: '',
  msg_type: 'text',
  category: 'general',
  contentJson: { ...defaultContentByType.text },
  variablesJson: {} as Record<string, any>,
})

const msgTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    text: '文本', markdown: 'Markdown', image: '图片',
    news: '图文', file: '文件', template_card: '模板卡片'
  }
  return map[type] || type
}

const fetchTemplates = async () => {
  loading.value = true
  try {
    const res = await request.get('/v1/templates')
    templates.value = res.list || res
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  form.id = null
  form.name = ''
  form.description = ''
  form.msg_type = 'text'
  form.category = 'general'
  form.contentJson = { ...defaultContentByType.text }
  form.variablesJson = {}
  dialogVisible.value = true
}

const editTemplate = (row: any) => {
  form.id = row.id
  form.name = row.name
  form.description = row.description || ''
  form.msg_type = row.msg_type
  form.category = row.category || 'general'
  // 解析 content — 后端 serialize_template 返回 content_json
  const rawContent = row.content_json ?? row.content
  try {
    form.contentJson = typeof rawContent === 'string' ? JSON.parse(rawContent) : (rawContent || {})
  } catch {
    form.contentJson = { ...(defaultContentByType[row.msg_type] || {}) }
  }
  // 解析 variables — 后端返回 variables_json
  const rawVars = row.variables_json ?? row.variable_schema
  try {
    form.variablesJson = typeof rawVars === 'string'
      ? JSON.parse(rawVars)
      : (rawVars || {})
  } catch {
    form.variablesJson = {}
  }
  dialogVisible.value = true
}

const handleMsgTypeChange = (type: string) => {
  form.contentJson = { ...(defaultContentByType[type] || {}) }
}

const cloneTemplate = async (row: any) => {
  try {
    await request.post(`/v1/templates/${row.id}/clone`)
    ElMessage.success('克隆成功')
    fetchTemplates()
  } catch (e) { console.error(e) }
}

const deleteTemplate = (row: any) => {
  ElMessageBox.confirm('确认删除该模板？', '警告', { type: 'warning' }).then(async () => {
    await request.delete(`/v1/templates/${row.id}`)
    ElMessage.success('删除成功')
    fetchTemplates()
  })
}

const saveTemplate = async () => {
  if (!form.name.trim()) {
    return ElMessage.warning('请输入模板名称')
  }
  try {
    await request.post('/v1/templates', {
      id: form.id,
      name: form.name,
      description: form.description,
      category: form.category,
      msg_type: form.msg_type,
      content_json: form.contentJson,
      variables_json: form.variablesJson,
    })
    dialogVisible.value = false
    ElMessage.success('保存成功')
    fetchTemplates()
  } catch (e) { console.error(e) }
}

onMounted(() => {
  fetchTemplates()
})
</script>

<style scoped>
.view-container {
  padding: 20px;
  background: var(--card-bg, #fff);
  border-radius: 4px;
}
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
</style>
