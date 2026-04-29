<template>
  <div class="prompt-manage-page">
    <div class="page-header">
      <h2>提示词管理</h2>
      <div class="header-actions">
        <el-select v-model="selectedSnapshot" placeholder="切换全局版本" size="small" style="width: 200px" @change="handleSnapshotChange">
          <el-option v-for="s in snapshots" :key="s.id" :label="`${s.name}（${s.template_count} 条）`" :value="s.id" />
        </el-select>
        <el-button size="small" @click="handleCreateSnapshot">保存当前快照</el-button>
        <el-button type="primary" size="small" @click="handleReseed" :loading="reseeding">
          从文件重新导入
        </el-button>
      </div>
    </div>

    <div class="main-layout">
      <!-- Left: tree -->
      <div class="tree-panel">
        <el-tree
          :data="treeData"
          :props="{ label: 'label', children: 'children' }"
          highlight-current
          default-expand-all
          @node-click="onNodeClick"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <span>{{ data.label }}</span>
              <el-tag v-if="data.version" size="small" type="info">{{ data.version }}</el-tag>
            </span>
          </template>
        </el-tree>
      </div>

      <!-- Right: editor -->
      <div class="editor-panel" v-if="current">
        <div class="editor-header">
          <div>
            <span class="editor-title">{{ current.label }}</span>
            <el-tag size="small">{{ current.version }}</el-tag>
            <span class="editor-meta">{{ current.layer }} / {{ current.key }}</span>
          </div>
          <div>
            <el-button size="small" @click="showVersions = !showVersions">
              {{ showVersions ? '隐藏版本' : '版本历史' }}
            </el-button>
            <el-button type="primary" size="small" @click="handleSave" :loading="saving">
              保存
            </el-button>
          </div>
        </div>

        <el-input
          v-model="editContent"
          type="textarea"
          :rows="24"
          class="editor-textarea"
          placeholder="提示词内容"
        />

        <div class="save-bar" v-if="editContent !== current.content">
          <el-input v-model="changeNote" placeholder="变更说明（可选）" size="small" style="width: 300px" />
          <el-button type="primary" size="small" @click="handleSave" :loading="saving">
            保存为新版本
          </el-button>
        </div>

        <!-- Version history -->
        <div v-if="showVersions" class="version-panel">
          <h4>版本历史</h4>
          <el-table :data="versions" size="small" v-loading="loadingVersions">
            <el-table-column prop="version" label="版本" width="80" />
            <el-table-column prop="change_note" label="说明" />
            <el-table-column prop="created_by" label="操作人" width="100" />
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" link @click="handlePreviewVersion(row)">查看</el-button>
                <el-button size="small" link type="warning" @click="handleRollback(row)">回滚</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div class="editor-panel empty-state" v-else>
        <el-empty description="请从左侧选择一个提示词模板" />
      </div>
    </div>

    <!-- Version preview dialog -->
    <el-dialog v-model="versionDialogVisible" title="版本内容预览" width="700px">
      <div v-if="previewVersion">
        <p><strong>版本：</strong>{{ previewVersion.version }} &nbsp; <strong>操作人：</strong>{{ previewVersion.created_by }}</p>
        <el-input type="textarea" :model-value="previewVersion.content" :rows="20" readonly />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '#/utils/request'

interface TemplateItem {
  id: number
  key: string
  label: string
  version: string
  layer: string
  content: string
  is_active: boolean
  updated_by: string | null
  updated_at: string | null
}

interface VersionItem {
  id: number
  version: string
  change_note: string | null
  content_length: number
  created_by: string | null
  created_at: string | null
}

const treeData = ref<any[]>([])
const current = ref<TemplateItem | null>(null)
const editContent = ref('')
const changeNote = ref('')
const saving = ref(false)
const reseeding = ref(false)

const showVersions = ref(false)
const versions = ref<VersionItem[]>([])
const loadingVersions = ref(false)

const versionDialogVisible = ref(false)
const previewVersion = ref<any>(null)

const snapshots = ref<any[]>([])
const selectedSnapshot = ref<number | null>(null)

const formatTime = (t: string | null) => t ? t.replace('T', ' ').slice(0, 19) : '-'

