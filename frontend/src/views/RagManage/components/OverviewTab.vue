<template>
  <div class="overview">
    <div v-if="loading" style="text-align: center; padding: 40px; color: var(--text-muted)">加载中...</div>
    <template v-else>
      <!-- Status Cards -->
      <div class="card-row">
        <div class="stat-card">
          <div class="stat-label">Qdrant 状态</div>
          <div class="stat-value">
            <span :class="status.qdrant_available ? 'dot dot-ok' : 'dot dot-off'" />
            {{ status.qdrant_available ? '可用' : '不可用' }}
          </div>
          <div class="stat-sub">模式：{{ status.qdrant_mode }} · {{ status.collection?.collection || '-' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">向量总数</div>
          <div class="stat-value">{{ status.collection?.vectors_count ?? '-' }}</div>
          <div class="stat-sub">资源 {{ status.indexed_resources?.total ?? 0 }} 条</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">磁盘占用</div>
          <div class="stat-value">{{ formatSize(status.collection?.disk_data_size) }}</div>
          <div class="stat-sub">内存 {{ formatSize(status.collection?.ram_data_size) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">向量维度</div>
          <div class="stat-value">{{ status.collection?.vector_dim ?? '-' }}</div>
          <div class="stat-sub">分片 {{ status.collection?.segments_count ?? '-' }}</div>
        </div>
      </div>

      <!-- Distribution Cards -->
      <div class="card-row">
        <div class="stat-card">
          <div class="stat-label">质量分布</div>
          <div class="dist-row">
            <span v-for="(label, key) in qualityLabels" :key="key" class="dist-item">
              <el-tag :type="qualityType(key)" size="small">{{ label }}</el-tag>
              <span class="dist-num">{{ qualityDist[key] ?? 0 }}</span>
            </span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">来源分布</div>
          <div class="dist-row">
            <span class="dist-item">
              <el-tag size="small" type="primary">话术</el-tag>
              <span class="dist-num">{{ sourceDist.speech_template ?? 0 }}</span>
            </span>
            <span class="dist-item">
              <el-tag size="small" type="success">素材</el-tag>
              <span class="dist-num">{{ sourceDist.material ?? 0 }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="action-bar">
        <el-button type="primary" @click="doReindex('all', true)" :loading="reindexing">
          全量重建索引
        </el-button>
        <el-button @click="doReindex('speech')" :loading="reindexing">增量：话术</el-button>
        <el-button @click="doReindex('material')" :loading="reindexing">增量：素材</el-button>
        <span v-if="reindexResult" class="reindex-result">{{ reindexResult }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

const loading = ref(false)
const reindexing = ref(false)
const reindexResult = ref('')
const status = ref<any>({})

const qualityLabels: Record<string, string> = { ok: 'OK', medium: '中', weak: '弱', stale: '过期' }

const qualityDist = computed(() => status.value.indexed_resources?.by_quality || {})
const sourceDist = computed(() => status.value.indexed_resources?.by_type || {})

const qualityType = (q: string) => {
  if (q === 'ok') return 'success'
  if (q === 'stale') return 'warning'
  if (q === 'weak') return 'danger'
  return 'info'
}

const formatSize = (bytes: number | undefined | null) => {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const fetchStatus = async () => {
  loading.value = true
  try {
    status.value = await request.get('/v1/rag/status')
  } catch {
    status.value = {}
  } finally {
    loading.value = false
  }
}

const doReindex = async (source: string, force = false) => {
  reindexing.value = true
  reindexResult.value = ''
  try {
    const res: any = await request.post('/v1/rag/reindex', null, { params: { source, force } })
    const results = res.results || {}
    const parts = Object.entries(results).map(([k, v]: any) => `${k}: 索引${v.indexed || 0} 跳过${v.skipped || 0} 错误${v.errors || 0}`)
    reindexResult.value = parts.join(' | ')
    ElMessage.success('索引重建完成')
    fetchStatus()
  } catch (e: any) {
    ElMessage.error('重建失败: ' + String(e))
  } finally {
    reindexing.value = false
  }
}

onMounted(fetchStatus)
</script>

<style scoped>
.card-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 16px;
}
.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}
.stat-sub {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-ok { background: #10b981; }
.dot-off { background: #ef4444; }
.dist-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 4px;
}
.dist-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.dist-num {
  font-size: 14px;
  font-weight: 600;
}
.action-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.reindex-result {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: 8px;
}
</style>
