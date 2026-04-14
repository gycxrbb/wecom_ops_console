<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="选择素材"
    width="920px"
    append-to-body
    class="asset-picker-dialog"
    :close-on-click-modal="!uploading"
    :close-on-press-escape="!uploading"
    :show-close="!uploading"
  >
    <div class="asset-picker">
      <aside class="asset-picker__sidebar">
        <div class="asset-picker__sidebar-header">
          <span>素材目录</span>
          <el-button link type="primary" @click="handleFolderSelect('all')">全部素材</el-button>
        </div>

        <button
          type="button"
          class="folder-shortcut"
          :class="{ 'is-active': currentFolderId === 'all' }"
          @click="handleFolderSelect('all')"
        >
          全部素材
        </button>
        <button
          type="button"
          class="folder-shortcut"
          :class="{ 'is-active': currentFolderId === 'uncategorized' }"
          @click="handleFolderSelect('uncategorized')"
        >
          未分类
        </button>
        <button
          v-if="emotionFolder"
          type="button"
          class="folder-shortcut folder-shortcut--emotion"
          :class="{ 'is-active': currentFolderId === String(emotionFolder.id) }"
          @click="handleEmotionFolderSelect"
        >
          表情包
        </button>

        <el-tree
          v-if="folderTree.length"
          :data="folderTree"
          node-key="id"
          :current-node-key="currentFolderTreeKey"
          highlight-current
          default-expand-all
          :expand-on-click-node="false"
          class="folder-tree"
          @node-click="handleFolderNodeClick"
        >
          <template #default="{ data }">
            <div class="folder-tree__node">
              <span class="folder-tree__name">{{ data.name }}</span>
              <span class="folder-tree__count">{{ data.asset_count }}</span>
            </div>
          </template>
        </el-tree>

        <div v-else class="folder-tree__empty">暂无文件夹</div>
      </aside>

      <section class="asset-picker__main">
        <div class="asset-picker__toolbar">
          <div class="asset-picker__toolbar-left">
            <el-radio-group v-model="listFilter" size="small">
              <el-radio-button label="all">全部</el-radio-button>
              <el-radio-button label="image">图片</el-radio-button>
              <el-radio-button label="file">文件</el-radio-button>
            </el-radio-group>
            <div class="asset-picker__summary">
              <span>{{ currentFolderLabel }}</span>
              <strong>{{ filteredList.length }}</strong>
            </div>
          </div>

          <el-upload
            :http-request="handleUpload"
            :show-file-list="false"
            :accept="acceptType === 'image' ? 'image/*' : undefined"
            :disabled="uploading"
          >
            <el-button type="primary" size="small" :loading="uploading">
              {{ uploading ? uploadButtonText : '上传到当前目录' }}
            </el-button>
          </el-upload>
        </div>

        <div v-if="showEmotionTools" class="asset-picker__emotion-tools">
          <div class="asset-picker__emotion-tools-row">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索表情包名称..."
              clearable
              size="small"
              class="asset-picker__emotion-search"
            />
            <span class="asset-picker__emotion-tip">最近使用会优先排在前面</span>
          </div>
          <div class="asset-picker__emotion-chips">
            <button
              v-for="chip in emotionCategoryChips"
              :key="chip.value"
              type="button"
              class="emotion-chip"
              :class="{ 'is-active': activeEmotionCategory === chip.value }"
              @click="activeEmotionCategory = chip.value"
            >
              {{ chip.label }}
            </button>
          </div>
        </div>

        <div class="upload-hint">{{ uploadHint }}</div>

        <transition name="upload-status-fade">
          <div v-if="uploading" class="asset-picker__upload-status">
            <el-icon class="asset-picker__upload-status-icon is-spinning"><Loading /></el-icon>
            <div class="asset-picker__upload-status-copy">
              <strong>{{ uploadStatusTitle }}</strong>
              <span>{{ uploadStatusDesc }}</span>
            </div>
          </div>
        </transition>

        <div v-if="folderBreadcrumbs.length" class="asset-picker__breadcrumbs">
          <button type="button" class="breadcrumb-link" @click="handleFolderSelect('all')">全部素材</button>
          <template v-for="folder in folderBreadcrumbs" :key="folder.id">
            <span class="breadcrumb-sep">/</span>
            <button type="button" class="breadcrumb-link" @click="handleFolderSelect(String(folder.id))">
              {{ folder.name }}
            </button>
          </template>
        </div>

        <div v-if="childFolders.length" class="child-folder-strip">
          <button
            v-for="folder in childFolders"
            :key="folder.id"
            type="button"
            class="child-folder-card"
            @click="handleFolderSelect(String(folder.id))"
          >
            <span class="child-folder-card__name">{{ folder.name }}</span>
            <span class="child-folder-card__meta">{{ folder.asset_count }} 个素材</span>
          </button>
        </div>

        <div v-loading="loading || uploading" :element-loading-text="uploadStatusTitle" class="asset-picker__content">
          <el-empty v-if="filteredList.length === 0" description="当前目录暂无素材" />

          <div v-else-if="listFilter === 'image' || listFilter === 'all'" class="asset-grid">
            <div
              v-for="item in filteredList"
              :key="item.id"
              class="asset-item"
              :class="{ selected: selectedId === item.id }"
              @click="selectedId = item.id; selectedAsset = item"
            >
              <div class="asset-thumb">
                <el-image
                  v-if="isImage(item)"
                  :src="buildAssetPreviewUrl(item)"
                  fit="cover"
                  style="width: 100%; height: 100%"
                />
                <el-icon v-else :size="32"><Document /></el-icon>
              </div>
              <div class="asset-name-row">
                <div class="asset-name">{{ item.name }}</div>
                <span v-if="isRecentEmotion(item.id)" class="asset-badge">最近使用</span>
              </div>
              <div class="asset-meta">{{ formatSize(item.file_size) }}</div>
            </div>
          </div>

          <el-table
            v-else
            :data="filteredList"
            highlight-current-row
            @current-change="(row: any) => { selectedId = row?.id; selectedAsset = row }"
            size="small"
          >
            <el-table-column prop="name" label="文件名" />
            <el-table-column prop="material_type" label="类型" width="80" />
            <el-table-column label="大小" width="100">
              <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </section>
    </div>

    <template #footer>
      <el-button :disabled="uploading" @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :disabled="!selectedId || uploading" @click="confirmSelect">确认选择</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Document, Loading } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import { ASSET_UPLOAD_HINT, buildAssetAuthUrl, validateAssetUpload } from '@/utils/assets'

