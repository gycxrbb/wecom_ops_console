<template>
  <div class="followup-panel">
    <div class="followup-panel__header" @click="collapsed = !collapsed">
      <span class="followup-panel__title">📝 1v1 跟进建议</span>
      <span class="followup-panel__count">{{ totalCount }} 条待跟进</span>
      <el-icon class="followup-panel__arrow" :class="{ 'is-expanded': !collapsed }">
        <ArrowRight />
      </el-icon>
    </div>

    <div v-if="!collapsed" class="followup-panel__body">
      <div
        v-for="(actions, groupName) in actionsByGroup"
        :key="groupName"
        class="followup-group"
      >
        <div class="followup-group__name">{{ groupName }}（{{ actions.length }} 条）</div>
        <div
          v-for="(action, idx) in actions"
          :key="idx"
          class="followup-item"
        >
          <div class="followup-item__left">
            <el-tag size="small" :type="tagType(action.action_type)">
              {{ action.label }}
            </el-tag>
            <span class="followup-item__name">{{ action.target_name }}</span>
            <span class="followup-item__rank">排名 #{{ action.rank }}</span>
          </div>
          <div class="followup-item__msg" :title="action.message">
            {{ truncate(action.message, 80) }}
          </div>
          <div class="followup-item__actions">
            <el-button size="small" text @click="copyMessage(action)">
              复制消息
            </el-button>
            <el-button size="small" text @click="viewDetail(action)">
              查看全文
            </el-button>
          </div>
        </div>
      </div>

      <div v-if="totalCount > 0" class="followup-panel__footer">
        <el-button size="small" @click="copyAll">复制全部消息</el-button>
      </div>
    </div>

    <el-dialog v-model="detailVisible" :title="detailAction?.label" width="520px">
      <div class="followup-detail">
        <div class="followup-detail__meta">
          <span>目标用户：{{ detailAction?.target_name }}</span>
          <span>所属群：{{ detailAction?.target_group }}</span>
          <span>排名：#{{ detailAction?.rank }}</span>
        </div>
        <div class="followup-detail__msg">{{ detailAction?.message }}</div>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="primary" @click="copyMessage(detailAction!)">复制消息</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'

type FollowupAction = {
  action_type: string
  label: string
  target_name: string
  target_group: string
  message: string
  customer_id: number
  rank: number
}

const props = defineProps<{
  actionsByGroup: Record<string, FollowupAction[]>
}>()

const collapsed = ref(false)
const detailVisible = ref(false)
const detailAction = ref<FollowupAction | null>(null)

const totalCount = computed(() => {
  return Object.values(props.actionsByGroup).reduce((sum, arr) => sum + arr.length, 0)
})

const tagType = (actionType: string) => {
  if (actionType.startsWith('praise') || actionType === 'congratulate_winner') return 'success'
  if (actionType.startsWith('remind') || actionType.startsWith('care')) return 'warning'
  return 'info'
}

const truncate = (text: string, max: number) => {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

const copyMessage = async (action: FollowupAction) => {
  if (!action) return
  try {
    await navigator.clipboard.writeText(action.message)
    ElMessage.success(`已复制「${action.target_name}」的 1v1 消息`)
  } catch {
    ElMessage.error('复制失败')
  }
}

const viewDetail = (action: FollowupAction) => {
  detailAction.value = action
  detailVisible.value = true
}

const copyAll = async () => {
  const lines: string[] = []
  for (const [group, actions] of Object.entries(props.actionsByGroup)) {
    lines.push(`【${group}】`)
    for (const a of actions) {
      lines.push(`${a.label} → ${a.target_name}（排名#${a.rank}）`)
      lines.push(a.message)
      lines.push('')
    }
  }
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    ElMessage.success(`已复制 ${totalCount.value} 条 1v1 消息`)
  } catch {
    ElMessage.error('复制失败')
  }
}
</script>

<style scoped>
.followup-panel {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--card-bg);
  overflow: hidden;
}
.followup-panel__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
}
.followup-panel__header:hover {
  background: var(--fill-color-light, #f5f7fa);
}
html.dark .followup-panel__header:hover {
  background: rgba(255, 255, 255, 0.06);
}
.followup-panel__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.followup-panel__count {
  font-size: 12px;
  color: var(--text-secondary);
}
.followup-panel__arrow {
  margin-left: auto;
  transition: transform 0.2s;
  color: var(--text-muted);
}
.followup-panel__arrow.is-expanded {
  transform: rotate(90deg);
}
.followup-panel__body {
  padding: 0 14px 12px;
}
.followup-group__name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  padding: 6px 0 4px;
  border-top: 1px dashed var(--border-color);
}
.followup-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  flex-wrap: wrap;
}
.followup-item__left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.followup-item__name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}
.followup-item__rank {
  font-size: 11px;
  color: var(--text-muted);
}
.followup-item__msg {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  flex: 1;
  min-width: 200px;
}
.followup-item__actions {
  flex-shrink: 0;
  display: flex;
  gap: 4px;
}
.followup-panel__footer {
  padding-top: 8px;
  border-top: 1px solid var(--border-color);
  text-align: right;
}
.followup-detail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}
.followup-detail__msg {
  font-size: 13px;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
  background: var(--fill-color-light, #f5f7fa);
  padding: 12px;
  border-radius: 8px;
}
html.dark .followup-detail__msg {
  background: rgba(255, 255, 255, 0.06);
}
</style>
