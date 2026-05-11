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
        <el-button type="primary" @click="importDialogVisible = true; importFile = null; importResult = null">
          <el-icon><Upload /></el-icon>
          导入 CSV
        </el-button>
      </div>
    </div>

    <div v-loading="loading" class="speech-body">
      <div v-if="!loading && scenes.length" class="speech-layout">
        <!-- Sidebar -->
        <div class="speech-sidebar">
          <div v-for="l1 in sidebarTree" :key="l1.id" class="speech-cat-group">
            <div class="speech-cat-l1" @click="toggleNode(`l1-${l1.id}`)" @mouseenter="hoveredL1 = l1.id" @mouseleave="hoveredL1 = null">
              <span class="speech-cat-arrow" :class="{ 'is-expanded': expandedState[`l1-${l1.id}`] }">&#9654;</span>
              <span class="speech-cat-l1-icon" v-html="getCategoryIcon(l1.name)"></span>
              <template v-if="renamingId === l1.id">
                <el-input v-model="renamingName" size="small" class="cat-rename-input" @keyup.enter="saveRename(l1)" @blur="saveRename(l1)" @click.stop />
              </template>
              <template v-else>
                <span class="speech-cat-name">{{ l1.name }}</span>
              </template>
              <div class="speech-cat-actions" v-if="hoveredL1 === l1.id && renamingId !== l1.id" @click.stop>
                <button class="cat-action-btn" title="新建子类" @click="openCreateL2(l1.id)">+</button>
                <button class="cat-action-btn" title="重命名" @click="startRename(l1)">&#9998;</button>
                <button class="cat-action-btn cat-action-btn--danger" title="删除" @click="handleDeleteCategory(l1)">&times;</button>
              </div>
            </div>
            <template v-if="expandedState[`l1-${l1.id}`]">
              <div v-for="l2 in l1.children" :key="l2.id" class="speech-cat-l2-wrap">
                <div class="speech-cat-l2" @click="toggleNode(`l2-${l2.id}`)" @mouseenter="hoveredL2 = l2.id" @mouseleave="hoveredL2 = null">
                  <span class="speech-cat-arrow" :class="{ 'is-expanded': expandedState[`l2-${l2.id}`] }">&#9654;</span>
                  <template v-if="renamingId === l2.id">
                    <el-input v-model="renamingName" size="small" class="cat-rename-input" @keyup.enter="saveRename(l2)" @blur="saveRename(l2)" @click.stop />
                  </template>
                  <template v-else>
                    <span class="speech-cat-name">{{ l2.name }}</span>
                  </template>
                  <div class="speech-cat-actions" v-if="hoveredL2 === l2.id && renamingId !== l2.id" @click.stop>
                    <button class="cat-action-btn" title="新建三级分类" @click="openCreateL3(l2.id)">+</button>
                    <button class="cat-action-btn" title="重命名" @click="startRename(l2)">&#9998;</button>
                    <button class="cat-action-btn" title="移动" @click="openMoveDialog(l2)">&#8693;</button>
                    <button class="cat-action-btn cat-action-btn--danger" title="删除" @click="handleDeleteCategory(l2)">&times;</button>
                  </div>
                </div>
                <template v-if="expandedState[`l2-${l2.id}`]">
                  <div v-for="l3 in l2.children" :key="l3.id" class="speech-cat-l3-wrap">
                    <div class="speech-cat-l3" @click="toggleNode(`l3-${l3.id}`)" @mouseenter="hoveredL3 = l3.id" @mouseleave="hoveredL3 = null">
                      <span class="speech-cat-arrow" :class="{ 'is-expanded': expandedState[`l3-${l3.id}`] }">&#9654;</span>
                      <template v-if="renamingId === l3.id">
                        <el-input v-model="renamingName" size="small" class="cat-rename-input" @keyup.enter="saveRename(l3)" @blur="saveRename(l3)" @click.stop />
                      </template>
                      <template v-else>
                        <span class="speech-cat-name">{{ l3.name }}</span>
                      </template>
                      <span class="speech-cat-count">{{ l3.scenes.length }}</span>
                      <div class="speech-cat-actions" v-if="hoveredL3 === l3.id && renamingId !== l3.id" @click.stop>
                        <button class="cat-action-btn" title="重命名" @click="startRename(l3)">&#9998;</button>
                        <button class="cat-action-btn" title="移动" @click="openMoveDialog(l3)">&#8693;</button>
                        <button class="cat-action-btn cat-action-btn--danger" title="删除" @click="handleDeleteCategory(l3)">&times;</button>
                      </div>
                    </div>
                    <template v-if="expandedState[`l3-${l3.id}`]">
                      <div v-for="scene in l3.scenes" :key="scene.key" class="speech-scene-item"
                        :class="{ 'is-active': activeScene === scene.key }"
                        @click="selectScene(scene.key)"
                        @mouseenter="hoveredScene = scene.key" @mouseleave="hoveredScene = null"
                      >
                        <span class="speech-scene-item__label">{{ scene.label }}</span>
                        <span class="speech-scene-item__key">{{ scene.key }}</span>
                        <button v-if="hoveredScene === scene.key" class="scene-categorize-btn" title="归类" @click.stop="openCategorizeDialog(scene.key)">&#128193;</button>
                      </div>
                      <div class="speech-scene-item speech-scene-item--action" @click="openCreateTemplate(l3.id, l3.code)">
                        <span style="color: var(--text-muted)">+ 新建话术</span>
                      </div>
                    </template>
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
              <div v-for="scene in uncategorizedScenes" :key="scene.key" class="speech-scene-item"
                :class="{ 'is-active': activeScene === scene.key }"
                @click="selectScene(scene.key)"
                @mouseenter="hoveredScene = scene.key" @mouseleave="hoveredScene = null"
              >
                <span class="speech-scene-item__label">{{ scene.label }}</span>
                <span class="speech-scene-item__key">{{ scene.key }}</span>
                <button v-if="hoveredScene === scene.key" class="scene-categorize-btn" title="归类" @click.stop="openCategorizeDialog(scene.key)">&#128193;</button>
              </div>
            </template>
          </div>

          <div class="speech-sidebar-footer">
            <button class="speech-new-l1-btn" @click="createL1DialogVisible = true; createL1Name = ''">+ 新建大类</button>
          </div>
        </div>

        <!-- Editor preview (click to open drawer) -->
        <div class="speech-editor" v-if="activeScene">
          <div class="speech-editor-card">
            <div class="speech-editor-card__header">
              <div class="speech-editor-card__title">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#22c55e" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                <span>{{ currentSceneLabel }}</span>
                <el-tag size="small" type="info">{{ activeScene }}</el-tag>
              </div>
              <div class="speech-editor-card__styles">
                <button v-for="tpl in currentTemplates" :key="tpl.style" class="speech-style-btn"
                  :class="{ 'is-active': activeStyle === tpl.style }" @click="activeStyle = tpl.style"
                >{{ styleLabel(tpl.style) }}</button>
              </div>
            </div>

            <div v-if="currentEditingTpl" class="speech-editor-card__preview" @click="openEditDrawer">
              <div class="speech-editor-card__preview-label">
                <span>{{ currentEditingTpl.label || '未命名' }}</span>
                <el-button type="primary" size="small">编辑</el-button>
              </div>
              <div class="speech-editor-card__preview-content">{{ currentEditingTpl._editContent?.slice(0, 120) }}{{ (currentEditingTpl._editContent?.length || 0) > 120 ? '...' : '' }}</div>
              <div v-if="currentEditingTpl.metadata_json && Object.keys(currentEditingTpl.metadata_json).length" class="speech-editor-card__rag-badges">
                <el-tag v-for="(val, key) in currentEditingTpl.metadata_json" :key="key" size="small" type="info" class="rag-badge">{{ key }}</el-tag>
              </div>
            </div>

            <div v-if="!currentTemplates.length" class="speech-editor-card__empty">该场景暂无模板</div>
          </div>
        </div>
      </div>

      <div v-if="!loading && !scenes.length" class="speech-empty">暂无话术数据</div>
    </div>

    <!-- Create L1 dialog -->
    <el-dialog v-model="createL1DialogVisible" title="新建大类" width="400px">
      <el-input v-model="createL1Name" placeholder="如：营销推广类" @keyup.enter="handleCreateL1" />
      <template #footer>
        <el-button @click="createL1DialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateL1">创建</el-button>
      </template>
    </el-dialog>

    <!-- Move category dialog -->
    <el-dialog v-model="moveDialogVisible" title="移动分类" width="400px">
      <p style="margin-bottom: 12px; color: var(--text-secondary);">将「{{ moveTargetNode?.name }}」移动到：</p>
      <el-cascader v-model="moveTargetParentId" :options="moveTargetOptions"
        :props="{ value: 'id', label: 'name', children: 'children', emitPath: false }"
        placeholder="选择目标分类" style="width: 100%" clearable
      />
      <template #footer>
        <el-button @click="moveDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!moveTargetParentId" @click="handleMoveCategory">确认移动</el-button>
      </template>
    </el-dialog>

    <!-- Categorize scene dialog -->
    <el-dialog v-model="categorizeDialogVisible" title="归类场景" width="400px">
      <p style="margin-bottom: 12px; color: var(--text-secondary);">
        将「{{ scenes.find(s => s.key === categorizeSceneKey)?.label || categorizeSceneKey }}」归类到：
      </p>
      <el-cascader v-model="categorizeTargetId" :options="categorizeOptions"
        :props="{ value: 'id', label: 'name', children: 'children', emitPath: false }"
        placeholder="选择分类" style="width: 100%" clearable
      />
      <template #footer>
        <el-button @click="categorizeDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!categorizeTargetId" @click="handleCategorizeScene">确认归类</el-button>
      </template>
    </el-dialog>

    <!-- Create template dialog -->
    <el-dialog v-model="createTemplateDialogVisible" title="新建话术" width="550px">
      <el-form label-width="80px">
        <el-form-item label="场景标识">
          <el-input v-model="createTemplateSceneKey" placeholder="英文标识，如 meal_checkin" />
        </el-form-item>
        <el-form-item label="风格">
          <el-select v-model="createTemplateStyle">
            <el-option label="专业风格" value="professional" />
            <el-option label="鼓励风格" value="encouraging" />
            <el-option label="竞争风格" value="competitive" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="createTemplateLabel" placeholder="话术标题" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="createTemplateContent" type="textarea" :rows="8" placeholder="话术内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createTemplateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createTemplateSaving" @click="handleCreateTemplate">创建</el-button>
      </template>
    </el-dialog>

    <!-- Edit drawer (content + RAG) -->
    <el-drawer v-model="editDrawerVisible" :title="`编辑：${currentEditingTpl?.label || currentSceneLabel}`" size="560px" :destroy-on-close="false">
      <template v-if="currentEditingTpl">
        <el-form label-width="80px" size="small">
          <el-form-item label="标题">
            <el-input v-model="currentEditingTpl.label" placeholder="话术标题" />
          </el-form-item>
          <el-form-item label="内容">
            <el-input v-model="currentEditingTpl._editContent" type="textarea" :rows="8"
              :placeholder="isPointsScene ? '话术内容（支持 {name} {rank} {detail} {activity} 占位符）' : '请输入话术内容'"
            />
            <div class="speech-char-count" :class="{ 'is-over': currentEditingTpl._editContent.length > 2000 }">
              {{ currentEditingTpl._editContent.length }}/2000
            </div>
            <span v-if="isPointsScene" class="speech-editor-card__hint">占位符: {name} {rank} {detail} {activity}</span>
          </el-form-item>
        </el-form>

        <el-divider content-position="left">RAG 配置</el-divider>

        <el-form label-width="80px" size="small">
          <el-form-item label="摘要">
            <el-input v-model="ragMetaForm.summary" type="textarea" :rows="2" placeholder="话术摘要，用于 RAG 检索增强" />
          </el-form-item>
          <el-form-item label="客户目标">
            <el-select v-model="ragMetaForm.customer_goal" multiple filterable allow-create placeholder="选择或输入标签">
              <el-option v-for="t in tagOptions('customer_goal')" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="干预场景">
            <el-select v-model="ragMetaForm.intervention_scene" multiple filterable allow-create placeholder="选择或输入标签">
              <el-option v-for="t in tagOptions('intervention_scene')" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="问题类型">
            <el-select v-model="ragMetaForm.question_type" multiple filterable allow-create placeholder="选择或输入标签">
              <el-option v-for="t in tagOptions('question_type')" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="安全级别">
            <el-radio-group v-model="ragMetaForm.safety_level">
              <el-radio value="">未设置</el-radio>
              <el-radio value="general">general</el-radio>
              <el-radio value="nutrition_education">nutrition_education</el-radio>
              <el-radio value="medical_sensitive">medical_sensitive</el-radio>
              <el-radio value="doctor_review">doctor_review</el-radio>
              <el-radio value="contraindicated">contraindicated</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="可见性">
            <el-radio-group v-model="ragMetaForm.visibility">
              <el-radio value="">未设置</el-radio>
              <el-radio value="coach_internal">内部</el-radio>
              <el-radio value="customer_visible">客户可见</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="自定义标签">
            <el-select v-model="ragMetaForm.tags" multiple filterable allow-create default-first-option placeholder="输入标签回车添加" />
          </el-form-item>
          <el-form-item label="使用说明">
            <el-input v-model="ragMetaForm.usage_note" type="textarea" :rows="2" placeholder="使用场景描述" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="editDrawerVisible = false">取消</el-button>
        <el-button type="primary" :loading="currentEditingTpl?._saving || ragMetaSaving" @click="handleSaveEditDrawer">保存全部</el-button>
      </template>
    </el-drawer>

    <!-- CSV Import dialog -->
    <el-dialog v-model="importDialogVisible" title="导入话术 CSV" width="720px">
      <div class="speech-import">
        <el-upload drag :auto-upload="false" :limit="1" accept=".csv,text/csv"
          :on-change="handleImportFileChange" :on-remove="handleImportFileRemove"
        >
          <div class="speech-import__drop">拖拽 CSV 到这里，或点击选择文件</div>
          <div class="el-upload__tip">字段兼容 source_id、source_type、title、clean_content、summary、intervention_scene、question_type、tone、status</div>
        </el-upload>
        <div class="speech-import__options">
          <el-checkbox v-model="importIndexRag">导入后同步 RAG 索引</el-checkbox>
        </div>
        <div v-if="importResult" class="speech-import__result">
          <div class="speech-import__summary">
            <div><span>新增</span><strong>{{ importResult.created }}</strong></div>
            <div><span>更新</span><strong>{{ importResult.updated }}</strong></div>
            <div><span>跳过</span><strong>{{ importResult.skipped }}</strong></div>
            <div><span>错误</span><strong>{{ importResult.errors?.length || 0 }}</strong></div>
          </div>
          <el-alert v-if="importResult.errors?.length" type="warning" :closable="false" show-icon class="speech-import__errors">
            <template #title>{{ importResult.errors.slice(0, 5).join('；') }}</template>
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
        <el-button type="primary" :disabled="!importFile" :loading="importing" @click="submitCsvImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'SpeechTemplates' })
