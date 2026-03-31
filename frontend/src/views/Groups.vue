<template>
  <div class="groups-container">
    <div class="header-actions">
      <h2>群管理</h2>
      <el-button type="primary" @click="dialogVisible = true">新增群</el-button>
    </div>

    <el-table :data="groups" style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="群名称" />
      <el-table-column prop="alias" label="别名" />
      <el-table-column prop="tags" label="标签">
        <template #default="{ row }">
          <el-tag v-for="tag in row.tags.split(',')" :key="tag" v-if="row.tags" size="small" style="margin-right: 4px">
            {{ tag }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="is_enabled" label="状态">
        <template #default="{ row }">
          <el-switch v-model="row.is_enabled" @change="toggleStatus(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button type="primary" link @click="editGroup(row)">编辑</el-button>
          <el-button type="danger" link @click="deleteGroup(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Dialog stub -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑群' : '新增群'">
      <el-form label-width="120px">
        <el-form-item label="群名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="Webhook URL" v-if="!form.id">
          <el-input v-model="form.webhook_url" type="password" />
        </el-form-item>
        <!-- more fields later -->
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveGroup">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'

const groups = ref([])
const loading = ref(false)
const dialogVisible = ref(false)

const form = reactive({
  id: null,
  name: '',
  webhook_url: '',
  alias: '',
  description: '',
  tags: '',
  is_enabled: true,
  is_test: false
})

const fetchGroups = async () => {
  loading.value = true
  try {
    const res = await request.get('/v1/groups')
    groups.value = res.list || res
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const editGroup = (row: any) => {
  Object.assign(form, row)
  // Ensure webhook_url is mostly not retrievable, just leave empty initially for edit
  form.webhook_url = ''
  dialogVisible.value = true
}

const deleteGroup = (row: any) => {
  ElMessageBox.confirm('确认删除?', '警告', { type: 'warning' }).then(async () => {
    await request.delete(`/v1/groups/${row.id}`)
    ElMessage.success('删除成功')
    fetchGroups()
  })
}

const saveGroup = async () => {
  const payload = { ...form }
  try {
    if (form.id) {
       // Assuming POST or PUT to same endpoint for simplicity if there's no id path. Let's see what backend needs.
       // Actually /api/v1/groups accepts POST for create and update? Wait docs say POST /api/v1/groups Create/update group.
       await request.post('/v1/groups', payload)
    } else {
       await request.post('/v1/groups', payload)
    }
    dialogVisible.value = false
    ElMessage.success('Saved successfully')
    fetchGroups()
  } catch (e) {
    console.error(e)
  }
}

const toggleStatus = async (row: any) => {
   // In real app, might just call an API to toggle
}

onMounted(() => {
  fetchGroups()
})
</script>

<style scoped>
.groups-container {
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
