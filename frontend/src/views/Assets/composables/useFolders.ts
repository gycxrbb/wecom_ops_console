import { ref } from 'vue'
import request from '#/utils/request'
import { ElMessage } from 'element-plus'

export interface Folder {
  id: number
  name: string
  sort_order: number
  parent_id: number | null
  is_system?: boolean
  asset_count: number
  child_count: number
  created_at: string
}

const folders = ref<Folder[]>([])
const loading = ref(false)

export function useFolders() {
  const fetchFolders = async () => {
    loading.value = true
    try {
      const res: any = await request.get('/v1/asset-folders')
      folders.value = res
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  const createFolder = async (name: string, parentId: number | null = null) => {
    try {
      await request.post('/v1/asset-folders', { name, parent_id: parentId })
      ElMessage.success('文件夹创建成功')
      await fetchFolders()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '创建失败')
    }
  }

  const renameFolder = async (id: number, name: string) => {
    try {
      await request.put(`/v1/asset-folders/${id}`, { name })
      ElMessage.success('重命名成功')
      await fetchFolders()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '重命名失败')
    }
  }

  const deleteFolder = async (id: number) => {
    try {
      await request.delete(`/v1/asset-folders/${id}`)
      ElMessage.success('文件夹已删除')
      await fetchFolders()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '删除失败')
    }
  }

  const moveFolder = async (id: number, parentId: number | null) => {
    try {
      await request.patch(`/v1/asset-folders/${id}/move`, { parent_id: parentId })
      ElMessage.success('文件夹已移动')
      await fetchFolders()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '移动失败')
    }
  }

  return { folders, loading, fetchFolders, createFolder, renameFolder, deleteFolder, moveFolder }
}