const props = defineProps<{
  visible: boolean
  acceptType?: 'image' | 'file' | 'all'
  preferredFolder?: 'emotion' | 'all'
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'select', asset: any): void
}>()

interface Folder {
  id: number
  name: string
  parent_id: number | null
  is_system?: boolean
  asset_count: number
  child_count: number
}

const assets = ref<any[]>([])
const folders = ref<Folder[]>([])
const loading = ref(false)
const uploading = ref(false)
const uploadingFileName = ref('')
const listFilter = ref(props.acceptType || 'all')
const selectedId = ref<number | null>(null)
const selectedAsset = ref<any>(null)
const currentFolderId = ref<string>('all')
const uploadHint = ASSET_UPLOAD_HINT
const searchKeyword = ref('')
const activeEmotionCategory = ref('all')

const EMOTION_RECENTS_KEY = 'emotion-picker-recents'
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

const readEmotionRecents = (): number[] => {
  try {
    const raw = window.localStorage.getItem(EMOTION_RECENTS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter(id => Number.isFinite(id)).map(Number) : []
  } catch {
    return []
  }
}

const writeEmotionRecents = (ids: number[]) => {
  try {
    window.localStorage.setItem(EMOTION_RECENTS_KEY, JSON.stringify(ids.slice(0, 12)))
  } catch {
    // ignore localStorage errors
  }
}

const recentEmotionIds = ref<number[]>(readEmotionRecents())

const matchesEmotionCategory = (name: string, category: string) => {
  if (category === 'all') return true
  const normalized = name.toLowerCase()
  return (emotionCategoryKeywords[category] || []).some(keyword => normalized.includes(keyword.toLowerCase()))
}

const filteredList = computed(() => {
  let available = assets.value.filter((item: any) => item.storage_status !== 'source_missing')
  if (currentFolderId.value === 'uncategorized') {
    available = available.filter((item: any) => item.folder_id == null)
  }
  if (listFilter.value !== 'all') {
    available = available.filter((item: any) => item.material_type === listFilter.value)
  }

  const keyword = searchKeyword.value.trim().toLowerCase()
  if (keyword) {
    available = available.filter((item: any) => String(item.name || '').toLowerCase().includes(keyword))
  }

  if (showEmotionTools.value && activeEmotionCategory.value !== 'all') {
    available = available.filter((item: any) => matchesEmotionCategory(String(item.name || ''), activeEmotionCategory.value))
  }

  if (showEmotionTools.value) {
    const rankMap = new Map(recentEmotionIds.value.map((id, index) => [id, index]))
    available = [...available].sort((a: any, b: any) => {
      const aRank = rankMap.has(a.id) ? rankMap.get(a.id)! : Number.MAX_SAFE_INTEGER
      const bRank = rankMap.has(b.id) ? rankMap.get(b.id)! : Number.MAX_SAFE_INTEGER
      if (aRank !== bRank) return aRank - bRank
      return String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN')
    })
  }

  return available
})

const folderTree = computed(() => buildFolderTree(folders.value))
const currentFolderTreeKey = computed(() => {
  if (currentFolderId.value === 'all' || currentFolderId.value === 'uncategorized') return undefined
  return Number(currentFolderId.value)
})
const currentFolder = computed(() => (
  currentFolderId.value === 'all' || currentFolderId.value === 'uncategorized'
    ? null
    : folders.value.find(folder => String(folder.id) === currentFolderId.value) || null
))
const emotionFolder = computed(() => (
  folders.value.find(folder => folder.is_system && folder.name === '表情包') || null
))
const childFolders = computed(() => {
  if (currentFolderId.value === 'uncategorized') return []
  const parentId = currentFolder.value?.id ?? null
  return folders.value.filter(folder => folder.parent_id === parentId)
})
const currentFolderLabel = computed(() => {
  if (currentFolderId.value === 'all') return '全部素材'
  if (currentFolderId.value === 'uncategorized') return '未分类'
  if (currentFolder.value?.is_system && currentFolder.value.name === '表情包') return '表情包'
  return currentFolder.value?.name || '当前目录'
})
const showEmotionTools = computed(() => (
  props.preferredFolder === 'emotion' && currentFolder.value?.is_system && currentFolder.value.name === '表情包'
))
const folderBreadcrumbs = computed(() => {
  const chain: Folder[] = []
  let cursor = currentFolder.value
  while (cursor) {
    chain.unshift(cursor)
    cursor = folders.value.find(folder => folder.id === cursor?.parent_id) || null
  }
  return chain
})

const uploadButtonText = computed(() => (
  uploadingFileName.value ? `上传中: ${uploadingFileName.value}` : '上传中...'
))

const uploadStatusTitle = computed(() => `正在上传到${currentFolderLabel.value}`)
const uploadStatusDesc = computed(() => (
  uploadingFileName.value
    ? `文件「${uploadingFileName.value}」上传完成前，请稍候片刻。`
    : '素材上传完成后会自动刷新当前目录并选中新素材。'
))

const isImage = (item: any) => item.material_type === 'image' || (item.mime_type || '').startsWith('image/')
const buildAssetPreviewUrl = (item: any) => buildAssetAuthUrl(item.preview_url || item.url)

const formatSize = (bytes: number) => {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const buildFolderTree = (list: Folder[]) => {
  const grouped = new Map<number | null, Folder[]>()
  list.forEach(folder => {
    const key = folder.parent_id ?? null
    const siblings = grouped.get(key) || []
    siblings.push(folder)
    grouped.set(key, siblings)
  })
  const build = (parentId: number | null): any[] => (
    (grouped.get(parentId) || [])
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
      .map(folder => ({
        ...folder,
        children: build(folder.id)
      }))
  )
  return build(null)
}

const fetchFolders = async () => {
  try {
    const res = await request.get('/v1/asset-folders')
    folders.value = res || []
  } catch (e) {
    console.error(e)
  }
}

const fetchAssets = async (folderId?: string) => {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (folderId && folderId !== 'all' && folderId !== 'uncategorized') params.folder_id = folderId
    const res = await request.get('/v1/assets', { params })
    assets.value = res.list || res
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleUpload = async (options: any) => {
  if (uploading.value) return
  const validation = validateAssetUpload(options.file, props.acceptType || 'all')
  if (!validation.valid) {
    ElMessage.warning(validation.message)
    return
  }

  const formData = new FormData()
  formData.append('file', options.file)
  if (currentFolderId.value !== 'all' && currentFolderId.value !== 'uncategorized') {
    formData.append('folder_id', currentFolderId.value)
  }

  try {
    uploading.value = true
    uploadingFileName.value = options.file?.name || ''
    await request.post('/v1/assets', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success('上传成功')
    await Promise.all([fetchAssets(currentFolderId.value), fetchFolders()])
    const newAsset = [...assets.value].reverse().find((item: any) => item.name === options.file.name)
    if (newAsset) {
      selectedId.value = newAsset.id
      selectedAsset.value = newAsset
    }
  } catch (e) {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
    uploadingFileName.value = ''
  }
}

const confirmSelect = () => {
  if (selectedAsset.value) {
    if (showEmotionTools.value && Number.isFinite(selectedAsset.value.id)) {
      recentEmotionIds.value = [
        selectedAsset.value.id,
        ...recentEmotionIds.value.filter(id => id !== selectedAsset.value.id),
      ].slice(0, 12)
      writeEmotionRecents(recentEmotionIds.value)
    }
    emit('select', selectedAsset.value)
    emit('update:visible', false)
  }
}

const isRecentEmotion = (assetId: number) => showEmotionTools.value && recentEmotionIds.value.includes(assetId)

const handleFolderSelect = async (folderId: string) => {
  currentFolderId.value = folderId
  selectedId.value = null
  selectedAsset.value = null
  await fetchAssets(folderId)
}

const handleFolderNodeClick = async (folder: Folder) => {
  await handleFolderSelect(String(folder.id))
}

const handleEmotionFolderSelect = async () => {
  if (!emotionFolder.value) {
    ElMessage.warning('表情包文件夹正在初始化，请稍后重试')
    return
  }
  if (props.acceptType === 'image') {
    listFilter.value = 'image'
  }
  await handleFolderSelect(String(emotionFolder.value.id))
}

const openPreferredFolder = async () => {
  if (props.preferredFolder === 'emotion') {
    if (props.acceptType === 'image') {
      listFilter.value = 'image'
    }
    if (emotionFolder.value) {
      await handleFolderSelect(String(emotionFolder.value.id))
      return
    }
  }
  await fetchAssets('all')
}

watch(() => props.visible, (val) => {
  if (val) {
    selectedId.value = null
    selectedAsset.value = null
    listFilter.value = props.acceptType || 'all'
    currentFolderId.value = 'all'
    searchKeyword.value = ''
    activeEmotionCategory.value = 'all'
    uploading.value = false
    uploadingFileName.value = ''
    recentEmotionIds.value = readEmotionRecents()
    void (async () => {
      await fetchFolders()
      await openPreferredFolder()
    })()
  }
})
</script>

<style scoped>
.asset-picker {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 18px;
  min-height: 420px;
  overflow: hidden;
}

.asset-picker__sidebar {
  border-right: 1px solid var(--el-border-color-lighter);
  padding-right: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.asset-picker__sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.folder-shortcut {
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  background: transparent;
  color: var(--el-text-color-secondary);
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  transition: 0.2s ease;
}

.folder-shortcut:hover,
.folder-shortcut.is-active {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.folder-shortcut--emotion {
  border-color: rgba(245, 158, 11, 0.22);
  background: rgba(245, 158, 11, 0.08);
  color: #b45309;
}

.folder-shortcut--emotion:hover,
.folder-shortcut--emotion.is-active {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(245, 158, 11, 0.14);
  color: #92400e;
}

.folder-tree {
  flex: 1;
  overflow: auto;
}

.folder-tree__node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.folder-tree__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-tree__count {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}

.folder-tree__empty {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
  padding: 10px 0;
}

.asset-picker__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.asset-picker__toolbar {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.asset-picker__toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.asset-picker__summary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.asset-picker__emotion-tools {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.asset-picker__emotion-tools-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.asset-picker__emotion-search {
  max-width: 280px;
}

.asset-picker__emotion-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.asset-picker__emotion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.emotion-chip {
  border: 1px solid var(--el-border-color-light);
  border-radius: 999px;
  background: transparent;
  color: var(--el-text-color-secondary);
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: 0.2s ease;
}

.emotion-chip:hover,
.emotion-chip.is-active {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(245, 158, 11, 0.14);
  color: #92400e;
}

.upload-hint {
  margin-bottom: 16px;
  font-size: 12px;
  color: #909399;
}

.asset-picker__upload-status {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(64, 158, 255, 0.24);
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.08), rgba(103, 194, 58, 0.08));
}

.asset-picker__upload-status-icon {
  color: var(--el-color-primary);
  font-size: 18px;
  flex: 0 0 auto;
}

.asset-picker__upload-status-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.asset-picker__upload-status-copy strong {
  color: var(--el-text-color-primary);
  font-size: 13px;
}

.asset-picker__upload-status-copy span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
}

.asset-picker__breadcrumbs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.breadcrumb-link {
  border: none;
  background: transparent;
  padding: 0;
  color: var(--el-color-primary);
  cursor: pointer;
}

.breadcrumb-sep {
  color: var(--el-text-color-placeholder);
}

.child-folder-strip {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.child-folder-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  background: var(--el-fill-color-blank);
  padding: 12px;
  text-align: left;
  cursor: pointer;
  transition: 0.2s ease;
}

.child-folder-card:hover {
  border-color: var(--el-color-primary-light-5);
  transform: translateY(-1px);
}

.child-folder-card__name {
  display: block;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.child-folder-card__meta {
  display: block;
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.asset-picker__content {
  min-height: 260px;
  overflow-y: auto;
  max-height: 420px;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}

.asset-item {
  cursor: pointer;
  border: 2px solid transparent;
  border-radius: 8px;
  padding: 8px;
  text-align: center;
  transition: border-color 0.2s;
}

.asset-item:hover {
  border-color: var(--el-color-primary-light-5);
}

.asset-item.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.asset-thumb {
  width: 100%;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 4px;
}

.asset-name {
  font-size: 12px;
  color: #606266;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: center;
}

.asset-badge {
  flex: 0 0 auto;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  font-size: 10px;
  line-height: 1.5;
}

.asset-meta {
  margin-top: 2px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

html.dark .folder-shortcut,
html.dark .child-folder-card {
  background: rgba(20, 24, 31, 0.92);
}

.upload-status-fade-enter-active,
.upload-status-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.upload-status-fade-enter-from,
.upload-status-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
