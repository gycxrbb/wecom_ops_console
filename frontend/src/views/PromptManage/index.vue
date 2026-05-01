<template>
  <div class="prompt-manage-page">
    <div class="page-header">
      <h2>提示词管理</h2>
      <div class="header-actions">
        <el-tag v-if="currentSnapshot" type="success" effect="dark" size="large" style="margin-right: 8px">
          当前版本：{{ currentSnapshot }}
        </el-tag>
        <el-tag v-else type="warning" effect="dark" size="large" style="margin-right: 8px">
          自定义版本（未关联快照）
        </el-tag>
        <el-button size="small" @click="snapshotLogVisible = true">版本记录</el-button>
        <el-button size="small" type="success" @click="commitDialogVisible = true">提交快照</el-button>
        <el-button size="small" @click="handleReseed" :loading="reseeding">从文件重新导入</el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #title>
        数据库中的提示词即为 AI 实际使用的版本。新建的场景/风格会自动注册到 AI 教练面板下拉列表中。
      </template>
    </el-alert>

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
            <span v-if="!data.children" class="tree-node" :class="{ 'node-inactive': data.is_active === false }">
              <span>{{ data.label }}</span>
              <el-tag v-if="data.is_active === false" size="small" type="info">未启用</el-tag>
              <el-tag v-else-if="data.version" size="small" type="success">{{ data.version }}</el-tag>
            </span>
            <span v-else class="tree-folder">
              <span>{{ data.label }}</span>
              <el-button class="folder-add-btn" size="small" link @click.stop="openCreateDialog(data.layer)">
                <el-icon><Plus /></el-icon>
              </el-button>
            </span>
          </template>
        </el-tree>
      </div>

      <!-- Right: editor -->
      <div class="editor-panel" v-if="current">
        <div class="editor-header">
          <div>
            <span class="editor-title">{{ current.label }}</span>
            <el-tag v-if="current.is_active" size="small" type="success" effect="dark">{{ current.version }} 生效中</el-tag>
            <el-tag v-else size="small" type="warning" effect="dark">未启用 — AI 不加载此模板</el-tag>
            <span class="editor-meta">{{ current.layer }} / {{ current.key }}</span>
          </div>
          <div>
            <el-button size="small" @click="showVersions = !showVersions">
              {{ showVersions ? '隐藏版本' : '版本历史' }}
            </el-button>
            <el-button type="danger" size="small" @click="handleDelete">删除</el-button>
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
        <el-empty description="请从左侧选择一个提示词模板，或点击分组旁的 + 号新建" />
      </div>
    </div>

    <!-- Version preview dialog -->
    <el-dialog v-model="versionDialogVisible" title="版本内容预览" width="700px">
      <div v-if="previewVersion">
        <p><strong>版本：</strong>{{ previewVersion.version }} &nbsp; <strong>操作人：</strong>{{ previewVersion.created_by }}</p>
        <el-input type="textarea" :model-value="previewVersion.content" :rows="20" readonly />
      </div>
    </el-dialog>

    <!-- Create template dialog -->
    <el-dialog v-model="createDialogVisible" title="新建提示词模板" width="600px">
      <el-form label-width="80px">
        <el-form-item label="所属层">
          <el-input :model-value="createLayerLabel" readonly />
        </el-form-item>
        <el-form-item label="标识符">
          <el-input v-model="createForm.key" placeholder="英文标识，如 prescription_gen" />
          <div class="form-hint">仅允许小写字母、数字、下划线，且以字母开头</div>
        </el-form-item>
        <el-form-item label="中文名">
          <el-input v-model="createForm.label" placeholder="如：处方生成" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="createForm.content" type="textarea" :rows="12" placeholder="Markdown 提示词内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- Commit snapshot dialog (git commit) -->
    <el-dialog v-model="commitDialogVisible" title="提交快照" width="500px">
      <p style="color: var(--el-text-color-secondary); margin-bottom: 16px;">
        将当前所有提示词状态保存为一个快照版本，类似于 git commit。
      </p>
      <el-form label-width="80px">
        <el-form-item label="版本名">
          <el-input v-model="commitForm.name" placeholder="如 v3.0（留空自动生成）" />
        </el-form-item>
        <el-form-item label="更新说明">
          <el-input v-model="commitForm.description" type="textarea" :rows="4" placeholder="本次更新做了什么改动？如：新增处方生成场景、优化餐评 Few-shot 示例" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="commitDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCommitSnapshot" :loading="committing">提交</el-button>
      </template>
    </el-dialog>

    <!-- Snapshot log dialog (git log) -->
    <el-dialog v-model="snapshotLogVisible" title="版本记录" width="800px">
      <div v-loading="loadingSnapshotLog">
        <div v-for="snap in snapshots" :key="snap.id" class="snap-log-item">
          <div class="snap-log-header">
            <template v-if="editingSnapId === snap.id">
              <el-input v-model="editingSnap.name" size="small" style="width: 140px" />
              <el-button size="small" type="primary" link @click="handleSaveSnapEdit(snap)">保存</el-button>
              <el-button size="small" link @click="editingSnapId = null">取消</el-button>
            </template>
            <template v-else>
              <span class="snap-log-name">{{ snap.name }}</span>
              <el-tag v-if="snap.is_current" size="small" type="success" effect="dark">当前版本</el-tag>
              <el-button size="small" link @click="startEditSnap(snap)" style="font-size: 12px">编辑</el-button>
            </template>
            <el-tag size="small" type="info">{{ snap.template_count }} 条模板</el-tag>
            <span class="snap-log-meta">{{ snap.created_by }} · {{ formatTime(snap.created_at) }}</span>
            <div class="snap-log-actions">
              <el-button size="small" link @click="loadSnapshotDiff(snap.id)">查看变更</el-button>
              <el-button size="small" link type="warning" @click="handleSnapshotChange(snap.id)">切换到此版本</el-button>
            </div>
          </div>
          <div v-if="editingSnapId === snap.id" class="snap-edit-desc">
            <el-input v-model="editingSnap.description" type="textarea" :rows="2" size="small" placeholder="更新说明" />
          </div>
          <div v-else-if="snap.description" class="snap-log-desc">{{ snap.description }}</div>

          <!-- Diff panel for this snapshot -->
          <div v-if="activeDiffId === snap.id && snapshotDiff" class="snap-diff-panel">
            <div class="snap-diff-summary">
              <el-tag v-if="snapshotDiff.summary.added" size="small" type="success">+{{ snapshotDiff.summary.added }} 新增</el-tag>
              <el-tag v-if="snapshotDiff.summary.modified" size="small" type="warning">~{{ snapshotDiff.summary.modified }} 修改</el-tag>
              <el-tag v-if="snapshotDiff.summary.removed" size="small" type="danger">-{{ snapshotDiff.summary.removed }} 删除</el-tag>
              <el-tag v-if="snapshotDiff.summary.unchanged" size="small" type="info">{{ snapshotDiff.summary.unchanged }} 未变</el-tag>
              <span v-if="snapshotDiff.previous_snapshot" class="snap-diff-vs">
                对比 {{ snapshotDiff.previous_snapshot.name }}
              </span>
              <span v-else class="snap-diff-vs">初始快照</span>
            </div>
            <el-table :data="snapshotDiff.changes" size="small" class="snap-diff-table">
              <el-table-column prop="key" label="模板" width="200" />
              <el-table-column label="变更" width="80">
                <template #default="{ row }">
                  <el-tag v-if="row.change === 'added'" size="small" type="success">新增</el-tag>
                  <el-tag v-else-if="row.change === 'modified'" size="small" type="warning">修改</el-tag>
                  <el-tag v-else-if="row.change === 'removed'" size="small" type="danger">删除</el-tag>
                  <el-tag v-else size="small" type="info">未变</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="版本">
                <template #default="{ row }">
                  <span v-if="row.change === 'modified'">{{ row.from_version }} → {{ row.to_version }}</span>
                  <span v-else>{{ row.version }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
        <el-empty v-if="!snapshots.length" description="暂无快照记录" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
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

const LAYER_LABELS: Record<string, string> = {
  base: '基础层 (L1/L2)',
  scene: '场景策略 (L3)',
  style: '风格模板',
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

const createDialogVisible = ref(false)
const creating = ref(false)
const createLayer = ref('')
const createForm = ref({ key: '', label: '', content: '' })

const commitDialogVisible = ref(false)
const committing = ref(false)
const commitForm = ref({ name: '', description: '' })

const snapshotLogVisible = ref(false)
const loadingSnapshotLog = ref(false)
const activeDiffId = ref<number | null>(null)
const snapshotDiff = ref<any>(null)

const editingSnapId = ref<number | null>(null)
const editingSnap = ref({ name: '', description: '' })
const currentSnapshot = ref<string | null>(null)

const createLayerLabel = computed(() => LAYER_LABELS[createLayer.value] || createLayer.value)

const formatTime = (t: string | null) => t ? t.replace('T', ' ').slice(0, 19) : '-'

const buildTree = async () => {
  const res: any = await request.get('/v1/admin/prompt-templates/tree')
  const data = res as Record<string, any>
  const layerKeyMap: Record<string, string> = { '基础层 (L1/L2)': 'base', '场景策略 (L3)': 'scene', '风格模板': 'style' }

  // Extract current snapshot info
  const meta = data['__meta__']
  currentSnapshot.value = meta?.current_snapshot?.name ?? null
  delete data['__meta__']

  treeData.value = Object.entries(data).map(([layerLabel, items]) => ({
    label: layerLabel,
    layer: layerKeyMap[layerLabel] || layerLabel,
    children: (items as any[]).map((item: any) => ({
      label: item.label,
      id: item.id,
      key: item.key,
      version: item.version,
      is_active: item.is_active,
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

const handleDelete = async () => {
  if (!current.value) return
  await ElMessageBox.confirm(
    `确定删除「${current.value.label}」（${current.value.key}）？删除后 AI 将不再使用此模板，相关版本历史也会清除。`,
    '确认删除',
    { type: 'warning' },
  )
  await request.delete(`/v1/admin/prompt-templates/${current.value.id}`)
  ElMessage.success('已删除')
  current.value = null
  buildTree()
}

const openCreateDialog = (layer: string) => {
  createLayer.value = layer
  createForm.value = { key: '', label: '', content: '' }
  createDialogVisible.value = true
}

const handleCreate = async () => {
  if (!createForm.value.key || !createForm.value.label) {
    ElMessage.warning('请填写标识符和中文名')
    return
  }
  creating.value = true
  try {
    await request.post('/v1/admin/prompt-templates', {
      layer: createLayer.value,
      key: createForm.value.key,
      label: createForm.value.label,
      content: createForm.value.content,
    })
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    current.value = null
    buildTree()
  } finally {
    creating.value = false
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

// ── Snapshot management (git-like) ──────────────────────────────────────────

const loadSnapshots = async () => {
  snapshots.value = await request.get('/v1/admin/prompt-templates/snapshots/list')
}

const handleCommitSnapshot = async () => {
  committing.value = true
  try {
    const res: any = await request.post('/v1/admin/prompt-templates/snapshots/create', {
      name: commitForm.value.name,
      description: commitForm.value.description,
    })
    ElMessage.success(`已提交快照「${res.name}」，包含 ${res.template_count} 个模板`)
    commitDialogVisible.value = false
    commitForm.value = { name: '', description: '' }
    loadSnapshots()
  } finally {
    committing.value = false
  }
}

const loadSnapshotDiff = async (snapshotId: number) => {
  if (activeDiffId.value === snapshotId) {
    activeDiffId.value = null
    snapshotDiff.value = null
    return
  }
  activeDiffId.value = snapshotId
  snapshotDiff.value = await request.get(`/v1/admin/prompt-templates/snapshots/${snapshotId}/diff`)
}

const startEditSnap = (snap: any) => {
  editingSnapId.value = snap.id
  editingSnap.value = {
    name: snap.name || '',
    description: snap.description || '',
  }
}

const handleSaveSnapEdit = async (snap: any) => {
  await request.put(`/v1/admin/prompt-templates/snapshots/${snap.id}`, {
    name: editingSnap.value.name,
    description: editingSnap.value.description,
  })
  snap.name = editingSnap.value.name
  snap.description = editingSnap.value.description
  editingSnapId.value = null
  ElMessage.success('快照信息已更新')
}

const handleSnapshotChange = async (snapshotId: number) => {
  const snap = snapshots.value.find((s: any) => s.id === snapshotId)
  if (!snap) return
  await ElMessageBox.confirm(
    `将把所有模板切换到快照「${snap.name}」的版本。不在该快照中的模板将被停用。确定？`,
    '确认全局切换',
  )
  const res: any = await request.post('/v1/admin/prompt-templates/snapshots/switch', {
    snapshot_id: snapshotId,
  })
  ElMessage.success(res.message)
  snapshotLogVisible.value = false
  current.value = null
  buildTree()
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
.tree-panel { width: 280px; flex-shrink: 0; background: var(--el-bg-color); border-radius: 8px; padding: 16px; border: 1px solid var(--el-border-color-lighter); }
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
.tree-folder { display: flex; align-items: center; gap: 6px; font-size: 13px; width: 100%; justify-content: space-between; }
.tree-folder span:first-child { font-weight: 600; }
.folder-add-btn { font-size: 14px; }
.node-inactive { opacity: 0.5; }
.form-hint { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }

/* Snapshot log (git log style) */
.snap-log-item { padding: 12px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.snap-log-item:last-child { border-bottom: none; }
.snap-log-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.snap-log-name { font-weight: 600; font-size: 15px; }
.snap-log-meta { color: var(--el-text-color-secondary); font-size: 12px; }
.snap-log-actions { margin-left: auto; }
.snap-log-desc { color: var(--el-text-color-regular); font-size: 13px; margin-top: 6px; padding-left: 2px; white-space: pre-wrap; }

/* Snapshot diff */
.snap-diff-panel { margin-top: 10px; padding: 12px; background: var(--el-fill-color-lighter); border-radius: 6px; }
.snap-diff-summary { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; }
.snap-diff-vs { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px; }
.snap-diff-table { background: transparent; }
</style>
