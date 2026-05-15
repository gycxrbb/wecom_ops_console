import request from '#/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'

export function useAiSessionAdmin() {
  const renameSession = async (customerId: number, sessionId: string, title: string): Promise<boolean> => {
    try {
      await request.patch(`/v1/crm-customers/${customerId}/ai/sessions/${sessionId}`, { title })
      return true
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '重命名失败')
      return false
    }
  }

  const togglePin = async (customerId: number, sessionId: string, pinned: boolean): Promise<boolean> => {
    try {
      await request.patch(`/v1/crm-customers/${customerId}/ai/sessions/${sessionId}`, { is_pinned: pinned })
      return true
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '操作失败')
      return false
    }
  }

  const deleteSession = async (customerId: number, sessionId: string): Promise<boolean> => {
    try {
      await ElMessageBox.confirm('删除后将无法恢复该对话记录，确认删除？', '删除对话', {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return false
    }
    try {
      await request.delete(`/v1/crm-customers/${customerId}/ai/sessions/${sessionId}`)
      return true
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '删除失败')
      return false
    }
  }

  const regenerateAutoTitle = async (customerId: number, sessionId: string): Promise<string | null> => {
    try {
      const res: any = await request.post(`/v1/crm-customers/${customerId}/ai/sessions/${sessionId}/auto-title`)
      return res.auto_title || null
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '生成标题失败')
      return null
    }
  }

  return { renameSession, togglePin, deleteSession, regenerateAutoTitle }
}
