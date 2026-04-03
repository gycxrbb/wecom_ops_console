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
          <div class="image-frame">
            <el-image :src="buildAssetAuthUrl(item.preview_url || item.url)" fit="cover" class="image-thumb" />
            <div class="image-overlay">
              <el-button size="small" circle type="primary" @click="handleDownload(item)" title="下载">
                <el-icon><Download /></el-icon>
              </el-button>
              <el-button size="small" circle type="warning" @click="handleMove(item)" title="移动">
                <el-icon><Rank /></el-icon>
              </el-button>
              <el-popconfirm title="确定要删除该素材吗？" @confirm="handleDelete(item)">
                <template #reference>
                  <el-button size="small" circle type="danger" title="删除">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
          <div class="image-name" :title="item.name">{{ item.name }}</div>
          <div class="image-meta">{{ formatSize(item.file_size) }}</div>
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
        <el-table-column prop="name" label="文件名" min-width="240" show-overflow-tooltip />
        <el-table-column prop="mime_type" label="类型" width="180" />
        <el-table-column label="大小" width="100">
          <template #default="scope">{{ formatSize(scope.row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="上传时间" width="160">
          <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="handleDownload(scope.row)">下载</el-button>
            <el-button link type="warning" @click="handleMove(scope.row)">移动</el-button>
            <el-popconfirm title="确定要删除该素材吗？" @confirm="handleDelete(scope.row)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
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
          v-for="folder in folders"
          :key="folder.id"
          class="move-item"
          :class="{ 'is-selected': moveTargetId === folder.id }"
          @click="moveTargetId = folder.id"
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
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Download, Delete, Rank, FolderOpened } from '@element-plus/icons-vue'
import { Folder as FolderIcon } from '@element-plus/icons-vue'
import { buildAssetAuthUrl } from '@/utils/assets'
import type { Asset } from '../composables/useAssets'
import type { Folder } from '../composables/useFolders'

const props = defineProps<{
  imageAssets: Asset[]
  fileAssets: Asset[]
  folders: Folder[]
}>()

const emit = defineEmits(['download', 'delete', 'move'])

const moveDialogVisible = ref(false)
const moveTargetId = ref<number | null>(null)
const moveAssetId = ref<number | null>(null)

const handleDownload = (item: Asset) => emit('download', item)
const handleDelete = (item: Asset) => emit('delete', item)

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
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}
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
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
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
}
.image-thumb {
  width: 100%;
  height: 100%;
}
.image-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}
.image-frame:hover .image-overlay {
  opacity: 1;
}
.image-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.image-meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
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
