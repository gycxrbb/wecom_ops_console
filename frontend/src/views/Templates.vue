<template>
  <div class="view-container">
    <div class="header-actions">
      <h2>模板中心</h2>
      <el-button type="primary" @click="dialogVisible = true">新增模板</el-button>
    </div>

    <el-table :data="templates" style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="模板名称" />
      <el-table-column prop="msg_type" label="消息类型" />
      <el-table-column prop="category" label="分类" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button type="primary" link @click="editTemplate(row)">编辑</el-button>
          <el-button type="primary" link @click="cloneTemplate(row)">克隆</el-button>
          <el-button type="danger" link @click="deleteTemplate(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑模板' : '新增模板'" width="60%">
      <el-form label-width="100px" :model="form">
        <el-form-item label="模板名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="分类"><el-input v-model="form.category" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="消息类型">
          <el-select v-model="form.msg_type">
            <el-option label="Text" value="text"></el-option>
            <el-option label="Markdown" value="markdown"></el-option>
            <el-option label="Image" value="image"></el-option>
            <el-option label="News" value="news"></el-option>
            <el-option label="File" value="file"></el-option>
            <el-option label="Template Card" value="template_card"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="内容(JSON)">
          <el-input type="textarea" :rows="6" v-model="form.content" />
        </el-form-item>
        <el-form-item label="变量示例">
          <el-input type="textarea" :rows="3" v-model="form.variables_schema" />
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

const templates = ref([])
const loading = ref(false)
const dialogVisible = ref(false)

const form = reactive({
  id: null,
  name: '',
  description: '',
  msg_type: 'text',
  category: 'default',
  content: '',
  variables_schema: '{}'
})

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

const editTemplate = (row: any) => {
  Object.assign(form, row)
  dialogVisible.value = true
}

const cloneTemplate = async (row: any) => {
  try {
    await request.post(/v1/templates/\/clone)
    ElMessage.success('Cloned')
    fetchTemplates()
  } catch (e) { console.error(e) }
}

const deleteTemplate = (row: any) => {
  ElMessageBox.confirm('Confirm delete?', 'Warning', { type: 'warning' }).then(async () => {
    await request.delete(/v1/templates/\)
    ElMessage.success('Deleted')
    fetchTemplates()
  })
}

const saveTemplate = async () => {
  try {
    await request.post('/v1/templates', form)
    dialogVisible.value = false
    ElMessage.success('Saved')
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
  background: #fff;
  border-radius: 4px;
}
.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
</style>
