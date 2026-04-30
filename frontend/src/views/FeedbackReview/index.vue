<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">AI 反馈审核</h1>
        <p class="page-desc">查看教练对 AI 回复的反馈，优化提示词质量</p>
      </div>
    </div>

    <!-- Stats cards -->
    <div class="stats-row" v-if="stats">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">反馈总数</div>
      </div>
      <div class="stat-card stat-card--like">
        <div class="stat-value">{{ stats.like_count }}</div>
        <div class="stat-label">有帮助</div>
      </div>
      <div class="stat-card stat-card--dislike">
        <div class="stat-value">{{ stats.dislike_count }}</div>
        <div class="stat-label">没帮助</div>
      </div>
      <div class="stat-card stat-card--rate">
        <div class="stat-value">{{ (stats.dislike_rate * 100).toFixed(1) }}%</div>
        <div class="stat-label">负面率</div>
      </div>
    </div>

    <el-card class="table-card">
      <!-- Filters -->
      <div class="toolbar">
        <el-select v-model="filters.rating" placeholder="评分" clearable style="width: 120px" @change="fetchList">
          <el-option label="有帮助" value="like" />
          <el-option label="没帮助" value="dislike" />
        </el-select>
        <el-select v-model="filters.reason_category" placeholder="原因分类" clearable style="width: 140px" @change="fetchList">
          <el-option v-for="r in reasonOptions" :key="r" :label="r" :value="r" />
        </el-select>
        <el-select v-model="filters.status" placeholder="处理状态" clearable style="width: 130px" @change="fetchList">
          <el-option label="待处理" value="new" />
          <el-option label="已审阅" value="reviewed" />
          <el-option label="已用于优化" value="used_for_prompt" />
          <el-option label="已忽略" value="ignored" />
        </el-select>
        <el-select v-model="filters.scene_key" placeholder="场景" clearable style="width: 120px" @change="fetchList">
          <el-option v-for="s in sceneOptions" :key="s" :label="s" :value="s" />
        </el-select>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
          @change="fetchList"
        />
      </div>

      <!-- Table -->
      <el-table :data="items" v-loading="loading" stripe style="width: 100%">
        <el-table-column label="客户" prop="crm_customer_id" width="80" />
        <el-table-column label="教练" prop="coach_user_id" width="80" />
        <el-table-column label="问题摘要" min-width="200">
          <template #default="{ row }">
            <span class="text-truncate">{{ row.user_question_snapshot || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="评分" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.rating === 'like' ? 'success' : 'danger'" size="small" effect="plain">
              {{ row.rating === 'like' ? '有帮助' : '没帮助' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="原因" width="110">
          <template #default="{ row }">
            <span v-if="row.reason_category">{{ row.reason_category }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="场景" prop="scene_key" width="100">
          <template #default="{ row }">
            <span>{{ sceneLabel(row.scene_key) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small" effect="plain">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            <span class="text-muted">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
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

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" title="反馈详情" width="640px" destroy-on-close>
      <template v-if="detail">
        <div class="detail-section">
          <div class="detail-label">教练提问</div>
          <div class="detail-content">{{ detail.user_question_snapshot || '(无)' }}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">AI 回答</div>
          <div class="detail-content detail-content--pre">{{ detail.ai_answer_snapshot || '(无)' }}</div>
        </div>
        <div class="detail-section" v-if="detail.customer_reply_snapshot">
          <div class="detail-label">客户话术（txt 代码块）</div>
          <div class="detail-content detail-content--code">{{ detail.customer_reply_snapshot }}</div>
        </div>
        <div class="detail-section" v-if="detail.reason_category || detail.reason_text">
          <div class="detail-label">反馈原因</div>
          <el-tag v-if="detail.reason_category" size="small" style="margin-right: 8px">{{ detail.reason_category }}</el-tag>
          <span>{{ detail.reason_text || '' }}</span>
        </div>
        <div class="detail-section" v-if="detail.expected_answer">
          <div class="detail-label">期望回答</div>
          <div class="detail-content detail-content--pre">{{ detail.expected_answer }}</div>
        </div>
        <el-descriptions :column="2" border size="small" class="detail-meta">
          <el-descriptions-item label="评分">
            <el-tag :type="detail.rating === 'like' ? 'success' : 'danger'" size="small">{{ detail.rating === 'like' ? '有帮助' : '没帮助' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detail.status)" size="small">{{ statusLabel(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="场景">{{ sceneLabel(detail.scene_key) || '-' }}</el-descriptions-item>
          <el-descriptions-item label="输出风格">{{ detail.output_style || '-' }}</el-descriptions-item>
          <el-descriptions-item label="Prompt 版本">{{ detail.prompt_version || '-' }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ detail.model || '-' }}</el-descriptions-item>
          <el-descriptions-item label="时间" :span="2">{{ formatTime(detail.created_at) }}</el-descriptions-item>
        </el-descriptions>

        <!-- Admin actions -->
        <div class="detail-actions">
          <el-select v-model="detailForm.status" style="width: 150px">
            <el-option label="待处理" value="new" />
            <el-option label="已审阅" value="reviewed" />
            <el-option label="已用于优化" value="used_for_prompt" />
            <el-option label="已忽略" value="ignored" />
          </el-select>
          <el-input
            v-model="detailForm.admin_note"
            type="textarea"
            :rows="2"
            placeholder="管理员备注..."
            style="flex: 1; margin-left: 12px"
          />
        </div>
      </template>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="saveStatus" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

interface FeedbackItem {
  feedback_id: string
  message_id: string
  crm_customer_id: number
  coach_user_id: number
  rating: string
  reason_category: string | null
  scene_key: string | null
  status: string
  user_question_snapshot: string | null
  created_at: string | null
}

interface FeedbackDetail extends FeedbackItem {
  session_id: string
  reason_text: string | null
  expected_answer: string | null
  ai_answer_snapshot: string | null
  customer_reply_snapshot: string | null
  output_style: string | null
  prompt_version: string | null
  prompt_hash: string | null
  model: string | null
  admin_note: string | null
  updated_at: string | null
}

interface Stats {
  total: number
  like_count: number
  dislike_count: number
  dislike_rate: number
  by_reason: { key: string; count: number }[]
  by_scene: { key: string; count: number }[]
  by_prompt_version: { key: string; count: number }[]
}

const items = ref<FeedbackItem[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 20

const stats = ref<Stats | null>(null)

const filters = reactive({
  rating: '' as string,
  reason_category: '' as string,
  status: '' as string,
  scene_key: '' as string,
})
const dateRange = ref<string[] | null>(null)

const detailVisible = ref(false)
const detail = ref<FeedbackDetail | null>(null)
const detailForm = reactive({ status: 'new', admin_note: '' })
const saving = ref(false)

const reasonOptions = [
  '回答不准确', '回答不完整', '缺乏共情', '语气不当',
  '信息过时', '格式不好', '安全问题', '其他',
]
const sceneOptions = ['meal_review', 'data_monitoring', 'abnormal_intervention', 'qa_support', 'period_review', 'long_term_maintenance']

const sceneLabel = (key: string | null | undefined) => {
  const map: Record<string, string> = {
    meal_review: '餐评', data_monitoring: '数据监测', abnormal_intervention: '异常干预',
    qa_support: '问题答疑', period_review: '周月复盘', long_term_maintenance: '长期维护',
  }
  return key ? (map[key] || key) : '-'
}

const statusLabel = (s: string) => {
  const map: Record<string, string> = { new: '待处理', reviewed: '已审阅', used_for_prompt: '已用于优化', ignored: '已忽略' }
  return map[s] || s
}

const statusTagType = (s: string) => {
  const map: Record<string, string> = { new: 'info', reviewed: 'success', used_for_prompt: 'warning', ignored: 'info' }
  return map[s] || 'info'
}

const formatTime = (t: string | null | undefined) => {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 19)
}

const fetchList = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize }
    if (filters.rating) params.rating = filters.rating
    if (filters.reason_category) params.reason_category = filters.reason_category
    if (filters.status) params.status = filters.status
    if (filters.scene_key) params.scene_key = filters.scene_key
    if (dateRange.value?.[0]) params.date_start = dateRange.value[0]
    if (dateRange.value?.[1]) params.date_end = dateRange.value[1]
    const res: any = await request.get('/v1/crm-customers/ai/feedback', { params })
    items.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const params: Record<string, any> = {}
    if (dateRange.value?.[0]) params.date_start = dateRange.value[0]
    if (dateRange.value?.[1]) params.date_end = dateRange.value[1]
    stats.value = await request.get('/v1/crm-customers/ai/feedback/stats', { params })
  } catch { /* stats are non-critical */ }
}

const openDetail = async (row: FeedbackItem) => {
  try {
    const res: any = await request.get(`/v1/crm-customers/ai/feedback/${row.feedback_id}`)
    detail.value = res
    detailForm.status = res.status
    detailForm.admin_note = res.admin_note || ''
    detailVisible.value = true
  } catch {
    ElMessage.error('获取详情失败')
  }
}

const saveStatus = async () => {
  if (!detail.value) return
  saving.value = true
  try {
    await request.patch(`/v1/crm-customers/ai/feedback/${detail.value.feedback_id}`, {
      status: detailForm.status,
      admin_note: detailForm.admin_note || null,
    })
    ElMessage.success('保存成功')
    detailVisible.value = false
    fetchList()
    fetchStats()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchList()
  fetchStats()
})
</script>

<style scoped>
.page-container { max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { font-size: 22px; font-weight: 700; margin: 0 0 4px; color: var(--text-primary); }
.page-desc { font-size: 14px; color: var(--text-muted); margin: 0; }

.stats-row { display: flex; gap: 16px; margin-bottom: 20px; }
.stat-card {
  flex: 1; padding: 16px 20px; border-radius: 12px; background: var(--card-bg);
  border: 1px solid var(--border-color); text-align: center;
}
.stat-value { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.stat-label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.stat-card--like .stat-value { color: #22c55e; }
.stat-card--dislike .stat-value { color: #ef4444; }
.stat-card--rate .stat-value { color: #f59e0b; }

.table-card { border-radius: 12px; }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.pagination-wrap { display: flex; justify-content: flex-end; margin-top: 16px; }
.text-truncate { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.text-muted { color: var(--text-muted); font-size: 13px; }

.detail-section { margin-bottom: 16px; }
.detail-label { font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }
.detail-content { font-size: 14px; line-height: 1.6; color: var(--text-primary); padding: 10px 14px; background: var(--el-fill-color-light); border-radius: 8px; }
.detail-content--pre { white-space: pre-wrap; max-height: 200px; overflow-y: auto; }
.detail-content--code { white-space: pre-wrap; max-height: 150px; overflow-y: auto; font-family: monospace; background: #f0fdf4; color: #166534; }
:global(html.dark) .detail-content--code { background: rgba(34,197,94,0.1); color: #86efac; }
.detail-meta { margin-top: 20px; }
.detail-actions { display: flex; align-items: flex-start; margin-top: 20px; gap: 0; }
</style>
