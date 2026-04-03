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
            :http-request="handleUpload"
          >
            <el-button type="primary" :loading="uploading">
              <el-icon><Upload /></el-icon> 上传素材
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
          @download="handleDownload"
          @delete="handleDelete"
          @move="handleMove"
        />
      </div>
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
import { FolderAdd, FolderOpened, Upload } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useAssets } from './composables/useAssets'
import { useFolders } from './composables/useFolders'
import FolderSidebar from './components/FolderSidebar.vue'
import AssetGrid from './components/AssetGrid.vue'
import FolderDialog from './components/FolderDialog.vue'
import type { Folder } from './composables/useFolders'

const {
  assets, loading, imageAssets, fileAssets,
  fetchAssets, uploadAsset, deleteAsset, moveAsset, downloadAsset
} = useAssets()

const {
  folders, fetchFolders, createFolder, renameFolder, deleteFolder, moveFolder
} = useFolders()

const activeFolderId = ref<string>('all')
const uploading = ref(false)
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

const handleUpload = async (options: any) => {
  uploading.value = true
  try {
    let folderId: number | null = null
    if (activeFolderId.value !== 'all' && activeFolderId.value !== 'uncategorized') {
      folderId = Number(activeFolderId.value)
    }
    await uploadAsset(options.file, folderId)
    await Promise.all([refreshCurrentAssets(), fetchFolders()])
  } catch (e) {
    console.error(e)
  } finally {
    uploading.value = false
  }
}

const handleDownload = (item: any) => downloadAsset(item)

const handleDelete = async (item: any) => {
  try {
    await deleteAsset(item.id)
    await Promise.all([refreshCurrentAssets(), fetchFolders()])
  } catch (e) {
    console.error(e)
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
</style>
