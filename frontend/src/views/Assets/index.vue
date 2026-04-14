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
          <el-button plain type="warning" @click="jumpToEmotionFolder">
            <el-icon><Picture /></el-icon> 表情包
          </el-button>
          <el-button plain class="voice-shortcut-btn" @click="jumpToVoiceFolder">
            <el-icon><Upload /></el-icon> 语音
          </el-button>
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
        <div class="paste-hint">支持 <kbd>{{ modKey }}</kbd>+<kbd>V</kbd> 直接粘贴图片、文件或音频到当前目录</div>
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
        <!-- 表情包分类筛选 -->
        <div v-if="isEmotionFolder" class="emotion-filter">
          <div class="emotion-filter__row">
            <el-input
              v-model="emotionSearch"
              placeholder="搜索表情包名称..."
              clearable
              size="small"
              class="emotion-filter__search"
            />
          </div>
          <div class="emotion-chips">
            <button
              v-for="chip in emotionCategoryChips"
              :key="chip.value"
              type="button"
              class="emotion-chip"
              :class="{ 'is-active': emotionCategory === chip.value }"
              @click="emotionCategory = chip.value"
            >{{ chip.label }}</button>
          </div>
        </div>

        <AssetGrid
          :image-assets="displayImageAssets"
          :file-assets="displayFileAssets"
          :folders="folders"
          :deleting-ids="deletingIds"
          :batch-mode="batchMode"
          :selected-ids="selectedIds"
          @download="handleDownload"
          @delete="handleDelete"
          @move="handleMove"
          @rename="handleRename"
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

    <CompressDialog
      v-model="compressDialogVisible"
      :file="pendingLargeFile"
      @compress="handleCompressed"
      @upload-original="handleUploadOriginal"
    />

    <!-- 粘贴上传命名弹窗 -->
    <el-dialog v-model="pasteNameVisible" title="为粘贴的资源命名" width="420px" destroy-on-close @close="cancelPasteName">
      <el-input v-model="pasteNameInput" placeholder="输入资源名称（不含扩展名）" @keyup.enter="confirmPasteName" autofocus />
      <div style="margin-top:8px;font-size:12px;color:var(--text-muted);">
        扩展名 <strong>.{{ pasteNameExt }}</strong> 会自动保留
      </div>
      <template #footer>
        <el-button @click="cancelPasteName">取消</el-button>
        <el-button type="primary" @click="confirmPasteName">确认上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { FolderAdd, FolderOpened, Upload, Operation, Picture } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Folder as FolderIcon } from '@element-plus/icons-vue'
import { useAssets } from './composables/useAssets'
import { useFolders } from './composables/useFolders'
import FolderSidebar from './components/FolderSidebar.vue'
import AssetGrid from './components/AssetGrid.vue'
import FolderDialog from './components/FolderDialog.vue'
import CompressDialog from './components/CompressDialog.vue'
import { isCompressibleImage } from '@/utils/imageCompress'
import type { Folder } from './composables/useFolders'

const {
  assets, loading, imageAssets, fileAssets,
  fetchAssets, uploadAsset, deleteAsset, moveAsset, renameAsset, downloadAsset,
  batchDeleteAssets, batchMoveAssets
} = useAssets()

const {
  folders, fetchFolders, createFolder, renameFolder, deleteFolder, moveFolder
} = useFolders()

const activeFolderId = ref<string>('all')
const uploading = ref(false)
const uploadProgress = ref({ done: 0, total: 0 })

// ---- 压缩对话框 ----
const LARGE_FILE_THRESHOLD = 20 * 1024 * 1024
const compressDialogVisible = ref(false)
const pendingLargeFile = ref<File | null>(null)
const pendingFolderId = ref<number | null>(null)

const uploadButtonText = computed(() => {
  if (!uploading.value) return '上传素材'
  const { done, total } = uploadProgress.value
  return total > 1 ? `上传中 ${done}/${total}` : '上传中...'
})

// ---- 表情包分类筛选 ----
const emotionCategoryChips = [
  { value: 'all', label: '全部' },
  { value: 'morning', label: '早安' },
  { value: 'reminder', label: '提醒' },
  { value: 'checkin', label: '打卡' },
  { value: 'encourage', label: '鼓励' },
  { value: 'night', label: '晚安' },
]
const emotionCategoryKeywords: Record<string, string[]> = {
  morning: ['早安', '早上好', 'morning', '早餐'],
  reminder: ['提醒', '喝水', '注意', '催', '提示'],
  checkin: ['打卡', '签到', '记录', '提交', '完成'],
  encourage: ['加油', '真棒', '鼓励', '点赞', '坚持', '优秀'],
  night: ['晚安', '休息', '睡觉', 'night'],
}
const emotionCategory = ref('all')
const emotionSearch = ref('')

const isEmotionFolder = computed(() =>
  currentFolder.value?.is_system && currentFolder.value.name === '表情包'
)

