<template>
  <div class="folder-sidebar">
    <div class="sidebar-header">
      <div>
        <span class="sidebar-title">文件夹</span>
        <div class="sidebar-subtitle">支持子文件夹层级管理</div>
      </div>
      <el-button size="small" text type="primary" @click="$emit('create')">
        <el-icon><Plus /></el-icon>
      </el-button>
    </div>

    <div class="folder-list">
      <div
        class="folder-item folder-item--root"
        :class="{ 'is-active': activeId === 'all' }"
        @click="$emit('select', 'all')"
        @dragover.prevent="handleRootDragOver('all')"
        @dragleave="handleDropLeave('all')"
        @drop.prevent="handleDropToRoot"
      >
        <el-icon :size="16"><Files /></el-icon>
        <span class="folder-name">全部素材</span>
        <span class="folder-count">{{ totalCount }}</span>
      </div>

      <div
        class="folder-item folder-item--root"
        :class="{ 'is-active': activeId === 'uncategorized' }"
        @click="$emit('select', 'uncategorized')"
      >
        <el-icon :size="16"><FolderOpened /></el-icon>
        <span class="folder-name">未分类</span>
        <span class="folder-count">{{ uncategorizedCount }}</span>
      </div>

      <el-divider style="margin: 10px 0" />

      <div v-for="folder in treeFolders" :key="folder.id" class="folder-node">
        <div
          class="folder-item"
          :class="{
            'is-active': activeId === String(folder.id),
            'is-drop-target': dropTargetId === folder.id
          }"
          :style="{ paddingLeft: `${12 + folder.depth * 18}px` }"
          @click="$emit('select', String(folder.id))"
          @contextmenu.prevent="openContextMenu($event, folder)"
          draggable="true"
          @dragstart="handleDragStart(folder)"
          @dragend="handleDragEnd"
          @dragover.prevent="handleDragOver(folder)"
          @dragleave="handleDropLeave(folder.id)"
          @drop.prevent="handleDrop(folder)"
        >
          <button
            v-if="folder.hasChildren"
            type="button"
            class="folder-toggle"
            @click.stop="toggle(folder.id)"
          >
            <el-icon :size="12">
              <ArrowRight v-if="!expandedIds.has(folder.id)" />
              <ArrowDown v-else />
            </el-icon>
          </button>
          <span v-else class="folder-toggle folder-toggle--placeholder"></span>

          <el-icon :size="16"><FolderIcon /></el-icon>
          <span class="folder-name">{{ folder.name }}</span>
          <span class="folder-count">{{ folder.asset_count }}</span>
          <div class="folder-hover-actions">
            <el-button size="small" text @click.stop="$emit('create-child', folder)">
              <el-icon :size="14"><Plus /></el-icon>
            </el-button>
            <el-button size="small" text @click.stop="$emit('rename', folder)">
              <el-icon :size="14"><Edit /></el-icon>
            </el-button>
            <el-button size="small" text type="danger" @click.stop="$emit('delete', folder)">
              <el-icon :size="14"><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <teleport to="body">
      <div
        v-if="contextMenu.visible"
        class="folder-context-menu"
        :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
      >
        <div class="ctx-item" @click="$emit('create-child', contextMenu.folder); contextMenu.visible = false">新建子文件夹</div>
        <div class="ctx-item" @click="$emit('rename', contextMenu.folder); contextMenu.visible = false">重命名</div>
        <div class="ctx-item danger" @click="$emit('delete', contextMenu.folder); contextMenu.visible = false">删除</div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ArrowDown, ArrowRight, Delete, Edit, Files, FolderOpened, Plus } from '@element-plus/icons-vue'
import { Folder as FolderIcon } from '@element-plus/icons-vue'
import type { Folder } from '../composables/useFolders'

type TreeFolder = Folder & {
  depth: number
  hasChildren: boolean
}

const props = defineProps<{
  folders: Folder[]
  activeId: string
  totalCount: number
  uncategorizedCount: number
}>()

const emit = defineEmits(['select', 'create', 'create-child', 'rename', 'delete', 'move'])

const expandedIds = ref<Set<number>>(new Set())
const contextMenu = reactive({ visible: false, x: 0, y: 0, folder: null as TreeFolder | null })
const dragFolderId = ref<number | null>(null)
const dropTargetId = ref<number | 'all' | null>(null)

const childrenMap = computed(() => {
  const map = new Map<number | null, Folder[]>()
  for (const folder of props.folders) {
    const key = folder.parent_id ?? null
    const list = map.get(key) || []
    list.push(folder)
    map.set(key, list)
  }
  return map
})

