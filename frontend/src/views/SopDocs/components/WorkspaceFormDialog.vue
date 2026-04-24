<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    :title="isEdit ? '编辑工作台' : '新建工作台'"
    width="500px"
    @open="handleOpen"
  >
    <el-form label-position="top" style="margin-top:-10px;">
      <el-form-item label="名称" required>
        <el-input v-model="form.name" placeholder="例如：2026Q2 减脂营专项" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="form.workspace_type" style="width:100%;">
          <el-option label="项目" value="project" />
          <el-option label="活动" value="campaign" />
          <el-option label="客户" value="customer" />
        </el-select>
      </el-form-item>
      <el-form-item label="业务线">
        <el-input v-model="form.biz_line" placeholder="可选" />
      </el-form-item>
      <el-form-item label="客户名称">
        <el-input v-model="form.client_name" placeholder="可选" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="简短描述（可选）" />
      </el-form-item>
      <el-form-item label="起止日期">
        <div style="display:flex;gap:8px;width:100%;">
          <el-input v-model="form.start_date" placeholder="开始 如 2026-04-01" style="flex:1;" />
          <el-input v-model="form.end_date" placeholder="结束 如 2026-06-30" style="flex:1;" />
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!form.name.trim()" @click="doSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const props = defineProps<{
  modelValue: boolean
  workspace?: any
}>()
const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  saved: []
}>()

const saving = ref(false)
const isEdit = computed(() => !!props.workspace?.id)

const form = reactive({
  name: '',
  workspace_type: 'project',
  biz_line: '',
  client_name: '',
  description: '',
  start_date: '',
  end_date: '',
})

const handleOpen = () => {
  if (props.workspace?.id) {
    form.name = props.workspace.name || ''
    form.workspace_type = props.workspace.workspace_type || 'project'
    form.biz_line = props.workspace.biz_line || ''
    form.client_name = props.workspace.client_name || ''
    form.description = props.workspace.description || ''
    form.start_date = props.workspace.start_date || ''
    form.end_date = props.workspace.end_date || ''
  } else {
    form.name = ''
    form.workspace_type = 'project'
    form.biz_line = ''
    form.client_name = ''
    form.description = ''
    form.start_date = ''
    form.end_date = ''
  }
}

const doSave = async () => {
  if (!form.name.trim()) return
  saving.value = true
  try {
    if (isEdit.value) {
      await request.put(`/v1/external-docs/workspaces/${props.workspace.id}`, form)
    } else {
      await request.post('/v1/external-docs/workspaces', form)
    }
    ElMessage.success(isEdit.value ? '工作台已更新' : '工作台已创建')
    emit('update:modelValue', false)
    emit('saved')
  } catch (e: any) {
    console.error(e)
  } finally {
    saving.value = false
  }
}
</script>
