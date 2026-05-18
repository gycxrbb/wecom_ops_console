<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loading } from '@element-plus/icons-vue'
import request from '#/utils/request'
import { useInvocationList } from './composables/useInvocationList'
import { useBrowserDiagnostics } from './composables/useBrowserDiagnostics'
import {
  STATUS_LABEL, STATUS_TAG_TYPE, ERROR_CODE_LABEL,
  SCENE_LABEL, formatTime,
  type InvocationListItem,
} from './composables/useInvocationTypes'

const route = useRoute()
const router = useRouter()

const {
  items, loading, total, page, pageSize,
  filters, dateRange,
  stats, trends, breakdown, detail, detailVisible,
  fetchList, fetchStats, fetchTrends, fetchBreakdown, openDetail,
  refresh, refreshCritical, filterByCustomer, filterBySession, clearGroupFilter,
} = useInvocationList()

const breakdownDimension = ref('model')
const dashboardLoaded = ref(false)
const groupMode = ref<'flat' | 'customer' | 'session'>('flat')

onMounted(async () => {
  // Load critical data first (list + stats cards)
  fetchList()
  fetchStats()
  // Lazy-load dashboard charts after critical data
  requestAnimationFrame(() => {
    setTimeout(() => {
      fetchTrends()
      fetchBreakdown('model')
      dashboardLoaded.value = true
    }, 100)
  })
  // Deep link: auto-open detail if call_id in query
  const cid = route.query.call_id as string
  const mid = route.query.message_id as string
  if (cid) {
    openDetail(cid)
    router.replace({ query: {} })
  } else if (mid) {
    // Cross-module: lookup call_id by message_id
    try {
      const res = await request.get('/v1/crm-customers/ai/invocations/lookup/by-message', { params: { message_id: mid } })
      if (res.call_id) openDetail(res.call_id)
    } catch { /* no invocation found */ }
    router.replace({ query: {} })
  }
})

const statusOptions = Object.entries(STATUS_LABEL).map(([k, v]) => ({ value: k, label: v }))

// --- Trend chart computation ---
const trendMax = computed(() => {
  if (!trends.value.length) return 1
  return Math.max(...trends.value.map(t => t.total), 1)
})

// --- Breakdown change handler ---
const onBreakdownChange = (dim: string) => {
  breakdownDimension.value = dim
  fetchBreakdown(dim)
}

// --- Grouped view ---
interface GroupInfo { key: string; label: string; items: InvocationListItem[] }
const groupedItems = computed<GroupInfo[]>(() => {
  if (groupMode.value === 'flat') return []
  const map = new Map<string, InvocationListItem[]>()
  for (const item of items.value) {
    const key = groupMode.value === 'customer'
      ? String(item.crm_customer_id || '_none')
      : (item.session_id || '_none')
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(item)
  }
  const groups: GroupInfo[] = []
  for (const [key, groupItems] of map) {
    const label = groupMode.value === 'customer'
      ? (groupItems[0].crm_customer_name || `客户 ${key}`)
      : (key === '_none' ? '无会话' : key.substring(0, 12) + '...')
    groups.push({ key, label, items: groupItems })
  }
  return groups
})

const onGroupModeChange = () => {
  clearGroupFilter()
}

// --- Cross-module navigation ---
const goToFeedback = (messageId: string) => {
  router.push({ path: '/feedback-review', query: { message_id: messageId } })
}

