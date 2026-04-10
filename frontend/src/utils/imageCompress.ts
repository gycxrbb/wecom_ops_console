export interface CompressOptions {
  quality: number       // 0.0 ~ 1.0
  maxWidth?: number     // 最大宽度，超过会等比缩放
  maxHeight?: number    // 最大高度，超过会等比缩放
}

export interface CompressResult {
  blob: Blob
  width: number
  height: number
  originalSize: number
  compressedSize: number
}

const MB = 1024 * 1024

export const COMPRESS_PRESETS = [
  { label: '轻度压缩', desc: '画质几乎无损，体积减少约 40%', quality: 0.75, maxWidth: 4096, maxHeight: 4096 },
  { label: '中度压缩', desc: '画质轻微损失，体积减少约 60%', quality: 0.55, maxWidth: 2560, maxHeight: 2560 },
  { label: '重度压缩', desc: '画质明显压缩，体积减少约 80%', quality: 0.35, maxWidth: 1600, maxHeight: 1600 },
] as const

export function isCompressibleImage(file: File): boolean {
  const type = (file.type || '').toLowerCase()
  return type === 'image/jpeg' || type === 'image/png' || type === 'image/webp'
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < MB) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / MB).toFixed(1) + ' MB'
}

export function compressImage(file: File, options: CompressOptions): Promise<CompressResult> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(file)

    img.onload = () => {
      URL.revokeObjectURL(url)

      let { width, height } = img
      const maxW = options.maxWidth || Infinity
      const maxH = options.maxHeight || Infinity

      // 等比缩放
      if (width > maxW || height > maxH) {
        const ratio = Math.min(maxW / width, maxH / height)
        width = Math.round(width * ratio)
        height = Math.round(height * ratio)
      }

      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height

      const ctx = canvas.getContext('2d')
      if (!ctx) {
        reject(new Error('Canvas 不可用'))
        return
      }

      ctx.drawImage(img, 0, 0, width, height)

      // 统一输出为 JPEG（压缩率最好）
      canvas.toBlob(
        (blob) => {
          if (!blob) {
            reject(new Error('压缩失败'))
            return
          }
          resolve({
            blob,
            width,
            height,
            originalSize: file.size,
            compressedSize: blob.size,
          })
        },
        'image/jpeg',
        options.quality,
      )
    }

    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片加载失败'))
    }

    img.src = url
  })
}

/** 快速估算压缩后大小（不实际压缩） */
export function estimateCompressedSize(file: File, quality: number): number {
  // 粗略估算：JPEG quality 近似对应体积比例
  const ratio = quality * quality * 0.6 + 0.05
  return Math.round(file.size * ratio)
}
