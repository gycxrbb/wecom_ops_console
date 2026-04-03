<template>
  <div class="folder-sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">文件夹</span>
      <el-button size="small" text type="primary" @click="$emit('create')">
        <el-icon><Plus /></el-icon>
      </el-button>
    </div>
    <div class="folder-list">
      <div
        class="folder-item"
        :class="{ 'is-active': activeId === 'all' }"
        @click="$emit('select', 'all')"
      >
        <el-icon :size="16"><Files /></el-icon>
        <span class="folder-name">全部素材</span>
        <span class="folder-count">{{ totalCount }}</span>
      </div>
      <div
        class="folder-item"
        :class="{ 'is-active': activeId === 'uncategorized' }"
        @click="$emit('select', 'uncategorized')"
      >
        <el-icon :size="16"><FolderOpened /></el-icon>
        <span class="folder-name">未分类</span>
        <span class="folder-count">{{ uncategorizedCount }}</span>
      </div>
      <el-divider style="margin: 8px 0" />
      <div
        v-for="folder in folders"
        :key="folder.id"
        class="folder-item"
        :class="{ 'is-active': activeId === String(folder.id) }"
        @click="$emit('select', String(folder.id))"
        @contextmenu.prevent="openContextMenu($event, folder)"
      >
        <el-icon :size="16"><FolderIcon /></el-icon>
        <span class="folder-name">{{ folder.name }}</span>
        <span class="folder-count">{{ folder.asset_count }}</span>
        <div class="folder-hover-actions" v-if="hoveredFolderId === folder.id">
          <el-button size="small" text @click.stop="$emit('rename', folder)">
            <el-icon :size="14"><Edit /></el-icon>
          </el-button>
          <el-button size="small" text type="danger" @click.stop="confirmDelete(folder)">
            <el-icon :size="14"><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <teleport to="body">
      <div v-if="contextMenu.visible" class="folder-context-menu" :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }">
        <div class="ctx-item" @click="$emit('rename', contextMenu.folder); contextMenu.visible = false">重命名</div>
        <div class="ctx-item danger" @click="confirmDelete(contextMenu.folder!); contextMenu.visible = false">删除</div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { Plus, FolderOpened, Files, Edit, Delete } from '@element-plus/icons-vue'
import { Folder as FolderIcon } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import type { Folder } from '../composables/useFolders'

const props = defineProps<{
  folders: Folder[]
  activeId: string
  totalCount: number
  uncategorizedCount: number
}>()

defineEmits(['select', 'create', 'rename'])

const hoveredFolderId = ref<number | null>(null)
const contextMenu = reactive({ visible: false, x: 0, y: 0, folder: null as Folder | null })

const openContextMenu = (e: MouseEvent, folder: Folder) => {
  contextMenu.x = e.clientX
  contextMenu.y = e.clientY
  contextMenu.folder = folder
  contextMenu.visible = true
  const close = () => { contextMenu.visible = false; document.removeEventListener('click', close) }
  setTimeout(() => document.addEventListener('click', close), 0)
}

const confirmDelete = async (folder: Folder) => {
  try {
    await ElMessageBox.confirm(`确定删除文件夹「${folder.name}」吗？仅可删除空文件夹。`, '删除文件夹', { type: 'warning' })
    // Parent handles the actual delete
    if (props.folders.find(f => f.id === folder.id)) {
      // emit a delete event
    }
  } catch { /* cancelled */ }
}
</script>

<style scoped>
.folder-sidebar {
  width: 220px;
  min-width: 220px;
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
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
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
  display: flex;
  gap: 2px;
  position: absolute;
  right: 8px;
}

.folder-context-menu {
  position: fixed;
  z-index: 9999;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
  padding: 4px 0;
  min-width: 120px;
}
.ctx-item {
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}
.ctx-item:hover { background: rgba(34, 197, 94, 0.08); }
.ctx-item.danger { color: #f56c6c; }
.ctx-item.danger:hover { background: rgba(245, 108, 108, 0.08); }
</style>
