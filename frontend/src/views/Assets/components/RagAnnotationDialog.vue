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
        <el-select v-model="form.customer_goal" multiple filterable placeholder="选择目标">
          <el-option v-for="g in goalOptions" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="干预场景">
        <el-select v-model="form.intervention_scene" multiple placeholder="选择场景">
          <el-option v-for="s in sceneOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="问题类型">
        <el-select v-model="form.question_type" multiple filterable allow-create default-first-option placeholder="选择或输入">
          <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <div class="rag-form-row">
        <el-form-item label="可见范围" class="rag-form-item--half">
          <el-radio-group v-model="form.visibility">
            <el-radio value="coach_internal">仅教练</el-radio>
            <el-radio value="customer_visible">可发客户</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="安全等级" class="rag-form-item--half">
          <el-radio-group v-model="form.safety_level">
            <el-radio value="general">通用</el-radio>
            <el-radio value="nutrition_education">营养科普</el-radio>
            <el-radio value="medical_sensitive">医疗敏感</el-radio>
            <el-radio value="doctor_review">需医生审核</el-radio>
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
</template>

<script setup lang="ts">
import { reactive, ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

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

const goalOptions = [
  { value: 'weight_loss', label: '减脂减重' },
  { value: 'glucose_control', label: '控糖' },
  { value: 'habit_building', label: '习惯养成' },
  { value: 'nutrition_education', label: '饮食营养教育' },
  { value: 'exercise_adherence', label: '运动坚持' },
  { value: 'emotion_support', label: '情绪支持' },
  { value: 'device_usage', label: '设备使用' },
  { value: 'maintenance', label: '长期维护' },
]
const sceneOptions = [
  { value: 'meal_checkin', label: '餐盘打卡' },
  { value: 'meal_review', label: '餐评' },
  { value: 'obstacle_breaking', label: '破障' },
  { value: 'qa_support', label: '问题答疑' },
  { value: 'period_review', label: '周月复盘' },
  { value: 'emotional_support', label: '情绪支持' },
  { value: 'maintenance', label: '长期维护' },
  { value: 'abnormal_intervention', label: '异常干预' },
]
const typeOptions = ['dining_out', 'carb_choose', 'low_calorie', 'late_night_snack', 'craving', 'hunger', 'food_safety', 'high_glucose', 'blood_fluctuation', 'data_monitoring', 'no_checkin', 'low_motivation', 'device_usage', 'plateau']

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
</style>
