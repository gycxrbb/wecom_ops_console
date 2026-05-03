<template>
  <div class="page-container">
    <div class="page-header">
      <h2 class="page-title">自动排行推送</h2>
      <p class="page-desc">配置每日自动积分排行推送，按设定时间自动生成排行消息并推送到目标群。</p>
    </div>

    <div class="toolbar">
      <el-button type="primary" @click="openDialog()">新建配置</el-button>
    </div>

    <div v-if="loading" style="text-align: center; padding: 60px; color: var(--text-muted)">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span style="margin-left: 8px">加载中...</span>
    </div>

    <el-table v-else :data="configs" stripe border style="width: 100%">
      <el-table-column prop="name" label="配置名称" min-width="140" />
      <el-table-column label="CRM 群" min-width="100" align="center">
        <template #default="{ row }">{{ row.crm_group_ids?.length || 0 }} 个</template>
      </el-table-column>
      <el-table-column label="目标群" min-width="120">
        <template #default="{ row }">{{ localGroupName(row.target_local_group_id) }}</template>
      </el-table-column>
      <el-table-column label="必选场景" min-width="140">
        <template #default="{ row }">
          <el-tag v-for="k in row.must_scene_keys" :key="k" size="small" class="scene-tag">{{ sceneLabel(k) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="推送时间" width="90" align="center">
        <template #default="{ row }">{{ String(row.push_hour ?? 0).padStart(2, '0') }}:{{ String(row.push_minute ?? 0).padStart(2, '0') }}</template>
      </el-table-column>
      <el-table-column label="启用" width="80" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.enabled" @change="toggleEnabled(row, $event)" />
        </template>
      </el-table-column>
      <el-table-column label="上次执行" min-width="160">
        <template #default="{ row }">
          <template v-if="row.last_run_at">{{ row.last_run_at }}</template>
          <span v-else style="color: var(--text-muted)">未执行</span>
          <div v-if="row.last_error" class="error-hint">{{ row.last_error }}</div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" align="center">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除此配置？" @confirm="deleteConfig(row.id)">
            <template #reference>
              <el-button size="small" text type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建/编辑 Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑配置' : '新建配置'" width="720px" destroy-on-close>
      <el-form :model="form" label-width="120px" label-position="right">
        <el-form-item label="配置名称" required>
          <el-input v-model="form.name" placeholder="如：首钢系列每日排行" />
        </el-form-item>

        <el-form-item label="CRM 群" required>
          <div class="crm-group-header">
            <el-input v-model="crmSearch" placeholder="搜索群名称" clearable size="small" class="crm-search" />
            <el-button size="small" @click="toggleCrmAll" :disabled="filteredCrmGroups.length === 0">
              {{ isAllCrmSelected ? '取消全选' : '全选' }}
            </el-button>
            <span class="crm-count">{{ form.crm_group_ids.length }}/{{ filteredCrmGroups.length }} 已选</span>
          </div>
          <div class="crm-group-list">
            <el-checkbox-group v-model="form.crm_group_ids">
              <el-checkbox
                v-for="g in filteredCrmGroups"
                :key="g.crm_group_id"
                :value="g.crm_group_id"
                class="crm-group-item"
              >{{ g.crm_group_name }}</el-checkbox>
            </el-checkbox-group>
            <div v-if="filteredCrmGroups.length === 0" class="crm-empty">无匹配群</div>
          </div>
          <div class="form-tip">从 CRM 数据库中选择要生成排行的群</div>
        </el-form-item>

        <el-form-item label="推送目标群" required>
          <el-select v-model="form.target_local_group_id" placeholder="选择目标内部群" style="width: 100%">
            <el-option
              v-for="g in localGroups"
              :key="g.id"
              :label="g.name"
              :value="g.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="推送时间" required>
          <el-time-picker v-model="form.push_time" format="HH:mm" placeholder="选择推送时间" style="width: 200px" />
        </el-form-item>

        <el-form-item label="必选场景" required>
          <el-checkbox-group v-model="form.must_scene_keys">
            <el-checkbox v-for="s in insightScenes" :key="s.key" :value="s.key">{{ s.label }}</el-checkbox>
          </el-checkbox-group>
          <div class="form-tip">每次推送必须包含这些场景</div>
        </el-form-item>

        <el-form-item label="可选场景池">
          <el-checkbox-group v-model="form.extra_scene_pool">
            <el-checkbox v-for="s in insightScenes" :key="s.key" :value="s.key">{{ s.label }}</el-checkbox>
          </el-checkbox-group>
          <div class="form-tip">从中随机补充场景，凑齐总场景数</div>
        </el-form-item>

        <el-form-item label="场景总数">
          <el-input-number v-model="form.scene_count" :min="1" :max="6" />
          <span class="form-tip" style="margin-left: 8px">必选 + 随机补齐到此数量</span>
        </el-form-item>

        <el-form-item label="话术风格">
          <el-select v-model="form.speech_style" style="width: 100%">
            <el-option label="专业" value="professional" />
            <el-option label="鼓励" value="encouraging" />
            <el-option label="竞技" value="competitive" />
          </el-select>
        </el-form-item>

        <el-form-item label="周一明细">
          <el-switch v-model="form.include_breakdown_on_monday" active-text="周一自动开启上周积分明细" />
        </el-form-item>

        <el-form-item label="跳过周末">
          <el-switch v-model="form.skip_weekends" />
        </el-form-item>

        <el-form-item label="跳过日期">
          <el-select
            v-model="form.skip_dates"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入日期 YYYY-MM-DD 回车添加"
            style="width: 100%"
          />
        </el-form-item>

        <!-- 未来执行预览 -->
        <el-form-item label="执行预览" v-if="previewRuns.length > 0">
          <div class="preview-runs">
            <div v-for="(r, i) in previewRuns" :key="i" class="preview-run-item">
              <span class="preview-run-index">#{{ i + 1 }}</span>
              <span class="preview-run-time">{{ r }}</span>
              <el-tag v-if="isWeekend(r)" size="small" type="info">周末跳过</el-tag>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

interface Config {
  id: number
  name: string
  enabled: boolean
  crm_group_ids: number[]
  target_local_group_id: number
  must_scene_keys: string[]
  extra_scene_pool: string[]
  scene_count: number
  speech_style: string
  include_breakdown_on_monday: boolean
  skip_weekends: boolean
  skip_dates: string[]
  push_hour: number
  push_minute: number
  last_run_at: string | null
  last_error: string
}

interface Scene {
  key: string
  label: string
}

interface CrmBinding {
  crm_group_id: number
  crm_group_name: string
}

interface LocalGroup {
  id: number
  name: string
}

const configs = ref<Config[]>([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const insightScenes = ref<Scene[]>([])
const crmGroups = ref<CrmBinding[]>([])
const localGroups = ref<LocalGroup[]>([])
const crmSearch = ref('')
const previewRuns = ref<string[]>([])

const form = reactive({
  name: '',
  crm_group_ids: [] as number[],
  target_local_group_id: null as number | null,
  push_time: new Date(2024, 0, 1, 0, 0) as Date | null,
  must_scene_keys: ['top_leader', 'top_six'] as string[],
  extra_scene_pool: [] as string[],
  scene_count: 3,
  speech_style: 'professional',
  include_breakdown_on_monday: true,
  skip_weekends: false,
  skip_dates: [] as string[],
})

const filteredCrmGroups = computed(() => {
  const q = crmSearch.value.trim().toLowerCase()
  if (!q) return crmGroups.value
  return crmGroups.value.filter(g => g.crm_group_name.toLowerCase().includes(q))
})

const isAllCrmSelected = computed(() => {
  if (filteredCrmGroups.value.length === 0) return false
  return filteredCrmGroups.value.every(g => form.crm_group_ids.includes(g.crm_group_id))
})

const sceneLabel = (key: string) => insightScenes.value.find(s => s.key === key)?.label || key
const localGroupName = (id: number) => localGroups.value.find(g => g.id === id)?.name || `群 #${id}`

const isWeekend = (dateStr: string) => {
  const d = new Date(dateStr)
  return d.getDay() === 0 || d.getDay() === 6
}

const toggleCrmAll = () => {
  if (isAllCrmSelected.value) {
    const visibleIds = new Set(filteredCrmGroups.value.map(g => g.crm_group_id))
    form.crm_group_ids = form.crm_group_ids.filter(id => !visibleIds.has(id))
  } else {
    const existing = new Set(form.crm_group_ids)
    for (const g of filteredCrmGroups.value) {
      if (!existing.has(g.crm_group_id)) {
        form.crm_group_ids.push(g.crm_group_id)
      }
    }
  }
}

const fetchPreviewRuns = async () => {
  const hour = form.push_time ? form.push_time.getHours() : 0
  const minute = form.push_time ? form.push_time.getMinutes() : 0
  try {
    const res: any = await request.post('/v1/crm-points/auto-ranking-preview-runs', {
      push_hour: hour,
      push_minute: minute,
      skip_weekends: form.skip_weekends,
      skip_dates: form.skip_dates,
    })
    previewRuns.value = res.next_runs || []
  } catch {
    previewRuns.value = []
  }
}

// Watch form fields to refresh preview
watch(
  () => [form.push_time, form.skip_weekends, form.skip_dates],
  () => { if (dialogVisible.value) fetchPreviewRuns() },
  { deep: true },
)

const fetchConfigs = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/v1/crm-points/auto-ranking-configs')
    configs.value = res.items || []
  } catch (e: any) {
    ElMessage.error('加载配置失败: ' + String(e))
  } finally {
    loading.value = false
  }
}

const fetchScenes = async () => {
  try {
    const res: any = await request.get('/v1/crm-points/insight-scenes')
    insightScenes.value = (res || []).map((s: any) => ({ key: s.key, label: s.label }))
  } catch { /* ignore */ }
}

const fetchCrmGroups = async () => {
  try {
    const res: any = await request.get('/v1/crm-groups')
    crmGroups.value = (res.groups || []).map((g: any) => ({
      crm_group_id: g.id,
      crm_group_name: g.name,
    }))
  } catch { /* ignore */ }
}

const fetchLocalGroups = async () => {
  try {
    const res: any = await request.get('/v1/crm-points/local-groups')
    localGroups.value = res.groups || []
  } catch { /* ignore */ }
}

const openDialog = (row?: Config) => {
  if (row) {
    editingId.value = row.id
    form.name = row.name
    form.crm_group_ids = [...row.crm_group_ids]
    form.target_local_group_id = row.target_local_group_id
    form.push_time = new Date(2024, 0, 1, row.push_hour ?? 0, row.push_minute ?? 0)
    form.must_scene_keys = [...row.must_scene_keys]
    form.extra_scene_pool = [...row.extra_scene_pool]
    form.scene_count = row.scene_count
    form.speech_style = row.speech_style
    form.include_breakdown_on_monday = row.include_breakdown_on_monday
    form.skip_weekends = row.skip_weekends
    form.skip_dates = [...row.skip_dates]
  } else {
    editingId.value = null
    form.name = ''
    form.crm_group_ids = []
    form.target_local_group_id = null
    form.push_time = new Date(2024, 0, 1, 0, 0)
    form.must_scene_keys = ['top_leader', 'top_six']
    form.extra_scene_pool = []
    form.scene_count = 3
    form.speech_style = 'professional'
    form.include_breakdown_on_monday = true
    form.skip_weekends = false
    form.skip_dates = []
  }
  crmSearch.value = ''
  previewRuns.value = []
  dialogVisible.value = true
  fetchPreviewRuns()
}

const saveConfig = async () => {
  if (!form.name) return ElMessage.warning('请填写配置名称')
  if (!form.crm_group_ids.length) return ElMessage.warning('请选择 CRM 群')
  if (!form.target_local_group_id) return ElMessage.warning('请选择推送目标群')
  if (!form.must_scene_keys.length) return ElMessage.warning('请选择至少一个必选场景')

  saving.value = true
  try {
    const pushHour = form.push_time ? form.push_time.getHours() : 0
    const pushMinute = form.push_time ? form.push_time.getMinutes() : 0
    await request.post('/v1/crm-points/auto-ranking-configs', {
      id: editingId.value,
      name: form.name,
      enabled: true,
      crm_group_ids: form.crm_group_ids,
      target_local_group_id: form.target_local_group_id,
      push_hour: pushHour,
      push_minute: pushMinute,
      must_scene_keys: form.must_scene_keys,
      extra_scene_pool: form.extra_scene_pool,
      scene_count: form.scene_count,
      speech_style: form.speech_style,
      include_breakdown_on_monday: form.include_breakdown_on_monday,
      skip_weekends: form.skip_weekends,
      skip_dates: form.skip_dates,
    })
    ElMessage.success(editingId.value ? '配置已更新' : '配置已创建')
    dialogVisible.value = false
    fetchConfigs()
  } catch (e: any) {
    ElMessage.error('保存失败: ' + String(e))
  } finally {
    saving.value = false
  }
}

const toggleEnabled = async (row: Config, val: boolean) => {
  try {
    await request.post('/v1/crm-points/auto-ranking-configs', {
      ...row,
      enabled: val,
    })
    row.enabled = val
  } catch (e: any) {
    ElMessage.error('更新失败: ' + String(e))
  }
}

const deleteConfig = async (id: number) => {
  try {
    await request.delete(`/v1/crm-points/auto-ranking-configs/${id}`)
    ElMessage.success('已删除')
    fetchConfigs()
  } catch (e: any) {
    ElMessage.error('删除失败: ' + String(e))
  }
}

onMounted(() => {
  fetchConfigs()
  fetchScenes()
  fetchCrmGroups()
  fetchLocalGroups()
})
</script>

<style scoped>
.page-container {
  max-width: 1200px;
  margin: 0 auto;
}
.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}
.toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}
.scene-tag {
  margin: 2px 4px 2px 0;
}
.error-hint {
  font-size: 12px;
  color: var(--el-color-danger);
  margin-top: 4px;
  line-height: 1.4;
}
.form-tip {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* CRM 群选择区 */
.crm-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.crm-search {
  width: 200px;
}
.crm-count {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
  white-space: nowrap;
}
.crm-group-list {
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 8px 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}
.crm-group-item {
  width: calc(50% - 8px);
  min-width: 180px;
}
.crm-empty {
  width: 100%;
  text-align: center;
  padding: 20px;
  color: var(--text-muted);
  font-size: 13px;
}
:global(html.dark) .crm-group-list {
  border-color: var(--el-border-color-dark);
}

/* 执行预览 */
.preview-runs {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.preview-run-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.preview-run-index {
  font-weight: 600;
  color: var(--el-color-primary);
  width: 24px;
}
.preview-run-time {
  font-family: 'SF Mono', 'Cascadia Code', monospace;
}

@media (max-width: 767px) {
  .toolbar { justify-content: flex-start; }
  .crm-group-item { width: 100%; min-width: 0; }
  .crm-search { width: 140px; }
}
</style>
