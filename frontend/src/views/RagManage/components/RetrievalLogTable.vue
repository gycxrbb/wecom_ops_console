<template>
  <div>
    <div class="filter-bar">
      <el-input v-model="customerId" placeholder="客户 ID" clearable size="small" style="width: 120px" @keyup.enter="fetchLogs" />
      <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" size="small" style="width: 260px" value-format="YYYY-MM-DD" @change="fetchLogs" />
      <el-button size="small" type="primary" @click="fetchLogs">查询</el-button>
    </div>

    <el-table :data="logs" v-loading="loading" stripe border size="small">
      <el-table-column prop="id" label="ID" width="60" align="center" />
      <el-table-column prop="customer_id" label="客户" width="70" align="center" />
      <el-table-column prop="query_text" label="查询" min-width="180" show-overflow-tooltip />
      <el-table-column label="命中" width="120" align="center">
        <template #default="{ row }">
          <span v-if="row.hits">参考 {{ row.hits.reference ?? 0 }} / 素材 {{ row.hits.material ?? 0 }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="latency_ms" label="耗时(ms)" width="80" align="center" />
      <el-table-column label="时间" width="160">
        <template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="70" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="viewLog(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination v-if="total > pageSize" :current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" style="margin-top: 12px" @current-change="(p: number) => { page = p; fetchLogs() }" />

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" title="检索日志详情" width="700px" destroy-on-close>
      <div v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ detail.latency_ms }} ms</el-descriptions-item>
          <el-descriptions-item label="客户 ID">{{ detail.customer_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="会话">{{ detail.session_id || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.hits" label="命中统计">
            参考 {{ detail.hits.reference ?? 0 }} / 素材 {{ detail.hits.material ?? 0 }} / 共 {{ detail.hits.total ?? 0 }}
          </el-descriptions-item>
        </el-descriptions>
        <div style="margin-top: 12px">
          <div class="detail-label">查询文本</div>
          <pre class="detail-block">{{ detail.query_text }}</pre>
        </div>
        <div v-if="detail.filter_json" style="margin-top: 8px">
          <div class="detail-label">过滤器</div>
          <pre class="detail-block">{{ JSON.stringify(detail.filter_json, null, 2) }}</pre>
        </div>
        <div v-if="detail.query_intent_json" style="margin-top: 8px">
          <div class="detail-label">查询意图</div>
          <pre class="detail-block">{{ JSON.stringify(detail.query_intent_json, null, 2) }}</pre>
        </div>
        <div v-if="detail.intent_json" style="margin-top: 8px">
          <div class="detail-label">意图分析</div>
          <pre class="detail-block">{{ JSON.stringify(detail.intent_json, null, 2) }}</pre>
        </div>
        <div v-if="detail.hit_json" style="margin-top: 8px">
          <div class="detail-label">命中结果 ({{ hitCountDisplay }})</div>
          <pre class="detail-block is-tall">{{ JSON.stringify(detail.hit_json, null, 2) }}</pre>
        </div>
        <div v-if="detail.rerank_scores_json" style="margin-top: 8px">
          <div class="detail-label">重排分数</div>
          <pre class="detail-block">{{ JSON.stringify(detail.rerank_scores_json, null, 2) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

const loading = ref(false)
const logs = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const customerId = ref('')
const dateRange = ref<string[]>([])
const detailVisible = ref(false)
const detail = ref<any>(null)

const hitCountDisplay = computed(() => {
  if (!detail.value?.hit_json) return '0 条'
  const hj = detail.value.hit_json
  if (Array.isArray(hj)) return `${hj.length} 条`
  const ref = (hj.phase1 || []).length
  const mat = (hj.material || []).length
  return `参考 ${ref} / 素材 ${mat}`
})

const fetchLogs = async () => {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize }
    if (customerId.value) params.customer_id = customerId.value
    if (dateRange.value?.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res: any = await request.get('/v1/rag/retrieval-logs', { params })
    logs.value = res.items || []
    total.value = res.total || 0
  } catch { logs.value = [] }
  finally { loading.value = false }
}

const viewLog = async (row: any) => {
  try {
    detail.value = await request.get(`/v1/rag/retrieval-logs/${row.id}`)
    detailVisible.value = true
  } catch (e: any) { ElMessage.error('加载失败: ' + String(e)) }
}

onMounted(fetchLogs)
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.detail-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 4px;
}
.detail-block {
  font-size: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  padding: 8px 12px;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
  max-height: 200px;
  overflow-y: auto;
}
.detail-block.is-tall {
  max-height: 400px;
}
</style>
