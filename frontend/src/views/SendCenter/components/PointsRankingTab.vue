<template>
  <div
    class="points-ranking-tab"
    v-loading="loading"
    element-loading-text="正在连接 CRM 数据库..."
  >
    <!-- CRM 不可用 -->
    <div v-if="!loading && !crmAvailable" class="content-selector__empty">
      <span>CRM 数据库未配置，无法使用积分排行功能</span>
    </div>

    <template v-else-if="!loading">
      <!-- 配置栏 -->
      <div class="ranking-config">
        <div class="ranking-config__row">
          <el-checkbox v-model="config.topNEnabled" label="Top N 上限" />
          <el-input-number
            v-if="config.topNEnabled"
            v-model="config.topN"
            :min="1"
            :max="100"
            :step="5"
            size="small"
          />
          <label>排序指标</label>
          <el-select v-model="config.rankMetric" size="small" style="width: 120px">
            <el-option label="当月积分" value="custom_month_points" />
            <el-option label="当前积分" value="current_points" />
            <el-option label="本周积分" value="week_points" />
          </el-select>
          <label>话术风格</label>
          <el-select v-model="config.speechStyle" size="small" style="width: 120px">
            <el-option label="专业" value="professional" />
            <el-option label="鼓励" value="encouraging" />
            <el-option label="竞技" value="competitive" />
          </el-select>
          <label>洞察场景</label>
          <el-select
            v-model="config.enabledScenes"
            multiple
            collapse-tags
            collapse-tags-tooltip
            size="small"
            style="width: 240px"
            placeholder="全部场景"
          >
            <el-option
              v-for="s in insightScenes"
              :key="s.key"
              :label="s.label"
              :value="s.key"
            />
          </el-select>
          <el-checkbox v-model="config.includeLastWeekBreakdown" size="small">上周积分明细</el-checkbox>
        </div>
      </div>

      <!-- 工具栏: 全选 -->
      <div class="ranking-toolbar">
        <el-checkbox
          :model-value="isAllChecked"
          :indeterminate="isIndeterminate"
          @change="toggleAll"
        >
          全选 ({{ checkedGroupIds.size }}/{{ crmGroups.length }})
        </el-checkbox>
      </div>

      <!-- CRM 群列表 -->
      <div class="ranking-groups">
        <div v-if="crmGroups.length === 0" class="content-selector__empty">
          <span>暂无 CRM 外部群数据</span>
        </div>
        <div
          v-for="g in crmGroups"
          :key="g.id"
          class="ranking-group-item"
          :class="{ 'is-checked': checkedGroupIds.has(g.id) }"
        >
          <el-checkbox
            :model-value="checkedGroupIds.has(g.id)"
            @change="toggleGroup(g.id)"
          />
          <div class="ranking-group-item__info">
            <span class="ranking-group-item__name">{{ g.name }}</span>
            <span class="ranking-group-item__meta">{{ g.member_count }} 人</span>
          </div>
        </div>
      </div>

      <!-- 操作栏 -->
      <div class="ranking-actions">
        <el-button
          type="primary"
          :disabled="checkedGroupIds.size === 0"
          :loading="generating"
          @click="generateRanking"
        >
          生成排行消息 ({{ checkedGroupIds.size }} 群)
        </el-button>
        <el-button
          :disabled="checkedGroupIds.size === 0"
          :loading="generatingGlobal"
          @click="generateGlobalRanking"
        >
          跨群总排行 ({{ checkedGroupIds.size }} 群)
        </el-button>
        <span v-if="generating && generateProgress" class="ranking-actions__progress">
          {{ generateProgress }}
        </span>
      </div>

      <div v-if="generating" class="ranking-progress-card">
        <div class="ranking-progress-card__header">
          <span class="ranking-progress-card__stage">{{ generateStageLabel }}</span>
          <span class="ranking-progress-card__elapsed">已耗时 {{ generateElapsedSeconds }} 秒</span>
        </div>
        <el-progress
          :percentage="generateProgressPercent"
          :stroke-width="10"
          :show-text="false"
        />
        <div class="ranking-progress-card__text">{{ generateProgress }}</div>
        <div class="ranking-progress-card__tip">
          首轮缓存未命中或群内积分流水较多时，后端会在“成员积分聚合 / 亮点洞察分析”阶段更慢，详细耗时会同步打印到后端日志。
        </div>
      </div>

      <div v-if="lastGenerateSummary" class="ranking-result">
        <div class="ranking-result__title">生成结果</div>
        <div class="ranking-result__stats">
          <span>选中 {{ lastGenerateSummary.requestedCount }} 个群</span>
          <span>入队 {{ lastGenerateSummary.queuedCount }} 条</span>
          <span v-if="lastGenerateSummary.skippedCount > 0">跳过 {{ lastGenerateSummary.skippedCount }} 个</span>

          <span v-if="lastGenerateSummary.insightCount > 0">命中洞察 {{ lastGenerateSummary.insightCount }} 条</span>
        </div>
        <div
          v-if="lastGenerateDiagnostics"
          class="ranking-result__stats ranking-result__stats--timing"
        >
          <span>总耗时 {{ formatMs(lastGenerateDiagnostics.total_ms) }}</span>
          <span>群名查询 {{ formatMs(lastGenerateDiagnostics.group_name_lookup_ms) }}</span>
          <span>成员积分聚合 {{ formatMs(lastGenerateDiagnostics.load_members_ms) }}</span>
          <span>洞察分析 {{ formatMs(lastGenerateDiagnostics.insights_ms) }}</span>
          <span>消息组装 {{ formatMs(lastGenerateDiagnostics.generate_items_ms) }}</span>
        </div>
        <div
          v-if="lastGenerateSummary.reasonLines.length > 0"
          class="ranking-result__reasons"
        >
          <div
            v-for="line in lastGenerateSummary.reasonLines"
            :key="line"
            class="ranking-result__reason"
          >
            {{ line }}
          </div>
        </div>
        <div
          v-if="lastGenerateDiagnostics?.slow_groups?.length"
          class="ranking-result__reasons"
        >
          <div class="ranking-result__subtitle">较慢群组</div>
          <div
            v-for="group in lastGenerateDiagnostics.slow_groups"
            :key="`${group.crm_group_id}-${group.elapsed_ms}`"
            class="ranking-result__reason"
          >
            {{ group.crm_group_name }}: {{ group.member_count }} 人，耗时 {{ formatMs(group.elapsed_ms) }}
          </div>
        </div>
      </div>

      <FollowupActionsPanel
        v-if="lastGenerateSummary && totalFollowupCount > 0"
        :actions-by-group="lastFollowupActions"
      />
      <div v-if="lastGenerateSummary && totalFollowupCount === 0" class="followup-empty-hint">
        暂无 1v1 跟进建议（需要成员匹配洞察场景才会生成）
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'
import FollowupActionsPanel from './FollowupActionsPanel.vue'

