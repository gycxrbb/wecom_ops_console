<template>
  <div>
    <!-- Filters -->
    <div class="filter-bar">
      <el-input v-model="filters.q" placeholder="搜索标题" clearable size="small" style="width: 160px" @clear="fetchList" @keyup.enter="fetchList" />
      <el-select v-model="filters.source_type" placeholder="来源" clearable size="small" style="width: 100px" @change="fetchList">
        <el-option label="话术" value="speech_template" />
        <el-option label="素材" value="material" />
      </el-select>
      <el-select v-model="filters.content_kind" placeholder="类型" clearable size="small" style="width: 100px" @change="fetchList">
        <el-option label="guidance" value="guidance" />
        <el-option label="qa" value="qa" />
        <el-option label="script" value="script" />
        <el-option label="material" value="material" />
        <el-option label="knowledge" value="knowledge" />
      </el-select>
      <el-select v-model="filters.quality" placeholder="质量" clearable size="small" style="width: 90px" @change="fetchList">
        <el-option label="ok" value="ok" />
        <el-option label="medium" value="medium" />
        <el-option label="weak" value="weak" />
        <el-option label="stale" value="stale" />
      </el-select>
      <el-select v-model="filters.rag_status" placeholder="状态" clearable size="small" style="width: 90px" @change="fetchList">
        <el-option label="active" value="active" />
        <el-option label="disabled" value="disabled" />
      </el-select>
      <el-select v-model="filters.safety_level" placeholder="安全" clearable size="small" style="width: 110px" @change="fetchList">
        <el-option label="通用" value="general" />
        <el-option label="营养宣教" value="nutrition_education" />
        <el-option label="医疗敏感" value="medical_sensitive" />
      </el-select>
      <el-select v-model="filters.visibility" placeholder="可见性" clearable size="small" style="width: 120px" @change="fetchList">
        <el-option label="coach_internal" value="coach_internal" />
        <el-option label="customer_visible" value="customer_visible" />
      </el-select>
      <el-button size="small" type="primary" @click="fetchList">查询</el-button>
    </div>

    <el-table :data="items" v-loading="loading" stripe border size="small">
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="source_type" label="来源" width="70" align="center">
        <template #default="{ row }">{{ row.source_type === 'speech_template' ? '话术' : '素材' }}</template>
      </el-table-column>
      <el-table-column prop="content_kind" label="类型" width="80" align="center" />
      <el-table-column prop="semantic_quality" label="质量" width="65" align="center">
        <template #default="{ row }">
          <el-tag :type="qualityType(row.semantic_quality)" size="small">{{ row.semantic_quality }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="safety_level" label="安全" width="90" align="center" />
      <el-table-column prop="chunk_count" label="分块" width="55" align="center" />
      <el-table-column prop="status" label="状态" width="70" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="150">
        <template #default="{ row }">{{ row.updated_at?.slice(0, 16).replace('T', ' ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="viewDetail(row)">详情</el-button>
          <el-button v-if="row.status === 'active'" size="small" text type="warning" @click="toggleStatus(row, 'disabled')">禁用</el-button>
          <el-button v-else size="small" text type="success" @click="toggleStatus(row, 'active')">启用</el-button>
          <el-button size="small" text @click="reindexOne(row)">重建</el-button>
          <el-popconfirm title="删除的是 RAG 索引，不删除原始话术/素材。确定？" @confirm="deleteResource(row)">
            <template #reference>
              <el-button size="small" text type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination v-if="total > pageSize" :current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" style="margin-top: 12px" @current-change="(p: number) => { page = p; fetchList() }" />

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" title="资源详情" width="700px" destroy-on-close>
      <div v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="标题">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ detail.source_type }} #{{ detail.source_id }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ detail.content_kind }}</el-descriptions-item>
          <el-descriptions-item label="质量">{{ detail.semantic_quality }}</el-descriptions-item>
          <el-descriptions-item label="安全级别">{{ detail.safety_level }}</el-descriptions-item>
          <el-descriptions-item label="可见性">{{ detail.visibility }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item>
          <el-descriptions-item label="分块数">{{ detail.chunks?.length || 0 }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detail.tags?.length" style="margin-top: 12px">
          <span style="font-size: 12px; color: var(--text-muted)">标签：</span>
          <el-tag v-for="t in detail.tags" :key="t.id" size="small" style="margin: 2px">{{ t.dimension }}:{{ t.name }}</el-tag>
        </div>
        <div v-if="detail.summary" style="margin-top: 12px">
          <div class="detail-label">摘要</div>
          <div class="detail-text">{{ detail.summary }}</div>
        </div>
        <div v-if="detail.semantic_text" style="margin-top: 12px">
          <div class="detail-label">语义文本 <el-button size="small" text @click="showFullText = !showFullText">{{ showFullText ? '收起' : '展开' }}</el-button></div>
          <pre class="detail-text" :class="{ 'is-truncated': !showFullText }">{{ detail.semantic_text }}</pre>
        </div>
        <div v-if="detail.chunks?.length" style="margin-top: 12px">
          <div class="detail-label">分块列表</div>
          <el-table :data="detail.chunks" size="small" border>
            <el-table-column prop="chunk_index" label="#" width="40" align="center" />
            <el-table-column prop="text_preview" label="文本预览" min-width="200" show-overflow-tooltip />
            <el-table-column prop="embedding_model" label="嵌入模型" width="160" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="60" align="center" />
          </el-table>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

const loading = ref(false)
const items = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filters = reactive({ q: '', source_type: '', content_kind: '', quality: '', rag_status: '', safety_level: '', visibility: '' })
const detailVisible = ref(false)
const detail = ref<any>(null)
const showFullText = ref(false)

const qualityType = (q: string) => {
  if (q === 'ok') return 'success'
  if (q === 'stale') return 'warning'
  if (q === 'weak') return 'danger'
  return 'info'
}

const fetchList = async () => {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (filters.q) params.q = filters.q
    if (filters.source_type) params.source_type = filters.source_type
    if (filters.content_kind) params.content_kind = filters.content_kind
    if (filters.quality) params.quality = filters.quality
    if (filters.rag_status) params.rag_status = filters.rag_status
    if (filters.safety_level) params.safety_level = filters.safety_level
    if (filters.visibility) params.visibility = filters.visibility
    const res: any = await request.get('/v1/rag/resources', { params })
    items.value = res.items || []
    total.value = res.total || 0
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

const viewDetail = async (row: any) => {
  try {
    detail.value = await request.get(`/v1/rag/resources/${row.id}`)
    showFullText.value = false
    detailVisible.value = true
  } catch (e: any) {
    ElMessage.error('加载失败: ' + String(e))
  }
}

const deleteResource = async (row: any) => {
  try {
    const res: any = await request.delete(`/v1/rag/resources/${row.id}`)
    if (res.status === 'fallback_disabled') {
      ElMessage.warning(res.message || 'Qdrant 删除失败，资源已降级为 disabled')
    } else {
      ElMessage.success('已删除')
    }
    fetchList()
  } catch (e: any) {
    ElMessage.error('删除失败: ' + String(e))
  }
}

const toggleStatus = async (row: any, target: string) => {
  try {
    const action = target === 'disabled' ? 'disable' : 'enable'
    await request.post(`/v1/rag/resources/${row.id}/${action}`)
    ElMessage.success(target === 'disabled' ? '已禁用' : '已启用')
    fetchList()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + String(e))
  }
}

const reindexOne = async (row: any) => {
  try {
    await request.post(`/v1/rag/resources/${row.id}/reindex`)
    ElMessage.success('重建完成')
    fetchList()
  } catch (e: any) {
    ElMessage.error('重建失败: ' + String(e))
  }
}

onMounted(fetchList)
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  align-items: center;
}
.detail-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.detail-text {
  font-size: 13px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  padding: 8px 12px;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
}
.detail-text.is-truncated {
  max-height: 120px;
  overflow: hidden;
  position: relative;
}
</style>