const buildTree = async () => {
  const res: any = await request.get('/v1/admin/prompt-templates/tree')
  const data = res as Record<string, any[]>
  treeData.value = Object.entries(data).map(([layerLabel, items]) => ({
    label: layerLabel,
    children: items.map((item: any) => ({
      label: item.label,
      id: item.id,
      key: item.key,
      version: item.version,
    })),
  }))
}

const onNodeClick = async (node: any) => {
  if (!node.id) return
  const res: any = await request.get(`/v1/admin/prompt-templates/${node.id}`)
  current.value = res
  editContent.value = res.content
  changeNote.value = ''
  if (showVersions.value) loadVersions()
}

const loadVersions = async () => {
  if (!current.value) return
  loadingVersions.value = true
  try {
    versions.value = await request.get(`/v1/admin/prompt-templates/${current.value.id}/versions`)
  } finally {
    loadingVersions.value = false
  }
}

const handleSave = async () => {
  if (!current.value) return
  saving.value = true
  try {
    const res: any = await request.put(`/v1/admin/prompt-templates/${current.value.id}`, {
      content: editContent.value,
      change_note: changeNote.value,
    })
    ElMessage.success(`已保存为 ${res.version}`)
    current.value.content = editContent.value
    current.value.version = res.version
    changeNote.value = ''
    buildTree()
    if (showVersions.value) loadVersions()
  } finally {
    saving.value = false
  }
}

const handlePreviewVersion = async (v: VersionItem) => {
  if (!current.value) return
  previewVersion.value = await request.get(
    `/v1/admin/prompt-templates/${current.value.id}/versions/${v.id}`
  )
  versionDialogVisible.value = true
}

const handleRollback = async (v: VersionItem) => {
  if (!current.value) return
  await ElMessageBox.confirm(`确定回滚到 ${v.version}？`, '确认回滚')
  await request.post(`/v1/admin/prompt-templates/${current.value.id}/rollback`, {
    version_id: v.id,
  })
  ElMessage.success('已回滚')
  onNodeClick({ id: current.value.id })
  buildTree()
}

const handleReseed = async () => {
  await ElMessageBox.confirm('将清空当前所有提示词并从 .md 文件重新导入，确定？', '确认重置')
  reseeding.value = true
  try {
    await request.post('/v1/admin/prompt-templates/seed')
    ElMessage.success('重新导入完成')
    current.value = null
    buildTree()
  } finally {
    reseeding.value = false
  }
}

const loadSnapshots = async () => {
  snapshots.value = await request.get('/v1/admin/prompt-templates/snapshots/list')
}

const handleSnapshotChange = async (snapshotId: number) => {
  const snap = snapshots.value.find((s: any) => s.id === snapshotId)
  if (!snap) return
  await ElMessageBox.confirm(
    `将把所有模板切换到快照「${snap.name}」的版本。不在该快照中的模板将保持当前内容。确定？`,
    '确认全局切换',
  )
  const res: any = await request.post('/v1/admin/prompt-templates/snapshots/switch', {
    snapshot_id: snapshotId,
  })
  ElMessage.success(res.message)
  current.value = null
  buildTree()
}

const handleCreateSnapshot = async () => {
  const res: any = await request.post('/v1/admin/prompt-templates/snapshots/create')
  ElMessage.success(`已创建快照「${res.name}」，包含 ${res.template_count} 个模板`)
  loadSnapshots()
}

onMounted(() => { buildTree(); loadSnapshots() })
</script>

<style scoped>
.prompt-manage-page { max-width: 1400px; margin: 0 auto; padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 18px; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.main-layout { display: flex; gap: 20px; min-height: 600px; }
.tree-panel { width: 260px; flex-shrink: 0; background: var(--el-bg-color); border-radius: 8px; padding: 16px; border: 1px solid var(--el-border-color-lighter); }
.editor-panel { flex: 1; background: var(--el-bg-color); border-radius: 8px; padding: 20px; border: 1px solid var(--el-border-color-lighter); }
.editor-panel.empty-state { display: flex; align-items: center; justify-content: center; }
.editor-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.editor-title { font-weight: 600; font-size: 16px; margin-right: 8px; }
.editor-meta { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 12px; }
.editor-textarea { font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; }
.save-bar { display: flex; gap: 12px; align-items: center; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--el-border-color-lighter); }
.version-panel { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--el-border-color-lighter); }
.version-panel h4 { margin: 0 0 12px 0; }
.tree-node { display: flex; align-items: center; gap: 6px; font-size: 13px; }
</style>