type RankingSlowGroup = {
  crm_group_id: number
  crm_group_name: string
  member_count: number
  elapsed_ms: number
}

type RankingDiagnostics = {
  total_ms: number
  group_name_lookup_ms: number
  load_members_ms: number
  insights_ms: number
  insights_skipped?: boolean
  generate_items_ms: number
  slow_groups: RankingSlowGroup[]
}

const emit = defineEmits<{
  'select-ranking': [items: Array<{
    id: number
    title: string
    msg_type: string
    description: string
    contentJson: Record<string, any>
    variablesJson: Record<string, any>
    targetGroupIds: number[]
  }>]
}>()

const loading = ref(true)
const generating = ref(false)
const generatingGlobal = ref(false)
const generateProgress = ref('')
const crmAvailable = ref(false)
const crmGroups = ref<any[]>([])
const checkedGroupIds = ref<Set<number>>(new Set())
const generateElapsedSeconds = ref(0)
const generateProgressPercent = ref(0)
const generateStageLabel = ref('')
const lastGenerateDiagnostics = ref<RankingDiagnostics | null>(null)
const lastFollowupActions = ref<Record<string, any[]>>({})
const lastGenerateSummary = ref<null | {
  requestedCount: number
  queuedCount: number
  skippedCount: number
  unboundCount: number
  insightCount: number
  reasonLines: string[]
}>(null)
let generateTimer: number | null = null

