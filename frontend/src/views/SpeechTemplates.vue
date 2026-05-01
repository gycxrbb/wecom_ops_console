<template>
  <div class="speech-page">
    <div class="speech-header">
      <div class="speech-header__left">
        <span class="speech-header__icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#22c55e" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </span>
        <div>
          <h2>话术管理</h2>
          <p class="speech-header__desc">管理运营干预话术，支持 CSV 批量导入并进入 RAG 语料索引</p>
        </div>
      </div>
      <div class="speech-header__actions">
        <el-button type="primary" @click="openImportDialog">
          <el-icon><Upload /></el-icon>
          导入 CSV
        </el-button>
      </div>
    </div>

    <div v-loading="loading" class="speech-body">
      <div v-if="!loading && scenes.length" class="speech-layout">
        <div class="speech-sidebar">
          <div v-for="l1 in sidebarTree" :key="l1.name" class="speech-cat-group">
            <div class="speech-cat-l1" @click="toggleNode(`l1-${l1.name}`)">
              <span class="speech-cat-arrow" :class="{ 'is-expanded': expandedState[`l1-${l1.name}`] }">&#9654;</span>
              <span class="speech-cat-l1-icon" v-html="getCategoryIcon(l1.name)"></span>
              <span class="speech-cat-name">{{ l1.name }}</span>
            </div>
            <template v-if="expandedState[`l1-${l1.name}`]">
              <div v-for="l2 in l1.children" :key="l2.name" class="speech-cat-l2-wrap">
                <div class="speech-cat-l2" @click="toggleNode(`l2-${l2.name}`)">
                  <span class="speech-cat-arrow" :class="{ 'is-expanded': expandedState[`l2-${l2.name}`] }">&#9654;</span>
                  <span class="speech-cat-name">{{ l2.name }}</span>
                  <span class="speech-cat-count">{{ l2.sceneCount }}</span>
                </div>
                <template v-if="expandedState[`l2-${l2.name}`]">
                  <div
                    v-for="scene in l2.scenes"
                    :key="scene.key"
                    class="speech-scene-item"
                    :class="{ 'is-active': activeScene === scene.key }"
                    @click="selectScene(scene.key)"
                  >
                    <span class="speech-scene-item__label">{{ scene.label }}</span>
                    <span class="speech-scene-item__key">{{ scene.key }}</span>
                  </div>
                </template>
              </div>
            </template>
          </div>

          <div v-if="uncategorizedScenes.length" class="speech-cat-group">
            <div class="speech-cat-l1" @click="toggleNode('uncategorized')">
              <span class="speech-cat-arrow" :class="{ 'is-expanded': expandedState['uncategorized'] }">&#9654;</span>
              <span class="speech-cat-l1-icon" v-html="getCategoryIcon('未分类')"></span>
              <span class="speech-cat-name">未分类</span>
              <span class="speech-cat-count">{{ uncategorizedScenes.length }}</span>
            </div>
            <template v-if="expandedState['uncategorized']">
              <div
                v-for="scene in uncategorizedScenes"
                :key="scene.key"
                class="speech-scene-item"
                :class="{ 'is-active': activeScene === scene.key }"
                @click="selectScene(scene.key)"
              >
                <span class="speech-scene-item__label">{{ scene.label }}</span>
                <span class="speech-scene-item__key">{{ scene.key }}</span>
              </div>
            </template>
          </div>
        </div>

        <div class="speech-editor" v-if="activeScene">
          <div class="speech-editor-card">
            <div class="speech-editor-card__header">
              <div class="speech-editor-card__title">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#22c55e" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                <span>{{ currentSceneLabel }}</span>
                <el-tag size="small" type="info">{{ activeScene }}</el-tag>
              </div>
              <div class="speech-editor-card__styles">
                <button
                  v-for="tpl in currentTemplates"
                  :key="tpl.style"
                  class="speech-style-btn"
                  :class="{ 'is-active': activeStyle === tpl.style }"
                  @click="activeStyle = tpl.style"
                >
                  {{ styleLabel(tpl.style) }}
                </button>
              </div>
            </div>

            <div v-if="currentEditingTpl" class="speech-editor-card__body">
              <div class="speech-editor-card__content-label">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#22c55e" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                <span>话术内容</span>
                <span class="speech-char-count" :class="{ 'is-over': currentEditingTpl._editContent.length > 2000 }">
                  {{ currentEditingTpl._editContent.length }}/2000
                </span>
              </div>
              <el-input
                v-model="currentEditingTpl._editContent"
                type="textarea"
                :rows="10"
                :placeholder="isPointsScene ? '话术内容（支持 {name} {rank} {detail} {activity} 占位符）' : '请输入话术内容'"
              />
              <div class="speech-editor-card__footer">
                <span v-if="isPointsScene" class="speech-editor-card__hint">占位符: {name} {rank} {detail} {activity}</span>
                <span v-else></span>
                <el-button
                  type="primary"
                  :loading="currentEditingTpl._saving"
                  :disabled="currentEditingTpl._editContent === currentEditingTpl.content"
                  @click="saveTemplate(currentEditingTpl)"
                >
                  保存
                </el-button>
              </div>
            </div>

            <div v-if="!currentTemplates.length" class="speech-editor-card__empty">
              该场景暂无模板
            </div>
          </div>
        </div>
      </div>

      <div v-if="!loading && !scenes.length" class="speech-empty">
        暂无话术数据
      </div>
    </div>

    <el-dialog v-model="importDialogVisible" title="导入话术 CSV" width="720px">
      <div class="speech-import">
        <el-upload
          drag
          :auto-upload="false"
          :limit="1"
          accept=".csv,text/csv"
          :on-change="handleImportFileChange"
          :on-remove="handleImportFileRemove"
        >
          <div class="speech-import__drop">拖拽 CSV 到这里，或点击选择文件</div>
          <div class="el-upload__tip">字段兼容 source_id、source_type、title、clean_content、summary、intervention_scene、question_type、tone、status</div>
        </el-upload>

        <div class="speech-import__options">
          <el-checkbox v-model="importIndexRag">导入后同步 RAG 索引</el-checkbox>
        </div>

        <div v-if="importResult" class="speech-import__result">
          <div class="speech-import__summary">
            <div>
              <span>新增</span>
              <strong>{{ importResult.created }}</strong>
            </div>
            <div>
              <span>更新</span>
              <strong>{{ importResult.updated }}</strong>
            </div>
            <div>
              <span>跳过</span>
              <strong>{{ importResult.skipped }}</strong>
            </div>
            <div>
              <span>错误</span>
              <strong>{{ importResult.errors?.length || 0 }}</strong>
            </div>
          </div>

          <el-alert
            v-if="importResult.errors?.length"
            type="warning"
            :closable="false"
            show-icon
            class="speech-import__errors"
          >
            <template #title>
              {{ importResult.errors.slice(0, 3).join('；') }}
            </template>
          </el-alert>

          <el-table v-if="importResult.rows?.length" :data="importResult.rows" size="small" max-height="220">
            <el-table-column prop="action" label="动作" width="90" />
            <el-table-column prop="scene_key" label="场景" width="150" />
            <el-table-column prop="style" label="风格" width="130" />
            <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
          </el-table>
        </div>
      </div>

      <template #footer>
        <el-button @click="importDialogVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :disabled="!importFile"
          :loading="importing"
          @click="submitCsvImport"
        >
          开始导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'SpeechTemplates' })
