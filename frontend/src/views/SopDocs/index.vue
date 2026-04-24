<template>
  <div class="sop-page" v-loading="loading">
    <!-- Hero -->
    <div class="sop-hero">
      <div class="sop-hero__left">
        <h1>飞书文档</h1>
        <p>登记飞书链接，按项目查看“当前在用”的文档</p>
      </div>
      <div class="sop-hero__actions">
        <el-button @click="wsFormVisible = true">新建工作台</el-button>
        <el-button type="primary" @click="quickAddVisible = true">登记飞书链接</el-button>
        <el-button @click="goGovernance()">查看待处理问题</el-button>
      </div>
    </div>

    <!-- My Workspaces -->
    <div class="sop-section" v-if="myWorkspaces.length">
      <div class="sop-section__header">
        <h3 class="sop-section__title">我负责的项目/专题</h3>
      </div>
      <div class="sop-card-row">
        <WorkspaceCard
          v-for="ws in myWorkspaces"
          :key="ws.id"
          :workspace="ws"
          @click="goWorkspace(ws.id)"
        />
      </div>
    </div>

    <div class="sop-section" v-if="systemWorkspaces.length">
      <div class="sop-section__header">
        <h3 class="sop-section__title">常用入口</h3>
      </div>
      <div class="sop-card-row">
        <WorkspaceCard
          v-for="ws in systemWorkspaces"
          :key="ws.id"
          :workspace="ws"
          @click="goWorkspace(ws.id)"
        />
      </div>
    </div>

    <div class="sop-section" v-if="sharedWorkspaces.length">
      <div class="sop-section__header">
        <h3 class="sop-section__title">其他可查看的项目</h3>
      </div>
      <div class="sop-card-row">
        <WorkspaceCard
          v-for="ws in sharedWorkspaces"
          :key="ws.id"
          :workspace="ws"
          @click="goWorkspace(ws.id)"
        />
      </div>
    </div>

    <!-- Recent Docs -->
    <div class="sop-section" v-if="recentDocs.length">
      <div class="sop-section__header">
        <h3 class="sop-section__title">我最近打开过</h3>
      </div>
      <div class="sop-card-grid">
        <ResourceCard
          v-for="doc in recentDocs"
          :key="doc.id"
          :doc="doc"
          @open="openDoc(doc)"
        />
      </div>
    </div>

    <!-- Governance Summary -->
    <div class="sop-section" v-if="governanceSummary && hasGovernanceIssues">
      <div class="sop-section__header">
        <h3 class="sop-section__title">需要处理的问题</h3>
      </div>
      <div class="gov-summary">
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
          <div class="gov-summary__label">“当前在用”重复</div>
        </button>
        <button type="button" class="gov-summary__item" v-if="governanceSummary.missing_official_docs.length" @click="goGovernance('missing_official')">
          <div class="gov-summary__count">{{ governanceSummary.missing_official_docs.length }}</div>
          <div class="gov-summary__label">还没设置“当前在用”</div>
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && !myWorkspaces.length && !recentDocs.length" style="text-align:center;padding:60px 0;">
      <el-empty description="还没有登记过飞书文档，先从“登记飞书链接”开始">
        <el-button type="primary" @click="quickAddVisible = true">登记飞书链接</el-button>
      </el-empty>
    </div>

    <!-- Quick Add Dialog -->
    <QuickAddDialog
      v-model="quickAddVisible"
      @success="fetchHome"
    />

    <!-- Workspace Form Dialog -->
    <WorkspaceFormDialog
      v-model="wsFormVisible"
      @saved="fetchHome"
    />
  </div>
</template>

<script lang="ts">
export default { name: 'SopDocsHome' }
</script>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSopDocsHome } from './composables/useSopDocsHome'
import WorkspaceCard from './components/WorkspaceCard.vue'
import ResourceCard from './components/ResourceCard.vue'
import QuickAddDialog from './components/QuickAddDialog.vue'
import WorkspaceFormDialog from './components/WorkspaceFormDialog.vue'

const router = useRouter()
const {
  myWorkspaces, sharedWorkspaces, systemWorkspaces, recentDocs, governanceSummary,
  loading, fetchHome, openResource,
} = useSopDocsHome()

const quickAddVisible = ref(false)
const wsFormVisible = ref(false)

const hasGovernanceIssues = computed(() => {
  if (!governanceSummary.value) return false
  const g = governanceSummary.value
  return g.needs_sorting.length > 0 || g.needs_verification.length > 0 ||
    g.duplicate_primary_docs.length > 0 || g.missing_official_docs.length > 0
})

const goWorkspace = (id: number) => {
  router.push(`/sop-docs/workspace/${id}`)
}

const goGovernance = (tab?: string) => {
  router.push({
    path: '/sop-docs/governance',
    query: tab ? { tab } : undefined,
  })
}

const openDoc = (doc: any) => {
  openResource(doc.id)
}
</script>

<style src="./styles/sopDocs.css"></style>
