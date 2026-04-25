<template>
  <div class="sop-page" v-loading="loading">
    <div class="ws-hero" v-if="workspace">
      <div class="ws-hero__left">
        <h1 style="display:flex;align-items:center;gap:12px;margin:0 0 12px;font-size:24px;font-weight:700;color:var(--text-primary);">
          {{ workspace.name }}
          <span v-if="workspace.current_stage_label" style="font-size:13px;font-weight:500;padding:4px 10px;border-radius:12px;background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;">{{ workspace.current_stage_label }}</span>
        </h1>
        <p style="margin:0;font-size:13px;color:var(--text-secondary);display:flex;align-items:center;gap:8px;">
          负责人：{{ workspace.owner_name || '暂无' }}
          <template v-if="workspace.biz_line"> · {{ workspace.biz_line }}</template>
        </p>
        <p v-if="workspace.description" style="margin:4px 0 0;font-size:13px;color:var(--text-muted);">{{ workspace.description }}</p>
      </div>

      <div class="ws-hero__stats">
        <div class="ws-hero__stat-item">
          <div class="ws-hero__stat-label">文档总数</div>
          <div class="ws-hero__stat-val">{{ workspace.doc_count || 0 }}</div>
          <div class="ws-hero__stat-sub">篇文档</div>
        </div>
      </div>

      <div class="sop-hero__actions" style="border-left:1px solid var(--border-color);padding-left:24px;margin-left:24px;height:100%;align-items:center;">
        <el-button @click="$router.push('/sop-docs')">返回</el-button>
        <el-button @click="wsFormVisible = true">编辑工作台</el-button>
        <el-button type="success" @click="quickAddVisible = true" style="background:#00B96B; border-color:#00B96B; color:white;">登记飞书链接</el-button>
        <el-button type="danger" plain @click="confirmDeleteWorkspace">删除工作台</el-button>
      </div>
    </div>

    <div v-if="overview" class="ws-detail-layout" style="display:flex; gap:24px; margin-top:24px;">
      <!-- Main: stages -->
      <div class="ws-detail-main" style="flex:1; min-width:0;">
        <!-- Featured Priority Docs -->
        <div class="sop-section" v-if="featuredDocs.length">
          <div class="sop-section__header">
            <h3 class="sop-section__title">优先处理</h3>
            <el-tag type="danger" size="small">{{ featuredDocs.length }}</el-tag>
          </div>
          <div class="sop-priority-list">
            <PriorityDocCard
              v-for="(doc, i) in featuredDocs"
              :key="doc.binding_id"
              :doc="doc"
              :index="i + 1"
              @open="openDoc(doc)"
            />
          </div>
        </div>
        <div v-for="stage in overview.stages" :key="stage.term?.id || 'unassigned'" class="sop-section">
          <div class="sop-section__header">
            <h3 class="sop-section__title">{{ stage.term?.label || '未分配阶段' }}</h3>
            <span style="font-size:12px;color:var(--text-muted);">
              {{ stage.official_docs.length + stage.support_docs.length + stage.candidate_docs.length }} 篇
            </span>
          </div>

          <!-- Stage doc table -->
          <el-table :data="getStageTableData(stage)" class="sop-doc-table" style="border:none;" v-if="getStageTableData(stage).length">
            <el-table-column prop="title" label="文档名称" min-width="220">
              <template #default="{ row }">
                <div class="sop-doc-title-cell">
                  <el-button link style="font-weight:600; color:var(--text-primary);" @click="openDoc(row)" class="sop-doc-title-btn">{{ row.title }}</el-button>
                  <span v-if="row.remark" class="sop-doc-remark-inline">{{ row.remark }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="90">
              <template #default="{ row }">
                <span class="doc-type-badge" :class="`doc-type-badge--${row.doc_type}`" style="border:1px solid transparent;">{{ docTypeLabel(row.doc_type) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <span class="role-badge" :class="`role-badge--${row.relation_role}`">{{ roleLabel(row.relation_role) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="90">
               <template #default="{ row }">
                 <span v-if="row.relation_role === 'official' || row.relation_role === 'candidate'" style="color:#ef4444; font-size:12px; font-weight:600;">高 <span style="font-size:10px;">↑</span></span>
                 <span v-else style="color:#10b981; font-size:12px; font-weight:600;">低 <span style="font-size:10px;">↓</span></span>
               </template>
            </el-table-column>
            <el-table-column label="最后更新" width="160">
              <template #default="{ row }">
                <span style="font-size:12px;color:var(--text-muted);">{{ row.updated_at?.slice(0, 10) }}<template v-if="row.updated_by_name"> · {{ row.updated_by_name }}</template></span>
              </template>
            </el-table-column>
            <el-table-column label="" width="50" fixed="right">
              <template #default="{ row }">
                <el-dropdown trigger="click">
                  <el-button link size="small" class="sop-actions-trigger">
                    <el-icon><MoreFilled /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="openDoc(row)">打开文档</el-dropdown-item>
                      <el-dropdown-item @click="openBindingEdit(row)">编辑</el-dropdown-item>
                      <el-dropdown-item @click="confirmRemove(row)" style="color:#ef4444;">移除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="这个阶段还没登记文档" :image-size="60" />
        </div>
      </div>

      <!-- Sidebar -->
      <div class="ws-detail-sidebar">
        <!-- Quick Tags -->
        <div class="sidebar-panel" v-if="overview.stages?.length">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <h4 style="margin:0;font-size:15px;font-weight:700;color:var(--text-primary);">快捷筛选</h4>
          </div>
          <div class="tag-cloud" style="display:flex; flex-wrap:wrap; gap:8px;">
            <el-tag
              v-for="stage in overview.stages"
              :key="stage.term?.id || 'none'"
              size="default"
              :type="isCurrentStage(stage) ? 'success' : 'info'"
              :effect="isCurrentStage(stage) ? 'light' : 'plain'"
              round
              style="cursor:pointer;"
            >
              {{ stage.term?.label || '未分配' }} <span style="opacity:0.7;margin-left:4px;">{{ stage.official_docs.length + stage.support_docs.length + stage.candidate_docs.length }}</span>
            </el-tag>
          </div>
        </div>

        <div class="sidebar-panel" v-if="overview.recent_updates?.length">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h4 style="margin:0;font-size:15px;font-weight:700;color:var(--text-primary);">最近更新</h4>
            <el-button link type="primary" size="small">更多 <el-icon><ArrowRight /></el-icon></el-button>
          </div>
          <div v-for="item in overview.recent_updates" :key="item.binding_id" class="sidebar-update-item">
            <div class="sidebar-update-item__title">{{ item.resource_title }}</div>
            <div class="sidebar-update-item__meta">
              <span class="role-badge" :class="`role-badge--${item.relation_role}`" style="font-size:10px;padding:0 5px;background:none;border:1px solid #e5e7eb;">{{ roleLabel(item.relation_role) }}</span>
              {{ item.updated_at?.slice(0, 10) }}
              <span v-if="item.owner_name"> · {{ item.owner_name }}</span>
            </div>
          </div>
        </div>

        <div class="sidebar-panel" v-if="overview.governance_flags?.length" style="background:#fffcf1; border-color:#fde68a;">
          <h4 style="margin:0 0 16px;font-size:15px;font-weight:700;color:#d97706;display:flex;align-items:center;gap:6px;">
            <el-icon><WarningFilled /></el-icon> 项目提醒
          </h4>
          <div v-for="(flag, idx) in overview.governance_flags" :key="idx" class="sidebar-flag-item" style="padding:12px; background:#fff; border-radius:8px; border:1px solid #fef08a; margin-bottom:12px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
            <div style="font-size:13px;font-weight:600;color:var(--text-primary);">{{ flag.label }}</div>
            <div style="font-size:12px;color:var(--text-muted);margin-top:6px;line-height:1.4;">{{ flag.reason }}</div>
            <div style="display:flex; justify-content:flex-end; margin-top:8px;">
              <el-icon style="color:#d97706; cursor:pointer;"><ArrowRight /></el-icon>
            </div>
          </div>
        </div>
      </div>
    </div>
    <el-empty v-else-if="!loading" description="工作台不存在" />

    <!-- Dialogs -->
    <QuickAddDialog v-model="quickAddVisible" @success="fetchOverview" />
    <WorkspaceFormDialog v-model="wsFormVisible" :workspace="workspace" @saved="fetchOverview" />
    <BindingEditDialog
      v-model="bindingEditVisible"
      :binding="editingBinding"
      :stage-terms="stageTerms"
      :deliverable-terms="deliverableTerms"
      @saved="fetchOverview"
    />
  </div>
</template>

<script lang="ts">
export default { name: 'WorkspaceDetail' }
</script>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MoreFilled, ArrowRight, WarningFilled } from '@element-plus/icons-vue'
import request from '#/utils/request'
import ResourceCard from './components/ResourceCard.vue'
import PriorityDocCard from './components/PriorityDocCard.vue'
import QuickAddDialog from './components/QuickAddDialog.vue'
import WorkspaceFormDialog from './components/WorkspaceFormDialog.vue'
import BindingEditDialog from './components/BindingEditDialog.vue'

const route = useRoute()
const router = useRouter()
const workspaceId = computed(() => route.params.id as string)

const workspace = ref<any>(null)
const overview = ref<any>(null)
const loading = ref(false)
const quickAddVisible = ref(false)
const wsFormVisible = ref(false)
const bindingEditVisible = ref(false)
const editingBinding = ref<any>(null)
const stageTerms = ref<any[]>([])
const deliverableTerms = ref<any[]>([])

const workspaceTypeLabels: Record<string, string> = {
  project: '项目', campaign: '活动', customer: '客户',
  template_hub: '模板库', inbox: '待整理',
}
const workspaceTypeLabel = computed(() => workspaceTypeLabels[workspace.value?.workspace_type] || '')
const statusLabels: Record<string, string> = {
  planning: '筹备中', running: '进行中', reviewing: '复盘中', archived: '已归档',
}
const statusLabel = computed(() => statusLabels[workspace.value?.status] || '')

const roleLabel = (role: string) => ({
  official: '当前在用', support: '参考资料', candidate: '备选方案', archive: '历史归档',
} as Record<string, string>)[role] || role

const docTypeLabel = (type: string) => ({
  doc: '文档', sheet: '表格', bitable: '多维表格', wiki: '知识库', folder: '文件夹',
} as Record<string, string>)[type] || '文档'

const featuredDocs = computed(() => {
  if (!overview.value?.stages) return []
  const currentStageId = workspace.value?.current_stage_term_id
  const stage = overview.value.stages.find((s: any) => s.term?.id === currentStageId)
  if (!stage) return []
  return stage.official_docs.slice(0, 4)
})

const isCurrentStage = (stage: any) => {
  return stage.term?.id === workspace.value?.current_stage_term_id
}

const getStageTableData = (stage: any) => {
  return [
    ...stage.official_docs.map((d: any) => ({ ...d, _role: 'official' })),
    ...stage.support_docs.map((d: any) => ({ ...d, _role: 'support' })),
    ...stage.candidate_docs.map((d: any) => ({ ...d, _role: 'candidate' })),
    ...(stage.archive_docs || []).map((d: any) => ({ ...d, _role: 'archive' })),
  ]
}

const fetchOverview = async () => {
  loading.value = true
  try {
    const [ov, terms] = await Promise.all([
      request.get(`/v1/external-docs/workspaces/${workspaceId.value}/overview`),
      stageTerms.value.length ? Promise.resolve(null) : request.get('/v1/external-docs/terms'),
    ])
    overview.value = ov
    workspace.value = ov?.workspace || null
    if (terms) {
      const all = terms as any[]
      stageTerms.value = all.filter((t: any) => t.dimension === 'stage')
      deliverableTerms.value = all.filter((t: any) => t.dimension === 'deliverable_type')
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const openDoc = (doc: any) => {
  request.post(`/v1/external-docs/resources/${doc.id}/open`, {
    workspace_id: Number(workspaceId.value),
    client_type: 'web',
  }).then((res) => {
    if (res?.open_url) window.open(res.open_url, '_blank')
  }).catch(console.error)
}

const openBindingEdit = (doc: any) => {
  editingBinding.value = doc
  bindingEditVisible.value = true
}

const confirmRemove = async (doc: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要从当前工作台移除「${doc.title}」吗？文档本身不会被删除，只是解除绑定关系。`,
      '移除文档',
      { type: 'warning', confirmButtonText: '移除', cancelButtonText: '取消' },
    )
    await request.delete(`/v1/external-docs/bindings/${doc.binding_id}`)
    ElMessage.success('已移除')
    fetchOverview()
  } catch {
    // cancelled
  }
}

const confirmDeleteWorkspace = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除工作台「${workspace.value?.name}」吗？该工作台下所有文档绑定也会被移除，文档本身不会被删除。此操作不可撤销。`,
      '删除工作台',
      { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await request.delete(`/v1/external-docs/workspaces/${workspaceId.value}`)
    ElMessage.success('工作台已删除')
    router.push('/sop-docs')
  } catch {
    // cancelled
  }
}

onMounted(fetchOverview)
watch(workspaceId, fetchOverview)
</script>

<style src="./styles/sopDocs.css" scoped></style>
<style scoped>
.ws-detail-layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 20px;
  align-items: start;
}
@media (max-width: 900px) {
  .ws-detail-layout { grid-template-columns: 1fr; }
}
.ws-detail-main { min-width: 0; }
.ws-detail-sidebar { display: flex; flex-direction: column; gap: 16px; }
.sidebar-panel {
  padding: 14px 16px; border-radius: 16px;
  border: 1px solid var(--border-color, #e5e7eb);
  background: var(--card-bg, #fff);
}
.tag-cloud { display: flex; flex-wrap: wrap; gap: 0; }
.sidebar-update-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}
.sidebar-update-item:last-child { border-bottom: none; padding-bottom: 0; }
.sidebar-update-item:first-child { padding-top: 0; }
.sidebar-flag-item {
  padding: 8px 10px; border-radius: 6px; margin-bottom: 6px;
  background: rgba(245,158,11,.08); color: #b45309; font-size: 13px;
}
:global(html.dark) .sidebar-panel { background: rgba(39,40,42,.92); border-color: #414243; }
:global(html.dark) .sidebar-flag-item { background: rgba(245,158,11,.12); color: #fbbf24; }
</style>