import { ref, computed, reactive, watch, onMounted } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import request from '#/utils/request'

type Template = {
  id: number
  scene_key: string
  style: string
  label: string
  content: string
  is_builtin: number
  _editContent: string
  _saving: boolean
}

type Scene = {
  key: string
  label: string
  styles: string[]
  category_id?: number
  category_l1?: string
  category_l2?: string
}

type CategoryL2Node = {
  name: string
  sceneCount: number
  scenes: Scene[]
}

type CategoryL1Node = {
  name: string
  children: CategoryL2Node[]
}

type ImportResult = {
  created: number
  updated: number
  skipped: number
  errors: string[]
  rows: Array<{
    source_id: string
    title: string
    scene_key: string
    style: string
    action: string
  }>
  rag_index?: Record<string, number> | null
}

const loading = ref(true)
const scenes = ref<Scene[]>([])
const templatesMap = ref<Record<string, Template[]>>({})
const activeScene = ref('')
const activeStyle = ref('')
const expandedState = reactive<Record<string, boolean>>({})
const importDialogVisible = ref(false)
const importFile = ref<File | null>(null)
const importIndexRag = ref(true)
const importing = ref(false)
const importResult = ref<ImportResult | null>(null)

const sidebarTree = computed<CategoryL1Node[]>(() => {
  const l1Map = new Map<string, Map<string, Scene[]>>()
  for (const scene of scenes.value) {
    const l1 = scene.category_l1 || ''
    const l2 = scene.category_l2 || ''
    if (!l1 || !l2) continue
    if (!l1Map.has(l1)) l1Map.set(l1, new Map())
    const l2Map = l1Map.get(l1)!
    if (!l2Map.has(l2)) l2Map.set(l2, [])
    l2Map.get(l2)!.push(scene)
  }
  const result: CategoryL1Node[] = []
  for (const [l1Name, l2Map] of l1Map) {
    const children: CategoryL2Node[] = []
    for (const [l2Name, l2Scenes] of l2Map) {
      children.push({ name: l2Name, sceneCount: l2Scenes.length, scenes: l2Scenes })
    }
    result.push({ name: l1Name, children })
  }
  return result
})

