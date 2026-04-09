<template>
  <div class="assets-layout">
    <FolderSidebar
      :folders="folders"
      :active-id="activeFolderId"
      :total-count="totalAssetCount"
      :uncategorized-count="uncategorizedCount"
      @select="handleFolderSelect"
      @create="openCreateDialog"
      @create-child="openCreateChildDialog"
      @rename="openRenameDialog"
      @delete="handleFolderDelete"
      @move="handleFolderMove"
    />

    <div class="assets-main">
      <div class="assets-header">
        <div class="assets-header__left">
          <div class="assets-breadcrumbs" v-if="folderBreadcrumbs.length">
            <button type="button" class="breadcrumb-link" @click="handleFolderSelect('all')">全部素材</button>
            <template v-for="folder in folderBreadcrumbs" :key="folder.id">
              <span class="breadcrumb-sep">/</span>
              <button type="button" class="breadcrumb-link" @click="handleFolderSelect(String(folder.id))">
                {{ folder.name }}
              </button>
            </template>
          </div>
          <h1 class="assets-title">{{ currentFolderName }}</h1>
          <p class="assets-desc">
            {{ currentFolderDescription }}
          </p>
          <button
            v-if="parentFolder"
            type="button"
            class="back-link"
            @click="handleFolderSelect(String(parentFolder.id))"
          >
            返回上级：{{ parentFolder.name }}
          </button>
        </div>
        <div class="assets-header__right">
          <el-button
            :type="batchMode ? 'primary' : 'default'"
            plain
            @click="toggleBatchMode"
          >
            <el-icon><Operation /></el-icon> {{ batchMode ? '退出批量' : '批量管理' }}
          </el-button>
          <el-button plain @click="openCreateDialog">
            <el-icon><FolderAdd /></el-icon> 新建文件夹
          </el-button>
          <el-button
            v-if="currentFolder"
            plain
            type="success"
            @click="openCreateChildDialog(currentFolder)"
          >
            <el-icon><FolderOpened /></el-icon> 新建子文件夹
          </el-button>
          <el-upload
            action="javascript:;"
            :show-file-list="false"
            :auto-upload="false"
            :on-change="handleFileChange"
            multiple
          >
            <el-button type="primary" :loading="uploading">
              <el-icon><Upload /></el-icon> {{ uploadButtonText }}
            </el-button>
          </el-upload>
        </div>
      </div>

      <div class="assets-summary">
        <div class="summary-chip">
          <span class="summary-label">当前目录</span>
          <strong>{{ assets.length }}</strong>
        </div>
        <div class="summary-chip">
          <span class="summary-label">图片</span>
          <strong>{{ imageAssets.length }}</strong>
        </div>
        <div class="summary-chip">
          <span class="summary-label">文件</span>
          <strong>{{ fileAssets.length }}</strong>
        </div>
        <div class="summary-chip" v-if="childFolders.length">
          <span class="summary-label">子文件夹</span>
          <strong>{{ childFolders.length }}</strong>
        </div>
      </div>

      <div v-if="childFolders.length" class="child-folder-panel">
        <div class="child-folder-panel__header">
          <div>
            <h3>子文件夹</h3>
            <p>当前目录下的内容分区，点击可继续向下进入。</p>
          </div>
        </div>
        <div class="child-folder-grid">
          <button
            v-for="folder in childFolders"
            :key="folder.id"
            type="button"
            class="child-folder-card"
            @click="handleFolderSelect(String(folder.id))"
          >
            <div class="child-folder-card__title">
              <el-icon><FolderOpened /></el-icon>
              <span>{{ folder.name }}</span>
            </div>
            <div class="child-folder-card__meta">{{ folder.asset_count }} 个素材</div>
            <div class="child-folder-card__meta" v-if="folder.child_count">{{ folder.child_count }} 个子文件夹</div>
          </button>
        </div>
      </div>

      <div v-loading="loading">
        <AssetGrid
          :image-assets="imageAssets"
          :file-assets="fileAssets"
          :folders="folders"
          :deleting-ids="deletingIds"
          :batch-mode="batchMode"
          :selected-ids="selectedIds"
          @download="handleDownload"
          @delete="handleDelete"
          @move="handleMove"
          @toggle-select="toggleSelect"
        />
      </div>

      <!-- 批量操作浮动栏 -->
      <transition name="batch-bar-fade">
        <div v-if="batchMode && selectedIds.length > 0" class="batch-action-bar">
          <div class="batch-action-bar__info">
            <strong>{{ selectedIds.length }}</strong> 项已选中
          </div>
          <div class="batch-action-bar__actions">
            <el-button size="small" @click="selectAll">全选</el-button>
            <el-button size="small" @click="clearSelection">取消全选</el-button>
            <el-button size="small" type="warning" @click="openBatchMoveDialog">批量移动</el-button>
            <el-button size="small" type="danger" @click="handleBatchDelete">批量删除</el-button>
          </div>
        </div>
      </transition>

      <!-- 批量移动对话框 -->
      <el-dialog v-model="batchMoveDialogVisible" title="批量移动到文件夹" width="400px">
        <div class="move-folder-list">
          <div
            class="move-item"
            :class="{ 'is-selected': batchMoveTargetId === null }"
            @click="batchMoveTargetId = null"
          >
            <el-icon><FolderOpened /></el-icon>
            <span>未分类</span>
          </div>
          <div
            v-for="folder in flattenedFolders"
            :key="folder.id"
            class="move-item"
            :class="{ 'is-selected': batchMoveTargetId === folder.id }"
            @click="batchMoveTargetId = folder.id"
            :style="{ paddingLeft: `${14 + folder.depth * 18}px` }"
          >
            <el-icon><FolderIcon /></el-icon>
            <span>{{ folder.name }}</span>
          </div>
        </div>
        <template #footer>
          <el-button @click="batchMoveDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleBatchMove">确定移动</el-button>
        </template>
      </el-dialog>
    </div>

    <FolderDialog
      v-model="folderDialogVisible"
      :mode="folderDialogMode"
      :initial-name="folderDialogInitialName"
      @confirm="handleFolderDialogConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { FolderAdd, FolderOpened, Upload, Operation } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Folder as FolderIcon } from '@element-plus/icons-vue'
