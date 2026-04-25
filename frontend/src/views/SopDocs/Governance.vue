<template>
  <div class="sop-page" v-loading="loading">
    <div class="sop-hero">
      <div class="sop-hero__left">
        <h1>待处理问题</h1>
        <p>在这里处理还没归类、待确认可用和设置冲突的问题</p>
      </div>
      <div class="sop-hero__actions">
        <el-button @click="$router.push('/sop-docs')">返回</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="还没归类" name="needs_sorting">
        <el-table :data="queue?.needs_sorting || []" empty-text="暂无还没归类的文档">
          <el-table-column prop="title" label="文档名称" />
          <el-table-column prop="doc_type" label="类型" width="100">
            <template #default="{ row }">
              {{ docTypeLabel(row.doc_type) }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="handleSort(row)">归类</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="待确认可用" name="needs_verification">
        <el-table :data="queue?.needs_verification || []" empty-text="暂无待确认可用的文档">
          <el-table-column prop="title" label="文档名称" />
          <el-table-column prop="verification_status" label="当前状态" width="140">
            <template #default="{ row }">
              <el-tag :type="row.verification_status === 'broken' ? 'danger' : 'warning'" size="small">
                {{ verificationLabel(row.verification_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="180" />
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="handleVerify(row)" :loading="verifyingId === row.resource_id">
                标记已确认
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label='当前在用 重复' name="duplicate_primary">
        <el-table :data="queue?.duplicate_primary_docs || []" empty-text="暂无重复设置">
          <el-table-column prop="workspace_name" label="项目/专题" />
          <el-table-column prop="duplicate_count" label="重复数" width="100" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" @click="goWorkspace(row.workspace_id)">前往处理</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label='还没设置"当前在用"' name="missing_official">
        <el-table :data="queue?.missing_official_docs || []" empty-text="暂无缺失">
          <el-table-column prop="workspace_name" label="项目/专题" />
          <el-table-column prop="workspace_type" label="类型" width="100">
            <template #default="{ row }">
              {{ workspaceTypeLabel(row.workspace_type) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="goWorkspace(row.workspace_id)">前往设置</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- Quick Add for sorting -->
    <QuickAddDialog v-model="sortDialogVisible" @success="fetchQueue" />
  </div>
</template>

<script lang="ts">
export default { name: 'SopDocsGovernance' }
</script>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'
import QuickAddDialog from './components/QuickAddDialog.vue'

const queue = ref<any>(null)
const loading = ref(false)
const route = useRoute()
const router = useRouter()
const activeTab = ref(String(route.query.tab || 'needs_sorting'))
const verifyingId = ref<number | null>(null)
const sortDialogVisible = ref(false)

const verificationLabel = (status: string) => ({
  broken: '链接失效',
  need_check: '待复核',
  unverified: '还没确认',
  verified: '已确认',
} as Record<string, string>)[status] || status

const workspaceTypeLabel = (type: string) => ({
  project: '项目',
  campaign: '活动',
  customer: '客户',
  template_hub: '模板库',
  inbox: '待整理',
} as Record<string, string>)[type] || type

const docTypeLabel = (type: string) => ({
  doc: '文档', sheet: '表格', bitable: '多维表', wiki: '知识库', folder: '文件夹',
} as Record<string, string>)[type] || type

const fetchQueue = async () => {
  loading.value = true
  try {
    queue.value = await request.get('/v1/external-docs/governance/queue')
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleSort = (_row: any) => {
  sortDialogVisible.value = true
}

const handleVerify = async (row: any) => {
  verifyingId.value = row.resource_id
  try {
    await request.put(`/v1/external-docs/resources/${row.resource_id}`, {
      verification_status: 'verified',
    })
    ElMessage.success('已标记为确认可用')
    fetchQueue()
  } catch (e) {
    console.error(e)
  } finally {
    verifyingId.value = null
  }
}

const goWorkspace = (id: number) => {
  router.push(`/sop-docs/workspace/${id}`)
}

onMounted(fetchQueue)

watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})
</script>

<style src="./styles/sopDocs.css"></style>