const uncategorizedScenes = computed(() =>
  scenes.value.filter(s => !s.category_l1 || !s.category_l2)
)

const currentSceneLabel = computed(() => {
  const s = scenes.value.find(s => s.key === activeScene.value)
  return s?.label || activeScene.value
})

const currentTemplates = computed(() =>
  templatesMap.value[activeScene.value] || []
)

const currentEditingTpl = computed(() =>
  currentTemplates.value.find(t => t.style === activeStyle.value) || currentTemplates.value[0] || null
)

const selectScene = (key: string) => {
  activeScene.value = key
  const tpls = templatesMap.value[key]
  if (tpls?.length) {
    activeStyle.value = tpls[0].style
  }
}

const toggleNode = (key: string) => {
  expandedState[key] = !expandedState[key]
}

const styleLabel = (style: string) => {
  const map: Record<string, string> = {
    professional: '专业风格',
    encouraging: '鼓励风格',
    competitive: '竞争风格',
  }
  return map[style] || style
}

const getCategoryIcon = (name: string): string => {
  const svg = (paths: string) =>
    `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`
  if (name.includes('健康')) return svg('<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78z"/>')
  if (name.includes('社区')) return svg('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>')
  if (name.includes('服务') || name.includes('支持')) return svg('<path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>')
  if (name.includes('系统')) return svg('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>')
  return svg('<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>')
}

const isPointsScene = computed(() => {
  const scene = scenes.value.find(s => s.key === activeScene.value)
  return scene?.category_l2 === '积分管理'
})

function expandAllNodes() {
  for (const l1 of sidebarTree.value) {
    expandedState[`l1-${l1.name}`] = true
    for (const l2 of l1.children) {
      expandedState[`l2-${l2.name}`] = true
    }
  }
  if (uncategorizedScenes.value.length) {
    expandedState['uncategorized'] = true
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const [scenesData, templatesData]: [any[], any] = await Promise.all([
      request.get('/v1/speech-templates/scenes'),
      request.get('/v1/speech-templates'),
    ])
    scenes.value = scenesData
    const map: Record<string, Template[]> = {}
    for (const [key, list] of Object.entries(templatesData as Record<string, any[]>)) {
      map[key] = list.map((t: any) => ({
        ...t,
        _editContent: t.content,
        _saving: false,
      }))
    }
    templatesMap.value = map
    if (scenes.value.length && (!activeScene.value || !scenes.value.some(s => s.key === activeScene.value))) {
      const first = scenes.value.find(s => map[s.key]?.length)
      activeScene.value = first?.key || scenes.value[0].key
    }
    const tpls = map[activeScene.value]
    if (tpls?.length && !tpls.some(t => t.style === activeStyle.value)) {
      activeStyle.value = tpls[0].style
    }
    expandAllNodes()
  } catch (e) {
    console.error(e)
    ElMessage.error('加载话术模板失败')
  } finally {
    loading.value = false
  }
}

const openImportDialog = () => {
  importDialogVisible.value = true
  importFile.value = null
  importResult.value = null
}

const handleImportFileChange = (uploadFile: UploadFile) => {
  const raw = uploadFile.raw
  if (!raw) return
  if (!(raw.name || '').toLowerCase().endsWith('.csv')) {
    importFile.value = null
    ElMessage.warning('请上传 CSV 文件')
    return
  }
  importFile.value = raw
  importResult.value = null
}

const handleImportFileRemove = () => {
  importFile.value = null
  importResult.value = null
}

