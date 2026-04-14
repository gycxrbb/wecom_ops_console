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
  storage_provider: string
  storage_status: string
  bucket_name: string
  storage_key: string
  public_url: string
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

    // 尝试客户端直传
    try {
      const prepareRes: any = await request.post('/v1/assets/prepare-upload', {
        filename: file.name,
        mime_type: file.type || 'application/octet-stream',
      })
      if (prepareRes.mode === 'qiniu' && prepareRes.upload_url && prepareRes.token) {
        // 客户端直传七牛
        const qiniuForm = new FormData()
        qiniuForm.append('token', prepareRes.token)
        qiniuForm.append('key', prepareRes.object_key)
        qiniuForm.append('file', file)
        await fetch(prepareRes.upload_url, { method: 'POST', body: qiniuForm })
        // 确认上传，创建数据库记录
        await request.post('/v1/assets/confirm-upload', {
          object_key: prepareRes.object_key,
          public_url: prepareRes.public_url,
          name: file.name,
          folder_id: folderId ?? null,
          file_size: file.size,
          mime_type: file.type || 'application/octet-stream',
        })
        if (!silent) ElMessage.success('上传成功')
        return
      }
    } catch {
      // 直传失败，回退到服务器中转
    }

    // 服务器中转上传（fallback）
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

  const renameAsset = async (id: number, name: string) => {
    await request.patch(`/v1/assets/${id}/rename`, { name })
    ElMessage.success('重命名成功')
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

  const batchDeleteAssets = async (ids: number[]) => {
    let failed = 0
    for (const id of ids) {
      try {
        await request.delete(`/v1/assets/${id}`)
      } catch {
        failed++
      }
    }
    if (failed === 0) {
      ElMessage.success(`已删除 ${ids.length} 个素材`)
    } else {
      ElMessage.warning(`${ids.length - failed} 个删除成功，${failed} 个失败`)
    }
  }

  const batchMoveAssets = async (ids: number[], folderId: number | null) => {
    let failed = 0
    for (const id of ids) {
      try {
        await request.patch(`/v1/assets/${id}/move`, { folder_id: folderId })
      } catch {
        failed++
      }
    }
    if (failed === 0) {
      ElMessage.success(`已移动 ${ids.length} 个素材`)
    } else {
      ElMessage.warning(`${ids.length - failed} 个移动成功，${failed} 个失败`)
    }
  }

  return {
    assets, loading, imageAssets, fileAssets,
    fetchAssets, uploadAsset, deleteAsset, moveAsset, renameAsset, downloadAsset,
    batchDeleteAssets, batchMoveAssets
  }
}
