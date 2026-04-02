export const IMAGE_UPLOAD_LIMIT_BYTES = 2 * 1024 * 1024
export const FILE_UPLOAD_LIMIT_BYTES = 20 * 1024 * 1024

const MB = 1024 * 1024

export const ASSET_UPLOAD_HINT = `图片不超过 ${(IMAGE_UPLOAD_LIMIT_BYTES / MB).toFixed(0)} MB，文件不超过 ${(FILE_UPLOAD_LIMIT_BYTES / MB).toFixed(0)} MB`

const isImageFile = (file: File) => (file.type || '').startsWith('image/')

export const buildAssetAuthUrl = (url?: string) => {
  if (!url) return ''
  const token = localStorage.getItem('access_token')
  if (!token) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}token=${encodeURIComponent(token)}`
}

export const buildAssetDownloadHeaders = () => {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const validateAssetUpload = (file: File, acceptType: 'image' | 'file' | 'all' = 'all') => {
  const imageFile = isImageFile(file)

  if (acceptType === 'image' && !imageFile) {
    return { valid: false, message: '当前入口只支持上传图片素材' }
  }

  if (acceptType === 'file' && imageFile) {
    return { valid: false, message: '当前入口只支持上传文件素材' }
  }

  const limit = imageFile ? IMAGE_UPLOAD_LIMIT_BYTES : FILE_UPLOAD_LIMIT_BYTES
  const limitLabel = `${(limit / MB).toFixed(0)} MB`

  if (file.size > limit) {
    return {
      valid: false,
      message: `${imageFile ? '图片' : '文件'}大小不能超过 ${limitLabel}`
    }
  }

  return { valid: true, message: '' }
}