const submitCsvImport = async () => {
  if (!importFile.value) {
    ElMessage.warning('请先选择 CSV 文件')
    return
  }
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    formData.append('index_rag', String(importIndexRag.value))
    const result: ImportResult = await request.post('/v1/speech-templates/import-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importResult.value = result
    await fetchData()
    const firstRow = result.rows?.[0]
    if (firstRow?.scene_key) activeScene.value = firstRow.scene_key
    if (result.errors?.length) {
      ElMessage.warning(`导入完成，${result.errors.length} 条需要处理`)
    } else {
      ElMessage.success(`导入完成：新增 ${result.created}，更新 ${result.updated}`)
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('CSV 导入失败')
  } finally {
    importing.value = false
  }
}

const saveTemplate = async (tpl: Template) => {
  if (!tpl.id) return
  tpl._saving = true
  try {
    await request.put(`/v1/speech-templates/${tpl.id}`, {
      content: tpl._editContent,
      label: tpl.label,
    })
    tpl.content = tpl._editContent
    ElMessage.success('话术已保存')
  } catch (e) {
    console.error(e)
    ElMessage.error('保存失败')
  } finally {
    tpl._saving = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.speech-page {
  padding: 0;
}
.speech-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}
.speech-header__left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.speech-header__icon {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: #f0fdf4;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
html.dark .speech-header__icon {
  background: rgba(34, 197, 94, 0.15);
}
.speech-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}
.speech-header__desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 6px 0 0;
}
.speech-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.speech-body {
  min-height: 300px;
}
.speech-layout {
  display: flex;
  gap: 24px;
  align-items: stretch;
}
.speech-sidebar {
  width: 280px;
  flex-shrink: 0;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--card-bg);
  overflow-y: auto;
  max-height: calc(100vh - 200px);
}
.speech-cat-group {
  border-bottom: 1px solid var(--border-color);
}
.speech-cat-group:last-child {
  border-bottom: none;
}
.speech-cat-l1 {
  padding: 14px 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  transition: background 0.15s;
  user-select: none;
}
.speech-cat-l1:hover {
  background: var(--fill-color-light, #f5f7fa);
}
html.dark .speech-cat-l1:hover {
  background: rgba(255, 255, 255, 0.06);
}
.speech-cat-l1-icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.speech-cat-l2-wrap {
  border-top: 1px solid var(--border-color);
}
.speech-cat-l2 {
  padding: 10px 16px 10px 32px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  transition: background 0.15s;
  user-select: none;
}
.speech-cat-l2:hover {
  background: var(--fill-color-light, #f5f7fa);
}
html.dark .speech-cat-l2:hover {
  background: rgba(255, 255, 255, 0.04);
}
.speech-cat-arrow {
  font-size: 9px;
  color: var(--text-muted);
  transition: transform 0.2s;
  flex-shrink: 0;
}
.speech-cat-arrow.is-expanded {
  transform: rotate(90deg);
}
.speech-cat-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.speech-cat-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--fill-color, #f0f0f0);
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
}
html.dark .speech-cat-count {
  background: rgba(255, 255, 255, 0.1);
}
.speech-scene-item {
  padding: 10px 16px 10px 48px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--border-color);
  transition: background 0.15s;
}
.speech-scene-item:hover {
  background: var(--fill-color-light, #f5f7fa);
}
html.dark .speech-scene-item:hover {
  background: rgba(255, 255, 255, 0.04);
}
.speech-scene-item.is-active {
  background: #f0fdf4;
  border-left: 3px solid #22c55e;
}
html.dark .speech-scene-item.is-active {
  background: rgba(34, 197, 94, 0.12);
}
.speech-scene-item__label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}
.speech-scene-item__key {
  font-size: 12px;
  color: var(--text-muted);
}
.speech-editor {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.speech-editor-card {
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  flex: 1;
  display: flex;
  flex-direction: column;
}
html.dark .speech-editor-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}
.speech-editor-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 28px;
  border-bottom: 1px solid var(--border-color);
}
.speech-editor-card__title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}
.speech-editor-card__title .el-tag {
  font-size: 12px;
}
.speech-editor-card__styles {
  display: flex;
  gap: 8px;
}
.speech-style-btn {
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
}
.speech-style-btn:hover {
  border-color: #22c55e;
  color: #22c55e;
}
.speech-style-btn.is-active {
  background: #f0fdf4;
  border-color: #22c55e;
  color: #22c55e;
  font-weight: 500;
}
html.dark .speech-style-btn.is-active {
  background: rgba(34, 197, 94, 0.12);
}
.speech-editor-card__body {
  padding: 24px 28px 28px;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.speech-editor-card__body :deep(.el-textarea) {
  flex: 1;
}
.speech-editor-card__body :deep(.el-textarea__inner) {
  height: 100% !important;
  min-height: 180px !important;
}
.speech-editor-card__content-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 14px;
}
.speech-char-count {
  margin-left: auto;
  font-size: 13px;
  font-weight: 400;
  color: var(--text-muted);
}
.speech-char-count.is-over {
  color: #ef4444;
  font-weight: 500;
}
.speech-editor-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
}
.speech-editor-card__hint {
  font-size: 13px;
  color: var(--text-muted);
}
.speech-editor-card__empty {
  padding: 56px 28px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 15px;
}
.speech-empty {
  text-align: center;
  padding: 72px 24px;
  color: var(--text-secondary);
  font-size: 15px;
}
.speech-import {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.speech-import__drop {
  font-size: 14px;
  color: var(--text-primary);
}
.speech-import__options {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}
.speech-import__result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.speech-import__summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
.speech-import__summary > div {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--card-bg);
  padding: 10px 12px;
}
.speech-import__summary span {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
}
.speech-import__summary strong {
  display: block;
  margin-top: 4px;
  font-size: 18px;
  color: var(--text-primary);
}
.speech-import__errors {
  margin: 0;
}
@media (max-width: 768px) {
  .speech-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 16px;
  }
  .speech-layout {
    flex-direction: column;
  }
  .speech-sidebar {
    width: 100%;
    max-height: none;
  }
  .speech-editor-card__header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
  .speech-import__summary {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
