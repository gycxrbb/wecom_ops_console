<template>
  <div class="sop-page" v-loading="loading">
    <div class="sop-hero">
      <div class="sop-hero__left">
        <h1>{{ workspace?.name || '工作台详情' }}</h1>
        <p>按阶段查看当前在用、参考资料和备选方案</p>
      </div>
      <div class="sop-hero__actions">
        <el-button @click="$router.push('/sop-docs')">返回</el-button>
        <el-button type="primary" @click="quickAddVisible = true">登记飞书链接</el-button>
      </div>
    </div>

    <div v-if="overview">
      <div v-for="stage in overview.stages" :key="stage.term?.id || 'unassigned'" class="sop-section">
        <div class="sop-section__header">
          <h3 class="sop-section__title">{{ stage.term?.label || '未分配阶段' }}</h3>
        </div>
        <template v-if="stage.official_docs.length">
          <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">正式文档</div>
          <div class="sop-card-grid" style="margin-bottom:12px;">
            <ResourceCard v-for="doc in stage.official_docs" :key="doc.binding_id" :doc="doc" @open="openDoc(doc)" />
          </div>
        </template>
        <template v-if="stage.support_docs.length">
          <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">参考资料</div>
          <div class="sop-card-grid" style="margin-bottom:12px;">
            <ResourceCard v-for="doc in stage.support_docs" :key="doc.binding_id" :doc="doc" @open="openDoc(doc)" />
          </div>
        </template>
        <template v-if="stage.candidate_docs.length">
          <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">备选方案</div>
          <div class="sop-card-grid">
            <ResourceCard v-for="doc in stage.candidate_docs" :key="doc.binding_id" :doc="doc" @open="openDoc(doc)" />
          </div>
        </template>
        <template v-if="stage.archive_docs.length">
          <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px;">历史归档</div>
          <div class="sop-card-grid">
            <ResourceCard v-for="doc in stage.archive_docs" :key="doc.binding_id" :doc="doc" @open="openDoc(doc)" />
          </div>
        </template>
        <el-empty v-if="!stage.official_docs.length && !stage.support_docs.length && !stage.candidate_docs.length"
          description="这个阶段还没登记文档" :image-size="60" />
      </div>
    </div>
    <el-empty v-else-if="!loading" description="工作台不存在" />

    <QuickAddDialog v-model="quickAddVisible" @success="fetchOverview" />
  </div>
</template>

<script lang="ts">
export default { name: 'WorkspaceDetail' }
</script>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import request from '@/utils/request'
import ResourceCard from './components/ResourceCard.vue'
import QuickAddDialog from './components/QuickAddDialog.vue'

const route = useRoute()
const workspaceId = computed(() => route.params.id as string)

const workspace = ref<any>(null)
const overview = ref<any>(null)
const loading = ref(false)
const quickAddVisible = ref(false)

const fetchOverview = async () => {
  loading.value = true
  try {
    overview.value = await request.get(`/v1/external-docs/workspaces/${workspaceId.value}/overview`)
    workspace.value = overview.value?.workspace || null
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
    if (res?.open_url) {
      window.open(res.open_url, '_blank')
    }
  }).catch((error) => {
    console.error(error)
  })
}

onMounted(fetchOverview)
watch(workspaceId, fetchOverview)
</script>

<style src="./styles/sopDocs.css"></style>
