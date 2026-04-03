<template>
  <div class="assets-layout">
    <!-- Left: Folder Sidebar -->
    <FolderSidebar
      :folders="folders"
      :active-id="activeFolderId"
      :total-count="totalAssetCount"
      :uncategorized-count="uncategorizedCount"
      @select="handleFolderSelect"
      @create="openCreateDialog"
      @rename="openRenameDialog"
    />

    <!-- Right: Content Area -->
    <div class="assets-main">
      <div class="assets-header">
        <div class="assets-header__left">
          <h1 class="assets-title">{{ currentFolderName }}</h1>
          <p class="assets-desc">图片和文件分区管理，图片按缩略图浏览，文件按列表查看</p>
        </div>
        <div class="assets-header__right">
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
          <span class="summary-label">全部</span>
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

    <!-- Folder Create/Rename Dialog -->
    <FolderDialog
      v-model="folderDialogVisible"
      :mode="folderDialogMode"
      :initial-name="folderDialogInitialName"
      @confirm="handleFolderDialogConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Upload } from '@element-plus/icons-vue'
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
  folders, fetchFolders, createFolder, renameFolder, deleteFolder
} = useFolders()

const activeFolderId = ref<string>('all')
const uploading = ref(false)
const folderDialogVisible = ref(false)
const folderDialogMode = ref<'create' | 'rename'>('create')
const folderDialogInitialName = ref('')
const editingFolder = ref<Folder | null>(null)

const totalAssetCount = computed(() => assets.value.length)
const uncategorizedCount = computed(() => assets.value.filter(a => a.folder_id == null).length)

const currentFolderName = computed(() => {
  if (activeFolderId.value === 'all') return '全部素材'
  if (activeFolderId.value === 'uncategorized') return '未分类'
  const f = folders.value.find(f => String(f.id) === activeFolderId.value)
  return f ? f.name : '素材库'
})

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
    await fetchAssets(activeFolderId.value === 'all' ? undefined : activeFolderId.value)
    await fetchFolders()
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
    await fetchAssets(activeFolderId.value === 'all' ? undefined : activeFolderId.value)
    await fetchFolders()
  } catch (e) { console.error(e) }
}

const handleMove = async (assetId: number, folderId: number | null) => {
  try {
    await moveAsset(assetId, folderId)
    await fetchAssets(activeFolderId.value === 'all' ? undefined : activeFolderId.value)
    await fetchFolders()
  } catch (e) { console.error(e) }
}

const openCreateDialog = () => {
  folderDialogMode.value = 'create'
  folderDialogInitialName.value = ''
  editingFolder.value = null
  folderDialogVisible.value = true
}

const openRenameDialog = (folder: Folder) => {
  folderDialogMode.value = 'rename'
  folderDialogInitialName.value = folder.name
  editingFolder.value = folder
  folderDialogVisible.value = true
}

const handleFolderDialogConfirm = async (name: string) => {
  if (folderDialogMode.value === 'create') {
    await createFolder(name)
  } else if (editingFolder.value) {
    await renameFolder(editingFolder.value.id, name)
  }
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

.assets-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
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
</style>