const config = ref({
  topNEnabled: false,
  topN: 30,
  rankMetric: 'custom_month_points',
  speechStyle: 'professional',
  includeWeekMonth: true,
  skipEmptyGroups: true,
  enabledScenes: [] as string[],
  includeLastWeekBreakdown: false,
})

const insightScenes = ref<Array<{key: string; label: string}>>([])

// ── 全选逻辑 ──
const isAllChecked = computed(() => crmGroups.value.length > 0 && checkedGroupIds.value.size === crmGroups.value.length)
const isIndeterminate = computed(() => checkedGroupIds.value.size > 0 && checkedGroupIds.value.size < crmGroups.value.length)

const totalFollowupCount = computed(() => {
  return Object.values(lastFollowupActions.value).reduce((s, arr) => s + arr.length, 0)
})

const toggleAll = (checked: boolean) => {
  if (checked) {
    checkedGroupIds.value = new Set(crmGroups.value.map(g => g.id))
  } else {
    checkedGroupIds.value = new Set()
  }
}

const toggleGroup = (gid: number) => {
  if (checkedGroupIds.value.has(gid)) {
    checkedGroupIds.value.delete(gid)
  } else {
    checkedGroupIds.value.add(gid)
  }
}

const resolveGenerateStage = (elapsedSeconds: number) => {
  if (elapsedSeconds < 2) return '已提交请求，等待后端响应'
  if (elapsedSeconds < 8) return '正在加载 CRM 群成员与积分'
  if (elapsedSeconds < 20) return '正在生成积分排行与亮点话术'
  return '处理时间较长，正在等待后端完成慢查询/洞察分析'
}

const clearGenerateTimer = () => {
  if (generateTimer !== null) {
    window.clearInterval(generateTimer)
    generateTimer = null
  }
}

const startGenerateProgress = (groupCount: number) => {
  clearGenerateTimer()
  generateElapsedSeconds.value = 0
  generateProgressPercent.value = 8
  generateStageLabel.value = resolveGenerateStage(0)
  generateProgress.value = `已提交 ${groupCount} 个群，正在生成积分排行...`
  generateTimer = window.setInterval(() => {
    generateElapsedSeconds.value += 1
    generateStageLabel.value = resolveGenerateStage(generateElapsedSeconds.value)
    generateProgressPercent.value = Math.min(92, 8 + generateElapsedSeconds.value * 4)
    generateProgress.value = `正在生成 ${groupCount} 个群的积分排行，已耗时 ${generateElapsedSeconds.value} 秒`
  }, 1000)
}

const finishGenerateProgress = (previewCount: number) => {
  clearGenerateTimer()
  generateProgressPercent.value = 100
  generateStageLabel.value = '后端已完成排行生成'
  generateProgress.value = `后端已返回 ${previewCount} 个群的生成结果`
}