import { useAssets } from './composables/useAssets'
import { useFolders } from './composables/useFolders'
import FolderSidebar from './components/FolderSidebar.vue'
import AssetGrid from './components/AssetGrid.vue'
import FolderDialog from './components/FolderDialog.vue'
import type { Folder } from './composables/useFolders'

const {
  assets, loading, imageAssets, fileAssets,
  fetchAssets, uploadAsset, deleteAsset, moveAsset, downloadAsset,
  batchDeleteAssets, batchMoveAssets
} = useAssets()

const {
  folders, fetchFolders, createFolder, renameFolder, deleteFolder, moveFolder
} = useFolders()

const activeFolderId = ref<string>('all')
const uploading = ref(false)
const uploadProgress = ref({ done: 0, total: 0 })

const uploadButtonText = computed(() => {
  if (!uploading.value) return '上传素材'
  const { done, total } = uploadProgress.value
  return total > 1 ? `上传中 ${done}/${total}` : '上传中...'
})
const folderDialogVisible = ref(false)
const folderDialogMode = ref<'create' | 'rename'>('create')
const folderDialogInitialName = ref('')
const editingFolder = ref<Folder | null>(null)
const creatingParentFolder = ref<Folder | null>(null)

const totalAssetCount = computed(() => assets.value.length)
const uncategorizedCount = computed(() => assets.value.filter(a => a.folder_id == null).length)

const currentFolder = computed(() => {
  if (activeFolderId.value === 'all' || activeFolderId.value === 'uncategorized') return null
  return folders.value.find(folder => String(folder.id) === activeFolderId.value) || null
})

const childFolders = computed(() => {
  const parentId = currentFolder.value?.id ?? null
  return folders.value.filter(folder => folder.parent_id === parentId)
})

const parentFolder = computed(() => (
  currentFolder.value?.parent_id != null
    ? folders.value.find(folder => folder.id === currentFolder.value?.parent_id) || null
    : null
))

const folderBreadcrumbs = computed(() => {
  const list: Folder[] = []
  let cursor = currentFolder.value
  while (cursor) {
    list.unshift(cursor)
    cursor = folders.value.find(folder => folder.id === cursor?.parent_id) || null
  }
  return list
})

