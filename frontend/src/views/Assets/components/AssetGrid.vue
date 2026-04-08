<template>
  <div class="asset-grid-container">
    <!-- Image Section -->
    <div class="section-card">
      <div class="section-header">
        <div>
          <h3>图片素材</h3>
          <p>按缩略图浏览，适合快速挑选要发送的图片。</p>
        </div>
        <span class="section-count">{{ imageAssets.length }} 项</span>
      </div>
      <el-empty v-if="imageAssets.length === 0" description="暂无图片素材" :image-size="60" />
      <div v-else class="image-grid">
        <div v-for="item in imageAssets" :key="item.id" class="image-card">
          <div class="image-frame" @click="openPreview(item)">
            <el-image
              :src="buildAssetAuthUrl(item.preview_url || item.url)"
              :preview-src-list="[]"
              fit="cover"
              class="image-thumb"
            />
          </div>
          <div class="asset-row">
            <div class="image-name" :title="item.name">{{ item.name }}</div>
            <el-tag size="small" :type="statusTagType(item.storage_status)">{{ statusLabel(item.storage_status) }}</el-tag>
          </div>
          <div class="image-meta">{{ formatSize(item.file_size) }} · {{ formatDate(item.created_at) }}</div>
          <div class="image-actions">
            <el-button size="small" link type="primary" @click="handleDownload(item)" :disabled="isUnavailable(item)">
              <el-icon><Download /></el-icon> 下载
            </el-button>
            <el-button size="small" link @click="handleCopyUrl(item)" :disabled="!item.public_url || isUnavailable(item)">
              <el-icon><Link /></el-icon> 地址
            </el-button>
            <el-button size="small" link type="warning" @click="handleMove(item)">
              <el-icon><Rank /></el-icon> 移动
            </el-button>
            <el-popconfirm title="确定要删除该素材吗？删除后不可恢复。" @confirm="handleDelete(item)" :disabled="props.deletingIds?.has(item.id)">
              <template #reference>
                <el-button size="small" link type="danger" :loading="props.deletingIds?.has(item.id)">
                  <el-icon><Delete /></el-icon> 删除
                </el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </div>

    <!-- File Section -->
    <div class="section-card">
      <div class="section-header">
        <div>
          <h3>文件素材</h3>
          <p>按列表管理，清楚查看文件名、类型、大小和上传时间。</p>
        </div>
        <span class="section-count">{{ fileAssets.length }} 项</span>
      </div>
      <el-empty v-if="fileAssets.length === 0" description="暂无文件素材" :image-size="60" />
      <el-table v-else :data="fileAssets" style="width: 100%">
        <el-table-column label="文件名" min-width="220" show-overflow-tooltip>
          <template #default="scope">
            <span class="file-name-link" @click="openPreview(scope.row)">{{ scope.row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="scope">
            <el-tag size="small" :type="statusTagType(scope.row.storage_status)">{{ statusLabel(scope.row.storage_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="mime_type" label="类型" width="160" />
        <el-table-column label="大小" width="100">
          <template #default="scope">{{ formatSize(scope.row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="上传时间" width="170">
          <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="scope">
            <div class="file-action-group">
              <el-button link type="primary" :disabled="isUnavailable(scope.row)" @click="handleDownload(scope.row)">下载</el-button>
              <el-button link :disabled="!scope.row.public_url || isUnavailable(scope.row)" @click="handleCopyUrl(scope.row)">复制地址</el-button>
              <el-button link type="warning" @click="handleMove(scope.row)">移动</el-button>
              <el-popconfirm title="确定要删除该素材吗？删除后不可恢复。" @confirm="handleDelete(scope.row)" :disabled="props.deletingIds?.has(scope.row.id)">
                <template #reference>
                  <el-button link type="danger" :loading="props.deletingIds?.has(scope.row.id)">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Move Dialog -->
    <el-dialog v-model="moveDialogVisible" title="移动到文件夹" width="400px">
      <div class="move-folder-list">
        <div
          class="move-item"
          :class="{ 'is-selected': moveTargetId === null }"
          @click="moveTargetId = null"
        >
          <el-icon><FolderOpened /></el-icon>
          <span>未分类</span>
        </div>
        <div
          v-for="folder in flattenedFolders"
          :key="folder.id"
          class="move-item"
          :class="{ 'is-selected': moveTargetId === folder.id }"
          @click="moveTargetId = folder.id"
          :style="{ paddingLeft: `${14 + folder.depth * 18}px` }"
        >
          <el-icon><FolderIcon /></el-icon>
          <span>{{ folder.name }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="moveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmMove">确定移动</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewDialogVisible" title="素材预览" width="720px">
      <template v-if="previewAsset">
        <div class="preview-panel">
          <div class="preview-panel__media">
            <el-image
              v-if="isImageAsset(previewAsset)"
              :src="buildAssetAuthUrl(previewAsset.preview_url || previewAsset.public_url || previewAsset.url)"
              fit="contain"
              class="preview-image"
            />
            <video
              v-else-if="isVideoAsset(previewAsset)"
              :src="buildAssetAuthUrl(previewAsset.public_url || previewAsset.url)"
              class="preview-video"
              controls
            />
            <div v-else class="preview-fallback">
              <el-icon :size="32"><Document /></el-icon>
              <p>该素材暂不支持内嵌预览，可复制公网地址或直接下载查看。</p>
            </div>
          </div>
          <div class="preview-panel__meta">
            <div class="preview-title">{{ previewAsset.name }}</div>
            <div class="preview-meta">类型：{{ previewAsset.mime_type || previewAsset.material_type }}</div>
            <div class="preview-meta">大小：{{ formatSize(previewAsset.file_size) }}</div>
            <div class="preview-meta">上传时间：{{ formatDate(previewAsset.created_at) }}</div>
            <div class="preview-meta">存储位置：{{ previewAsset.storage_provider || 'local' }}</div>
            <div class="preview-meta">
              状态：
              <el-tag size="small" :type="statusTagType(previewAsset.storage_status)">{{ statusLabel(previewAsset.storage_status) }}</el-tag>
            </div>
            <div class="preview-url-label">公网地址</div>
            <div class="preview-url">{{ previewAsset.public_url || '暂无公网地址' }}</div>
            <div class="preview-actions">
              <el-button :disabled="!previewAsset.public_url" @click="handleCopyUrl(previewAsset)">复制地址</el-button>
              <el-button :disabled="!previewAsset.public_url" @click="openPublicUrl(previewAsset)">打开地址</el-button>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Delete, Rank, FolderOpened, Link, Document } from '@element-plus/icons-vue'
import { Folder as FolderIcon } from '@element-plus/icons-vue'
import { buildAssetAuthUrl, copyAssetPublicUrl, formatAssetDateTime } from '@/utils/assets'
import type { Asset } from '../composables/useAssets'
import type { Folder } from '../composables/useFolders'

const props = defineProps<{
  imageAssets: Asset[]
  fileAssets: Asset[]
  folders: Folder[]
  deletingIds?: Set<number>
}>()

const emit = defineEmits(['download', 'delete', 'move'])

const moveDialogVisible = ref(false)
const moveTargetId = ref<number | null>(null)
const moveAssetId = ref<number | null>(null)
const previewDialogVisible = ref(false)
const previewAsset = ref<Asset | null>(null)

const flattenedFolders = computed(() => {
  const map = new Map<number | null, Folder[]>()
  for (const folder of props.folders) {
    const key = folder.parent_id ?? null
    const list = map.get(key) || []
    list.push(folder)
    map.set(key, list)
  }

  const result: Array<Folder & { depth: number }> = []
  const walk = (parentId: number | null, depth: number) => {
    const children = map.get(parentId) || []
    for (const folder of children) {
      result.push({ ...folder, depth })
      walk(folder.id, depth + 1)
    }
  }

  walk(null, 0)
  return result
})

const handleDownload = (item: Asset) => emit('download', item)
const handleDelete = (item: Asset) => emit('delete', item)
const openPreview = (item: Asset) => {
  previewAsset.value = item
  previewDialogVisible.value = true
}

const openPublicUrl = (item: Asset) => {
  if (!item.public_url) {
    ElMessage.warning('当前素材还没有可用的公网地址')
    return
  }
  window.open(item.public_url, '_blank', 'noopener')
}

const handleCopyUrl = async (item: Asset) => {
  try {
    await copyAssetPublicUrl(item.public_url)
    ElMessage.success('公网地址已复制')
  } catch (error: any) {
    ElMessage.warning(error?.message || '复制失败')
  }
}

const handleMove = (item: Asset) => {
  moveAssetId.value = item.id
  moveTargetId.value = item.folder_id
  moveDialogVisible.value = true
}

const confirmMove = () => {
  if (moveAssetId.value != null) {
    emit('move', moveAssetId.value, moveTargetId.value)
  }
  moveDialogVisible.value = false
}

const formatSize = (bytes: number) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateStr: string) => {
  return formatAssetDateTime(dateStr)
}

const statusLabel = (status?: string) => {
  if (status === 'source_missing') return '源文件缺失'
  if (status === 'deleted') return '已删除'
  return '正常'
}

const statusTagType = (status?: string) => {
  if (status === 'source_missing') return 'danger'
  if (status === 'deleted') return 'info'
  return 'success'
}

const isImageAsset = (item: Asset) => item.material_type === 'image' || (item.mime_type || '').startsWith('image/')
const isVideoAsset = (item: Asset) => (item.mime_type || '').startsWith('video/')
const isUnavailable = (item: Asset) => ['source_missing', 'deleted'].includes(item.storage_status || '')
</script>

<style scoped>
.section-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 20px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.section-header h3 {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.section-header p {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}
.section-count {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-color);
  padding: 3px 10px;
  border-radius: 10px;
}

/* Image Grid */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 16px;
}
.image-card {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 10px;
  background: var(--card-bg);
  transition: box-shadow 0.2s;
}
.image-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}
.image-frame {
  aspect-ratio: 1 / 1;
  border-radius: 10px;
  overflow: hidden;
  background: var(--bg-color);
  margin-bottom: 10px;
  position: relative;
  cursor: pointer;
}
.image-frame:hover {
  opacity: 0.85;
}
.image-thumb {
  width: 100%;
  height: 100%;
}
.image-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  gap: 0;
}
.image-actions .el-button {
  font-size: 12px;
  padding: 4px 2px;
  flex: 1;
  justify-content: center;
}
.image-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-name-link {
  color: var(--primary-color);
  cursor: pointer;
  font-weight: 500;
}
.file-name-link:hover {
  text-decoration: underline;
}
.file-action-group {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
}
.file-action-group .el-button {
  font-size: 13px;
  padding: 2px 0;
}
.asset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.image-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.preview-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(260px, 0.9fr);
  gap: 20px;
}

.preview-panel__media {
  min-height: 320px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.preview-image,
.preview-video {
  width: 100%;
  max-height: 420px;
}

.preview-fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
  text-align: center;
  padding: 24px;
}

.preview-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.preview-meta {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.preview-url-label {
  margin-top: 12px;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.preview-url {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-secondary);
  word-break: break-all;
}

.preview-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}

/* Move Dialog */
.move-folder-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.move-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid var(--border-color);
  transition: all 0.15s;
  font-size: 14px;
}
.move-item:hover { border-color: var(--primary-color); }
.move-item.is-selected {
  border-color: var(--primary-color);
  background: rgba(34, 197, 94, 0.08);
}
</style>