const formatMs = (value?: number) => {
  if (!value && value !== 0) return '--'
  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}s`
  }
  return `${value}ms`
}

const generateGlobalRanking = async () => {
  const allIds = [...checkedGroupIds.value]
  if (allIds.length === 0) return

  generatingGlobal.value = true
  try {
    const res: any = await request.post('/v1/crm-points/preview-global-ranking', {
      crm_group_ids: allIds,
      top_n: 10,
      speech_style: config.value.speechStyle,
    }, { timeout: 120000 })

    if (!res.ok || !res.data) {
      ElMessage.warning(res.message || '无有效积分数据')
      return
    }

    const data = res.data
    const batchItems = [{
      id: -1,
      title: '🏆 首钢减重项目 — 跨群总排行',
      msg_type: 'markdown',
      description: `覆盖 ${data.group_count} 个社群，${data.member_count} 位活跃成员`,
      contentJson: data.content_json,
      variablesJson: {},
      targetGroupIds: [],
    }]
    emit('select-ranking', batchItems)
    ElMessage.success(`已生成跨群总排行（${data.group_count} 群，TOP10 个人 + 社群 PK）`)
  } catch (e: any) {
    ElMessage.error('生成跨群排行失败: ' + String(e?.message || e))
  } finally {
    generatingGlobal.value = false
  }
}

const generateRanking = async () => {
  const allIds = [...checkedGroupIds.value]
  if (allIds.length === 0) return

  generating.value = true
  startGenerateProgress(allIds.length)
  lastGenerateDiagnostics.value = null
  lastGenerateSummary.value = null

  const reqConfig = { rank_metric: config.value.rankMetric, speech_style: config.value.speechStyle, include_week_month: config.value.includeWeekMonth, skip_empty_groups: config.value.skipEmptyGroups, top_n: config.value.topNEnabled ? config.value.topN : 9999, enabled_scenes: config.value.enabledScenes, include_last_week_breakdown: config.value.includeLastWeekBreakdown }

  try {
    const res: any = await request.post('/v1/crm-points/preview-ranking', {
      crm_group_ids: allIds,
      ...reqConfig,
    }, { timeout: 180000 })

    const previewItems = res.items || []
    lastGenerateDiagnostics.value = res.diagnostics || null
    finishGenerateProgress(previewItems.length)
    const skipped = previewItems.filter((item: any) => item.skipped)
    const validItems = previewItems.filter((item: any) => !item.skipped)
    const insightCount = validItems.reduce((sum: number, item: any) => sum + ((item.insights || []).length), 0)
    const selectedSceneLabels = insightScenes.value
      .filter(scene => config.value.enabledScenes.includes(scene.key))
      .map(scene => scene.label)

    // 提取 1v1 跟进动作
    const followupMap: Record<string, any[]> = {}
    for (const item of validItems) {
      const actions = item.followup_1v1 || []
      if (actions.length > 0) {
        followupMap[item.crm_group_name || `群#${item.crm_group_id}`] = actions
      }
    }
    lastFollowupActions.value = followupMap

    if (validItems.length === 0) {
      lastGenerateSummary.value = {
        requestedCount: allIds.length,
        queuedCount: 0,
        skippedCount: skipped.length,
        unboundCount: 0,
        insightCount,
        reasonLines: [
          ...skipped.map((item: any) => `${item.crm_group_name}: ${item.skip_reason || '未生成消息'}`),
          ...(config.value.enabledScenes.length > 0 && insightCount === 0
            ? [`当前所选洞察场景未命中任何成员: ${selectedSceneLabels.join('、')}`]
            : []),
          ...(lastGenerateDiagnostics.value?.insights_skipped
            ? ['洞察分析已降级跳过，请查看后端日志中的“批量洞察查询失败”']
            : []),
        ],
      }
      ElMessage.warning('所选群组均无正积分成员，未生成排行消息')
      return
    }

    const batchItems = validItems
      .filter((item: any) => item.content_json)
      .map((item: any) => ({
        id: item.crm_group_id,
        title: `📊 ${item.crm_group_name} 积分排行`,
        msg_type: 'markdown',
        description: `${item.member_count} 人上榜`,
        contentJson: item.content_json,
        variablesJson: {},
        targetGroupIds: [],
      }))

    lastGenerateSummary.value = {
      requestedCount: allIds.length,
      queuedCount: batchItems.length,
      skippedCount: skipped.length,
      unboundCount: 0,
      insightCount,
      reasonLines: [
        ...skipped.map((item: any) => `${item.crm_group_name}: ${item.skip_reason || '未生成消息'}`),
        ...(config.value.enabledScenes.length > 0 && insightCount === 0
          ? [`当前所选洞察场景未命中任何成员: ${selectedSceneLabels.join('、')}`]
          : []),
        ...(lastGenerateDiagnostics.value?.insights_skipped
          ? ['洞察分析已降级跳过，请查看后端日志中的”批量洞察查询失败”']
          : []),
      ],
    }

    if (batchItems.length === 0) {
      ElMessage.warning('没有可发送的排行消息（所选群组无正积分成员）')
      return
    }

    emit('select-ranking', batchItems)
  } catch (e: any) {
    const message = String(e?.message || e)
    if (/timeout|超时/i.test(message)) {
      ElMessage.error('生成排行请求超时，请查看后端日志中的“CRM 积分排行预览”耗时记录')
    } else {
      ElMessage.error('生成排行失败: ' + message)
    }
  } finally {
    clearGenerateTimer()
    generating.value = false
    generateProgress.value = ''
  }
}