const matchesEmotionCategory = (name: string) => {
  if (emotionCategory.value === 'all') return true
  const keywords = emotionCategoryKeywords[emotionCategory.value] || []
  const lower = name.toLowerCase()
  return keywords.some(k => lower.includes(k.toLowerCase()))
}

const emotionFilteredAssets = computed(() => {
  if (!isEmotionFolder.value) return assets.value
  let list = assets.value
  // 分类关键字过滤
  if (emotionCategory.value !== 'all') {
    list = list.filter((a: any) => matchesEmotionCategory(a.name || ''))
  }
  // 搜索
  const q = emotionSearch.value.trim().toLowerCase()
  if (q) {
    list = list.filter((a: any) => (a.name || '').toLowerCase().includes(q))
  }
  return list
})

const isImage = (item: any) => item.material_type === 'image' || (item.mime_type || '').startsWith('image/')
const displayImageAssets = computed(() => emotionFilteredAssets.value.filter(isImage))
const displayFileAssets = computed(() => emotionFilteredAssets.value.filter((item: any) => !isImage(item)))

const folderDialogVisible = ref(false)
const folderDialogMode = ref<'create' | 'rename'>('create')
const folderDialogInitialName = ref('')
const editingFolder = ref<Folder | null>(null)
const creatingParentFolder = ref<Folder | null>(null)

const modKey = computed(() => /Mac|iPod|iPhone|iPad/.test(navigator.platform) ? 'Cmd' : 'Ctrl')

const AUDIO_MIME_EXTENSION_MAP: Record<string, string> = {
  'audio/amr': 'amr',
  'audio/3gpp': 'amr',
  'audio/mpeg': 'mp3',
  'audio/mp3': 'mp3',
  'audio/wav': 'wav',
  'audio/x-wav': 'wav',
  'audio/m4a': 'm4a',
  'audio/x-m4a': 'm4a',
  'audio/mp4': 'm4a',
  'audio/aac': 'aac',
  'audio/ogg': 'ogg',
  'audio/opus': 'opus',
  'audio/flac': 'flac',
  'audio/x-ms-wma': 'wma',
}

const getNormalizedPasteExtension = (file: File) => {
  const mime = (file.type || '').split(';', 1)[0].trim().toLowerCase()
  if (AUDIO_MIME_EXTENSION_MAP[mime]) return AUDIO_MIME_EXTENSION_MAP[mime]

  const rawExt = (file.name?.split('.').pop() || '').trim().toLowerCase()
  if (rawExt === 'mpeg') return 'mp3'
  return rawExt || 'png'
}


const totalAssetCount = computed(() => assets.value.length)
const uncategorizedCount = computed(() => assets.value.filter(a => a.folder_id == null).length)

const currentFolder = computed(() => {
  if (activeFolderId.value === 'all' || activeFolderId.value === 'uncategorized') return null
  return folders.value.find(folder => String(folder.id) === activeFolderId.value) || null
})

const emotionFolder = computed(() => (
  folders.value.find(folder => folder.is_system && folder.name === '表情包') || null
))
const voiceFolder = computed(() => (
  folders.value.find(folder => folder.is_system && folder.name === '语音') || null
))

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
  if (currentFolder.value?.is_system && currentFolder.value.name === '表情包') {
    return '运营常用静态表情图专区，建议统一上传 PNG、JPG 或 WebP，再作为独立图片消息发送。'
  }
  if (currentFolder.value?.is_system && currentFolder.value.name === '语音') {
    return '语音专区支持上传 mp3、wav、m4a 等常见音频，系统会自动转成企微需要的 AMR 后再入库。'
  }
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

const jumpToEmotionFolder = () => {
  if (!emotionFolder.value) {
    ElMessage.warning('表情包文件夹正在初始化，请稍后重试')
    return
  }
  handleFolderSelect(String(emotionFolder.value.id))
}