const treeFolders = computed<TreeFolder[]>(() => {
  const result: TreeFolder[] = []
  const walk = (parentId: number | null, depth: number) => {
    const children = childrenMap.value.get(parentId) || []
    for (const folder of children) {
      const hasChildren = (childrenMap.value.get(folder.id) || []).length > 0
      result.push({ ...folder, depth, hasChildren })
      if (hasChildren && expandedIds.value.has(folder.id)) {
        walk(folder.id, depth + 1)
      }
    }
  }
  walk(null, 0)
  return result
})

watch(() => props.folders, (folders) => {
  const next = new Set(expandedIds.value)
  folders.forEach(folder => {
    if (folder.parent_id == null) next.add(folder.id)
  })
  expandedIds.value = next
}, { immediate: true })

watch(() => props.activeId, (activeId) => {
  const id = Number(activeId)
  if (!Number.isFinite(id)) return
  const next = new Set(expandedIds.value)
  let cursor = props.folders.find(folder => folder.id === id) || null
  while (cursor?.parent_id != null) {
    next.add(cursor.parent_id)
    cursor = props.folders.find(folder => folder.id === cursor?.parent_id) || null
  }
  expandedIds.value = next
}, { immediate: true })

const toggle = (id: number) => {
  const next = new Set(expandedIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expandedIds.value = next
}

const openContextMenu = (e: MouseEvent, folder: TreeFolder) => {
  contextMenu.x = e.clientX
  contextMenu.y = e.clientY
  contextMenu.folder = folder
  contextMenu.visible = true
  const close = () => {
    contextMenu.visible = false
    document.removeEventListener('click', close)
  }
  setTimeout(() => document.addEventListener('click', close), 0)
}

const isDescendantOf = (targetId: number, sourceId: number): boolean => {
  let cursor = props.folders.find(folder => folder.id === targetId) || null
  while (cursor?.parent_id != null) {
    if (cursor.parent_id === sourceId) return true
    cursor = props.folders.find(folder => folder.id === cursor?.parent_id) || null
  }
  return false
}

const handleDragStart = (folder: TreeFolder) => {
  dragFolderId.value = folder.id
}

const handleDragEnd = () => {
  dragFolderId.value = null
  dropTargetId.value = null
}

const handleDragOver = (folder: TreeFolder) => {
  if (dragFolderId.value == null || dragFolderId.value === folder.id) return
  if (isDescendantOf(folder.id, dragFolderId.value)) return
  dropTargetId.value = folder.id
}

const handleRootDragOver = (target: 'all') => {
  if (dragFolderId.value == null) return
  dropTargetId.value = target
}

const handleDropLeave = (target: number | 'all') => {
  if (dropTargetId.value === target) {
    dropTargetId.value = null
  }
}

const handleDrop = (folder: TreeFolder) => {
  if (dragFolderId.value == null || dragFolderId.value === folder.id) return
  if (isDescendantOf(folder.id, dragFolderId.value)) return
  emit('move', dragFolderId.value, folder.id)
  handleDragEnd()
}

const handleDropToRoot = () => {
  if (dragFolderId.value == null) return
  emit('move', dragFolderId.value, null)
  handleDragEnd()
}
</script>

<style scoped>
.folder-sidebar {
  width: 200px;
  min-width: 200px;
  border-right: 1px solid var(--border-color);
  background: var(--card-bg);
  display: flex;
  flex-direction: column;
  border-radius: 16px 0 0 16px;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 16px 12px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-title {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.sidebar-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}

.folder-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.folder-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
}

.folder-item:hover {
  background: rgba(34, 197, 94, 0.06);
}

.folder-item.is-active {
  background: rgba(34, 197, 94, 0.12);
  color: var(--primary-color);
  font-weight: 600;
}

.folder-item.is-drop-target {
  outline: 1px dashed var(--primary-color);
  background: rgba(34, 197, 94, 0.1);
}

.folder-item--root {
  padding-left: 12px !important;
}

.folder-toggle {
  width: 14px;
  min-width: 14px;
  height: 14px;
  border: none;
  background: transparent;
  padding: 0;
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.folder-toggle--placeholder {
  cursor: default;
}

.folder-name {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-color);
  padding: 1px 7px;
  border-radius: 10px;
}

.folder-hover-actions {
  display: none;
  gap: 2px;
  margin-left: auto;
}

.folder-item:hover .folder-hover-actions {
  display: flex;
}

.folder-context-menu {
  position: fixed;
  z-index: 9999;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  padding: 4px 0;
  min-width: 140px;
}

.ctx-item {
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.ctx-item:hover {
  background: rgba(34, 197, 94, 0.08);
}

@media (max-width: 767px) {
  .folder-sidebar {
    width: 100%;
    min-width: unset;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
    border-radius: 16px 16px 0 0;
    max-height: 200px;
  }
}
</style>
