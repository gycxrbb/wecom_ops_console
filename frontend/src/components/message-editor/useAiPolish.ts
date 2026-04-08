import { ref } from 'vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

export function useAiPolish() {
  const aiDialogVisible = ref(false)
  const aiInstruction = ref('')
  const aiLoading = ref(false)

  const openAiDialog = () => {
    aiInstruction.value = ''
    aiDialogVisible.value = true
  }

  const doPolish = async (currentContent: string, msgType: string): Promise<string | null> => {
    if (!aiInstruction.value.trim() && !currentContent.trim()) {
      ElMessage.warning('请输入修改指令')
      return null
    }
    aiLoading.value = true
    try {
      const res: any = await request.post('/v1/ai/polish', {
        content: currentContent,
        instruction: aiInstruction.value || '润色优化这段文字',
        msg_type: msgType,
      })
      aiDialogVisible.value = false
      aiInstruction.value = ''
      return res.content || ''
    } catch (e: any) {
      ElMessage.error('AI 润色失败: ' + (e?.message || String(e)))
      return null
    } finally {
      aiLoading.value = false
    }
  }

  return { aiDialogVisible, aiInstruction, aiLoading, openAiDialog, doPolish }
}
