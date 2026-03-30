<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">用户管理</h1>
      <el-button type="primary" @click="handleCreate">
        <el-icon><Plus /></el-icon> 新增用户
      </el-button>
    </div>

    <el-card shadow="never" class="table-card">
      <el-table :data="users" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="display_name" label="显示名称" />
        <el-table-column prop="role" label="角色">
          <template #default="scope">
            <el-tag :type="scope.row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ scope.row.role.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'info'" size="small">
              {{ scope.row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="handleEdit(scope.row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingUser?.id ? '编辑用户' : '新增用户'"
      width="480px"
      append-to-body
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入系统登录名" :disabled="!!editingUser?.id" />
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="form.display_name" placeholder="请输入显示名称" />
        </el-form-item>
        <el-form-item label="密码" prop="password" :rules="editingUser?.id ? [] : { required: true, message: '必填', trigger: 'blur' }">
          <el-input v-model="form.password" type="password" placeholder="留空则不修改密码" show-password />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width: 100%">
            <el-option label="Admin" value="admin" />
            <el-option label="Coach" value="coach" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveUser" :loading="saving">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const users = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingUser = ref<any>(null)
const formRef = ref()

const form = ref({
  id: '',
  username: '',
  display_name: '',
  password: '',
  role: 'coach',
  is_active: true
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }]
}

const fetchUsers = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/users')
    users.value = res
  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  editingUser.value = null
  form.value = {
    id: '',
    username: '',
    display_name: '',
    password: '',
    role: 'coach',
    is_active: true
  }
  dialogVisible.value = true
}

const handleEdit = (row: any) => {
  editingUser.value = row
  form.value = {
    id: row.id,
    username: row.username,
    display_name: row.display_name,
    password: '',
    role: row.role,
    is_active: row.is_active
  }
  dialogVisible.value = true
}

const saveUser = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    saving.value = true
    try {
      await request.post('/v1/users', form.value)
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchUsers()
    } catch (error) {
      console.error(error)
    } finally {
      saving.value = false
    }
  })
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.page-container {
  max-width: 1200px;
  margin: 0 auto;
}
.table-card {
  border-radius: 12px;
}
</style>
