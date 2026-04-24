<template>
  <div class="sop-page" v-loading="loading">
    <!-- Overview Header -->
    <div class="sop-hero" v-if="workspace">
      <div class="sop-hero__left">
        <h1>{{ workspace.name }}</h1>
        <p style="margin-top:6px;">
          <span class="ws-card__badge" :class="`ws-card__badge--${workspace.workspace_type}`" style="margin-right:4px;">{{ workspaceTypeLabel }}</span>
          <span v-if="workspace.status" class="ws-card__badge ws-card__badge--status" style="margin-right:4px;">{{ statusLabel }}</span>
          <span v-if="workspace.current_stage_label" class="ws-card__badge ws-card__badge--status" style="background:rgba(34,197,94,.08);color:#16a34a;">{{ workspace.current_stage_label }}</span>
        </p>
        <p style="margin-top:4px;font-size:13px;color:var(--text-muted);">
          <span v-if="workspace.owner_name">负责人：{{ workspace.owner_name }}</span>
          <span v-if="workspace.biz_line"> · {{ workspace.biz_line }}</span>
          <span v-if="workspace.client_name"> · {{ workspace.client_name }}</span>
          <span v-if="workspace.start_date"> · {{ workspace.start_date }} ~ {{ workspace.end_date }}</span>
        </p>
        <p v-if="workspace.description" style="margin-top:4px;font-size:13px;color:var(--text-muted);">{{ workspace.description }}</p>
      </div>
      <div class="sop-hero__actions">
        <el-button @click="$router.push('/sop-docs')">返回</el-button>
        <el-button @click="wsFormVisible = true">编辑工作台</el-button>
        <el-button type="primary" @click="quickAddVisible = true">登记飞书链接</el-button>
      </div>
    </div>

    <div v-if="overview" class="ws-detail-layout">
      <!-- Main: stages -->
      <div class="ws-detail-main">
        <div v-for="stage in overview.stages" :key="stage.term?.id || 'unassigned'" class="sop-section">
          <div class="sop-section__header">
            <h3 class="sop-section__title">{{ stage.term?.label || '未分配阶段' }}</h3>
            <span style="font-size:12px;color:var(--text-muted);">
              {{ stage.official_docs.length + stage.support_docs.length + stage.candidate_docs.length }} 篇
            </span>
          </div>
          <template v-if="stage.official_docs.length">
            <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">正式文档</div>
            <div class="sop-card-grid" style="margin-bottom:12px;">
              <ResourceCard v-for="doc in stage.official_docs" :key="doc.binding_id" :doc="doc" editable
                @open="openDoc(doc)" @edit="openBindingEdit(doc)" @remove="confirmRemove(doc)" />
            </div>
          </template>
          <template v-if="stage.support_docs.length">
            <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">参考资料</div>
            <div class="sop-card-grid" style="margin-bottom:12px;">
              <ResourceCard v-for="doc in stage.support_docs" :key="doc.binding_id" :doc="doc" editable
                @open="openDoc(doc)" @edit="openBindingEdit(doc)" @remove="confirmRemove(doc)" />
            </div>
          </template>
          <template v-if="stage.candidate_docs.length">
            <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">备选方案</div>
            <div class="sop-card-grid" style="margin-bottom:12px;">
              <ResourceCard v-for="doc in stage.candidate_docs" :key="doc.binding_id" :doc="doc" editable
                @open="openDoc(doc)" @edit="openBindingEdit(doc)" @remove="confirmRemove(doc)" />
            </div>
          </template>
          <template v-if="stage.archive_docs && stage.archive_docs.length">
            <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">历史归档</div>
            <div class="sop-card-grid">
              <ResourceCard v-for="doc in stage.archive_docs" :key="doc.binding_id" :doc="doc" editable
                @open="openDoc(doc)" @edit="openBindingEdit(doc)" @remove="confirmRemove(doc)" />
            </div>
          </template>
          <el-empty v-if="!stage.official_docs.length && !stage.support_docs.length && !stage.candidate_docs.length"
            description="这个阶段还没登记文档" :image-size="60" />
        </div>
      </div>

      <!-- Sidebar -->
      <div class="ws-detail-sidebar">
        <div class="sidebar-panel" v-if="overview.recent_updates?.length">
          <h4 style="margin:0 0 10px;font-size:14px;font-weight:700;color:var(--text-primary);">最近更新</h4>
          <div v-for="item in overview.recent_updates" :key="item.binding_id" class="sidebar-update-item">
            <div style="font-size:13px;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ item.resource_title }}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">
              <span class="role-badge" :class="`role-badge--${item.relation_role}`" style="font-size:10px;padding:0 5px;">{{ roleLabel(item.relation_role) }}</span>
              {{ item.updated_at?.slice(0, 10) }}
            </div>
          </div>
        </div>

        <div class="sidebar-panel" v-if="overview.governance_flags?.length">
          <h4 style="margin:0 0 10px;font-size:14px;font-weight:700;color:var(--text-primary);">待处理</h4>
          <div v-for="(flag, idx) in overview.governance_flags" :key="idx" class="sidebar-flag-item">
            {{ flag.label }}
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
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'
import ResourceCard from './components/ResourceCard.vue'
import QuickAddDialog from './components/QuickAddDialog.vue'
import WorkspaceFormDialog from './components/WorkspaceFormDialog.vue'
import BindingEditDialog from './components/BindingEditDialog.vue'

const route = useRoute()
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

onMounted(fetchOverview)
watch(workspaceId, fetchOverview)
</script>

<style src="./styles/sopDocs.css" scoped></style>
<style scoped>
.ws-detail-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 20px;
  align-items: start;
}
@media (max-width: 900px) {
  .ws-detail-layout { grid-template-columns: 1fr; }
}
.ws-detail-main { min-width: 0; }
.ws-detail-sidebar { display: flex; flex-direction: column; gap: 16px; }
.sidebar-panel {
  padding: 14px 16px; border-radius: 10px;
  border: 1px solid var(--border-color, #e5e7eb);
  background: var(--card-bg, #fff);
}
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
