<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="修改文档绑定"
    width="460px"
    @open="initForm"
  >
    <el-form label-position="top" style="margin-top:-10px;">
      <el-form-item label="文档角色">
        <el-radio-group v-model="form.relation_role">
          <el-radio-button value="official">当前在用</el-radio-button>
          <el-radio-button value="support">参考资料</el-radio-button>
          <el-radio-button value="candidate">备选方案</el-radio-button>
          <el-radio-button value="archive">历史归档</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="所属阶段">
        <el-select v-model="form.primary_stage_term_id" placeholder="选择阶段" clearable style="width:100%;">
          <el-option v-for="t in stageTerms" :key="t.id" :label="t.label" :value="t.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="产物类型">
        <el-select v-model="form.deliverable_term_id" placeholder="可选" clearable style="width:100%;">
          <el-option v-for="t in deliverableTerms" :key="t.id" :label="t.label" :value="t.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="form.remark" placeholder="可选" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const props = defineProps<{
  modelValue: boolean
  binding: any
  stageTerms: any[]
  deliverableTerms: any[]
}>()
const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  saved: []
}>()

const saving = ref(false)
const form = reactive({
  relation_role: 'support',
  primary_stage_term_id: null as number | null,
  deliverable_term_id: null as number | null,
  remark: '',
})

const initForm = () => {
  if (props.binding) {
    form.relation_role = props.binding.relation_role || 'support'
    form.primary_stage_term_id = props.binding.primary_stage_term_id || null
    form.deliverable_term_id = props.binding.deliverable_term_id || null
    form.remark = props.binding.remark || ''
  }
}

const doSave = async () => {
  if (!props.binding?.binding_id) return
  saving.value = true
  try {
    await request.put(`/v1/external-docs/bindings/${props.binding.binding_id}`, {
      relation_role: form.relation_role,
      primary_stage_term_id: form.primary_stage_term_id,
      deliverable_term_id: form.deliverable_term_id,
      remark: form.remark,
    })
    ElMessage.success('已更新')
    emit('update:modelValue', false)
    emit('saved')
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}
</script>
