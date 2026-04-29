<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="RAG 语义标注"
    width="560px"
    :close-on-click-modal="false"
  >
    <el-form label-width="90px" label-position="top" class="rag-form">
      <el-form-item label="摘要">
        <el-input v-model="form.summary" type="textarea" :rows="2" placeholder="一句话描述素材内容" />
      </el-form-item>
      <el-form-item v-if="isImage" label="图片说明">
        <el-input v-model="form.alt_text" type="textarea" :rows="2" placeholder="描述图片内容，用于检索匹配" />
      </el-form-item>
      <el-form-item v-else-if="isVideo" label="视频转写">
        <el-input v-model="form.transcript" type="textarea" :rows="2" placeholder="视频内容摘要或转写文本" />
      </el-form-item>
      <el-form-item label="使用场景">
        <el-input v-model="form.usage_note" type="textarea" :rows="2" placeholder="什么时候用这个素材" />
      </el-form-item>
      <el-form-item label="适用目标">
        <div class="tag-field">
          <el-select v-model="form.customer_goal" multiple filterable placeholder="选择目标" class="tag-field__select">
            <el-option v-for="g in tagOptions('customer_goal')" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
          <el-button link type="primary" @click="openCreateTag('customer_goal', '适用目标')">+</el-button>
        </div>
      </el-form-item>
      <el-form-item label="干预场景">
        <div class="tag-field">
          <el-select v-model="form.intervention_scene" multiple filterable placeholder="选择场景" class="tag-field__select">
            <el-option v-for="s in tagOptions('intervention_scene')" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <el-button link type="primary" @click="openCreateTag('intervention_scene', '干预场景')">+</el-button>
        </div>
      </el-form-item>
      <el-form-item label="问题类型">
        <div class="tag-field">
          <el-select v-model="form.question_type" multiple filterable placeholder="选择类型" class="tag-field__select">
            <el-option v-for="t in tagOptions('question_type')" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
          <el-button link type="primary" @click="openCreateTag('question_type', '问题类型')">+</el-button>
        </div>
      </el-form-item>
      <div class="rag-form-row">
        <el-form-item label="可见范围" class="rag-form-item--half">
          <el-radio-group v-model="form.visibility">
            <el-radio v-for="v in tagOptions('visibility')" :key="v.value" :value="v.value">{{ v.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="安全等级" class="rag-form-item--half">
          <el-radio-group v-model="form.safety_level">
            <el-radio v-for="s in tagOptions('safety_level')" :key="s.value" :value="s.value">{{ s.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
      </div>
      <div class="rag-form-row">
        <el-form-item label="版权" class="rag-form-item--half">
          <el-select v-model="form.copyright_status">
            <el-option label="自有" value="owned" />
            <el-option label="已授权" value="licensed" />
            <el-option label="未知" value="unknown" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用 RAG" class="rag-form-item--half">
          <el-switch v-model="form.rag_enabled" />
        </el-form-item>
      </div>
    </el-form>
    <template #footer>
      <el-button @click="handleSkip">跳过</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="createTagVisible" :title="'新增' + createTagLabel" width="360px" append-to-body>
    <el-form label-width="70px">
      <el-form-item label="编码">
        <el-input v-model="newTagCode" placeholder="英文，如 new_goal" />
      </el-form-item>
      <el-form-item label="名称">
        <el-input v-model="newTagName" placeholder="中文名称" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createTagVisible = false">取消</el-button>
      <el-button type="primary" :loading="creating" @click="handleCreateTag">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'
import { useRagTags } from '#/composables/useRagTags'

const props = defineProps<{
  modelValue: boolean
  assetId: number | null
  assetName: string
  materialType?: string
  initialMeta?: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'saved'): void
}>()

const { options: tagOptions, createTag } = useRagTags()

const isImage = computed(() => props.materialType === 'image')
const isVideo = computed(() => props.materialType === 'file' && (props.assetName || '').match(/\.(mp4|mov|avi|mkv)$/i))

const defaultForm = () => ({
  summary: '',
  alt_text: '',
  transcript: '',
  usage_note: '',
  customer_goal: [] as string[],
  intervention_scene: [] as string[],
  question_type: [] as string[],
  visibility: 'coach_internal',
  safety_level: 'general',
  copyright_status: 'owned',
  customer_sendable: false,
  rag_enabled: true,
})

const form = reactive(defaultForm())
const saving = ref(false)

watch(() => props.modelValue, (val) => {
  if (val) {
    const meta = props.initialMeta || {}
    Object.assign(form, {
      ...defaultForm(),
      ...meta,
      customer_goal: meta.customer_goal || [],
      intervention_scene: meta.intervention_scene || [],
      question_type: meta.question_type || [],
    })
  }
})

// Inline tag creation
const createTagVisible = ref(false)
const createTagDimension = ref('')
const createTagLabel = ref('')
const newTagCode = ref('')
const newTagName = ref('')
const creating = ref(false)

function openCreateTag(dimension: string, label: string) {
  createTagDimension.value = dimension
  createTagLabel.value = label
  newTagCode.value = ''
  newTagName.value = ''
  createTagVisible.value = true
}

async function handleCreateTag() {
  const code = newTagCode.value.trim().toLowerCase().replace(/[\s-]+/g, '_')
  const name = newTagName.value.trim()
  if (!code || !name) {
    ElMessage.warning('编码和名称不能为空')
    return
  }
  creating.value = true
  try {
    await createTag(createTagDimension.value, code, name)
    ElMessage.success('标签已创建')
    createTagVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

const handleSkip = () => {
  emit('update:modelValue', false)
}

const handleSave = async () => {
  if (!props.assetId) return
  saving.value = true
  try {
    await request.patch(`/v1/assets/${props.assetId}/rag-meta`, { ...form })
    ElMessage.success('RAG 标注已保存')
    emit('update:modelValue', false)
    emit('saved')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.rag-form { max-height: 65vh; overflow-y: auto; padding-right: 8px; }
.rag-form-row { display: flex; gap: 16px; }
.rag-form-item--half { flex: 1; }
.tag-field { display: flex; align-items: center; gap: 4px; width: 100%; }
.tag-field__select { flex: 1; }
</style>
