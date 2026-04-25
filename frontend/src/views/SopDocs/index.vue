<template>
  <div class="sop-page" v-loading="loading">
        <!-- Overview Header with Actions (Design align) -->
    <div class="sop-hero" style="margin-bottom: 24px;">
      <div class="sop-hero__left">
        <h1>飞书文档集中管理</h1>
        <p style="margin-top:6px;">高效管理文档，驱动运营提效</p>
      </div>
      <div class="sop-hero__actions">
        <el-button @click="wsFormVisible = true">新建工作台</el-button>
        <el-button type="success" @click="quickAddVisible = true" style="background:#00B96B; border-color:#00B96B; color:white;">登记飞书链接</el-button>
      </div>
    </div>

    <!-- Stats Row -->
    <div class="sop-stats-grid">
      <StatCard label="待处理文档" :value="stats.pending" color="orange" />
      <StatCard label="今日必看" :value="stats.todayMustSee" color="blue" />
      <StatCard label="当前在用" :value="stats.inUse" color="green" />
      <StatCard label="最近更新" :value="stats.totalDocs" color="red" />
    </div>

    <div class="sop-home-grid">
      <!-- Left: Main Content -->
      <div class="sop-home-main">
        <!-- Priority Section -->
        <div class="sop-section" v-if="priorityDocs.length">
          <div class="sop-section__header">
            <h3 class="sop-section__title">今日必看 · 优先处理 <span style="font-size:12px;font-weight:normal;color:var(--text-muted);margin-left:8px;">建议优先查看</span></h3>
            <el-tag type="danger" size="small" effect="dark" round style="font-weight:bold;">{{ priorityDocs.length }}</el-tag>
          </div>
          <div class="sop-priority-list">
            <PriorityDocCard
              v-for="(doc, i) in priorityDocs"
              :key="doc.resource_id"
              :doc="doc"
              :index="i + 1"
              @open="openStageDoc(doc)"
            />
          </div>
        </div>

        <!-- Document Table Section -->
        <div class="sop-section">
          <div class="sop-table-tabs">
            <button
              v-for="tab in tableTabs"
              :key="tab.key"
              class="sop-table-tab"
              :class="{ 'sop-table-tab--active': activeTab === tab.key }"
              @click="setTab(tab.key)"
            >
              {{ tab.label }}
              <span v-if="tab.count > 0" class="sop-table-tab__count">{{ tab.count }}</span>
            </button>
          </div>

          <FilterBar
            :workspace-id="filters.workspace_id"
            :stage-term-id="filters.stage_term_id"
            :keyword="filters.keyword"
            :workspaces="myWorkspaces"
            :stage-terms="stageTerms"
            @update:workspace-id="filters.workspace_id = $event; filters.page = 1"
            @update:stage-term-id="filters.stage_term_id = $event; filters.page = 1"
            @update:keyword="filters.keyword = $event; filters.page = 1"
          />

          <el-table :data="bindingRows" style="margin-top: 12px; border:none;" v-loading="bindingLoading" class="sop-doc-table">
            <el-table-column prop="title" label="文档名称" min-width="220">
              <template #default="{ row }">
                <div class="sop-doc-title-cell">
                  <el-button link style="font-weight:600; color:var(--text-primary);" @click="openBindingRow(row)" class="sop-doc-title-btn">{{ row.title }}</el-button>
                  <span v-if="row.remark" class="sop-doc-remark-inline">{{ row.remark }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="workspace_name" label="所属项目" width="160" show-overflow-tooltip />
            <el-table-column prop="stage_label" label="阶段" width="100" show-overflow-tooltip />
            <el-table-column prop="relation_role" label="状态" width="100">
              <template #default="{ row }">
                <span class="role-badge" :class="`role-badge--${row.relation_role}`" style="border: 1px solid transparent;">{{ roleLabel(row.relation_role) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="90">
               <template #default="{ row }">
                 <span v-if="row.relation_role === 'official' || row.relation_role === 'candidate'" style="color:#ef4444; font-size:12px; font-weight:600;">高 <span style="font-size:10px;">↑</span></span>
                 <span v-else style="color:#10b981; font-size:12px; font-weight:600;">低 <span style="font-size:10px;">↓</span></span>
               </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="最后更新" width="110">
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
                  <el-dropdown-item @click="openBindingRow(row)">打开文档</el-dropdown-item>
                  <el-dropdown-item @click="goBindingWorkspace(row)">查看项目</el-dropdown-item>
                </el-dropdown-menu>
              </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="bindingTotal > filters.page_size"
            :current-page="filters.page"
            :page-size="filters.page_size"
            :total="bindingTotal"
            layout="prev, pager, next"
            @current-change="filters.page = $event"
            style="margin-top: 12px; text-align: right;"
          />
        </div>
      </div>

      <!-- Right: Sidebar -->
      <div class="sop-sidebar">
        <div class="sop-sidebar__panel" v-if="myWorkspaces.length">
          <h4>我负责的项目 <span style="font-weight: normal; font-size: 12px; color: var(--text-muted); float: right;">{{ myWorkspaces.length }}个</span></h4>
          <div style="display:flex; flex-direction:column; gap:8px;">
            <div
              v-for="ws in myWorkspaces"
              :key="ws.id"
              class="sop-sidebar__project-item ws-card-mini"
              @click="goWorkspace(ws.id)"
            >
              <div class="ws-card-mini__main">
                <div class="ws-card-mini__title">{{ ws.name }}</div>
                <div class="ws-card-mini__meta">
                  <span class="role-badge" style="background:transparent; padding:0; color:var(--text-muted);">负责人: {{ ws.owner_name || '暂无' }}</span>
                </div>
              </div>
              <div class="ws-card-mini__right">
                <span class="ws-card-mini__stage" v-if="ws.current_stage_label">{{ ws.current_stage_label }}</span>
                <span class="ws-card-mini__count"><el-icon style="margin-right:2px; vertical-align: middle;"><Document /></el-icon>{{ ws.doc_count }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="sop-sidebar__panel">
          <h4>我负责的项目</h4>
          <div style="color:var(--text-muted);font-size:13px;">暂无负责的项目</div>
        </div>

        <div class="sop-sidebar__panel" v-if="governanceSummary && hasGovernanceIssues">
          <h4>需要处理</h4>
          <div class="gov-summary" style="flex-direction:column;">
            <button type="button" class="gov-summary__item" v-if="governanceSummary.needs_sorting.length" @click="goGovernance('needs_sorting')">
              <div class="gov-summary__count">{{ governanceSummary.needs_sorting.length }}</div>
              <div class="gov-summary__label">还没归类</div>
            </button>
            <button type="button" class="gov-summary__item" v-if="governanceSummary.needs_verification.length" @click="goGovernance('needs_verification')">
              <div class="gov-summary__count">{{ governanceSummary.needs_verification.length }}</div>
              <div class="gov-summary__label">待确认可用</div>
            </button>
            <button type="button" class="gov-summary__item" v-if="governanceSummary.duplicate_primary_docs.length" @click="goGovernance('duplicate_primary')">
              <div class="gov-summary__count">{{ governanceSummary.duplicate_primary_docs.length }}</div>
              <div class="gov-summary__label">当前在用重复</div>
            </button>
            <button type="button" class="gov-summary__item" v-if="governanceSummary.missing_official_docs.length" @click="goGovernance('missing_official')">
              <div class="gov-summary__count">{{ governanceSummary.missing_official_docs.length }}</div>
              <div class="gov-summary__label">未设置当前在用</div>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && !myWorkspaces.length && !bindingRows.length" style="text-align:center;padding:60px 0;">
      <el-empty description='还没有登记过飞书文档，先从"登记飞书链接"开始'>
        <el-button type="primary" @click="quickAddVisible = true">登记飞书链接</el-button>
      </el-empty>
    </div>

    <!-- Dialogs -->
    <QuickAddDialog v-model="quickAddVisible" @success="refresh" />
    <WorkspaceFormDialog v-model="wsFormVisible" @saved="refresh" />
  </div>
</template>

<script lang="ts">
export default { name: 'SopDocsHome' }
</script>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { MoreFilled, Document } from '@element-plus/icons-vue'
import { useSopDocsHome } from './composables/useSopDocsHome'
import { useBindingList } from './composables/useBindingList'
import request from '#/utils/request'
import StatCard from './components/StatCard.vue'
import PriorityDocCard from './components/PriorityDocCard.vue'
import FilterBar from './components/FilterBar.vue'
import QuickAddDialog from './components/QuickAddDialog.vue'
import WorkspaceFormDialog from './components/WorkspaceFormDialog.vue'

const router = useRouter()
const {
  myWorkspaces, currentStageDocs, governanceSummary,
  loading, fetchHome, openResource,
} = useSopDocsHome()

const {
  items: bindingRows, total: bindingTotal, loading: bindingLoading,
  filters, setTab, fetchList,
} = useBindingList()

const quickAddVisible = ref(false)
const wsFormVisible = ref(false)
const stageTerms = ref<any[]>([])

const activeTab = computed(() => filters.relation_role || 'all')

const stats = computed(() => {
  const gov = governanceSummary.value
  return {
    pending: (gov?.needs_sorting?.length || 0) + (gov?.needs_verification?.length || 0),
    todayMustSee: currentStageDocs.value.length,
    inUse: currentStageDocs.value.filter(d => d.relation_role === 'official').length,
    totalDocs: myWorkspaces.value.reduce((sum, ws) => sum + (ws.doc_count || 0), 0),
  }
})

const priorityDocs = computed(() => currentStageDocs.value)

const tableTabs = computed(() => [
  { key: 'all', label: '全部文档', count: bindingTotal.value },
  { key: 'official', label: '当前在用', count: bindingRows.value.filter(r => r.relation_role === 'official').length },
  { key: 'support', label: '参考资料', count: bindingRows.value.filter(r => r.relation_role === 'support').length },
  { key: 'candidate', label: '备选方案', count: bindingRows.value.filter(r => r.relation_role === 'candidate').length },
])

const hasGovernanceIssues = computed(() => {
  if (!governanceSummary.value) return false
  const g = governanceSummary.value
  return g.needs_sorting.length > 0 || g.needs_verification.length > 0 ||
    g.duplicate_primary_docs.length > 0 || g.missing_official_docs.length > 0
})

const roleLabel = (role: string) => {
  const map: Record<string, string> = { official: '当前在用', support: '参考资料', candidate: '备选方案', archive: '历史归档' }
  return map[role] || role
}

const docTypeLabel = (type: string) => {
  const map: Record<string, string> = { doc: '文档', sheet: '表格', bitable: '多维表格', wiki: '知识库', folder: '文件夹' }
  return map[type] || '文档'
}

const typeLabel = (type: string) => {
  const map: Record<string, string> = { project: '项目', campaign: '活动', customer: '客户', template_hub: '模板', inbox: '收件箱' }
  return map[type] || type
}

const fetchTerms = async () => {
  try {
    const terms = await request.get('/v1/external-docs/terms', { params: { dimension: 'stage' } })
    stageTerms.value = terms || []
  } catch (e) { console.error(e) }
}

const refresh = async () => {
  await Promise.all([fetchHome(), fetchList()])
}

const goWorkspace = (id: number) => router.push(`/sop-docs/workspace/${id}`)
const goGovernance = (tab?: string) => router.push({ path: '/sop-docs/governance', query: tab ? { tab } : undefined })
const openStageDoc = (doc: any) => openResource(doc.resource_id, doc.workspace_id)
const openBindingRow = (row: any) => openResource(row.resource_id, row.workspace_id || undefined)
const goBindingWorkspace = (row: any) => { if (row.workspace_id) router.push(`/sop-docs/workspace/${row.workspace_id}`) }

onMounted(() => { fetchTerms(); refresh() })
</script>

<style src="./styles/sopDocs.css"></style>
