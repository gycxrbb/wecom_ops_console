import { ref, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { validateAssetUpload, buildAssetDownloadHeaders } from '@/utils/assets'

export interface Asset {
  id: number
  name: string
  material_type: string
  mime_type: string
  file_size: number
  folder_id: number | null
  url: string
  preview_url: string
  download_url: string
  created_at: string
}

const assets = ref<Asset[]>([])
const loading = ref(false)

const isImage = (item: Asset) => item.material_type === 'image' || (item.mime_type || '').startsWith('image/')
const imageAssets = computed(() => assets.value.filter(isImage))
const fileAssets = computed(() => assets.value.filter(item => !isImage(item)))

export function useAssets() {
  const fetchAssets = async (folderId?: string | null) => {
    loading.value = true
    try {
      const params: any = {}
      if (folderId && folderId !== 'all') params.folder_id = folderId
      const res: any = await request.get('/v1/assets', { params })
      assets.value = res
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  }

  const uploadAsset = async (file: File, folderId?: number | null, silent = false) => {
    const validation = validateAssetUpload(file, 'all')
    if (!validation.valid) {
      if (!silent) ElMessage.warning(validation.message)
      throw new Error(validation.message)
    }
    const formData = new FormData()
    formData.append('file', file)
    if (folderId != null) formData.append('folder_id', String(folderId))
    await request.post('/v1/assets', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    if (!silent) ElMessage.success('上传成功')
  }

  const deleteAsset = async (id: number) => {
    await request.delete(`/v1/assets/${id}`)
    ElMessage.success('删除成功')
  }

  const moveAsset = async (assetId: number, folderId: number | null) => {
    await request.patch(`/v1/assets/${assetId}/move`, { folder_id: folderId })
    ElMessage.success('移动成功')
  }

  const downloadAsset = async (row: Asset) => {
    const targetUrl = row.download_url || row.url
    const response = await axios.get(targetUrl, {
      responseType: 'blob',
      headers: buildAssetDownloadHeaders()
    })
    const downloadUrl = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = row.name || 'asset'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(downloadUrl)
  }

  return {
    assets, loading, imageAssets, fileAssets,
    fetchAssets, uploadAsset, deleteAsset, moveAsset, downloadAsset
  }
}