// --- Browser diagnostics ---
const { running: diagRunning, results: diagResults, run: runDiag } = useBrowserDiagnostics()
const diagVisible = ref(false)
const startDiag = async () => {
  diagVisible.value = true
  await runDiag()
}
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>AI 调用审计</h2>
        <p class="page-desc">查看所有 AI 对话调用记录，包含成功、失败和异常的完整 trace</p>
      </div>
      <el-button type="info" plain size="small" @click="startDiag" :loading="diagRunning">
        浏览器诊断
      </el-button>
    </div>

    <!-- Browser diagnostics panel -->
    <el-card v-if="diagVisible" shadow="never" class="diag-card">
      <template #header>
        <div style="display: flex; align-items: center; justify-content: space-between">
          <span class="card-header-title">浏览器侧诊断</span>
          <el-button text size="small" @click="diagVisible = false">关闭</el-button>
        </div>
      </template>
      <div class="diag-notice">
        以下结果仅作为辅助判断，帮助定位网络或服务连通性问题，不代表最终诊断结论。
      </div>
      <div v-if="diagRunning" style="text-align: center; padding: 20px">
        <el-icon class="is-loading" :size="20"><Loading /></el-icon>
        <span style="margin-left: 8px; color: #909399">正在执行诊断...</span>
      </div>
      <el-table v-else :data="diagResults" size="small" stripe>
        <el-table-column prop="name" label="检查项" width="130" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ok' ? 'success' : row.status === 'timeout' ? 'warning' : 'danger'" size="small">
              {{ row.status === 'ok' ? '正常' : row.status === 'timeout' ? '超时' : '异常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="latency_ms" label="耗时" width="90">
          <template #default="{ row }">{{ row.latency_ms }}ms</template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" min-width="200" />
      </el-table>
    </el-card>

    <!-- Stats cards -->
    <el-row :gutter="16" class="stats-row" v-if="stats">
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-title">总调用</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" style="color: #67c23a">{{ stats.total ? ((1 - stats.error_rate) * 100).toFixed(1) : 0 }}%</div>
          <div class="stat-title">成功率</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value">{{ Math.round(stats.avg_latency_ms) }}ms</div>
          <div class="stat-title">平均耗时</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" style="color: #f56c6c">{{ stats.error_count }}</div>
          <div class="stat-title">失败数</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" style="color: #409eff">{{ (stats.total_tokens / 1000).toFixed(1) }}k</div>
          <div class="stat-title">Token 消耗</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value" style="color: #e6a23c">{{ stats.error_rate ? (stats.error_rate * 100).toFixed(1) : 0 }}%</div>
          <div class="stat-title">错误率</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Dashboard: Trends + Breakdown -->
    <el-row :gutter="16" class="dashboard-row">
      <el-col :span="14">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <span class="card-header-title">调用趋势（近14天）</span>
          </template>
          <div v-if="trends.length" class="trend-chart">
            <div class="trend-bars">
              <div v-for="t in trends" :key="t.date" class="trend-col" :title="`${t.date}: ${t.total} 次`">
                <div class="trend-bar-wrap">
                  <div class="trend-bar trend-bar-success" :style="{ height: (t.success_count / trendMax * 100) + '%' }"></div>
                  <div class="trend-bar trend-bar-error" :style="{ height: (t.error_count / trendMax * 100) + '%' }"></div>
                </div>
                <div class="trend-label">{{ t.date.slice(5) }}</div>
              </div>
            </div>
            <div class="trend-legend">
              <span class="legend-item"><span class="legend-dot" style="background: #67c23a"></span> 成功</span>
              <span class="legend-item"><span class="legend-dot" style="background: #f56c6c"></span> 失败</span>
            </div>
          </div>
          <el-empty v-else description="暂无趋势数据" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header-row">
              <span class="card-header-title">维度分析</span>
              <el-radio-group v-model="breakdownDimension" size="small" @change="onBreakdownChange">
                <el-radio-button value="model">模型</el-radio-button>
                <el-radio-button value="scene">场景</el-radio-button>
                <el-radio-button value="error_code">错误码</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <el-table :data="breakdown" size="small" stripe max-height="280" v-if="breakdown.length">
            <el-table-column prop="key" :label="breakdownDimension === 'error_code' ? '错误码' : breakdownDimension === 'scene' ? '场景' : '模型'" min-width="120">
              <template #default="{ row }">
                {{ breakdownDimension === 'error_code' ? (ERROR_CODE_LABEL[row.key] || row.key) :
                   breakdownDimension === 'scene' ? (SCENE_LABEL[row.key] || row.key) : row.key }}
              </template>
            </el-table-column>
            <el-table-column prop="total" label="调用" width="60" />
            <el-table-column label="成功" width="60">
              <template #default="{ row }">{{ row.success_count }}</template>
            </el-table-column>
            <el-table-column label="失败" width="60">
              <template #default="{ row }">
                <span :style="{ color: row.error_count > 0 ? '#f56c6c' : '' }">{{ row.error_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="耗时" width="70">
              <template #default="{ row }">{{ Math.round(row.avg_latency_ms) }}ms</template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无数据" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Errors by code (when present) -->
    <el-card shadow="never" class="errors-card" v-if="stats?.errors_by_code?.length">
      <template #header>
        <span class="card-header-title">错误码分布 TOP {{ stats.errors_by_code.length }}</span>
      </template>
      <div class="errors-bar-chart">
        <div v-for="(item, idx) in stats.errors_by_code" :key="item.code" class="errors-bar-row">
          <span class="errors-bar-label">{{ ERROR_CODE_LABEL[item.code] || item.code }}</span>
          <div class="errors-bar-track">
            <div class="errors-bar-fill" :style="{ width: (item.count / stats.errors_by_code[0].count * 100) + '%' }"></div>
          </div>
          <span class="errors-bar-count">{{ item.count }}</span>
        </div>
      </div>
    </el-card>

    <!-- Filters -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <div class="filter-row">
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 120px" @change="refreshCritical">
          <el-option v-for="o in statusOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-input v-model="filters.error_code" placeholder="错误码" clearable style="width: 180px" @clear="refresh" @keyup.enter="refresh" />
        <el-input v-model="filters.primary_model" placeholder="模型" clearable style="width: 140px" @clear="refresh" @keyup.enter="refresh" />
        <el-input v-model="filters.session_id" placeholder="Session ID" clearable style="width: 180px" @clear="refresh" @keyup.enter="refresh" />
        <el-date-picker v-model="dateRange" type="daterange" range-separator="-" start-placeholder="开始日期" end-placeholder="结束日期"
          value-format="YYYY-MM-DD" style="width: 260px" @change="refresh" />
        <el-button type="primary" @click="refresh">查询</el-button>
      </div>
    </el-card>

    <!-- Table -->
    <el-card shadow="never">
      <div class="group-bar">
        <span style="font-size: 13px; color: #606266">归类方式：</span>
        <el-radio-group v-model="groupMode" size="small" @change="onGroupModeChange">
          <el-radio-button value="flat">平铺</el-radio-button>
          <el-radio-button value="customer">按客户</el-radio-button>
          <el-radio-button value="session">按会话</el-radio-button>
        </el-radio-group>
        <el-button v-if="filters.crm_customer_id || filters.session_id" size="small" text type="primary" @click="clearGroupFilter" style="margin-left: 8px">
          清除筛选
        </el-button>
      </div>

      <!-- Flat list mode -->
      <el-table v-if="groupMode === 'flat'" :data="items" v-loading="loading" stripe @row-click="(row: any) => openDetail(row.call_id)" style="cursor: pointer">
        <el-table-column prop="call_id" label="Call ID" width="140">
          <template #default="{ row }">
            <span :title="row.call_id">{{ row.call_id?.substring(0, 8) }}...</span>
          </template>
        </el-table-column>
        <el-table-column label="客户" width="120">
          <template #default="{ row }">
            <el-link v-if="row.crm_customer_id" type="primary" :underline="false" @click.stop="filterByCustomer(row.crm_customer_id)">
              {{ row.crm_customer_name || row.crm_customer_id }}
            </el-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="提问者" width="90">
          <template #default="{ row }">
            <span>{{ row.local_user_name || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提问内容" min-width="180">
          <template #default="{ row }">
            <span v-if="row.user_message_preview" class="preview-text" :title="row.user_message_preview">{{ row.user_message_preview }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="(STATUS_TAG_TYPE[row.status] || 'info') as any" size="small">
              {{ STATUS_LABEL[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_code" label="错误码" width="120">
          <template #default="{ row }">
            <span v-if="row.error_code" :title="row.error_code">
              {{ ERROR_CODE_LABEL[row.error_code] || row.error_code }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="primary_model" label="模型" width="110" />
        <el-table-column prop="latency_ms" label="耗时" width="80" sortable>
          <template #default="{ row }">{{ row.latency_ms }}ms</template>
        </el-table-column>
        <el-table-column prop="total_tokens" label="Tokens" width="80" />
        <el-table-column prop="started_at" label="时间" width="160">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
      </el-table>

      <!-- Grouped mode -->
      <div v-else v-loading="loading">
        <el-collapse v-if="groupedItems.length">
          <el-collapse-item v-for="group in groupedItems" :key="group.key" :name="group.key">
            <template #title>
              <div class="group-header">
                <span class="group-label">{{ group.label }}</span>
                <span class="group-count">{{ group.items.length }} 条记录</span>
              </div>
            </template>
            <el-table :data="group.items" size="small" stripe @row-click="(row: any) => openDetail(row.call_id)" style="cursor: pointer">
              <el-table-column prop="call_id" label="Call ID" width="140">
                <template #default="{ row }">
                  <span :title="row.call_id">{{ row.call_id?.substring(0, 8) }}...</span>
                </template>
              </el-table-column>
              <el-table-column v-if="groupMode === 'session'" label="客户" width="120">
                <template #default="{ row }">
                  <el-link v-if="row.crm_customer_id" type="primary" :underline="false" @click.stop="filterByCustomer(row.crm_customer_id)">
                    {{ row.crm_customer_name || row.crm_customer_id }}
                  </el-link>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="提问内容" min-width="200">
                <template #default="{ row }">
                  <span v-if="row.user_message_preview" class="preview-text" :title="row.user_message_preview">{{ row.user_message_preview }}</span>
                  <span v-else class="text-muted">-</span>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="(STATUS_TAG_TYPE[row.status] || 'info') as any" size="small">
                    {{ STATUS_LABEL[row.status] || row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="primary_model" label="模型" width="110" />
              <el-table-column prop="latency_ms" label="耗时" width="80">
                <template #default="{ row }">{{ row.latency_ms }}ms</template>
              </el-table-column>
              <el-table-column prop="started_at" label="时间" width="160">
                <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
        <el-empty v-else description="暂无数据" :image-size="60" />
      </div>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchList"
        />
      </div>
    </el-card>

    <!-- Detail Drawer -->
    <el-drawer v-model="detailVisible" title="调用详情" size="680px" v-if="detail">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="Call ID">{{ detail.call_id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="(STATUS_TAG_TYPE[detail.status] || 'info') as any" size="small">
            {{ STATUS_LABEL[detail.status] || detail.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="客户">
          <el-link v-if="detail.crm_customer_id" type="primary" :underline="false" @click="detailVisible = false; filterByCustomer(detail.crm_customer_id!)">
            {{ detail.crm_customer_name || detail.crm_customer_id }}
          </el-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="提问者">{{ detail.local_user_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="会话" :span="2">
          <el-link v-if="detail.session_id" type="primary" :underline="false" @click="detailVisible = false; filterBySession(detail.session_id!)">
            {{ detail.session_id }}
          </el-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="模型">{{ detail.primary_model || '-' }}</el-descriptions-item>
        <el-descriptions-item label="场景">{{ SCENE_LABEL[detail.scene_key ?? ''] || detail.scene_key || '-' }}</el-descriptions-item>
        <el-descriptions-item label="执行模式">{{ detail.execution_mode }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ formatTime(detail.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ formatTime(detail.finished_at) }}</el-descriptions-item>
        <el-descriptions-item label="总耗时">{{ detail.latency_ms }}ms</el-descriptions-item>
        <el-descriptions-item label="Prepare">{{ detail.prepare_ms }}ms</el-descriptions-item>
        <el-descriptions-item label="首 Token">{{ detail.first_token_ms }}ms</el-descriptions-item>
        <el-descriptions-item label="Total Tokens">{{ detail.total_tokens }}</el-descriptions-item>
        <el-descriptions-item label="RAG 状态">{{ detail.rag_status || '-' }}</el-descriptions-item>
        <el-descriptions-item label="RAG 命中">{{ detail.rag_hit_count }}</el-descriptions-item>
      </el-descriptions>

      <!-- User question -->
      <div v-if="detail.user_message?.content" style="margin-top: 16px">
        <h4 style="margin-bottom: 8px">用户提问</h4>
        <div class="detail-content-box">{{ detail.user_message.content }}</div>
      </div>

      <!-- RAG recall -->
      <div v-if="detail.rag_logs?.length" style="margin-top: 16px">
        <h4 style="margin-bottom: 8px">RAG 召回 ({{ detail.rag_logs.length }} 次)</h4>
        <div v-for="(rag, idx) in detail.rag_logs" :key="idx" class="detail-rag-item">
          <div class="detail-rag-meta">
            <span>查询: {{ rag.query_text || '-' }}</span>
            <span style="color: #909399; margin-left: 8px">{{ rag.latency_ms }}ms</span>
          </div>
          <div v-if="rag.hit_json?.phase1?.length" class="detail-rag-hits">
            <div v-for="hit in rag.hit_json.phase1.slice(0, 5)" :key="hit.resource_id" class="detail-rag-hit">
              <span class="detail-rag-score">{{ hit.score?.toFixed(2) }}</span>
              <span>{{ hit.title }}</span>
            </div>
            <div v-if="rag.hit_json.phase1.length > 5" style="color: #909399; font-size: 12px">
              ... 共 {{ rag.hit_json.phase1.length }} 条
            </div>
          </div>
          <div v-else style="color: #909399; font-size: 12px">无命中</div>
        </div>
      </div>

      <!-- AI reply -->
      <div v-if="detail.assistant_message?.content" style="margin-top: 16px">
        <h4 style="margin-bottom: 8px">AI 回复</h4>
        <div class="detail-content-box detail-content-ai">{{ detail.assistant_message.content }}</div>
      </div>

      <!-- Error section -->
      <div v-if="detail.error_code" style="margin-top: 16px">
        <h4 style="color: #f56c6c; margin-bottom: 8px">错误信息</h4>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="错误阶段">{{ detail.error_stage }}</el-descriptions-item>
          <el-descriptions-item label="错误码">
            {{ ERROR_CODE_LABEL[detail.error_code] || detail.error_code }}
          </el-descriptions-item>
          <el-descriptions-item label="错误消息">{{ detail.error_message }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.error_detail" label="详细信息">
            <pre style="margin: 0; white-space: pre-wrap; max-height: 200px; overflow-y: auto; font-size: 12px">{{ detail.error_detail }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- Cross-module links -->
      <div v-if="detail.assistant_message_id" style="margin-top: 16px">
        <el-button size="small" @click="goToFeedback(detail.assistant_message_id)">
          查看关联反馈
        </el-button>
      </div>

      <!-- Steps timeline -->
      <div v-if="detail.steps?.length" style="margin-top: 16px">
        <h4 style="margin-bottom: 8px">执行步骤</h4>
        <el-table :data="detail.steps" size="small" stripe>
          <el-table-column prop="step_index" label="#" width="40" />
          <el-table-column prop="kind" label="类型" width="120" />
          <el-table-column prop="model" label="模型" width="120" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="latency_ms" label="耗时" width="80">
            <template #default="{ row }">{{ row.latency_ms }}ms</template>
          </el-table-column>
          <el-table-column label="Tokens" width="100">
            <template #default="{ row }">{{ row.prompt_tokens }}/{{ row.completion_tokens }}</template>
          </el-table-column>
          <el-table-column prop="error_message" label="错误" min-width="120">
            <template #default="{ row }">{{ row.error_message || '-' }}</template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.page-container { max-width: 1200px; margin: 0 auto; padding: 20px; }
.page-desc { color: #909399; font-size: 13px; margin: 0; }
.stats-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.stat-value { font-size: 28px; font-weight: 600; color: #303133; }
.stat-title { font-size: 13px; color: #909399; margin-top: 4px; }
.filter-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.text-muted { color: #909399; }

/* Dashboard */
.dashboard-row { margin-bottom: 16px; }
.chart-card { height: 340px; }
.chart-card :deep(.el-card__header) { padding: 12px 16px; }
.chart-card :deep(.el-card__body) { padding: 12px 16px; overflow-y: auto; }
.card-header-title { font-size: 14px; font-weight: 600; }
.card-header-row { display: flex; align-items: center; justify-content: space-between; }

/* Trend chart */
.trend-chart { display: flex; flex-direction: column; height: 100%; }
.trend-bars { display: flex; align-items: flex-end; gap: 4px; flex: 1; padding: 0 4px; min-height: 200px; }
.trend-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 0; }
.trend-bar-wrap { width: 100%; height: 180px; display: flex; flex-direction: column; justify-content: flex-end; }
.trend-bar { width: 100%; min-height: 2px; border-radius: 2px 2px 0 0; transition: height 0.3s; }
.trend-bar-success { background: #67c23a; }
.trend-bar-error { background: #f56c6c; }
.trend-label { font-size: 10px; color: #909399; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.trend-legend { display: flex; gap: 16px; padding-top: 8px; justify-content: center; }
.legend-item { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #606266; }
.legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }

/* Errors bar chart */
.errors-card { margin-bottom: 16px; }
.errors-card :deep(.el-card__header) { padding: 12px 16px; }
.errors-bar-chart { display: flex; flex-direction: column; gap: 8px; }
.errors-bar-row { display: flex; align-items: center; gap: 12px; }
.errors-bar-label { width: 120px; font-size: 13px; color: #606266; text-align: right; flex-shrink: 0; }
.errors-bar-track { flex: 1; height: 18px; background: #f5f7fa; border-radius: 4px; overflow: hidden; }
.errors-bar-fill { height: 100%; background: linear-gradient(90deg, #f56c6c, #fab6b6); border-radius: 4px; transition: width 0.3s; }
.errors-bar-count { width: 40px; font-size: 13px; font-weight: 600; color: #303133; }

/* Diagnostics */
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.diag-card { margin-bottom: 16px; }
.diag-card :deep(.el-card__header) { padding: 12px 16px; }
.diag-notice { font-size: 12px; color: #909399; margin-bottom: 12px; padding: 6px 10px; background: #fdf6ec; border-radius: 6px; }

/* Detail drawer content */
.detail-content-box {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: #303133;
  max-height: 300px;
  overflow-y: auto;
}
.detail-content-ai {
  background: #ecf5ff;
}
.detail-rag-item {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 8px;
}
.detail-rag-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.detail-rag-hits {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.detail-rag-hit {
  background: #f0f2f5;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 6px;
}
.detail-rag-score {
  font-weight: 600;
  color: #409eff;
}

/* Grouped view */
.group-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.group-header { display: flex; align-items: center; gap: 12px; width: 100%; }
.group-label { font-weight: 600; font-size: 14px; color: #303133; }
.group-count { font-size: 12px; color: #909399; }
.preview-text {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
  color: #606266;
}
</style>