const jumpToVoiceFolder = () => {
  if (!voiceFolder.value) {
    ElMessage.warning('语音文件夹正在初始化，请稍后重试')
    return
  }
  handleFolderSelect(String(voiceFolder.value.id))
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

  // 大文件检测：>= 20MB 弹出压缩对话框
  if (file.size >= LARGE_FILE_THRESHOLD) {
    pendingLargeFile.value = file
    pendingFolderId.value = folderId
    compressDialogVisible.value = true
    return
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

const handleCompressed = async (blob: Blob, originalFile: File) => {
  const newName = originalFile.name.replace(/\.[^.]+$/, '.jpg')
  const compressedFile = new File([blob], newName, { type: 'image/jpeg' })
  uploading.value = true
  try {
    await uploadAsset(compressedFile, pendingFolderId.value, true)
    await Promise.all([refreshCurrentAssets(), fetchFolders()])
    ElMessage.success('压缩上传成功')
  } catch {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
    pendingLargeFile.value = null
  }
}

const handleUploadOriginal = async (file: File) => {
  uploading.value = true
  try {
    await uploadAsset(file, pendingFolderId.value, true)
    await Promise.all([refreshCurrentAssets(), fetchFolders()])
    ElMessage.success('上传成功')
  } catch {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
    pendingLargeFile.value = null
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

const handleRename = async (assetId: number, name: string) => {
  try {
    await renameAsset(assetId, name)
    await refreshCurrentAssets()
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

// ---- 粘贴上传 ----
// --- 粘贴命名 ---
const pasteNameVisible = ref(false)
const pasteNameInput = ref('')
const pasteNameExt = ref('png')
let pendingPasteFiles: { file: File; ext: string }[] = []
let pendingPasteFolderId: number | null = null

const handlePaste = async (event: ClipboardEvent) => {
  const tag = (event.target as HTMLElement)?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

  const files = event.clipboardData?.files
  if (!files || files.length === 0) return

  event.preventDefault()
  if (uploading.value) return

  let folderId: number | null = null
  if (activeFolderId.value !== 'all' && activeFolderId.value !== 'uncategorized') {
    folderId = Number(activeFolderId.value)
  }

  // 收集文件，提取首个文件扩展名用于提示
  const items: { file: File; ext: string }[] = []
  for (let i = 0; i < files.length; i++) {
    const f = files[i]
    const ext = getNormalizedPasteExtension(f)
    items.push({ file: f, ext })
  }

  if (items.length === 0) return

  pendingPasteFiles = items
  pendingPasteFolderId = folderId
  pasteNameExt.value = items.length === 1 ? items[0].ext : '...'
  // 默认名称：去掉扩展名的原名，或者空
  const baseName = items[0].file.name?.replace(/\.[^.]+$/, '') || ''
  pasteNameInput.value = baseName === 'image' || baseName === 'clipboard' ? '' : baseName
  pasteNameVisible.value = true
}

const confirmPasteName = async () => {
  const name = pasteNameInput.value.trim()
  if (!name) {
    ElMessage.warning('请输入资源名称')
    return
  }
  pasteNameVisible.value = false

  uploading.value = true
  uploadProgress.value = { done: 0, total: pendingPasteFiles.length }
  try {
    for (let i = 0; i < pendingPasteFiles.length; i++) {
      const { file, ext } = pendingPasteFiles[i]
      const finalName = pendingPasteFiles.length === 1
        ? `${name}.${ext}`
        : `${name}_${i + 1}.${ext}`
      const renamed = new File([file], finalName, { type: file.type || 'image/png' })
      await uploadAsset(renamed, pendingPasteFolderId, true)
      uploadProgress.value = { done: i + 1, total: pendingPasteFiles.length }
    }
    await Promise.all([refreshCurrentAssets(), fetchFolders()])
    ElMessage.success(`已上传 ${pendingPasteFiles.length} 个文件`)
  } catch {
    ElMessage.error('粘贴上传失败')
  } finally {
    uploading.value = false
    pendingPasteFiles = []
  }
}

const cancelPasteName = () => {
  pasteNameVisible.value = false
  pendingPasteFiles = []
}

onMounted(async () => {
  document.addEventListener('paste', handlePaste)
  await Promise.all([fetchFolders(), fetchAssets()])
})

onBeforeUnmount(() => {
  document.removeEventListener('paste', handlePaste)
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
  overflow-x: auto;
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
  align-items: center;
}

.voice-shortcut-btn {
  border-color: rgba(59, 130, 246, 0.22);
  background: rgba(59, 130, 246, 0.08);
  color: #1d4ed8;
}

.voice-shortcut-btn:hover,
.voice-shortcut-btn:focus-visible {
  border-color: rgba(59, 130, 246, 0.32);
  background: rgba(59, 130, 246, 0.14);
  color: #1e40af;
}

.voice-shortcut-btn :deep(.el-icon) {
  color: inherit;
}

.paste-hint {
  grid-column: 1 / -1;
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.7;
  text-align: right;
  margin-top: 2px;
}
.paste-hint kbd {
  display: inline-block;
  padding: 0 4px;
  font-size: 10px;
  font-family: inherit;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: 3px;
  line-height: 1.6;
}

/* 表情包分类筛选 */
.emotion-filter {
  margin-bottom: 16px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}
.emotion-filter__row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.emotion-filter__search {
  max-width: 240px;
}
.emotion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.emotion-chip {
  appearance: none;
  border: 1px solid var(--border-color);
  padding: 4px 14px;
  border-radius: 16px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.emotion-chip.is-active {
  background: rgba(34, 197, 94, 0.1);
  border-color: var(--primary-color);
  color: var(--primary-color);
  font-weight: 500;
}
.emotion-chip:hover:not(.is-active) {
  color: var(--text-primary);
  border-color: var(--text-muted);
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
    overflow-x: auto;
  }
  .assets-header {
    flex-direction: column;
    gap: 12px;
  }
  .assets-header__right {
    flex-wrap: wrap;
  }
  .batch-action-bar {
    flex-direction: column;
    gap: 10px;
    align-items: stretch;
  }
  .batch-action-bar__actions {
    flex-wrap: wrap;
    justify-content: center;
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
