<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="登记飞书链接"
    width="540px"
    @open="handleOpen"
  >
    <!-- Step 1: URL -->
    <el-form label-width="80px" label-position="top" style="margin-top:-10px;">
      <el-form-item label="飞书链接">
        <div style="display:flex;gap:8px;">
          <el-input v-model="form.url" placeholder="粘贴飞书文档链接" @paste="onPaste" />
          <el-button type="primary" :loading="qa.resolving.value" @click="doResolve">识别链接</el-button>
        </div>
      </el-form-item>

      <template v-if="qa.resolved.value">
        <!-- Step 2: Title -->
        <el-form-item label="标题">
          <el-input v-model="form.title" placeholder="给这份文档起个容易找的名字" />
          <div v-if="qa.resolved.value.needs_manual_title" style="font-size:12px;color:var(--text-muted);margin-top:4px;">
            没能自动识别标题，请手动补一下
          </div>
        </el-form-item>

        <!-- Step 3: Workspace -->
        <el-form-item label="放到哪里">
          <el-select v-model="form.workspace_id" placeholder="选择项目、模板库或待整理" clearable style="width:100%;">
            <el-option v-for="ws in workspaceOptions" :key="ws.id" :label="ws.label" :value="ws.id" />
          </el-select>
        </el-form-item>

        <!-- Step 4: Stage -->
        <el-form-item label="当前阶段">
          <el-select v-model="form.primary_stage_term_id" placeholder="选择阶段" clearable style="width:100%;">
            <el-option v-for="t in qa.stageTerms.value" :key="t.id" :label="t.label" :value="t.id" />
          </el-select>
        </el-form-item>

        <!-- Step 4b: Deliverable Type -->
        <el-form-item label="产物类型">
          <el-select v-model="form.deliverable_term_id" placeholder="可选，如定位表、排期表、日报" clearable style="width:100%;">
            <el-option v-for="t in qa.deliverableTerms.value" :key="t.id" :label="t.label" :value="t.id" />
          </el-select>
        </el-form-item>

        <!-- Step 5: Role -->
        <el-form-item label="这份文档现在是干什么用的">
          <el-radio-group v-model="form.relation_role">
            <el-radio-button value="official">当前在用</el-radio-button>
            <el-radio-button value="support">参考资料</el-radio-button>
            <el-radio-button value="candidate">备选方案</el-radio-button>
          </el-radio-group>
          <div v-if="form.relation_role === 'official'" style="font-size:12px;color:#b45309;margin-top:4px;">
            “当前在用”表示这个阶段大家现在应优先打开这一份
          </div>
          <div v-else-if="selectedWorkspace?.workspace_type === 'template_hub'" style="font-size:12px;color:var(--text-muted);margin-top:4px;">
            你正在把这份文档沉淀到模板库，后续其他项目可以复用
          </div>
        </el-form-item>

        <!-- Step 6: Summary & Remark -->
        <el-form-item label="这份文档主要写什么">
          <el-input v-model="form.summary" type="textarea" :rows="2" placeholder="可选，帮助大家点开前先判断是不是要找的内容" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" placeholder="可选，比如“开营前统一用这版”" />
        </el-form-item>
      </template>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button
        v-if="qa.resolved.value"
        type="primary"
        :loading="qa.saving.value"
        :disabled="!form.title"
        @click="doSave(false)"
      >仅保存</el-button>
      <el-button
        v-if="qa.resolved.value"
        type="success"
        :loading="qa.saving.value"
        :disabled="!form.title"
        @click="doSave(true)"
      >保存并打开</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useQuickAdd } from '../composables/useQuickAdd'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  success: []
}>()

const qa = useQuickAdd()

const form = reactive({
  url: '',
  title: '',
  workspace_id: null as number | null,
  primary_stage_term_id: null as number | null,
  deliverable_term_id: null as number | null,
  relation_role: 'support',
  summary: '',
  remark: '',
  open_after_save: false,
})

const workspaceOptions = computed(() => qa.workspaces.value.map((ws) => {
  const typeLabelMap: Record<string, string> = {
    project: '项目',
    campaign: '活动',
    customer: '客户',
    template_hub: '模板库',
    inbox: '待整理',
  }
  const extraHintMap: Record<string, string> = {
    template_hub: '沉淀可复用内容',
    inbox: '先放这里，后续再归类',
  }
  const typeLabel = typeLabelMap[ws.workspace_type] || ws.workspace_type
  const extraHint = extraHintMap[ws.workspace_type]
  return {
    ...ws,
    label: extraHint ? `${ws.name}（${typeLabel}，${extraHint}）` : `${ws.name}（${typeLabel}）`,
  }
}))

const selectedWorkspace = computed(() =>
  qa.workspaces.value.find((ws) => ws.id === form.workspace_id) || null,
)

const handleOpen = () => {
  qa.reset()
  qa.fetchOptions()
  form.url = ''
  form.title = ''
  form.workspace_id = null
  form.primary_stage_term_id = null
  form.relation_role = 'support'
  form.summary = ''
  form.remark = ''
}

const onPaste = (e: ClipboardEvent) => {
  const text = e.clipboardData?.getData('text') || ''
  if (text.includes('feishu.cn') || text.includes('larksuite.com')) {
    form.url = text
    setTimeout(() => doResolve(), 100)
  }
}

const doResolve = async () => {
  if (!form.url.trim()) return
  await qa.resolveLink(form.url)
  if (qa.resolved.value?.ok) {
    if (!qa.resolved.value.needs_manual_title && qa.resolved.value.title_hint) {
      form.title = qa.resolved.value.title_hint
    }
  } else {
    ElMessage.warning(qa.resolved.value?.warnings?.[0] || '无法解析该链接')
  }
}

const doSave = async (openAfter: boolean) => {
  if (!form.title.trim()) {
    ElMessage.warning('请输入文档标题')
    return
  }
  form.open_after_save = openAfter
  try {
    const result = await qa.save(form)
    ElMessage.success('文档登记成功')
    if (openAfter && result?.open_url) {
      window.open(result.open_url, '_blank')
    }
    emit('update:modelValue', false)
    emit('success')
  } catch (e: any) {
    console.error(e)
  }
}
</script>