import { ref, onMounted } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import request from '#/utils/request'
import { useSpeechTemplates } from './SpeechTemplates/composables/useSpeechTemplates'
import { useRagTags } from '#/composables/useRagTags'

type ImportResult = {
  created: number; updated: number; skipped: number; errors: string[]
  rows: Array<{ source_id: string; title: string; scene_key: string; style: string; action: string }>
  rag_index?: Record<string, number> | null
}

const {
  loading, scenes, categories, templatesMap, activeScene, activeStyle, expandedState,
  hoveredL1, hoveredL2, hoveredL3, hoveredScene, renamingId, renamingName,
  createL1DialogVisible, createL1Name,
  moveDialogVisible, moveTargetNode, moveTargetParentId, moveTargetOptions,
  categorizeDialogVisible, categorizeSceneKey, categorizeTargetId, categorizeOptions,
  createTemplateDialogVisible, createTemplateCategoryId, createTemplateSceneKey,
  createTemplateStyle, createTemplateLabel, createTemplateContent, createTemplateSaving,
  editDrawerVisible, ragMetaForm, ragMetaSaving,
  sidebarTree, uncategorizedScenes, currentSceneLabel, currentTemplates,
  currentEditingTpl, isPointsScene,
  selectScene, toggleNode, styleLabel, getCategoryIcon, fetchData,
  saveTemplate, openCreateTemplate, handleCreateTemplate,
  startRename, saveRename, handleDeleteCategory, openMoveDialog, handleMoveCategory,
  openCreateL2, openCreateL3, handleCreateL1, openCategorizeDialog, handleCategorizeScene,
  handleSaveEditDrawer, openEditDrawer,
} = useSpeechTemplates()

const { options: tagOptions } = useRagTags()

// CSV import (kept local)
const importDialogVisible = ref(false)
const importFile = ref<File | null>(null)
const importIndexRag = ref(true)
const importing = ref(false)
const importResult = ref<ImportResult | null>(null)

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
  if (!importFile.value) { ElMessage.warning('请先选择 CSV 文件'); return }
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

onMounted(fetchData)
</script>

<style scoped>
@import './SpeechTemplates/styles.css';
</style>