const fetchCrmGroups = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/crm-groups')
    crmAvailable.value = res.available ?? false
    crmGroups.value = res.groups || []
  } catch {
    crmAvailable.value = false
    crmGroups.value = []
  } finally {
    loading.value = false
  }
}

const fetchInsightScenes = async () => {
  try {
    const res: any = await request.get('/v1/crm-points/insight-scenes')
    insightScenes.value = res || []
  } catch {
    insightScenes.value = []
  }
}

onMounted(() => {
  Promise.all([fetchCrmGroups(), fetchInsightScenes()])
})

onBeforeUnmount(() => {
  clearGenerateTimer()
})
</script>

<style scoped>
.points-ranking-tab {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 200px;
}

.ranking-config {
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--card-bg);
}
.ranking-config__row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.ranking-config__row label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.ranking-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}

.ranking-groups {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ranking-group-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  transition: background 0.15s;
}
.ranking-group-item:hover {
  background: var(--fill-color-light, #f5f7fa);
}
html.dark .ranking-group-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.ranking-group-item.is-checked {
  background: rgba(var(--el-color-primary-rgb), 0.06);
}
.ranking-group-item__info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.ranking-group-item__name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ranking-group-item__meta {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.ranking-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
}
.ranking-actions__warn {
  font-size: 12px;
  color: var(--el-color-warning);
}
.ranking-actions__progress {
  font-size: 12px;
  color: var(--text-secondary);
}

.ranking-progress-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid rgba(var(--el-color-primary-rgb), 0.16);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(var(--el-color-primary-rgb), 0.05), rgba(var(--el-color-primary-rgb), 0.02));
}

.ranking-progress-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ranking-progress-card__stage {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.ranking-progress-card__elapsed {
  font-size: 12px;
  color: var(--text-secondary);
}

.ranking-progress-card__text,
.ranking-progress-card__tip {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.ranking-result {
  padding: 12px 14px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--card-bg);
}

.ranking-result__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.ranking-result__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.ranking-result__stats--timing {
  padding-top: 6px;
  border-top: 1px dashed var(--border-color);
}

.ranking-result__reasons {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}

.ranking-result__subtitle {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.ranking-result__reason {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-muted);
}

.content-selector__empty {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 14px;
}

@media (max-width: 768px) {
  .ranking-config__row {
    gap: 6px;
  }
  .ranking-actions,
  .ranking-progress-card__header {
    flex-wrap: wrap;
  }
  .ranking-group-item {
    flex-wrap: wrap;
    padding: 10px;
  }
}
.followup-empty-hint {
  border: 1px dashed var(--border-color);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
  background: var(--card-bg);
}
</style>
