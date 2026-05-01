<template>
  <el-dialog
    v-model="visible"
    title="反馈：这条回复哪里不好？"
    width="520px"
    :close-on-click-modal="false"
    @close="resetForm"
  >
    <div class="feedback-summaries">
      <div class="feedback-summary-item">
        <span class="feedback-summary-label">你的问题</span>
        <p class="feedback-summary-text line-clamp-3">{{ truncate(userQuestion, 300) }}</p>
      </div>
      <div class="feedback-summary-item">
        <span class="feedback-summary-label">AI 回复</span>
        <p class="feedback-summary-text line-clamp-5">{{ truncate(aiAnswer, 600) }}</p>
      </div>
    </div>

    <el-form label-position="top" class="feedback-form">
      <el-form-item label="不满意原因" required>
        <el-select v-model="form.reason_category" placeholder="请选择原因" style="width: 100%">
          <el-option v-for="opt in reasonOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="具体说明" required>
        <el-input v-model="form.reason_text" type="textarea" :rows="3" placeholder="请描述具体问题" maxlength="500" show-word-limit />
      </el-form-item>
      <el-form-item label="更好的答复应该是什么样" required>
        <el-input v-model="form.expected_answer" type="textarea" :rows="3" placeholder="请描述你期望的回答" maxlength="1000" show-word-limit />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="danger" :loading="submitting" :disabled="!canSubmit" @click="handleSubmit">
        提交反馈
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  userQuestion: string
  aiAnswer: string
}>()

const emit = defineEmits<{
  submit: [data: { reason_category: string; reason_text: string; expected_answer: string }]
}>()

const visible = ref(false)
const submitting = ref(false)
const customerId = ref(0)
const messageId = ref('')

const form = reactive({
  reason_category: '',
  reason_text: '',
  expected_answer: '',
})

const reasonOptions = [
  { value: 'fact_wrong', label: '事实不准' },
  { value: 'speech_bad', label: '话术不好用' },
  { value: 'too_vague', label: '太空泛' },
  { value: 'not_warm', label: '不够温和' },
  { value: 'medical_boundary', label: '医疗边界不稳' },
  { value: 'no_customer_data', label: '没结合客户数据' },
  { value: 'format_wrong', label: '输出格式不对' },
  { value: 'other', label: '其他' },
]

const canSubmit = computed(() =>
  form.reason_category && form.reason_text.trim() && form.expected_answer.trim()
)

function truncate(text: string, limit: number) {
  if (!text) return ''
  return text.length > limit ? text.slice(0, limit) + '...' : text
}

function resetForm() {
  form.reason_category = ''
  form.reason_text = ''
  form.expected_answer = ''
}

function open(cId: number, mId: string) {
  customerId.value = cId
  messageId.value = mId
  resetForm()
  visible.value = true
}

async function handleSubmit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    emit('submit', {
      reason_category: form.reason_category,
      reason_text: form.reason_text.trim(),
      expected_answer: form.expected_answer.trim(),
    })
    visible.value = false
  } finally {
    submitting.value = false
  }
}

defineExpose({ open })
</script>

<style scoped>
.feedback-summaries { margin-bottom: 16px; display: flex; flex-direction: column; gap: 8px; }
.feedback-summary-item { padding: 8px 12px; background: #f9fafb; border-radius: 8px; }
:global(html.dark) .feedback-summary-item { background: rgba(255,255,255,0.06); }
.feedback-summary-label { font-size: 11px; color: #9ca3af; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
.feedback-summary-text { margin: 4px 0 0; font-size: 13px; color: #374151; line-height: 1.5; white-space: pre-wrap; }
.line-clamp-3 { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; text-overflow: ellipsis; }
.line-clamp-5 { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 5; overflow: hidden; text-overflow: ellipsis; }
:global(html.dark) .feedback-summary-text { color: #d1d5db; }
.feedback-form { margin-top: 4px; }
</style>