const currentFolderName = computed(() => {
  if (activeFolderId.value === 'all') return '全部素材'
  if (activeFolderId.value === 'uncategorized') return '未分类'
  return currentFolder.value?.name || '素材库'
})

const currentFolderDescription = computed(() => {
  if (activeFolderId.value === 'all') return '图片和文件统一浏览，也可以进入具体文件夹继续细分管理。'
  if (activeFolderId.value === 'uncategorized') return '还没有归档到任何文件夹的素材。'
  if (childFolders.value.length) return '当前目录下包含子文件夹和素材，可以继续向下整理。'
  return '当前目录下的素材列表。'
})

const refreshCurrentAssets = async () => {
  await fetchAssets(activeFolderId.value === 'all' ? undefined : activeFolderId.value)
}

const handleFolderSelect = (id: string) => {
  activeFolderId.value = id
  if (id === 'all') {
    fetchAssets()
  } else {
    fetchAssets(id)
  }
}

const handleFileChange = async (uploadFile: any) => {
  if (uploading.value) return
  // 只取本次变更的单个文件
  const file = uploadFile?.raw
  if (!file) return

  let folderId: number | null = null
  if (activeFolderId.value !== 'all' && activeFolderId.value !== 'uncategorized') {
    folderId = Number(activeFolderId.value)
  }

  uploading.value = true
  try {
    await uploadAsset(file, folderId, true)
    await Promise.all([refreshCurrentAssets(), fetchFolders()])
    ElMessage.success('上传成功')
  } catch {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

const handleDownload = (item: any) => downloadAsset(item)

const deletingIds = ref<Set<number>>(new Set())

// ---- 批量管理 ----
const batchMode = ref(false)
const selectedIds = ref<number[]>([])
const batchMoveDialogVisible = ref(false)
const batchMoveTargetId = ref<number | null>(null)

const toggleBatchMode = () => {
  batchMode.value = !batchMode.value
  if (!batchMode.value) {
    selectedIds.value = []
  }
}

const toggleSelect = (id: number) => {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
  } else {
    selectedIds.value.push(id)
  }
}

const selectAll = () => {
  selectedIds.value = assets.value.map(a => a.id)
}

const clearSelection = () => {
  selectedIds.value = []
}

const openBatchMoveDialog = () => {
  batchMoveTargetId.value = null
  batchMoveDialogVisible.value = true
}

const handleBatchMove = async () => {
  if (!selectedIds.value.length) return
  await batchMoveAssets(selectedIds.value, batchMoveTargetId.value)
  batchMoveDialogVisible.value = false
  selectedIds.value = []
  await Promise.all([refreshCurrentAssets(), fetchFolders()])
}

const handleBatchDelete = async () => {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedIds.value.length} 个素材吗？删除后不可恢复。`,
      '批量删除',
      { type: 'warning' }
    )
  } catch {
    return
  }
  await batchDeleteAssets(selectedIds.value)
  selectedIds.value = []
  await Promise.all([refreshCurrentAssets(), fetchFolders()])
}

const flattenedFolders = computed(() => {
  const map = new Map<number | null, Folder[]>()
  for (const folder of folders.value) {
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

const handleDelete = async (item: any) => {
  if (deletingIds.value.has(item.id)) return
  deletingIds.value.add(item.id)
  try {
    await deleteAsset(item.id)
    await Promise.all([refreshCurrentAssets(), fetchFolders()])
  } catch (e) {
    console.error(e)
  } finally {
    deletingIds.value.delete(item.id)
  }
}

const handleMove = async (assetId: number, folderId: number | null) => {
  try {
    await moveAsset(assetId, folderId)
    await Promise.all([refreshCurrentAssets(), fetchFolders()])
  } catch (e) {
    console.error(e)
  }
}

const openCreateDialog = () => {
  folderDialogMode.value = 'create'
  folderDialogInitialName.value = ''
  editingFolder.value = null
  creatingParentFolder.value = null
  folderDialogVisible.value = true
}

const openCreateChildDialog = (folder: Folder) => {
  folderDialogMode.value = 'create'
  folderDialogInitialName.value = ''
  editingFolder.value = null
  creatingParentFolder.value = folder
  folderDialogVisible.value = true
}

const openRenameDialog = (folder: Folder) => {
  folderDialogMode.value = 'rename'
  folderDialogInitialName.value = folder.name
  editingFolder.value = folder
  creatingParentFolder.value = null
  folderDialogVisible.value = true
}

const handleFolderDelete = async (folder: Folder) => {
  try {
    await ElMessageBox.confirm(`确定删除文件夹「${folder.name}」吗？如果里面还有素材或子文件夹，系统会阻止删除。`, '删除文件夹', { type: 'warning' })
    await deleteFolder(folder.id)
    if (String(folder.id) === activeFolderId.value) {
      handleFolderSelect(folder.parent_id != null ? String(folder.parent_id) : 'all')
    } else {
      await Promise.all([fetchFolders(), refreshCurrentAssets()])
    }
  } catch {
    // cancelled
  }
}

const handleFolderMove = async (folderId: number, parentId: number | null) => {
  await moveFolder(folderId, parentId)
  await Promise.all([fetchFolders(), refreshCurrentAssets()])
}

const handleFolderDialogConfirm = async (name: string) => {
  if (folderDialogMode.value === 'create') {
    await createFolder(name, creatingParentFolder.value?.id ?? null)
  } else if (editingFolder.value) {
    await renameFolder(editingFolder.value.id, name)
  }
  await Promise.all([fetchFolders(), refreshCurrentAssets()])
}

onMounted(async () => {
  await Promise.all([fetchFolders(), fetchAssets()])
})
</script>

<style scoped>
.assets-layout {
  display: flex;
  max-width: 1400px;
  margin: 0 auto;
  gap: 0;
  background: var(--card-bg);
  border-radius: 16px;
  border: 1px solid var(--border-color);
  overflow: hidden;
  min-height: calc(100vh - 140px);
}

.assets-main {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.assets-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 16px;
}

.assets-header__right {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.assets-breadcrumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: 8px;
}

.breadcrumb-link {
  border: none;
  padding: 0;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
}

.breadcrumb-link:hover {
  color: var(--primary-color);
}

.breadcrumb-sep {
  color: var(--text-muted);
  font-size: 12px;
}

.assets-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.assets-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.back-link {
  margin-top: 10px;
  border: none;
  padding: 0;
  background: transparent;
  color: var(--primary-color);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}

.back-link:hover {
  text-decoration: underline;
}

.assets-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.summary-chip {
  min-width: 100px;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--bg-color);
  font-size: 13px;
}

.summary-label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.child-folder-panel {
  margin-bottom: 20px;
  padding: 18px;
  border: 1px solid var(--border-color);
  border-radius: 14px;
  background: var(--bg-color);
}

.child-folder-panel__header h3 {
  margin: 0 0 4px;
  color: var(--text-primary);
  font-size: 15px;
}

.child-folder-panel__header p {
  margin: 0 0 14px;
  color: var(--text-muted);
  font-size: 12px;
}

.child-folder-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.child-folder-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.15s ease;
  text-align: left;
}

.child-folder-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-1px);
}

.child-folder-card__title {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 600;
}

.child-folder-card__meta {
  color: var(--text-muted);
  font-size: 12px;
}

/* ---- Mobile / Tablet ---- */
@media (max-width: 767px) {
  .assets-layout {
    flex-direction: column;
    min-height: auto;
  }
  .assets-main {
    padding: 16px;
  }
  .assets-header {
    flex-direction: column;
    gap: 12px;
  }
  .assets-header__right {
    flex-wrap: wrap;
  }
}
@media (max-width: 480px) {
  .assets-main {
    padding: 12px;
  }
}

/* ---- 批量操作浮动栏 ---- */
.batch-action-bar {
  position: sticky;
  bottom: 16px;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 20px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  margin-top: 16px;
}

.batch-action-bar__info {
  font-size: 13px;
  color: var(--text-secondary);
}

.batch-action-bar__info strong {
  color: var(--primary-color);
  font-size: 16px;
  margin-right: 4px;
}

.batch-action-bar__actions {
  display: flex;
  gap: 8px;
}

.batch-bar-fade-enter-active,
.batch-bar-fade-leave-active {
  transition: all 0.25s ease;
}
.batch-bar-fade-enter-from,
.batch-bar-fade-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

/* ---- 批量移动对话框 ---- */
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
