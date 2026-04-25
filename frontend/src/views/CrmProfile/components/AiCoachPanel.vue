<template>
  <el-drawer
    v-model="visible"
    direction="rtl"
    :size="drawerWidth + 'px'"
    :show-close="false"
    :with-header="false"
    class="ai-coach-drawer"
    :body-style="{ padding: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }"
    @close="visible = false"
  >
    <!-- Resize handle -->
    <div
      class="ai-resize-handle"
      @mousedown.prevent="onResizeStart"
    >
      <div class="ai-resize-handle__line" />
    </div>

    <div class="ai-panel">
      <!-- Custom header -->
      <div class="ai-panel-header">
        <div class="ai-panel-header__left">
          <div class="ai-panel-logo">
            <img src="https://cdn.mengfugui.com/logo.png" alt="AI Coach" style="width: 100%; height: 100%; border-radius: inherit; object-fit: cover;" />
          </div>
          <span class="ai-panel-header__title">AI 教练助手</span>
          <el-tag v-if="sessionId" size="small" type="success" round class="ai-session-tag">会话中</el-tag>
        </div>
        <div class="ai-panel-header__right">
          <el-button text circle size="small" @click="clearSession()" title="清空会话">
            <el-icon><Delete /></el-icon>
          </el-button>
          <el-button text circle size="small" @click="visible = false" title="关闭">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- Body: sidebar + main -->
      <div class="ai-panel-body">
        <!-- Sidebar rail -->
        <div class="ai-sidebar" :class="{ 'is-expanded': sidebarExpanded }">
          
          <div class="ai-sidebar-menu">
            <div class="ai-sidebar-menu-item" :class="{ 'is-active': sidebarTab === null }" @click="sidebarTab = null">
              <el-icon class="ai-sidebar-icon" :size="18"><ChatLineRound /></el-icon>
              <span class="ai-sidebar-menu-text">对话界面</span>
            </div>
            <div class="ai-sidebar-menu-item" :class="{ 'is-active': sidebarTab === 'history' }" @click="sidebarTab = 'history'" title="历史对话">
              <el-icon class="ai-sidebar-icon" :size="18"><Clock /></el-icon>
              <span class="ai-sidebar-menu-text">历史对话</span>
            </div>
            <div class="ai-sidebar-menu-item" :class="{ 'is-active': sidebarTab === 'context' }" @click="sidebarTab = 'context'" title="已加载信息">
              <el-icon class="ai-sidebar-icon" :size="18"><Document /></el-icon>
              <span class="ai-sidebar-menu-text">已加载信息</span>
            </div>
            <div class="ai-sidebar-menu-item" :class="{ 'is-active': sidebarTab === 'notes' }" @click="sidebarTab = 'notes'" title="专属补充信息">
              <el-icon class="ai-sidebar-icon" :size="18"><Setting /></el-icon>
              <span class="ai-sidebar-menu-text">客户配置</span>
              <span v-if="noteHasContent && !sidebarExpanded" class="ai-sidebar-dot ai-sidebar-dot--green" />
            </div>
          </div>

          <div class="ai-sidebar-toggle" @click="sidebarExpanded = !sidebarExpanded" :title="sidebarExpanded ? '收起侧边栏' : '展开侧边栏'">
            <el-icon class="ai-sidebar-icon" :size="18">
              <component :is="sidebarExpanded ? 'Fold' : 'Expand'" />
            </el-icon>
            <span class="ai-sidebar-menu-text" style="font-size: 13px;">收起</span>
          </div>
        </div>

        <!-- Sidebar panel (slides out) -->
        <transition name="ai-sidebar-slide">
          <div v-if="sidebarTab !== null" class="ai-sidebar-panel" :key="sidebarTab">
            <div class="ai-sidebar-panel__header">
              <span class="ai-sidebar-panel__title">
                {{ sidebarTab === 'history' ? '历史对话' : (sidebarTab === 'context' ? '已加载参考信息' : '客户专属配置') }}
              </span>
              <el-button text circle size="small" @click="sidebarTab = null"><el-icon><Close /></el-icon></el-button>
            </div>
            <div class="ai-sidebar-panel__body">
              <template v-if="sidebarTab === 'history'">
                <AiSessionHistoryList
                  :sessions="sessionHistory"
                  :loading="sessionHistoryLoading"
                  :active-session-id="sessionId"
                  @select="onSelectHistorySession"
                  @new-session="onCreateNewSession"
                />
              </template>
              <!-- Context tab -->
              <template v-else-if="sidebarTab === 'context'">
                <div class="ai-modules-row">
                  <span class="ai-modules-label">已加载参考信息</span>
                  <div class="ai-modules">
                    <span v-for="entry in usedModuleEntries" :key="entry.key" class="ai-module-chip">
                      <span class="ai-module-dot" :style="{ background: entry.color }" />
                      {{ entry.label }}
                    </span>
                  </div>
                </div>
                <div v-if="tokenDisplay" class="ai-token-hint">{{ tokenDisplay }}</div>
                <div class="ai-scene-bar" v-if="scenes.length">
                  <span class="ai-scene-label">工作场景</span>
                  <el-select v-model="currentScene" size="small" class="ai-scene-select">
                    <el-option v-for="s in scenes" :key="s.key" :label="s.label" :value="s.key" />
                  </el-select>
                </div>
                <div class="ai-scene-bar">
                  <span class="ai-scene-label">输出模式</span>
                  <el-select v-model="outputStyle" size="small" class="ai-scene-select">
                    <el-option label="教练简报" value="coach_brief" />
                    <el-option label="客户话术" value="customer_reply" />
                    <el-option label="交接备注" value="handoff_note" />
                    <el-option label="详细报告" value="detailed_report" />
                  </el-select>
                </div>
              </template>
              <template v-if="sidebarTab === 'notes'">
                <div class="ai-profile-note-hint">
                  <el-icon><InfoFilled /></el-icon>
                  <span>写长期背景信息，不要写本次问题。保存后对该客户所有 AI 对话生效。</span>
                </div>
                <div class="ai-note-fields-grid">
                  <div class="ai-note-field">
                    <label>沟通风格</label>
                    <el-input v-model="noteForm.communication_style_note" type="textarea" :rows="2" maxlength="1500" show-word-limit placeholder="例如：客户容易焦虑，先肯定再建议" class="ai-custom-textarea" />
                  </div>
                  <div class="ai-note-field">
                    <label>当前阶段重点</label>
                    <el-input v-model="noteForm.current_focus_note" type="textarea" :rows="2" maxlength="1500" show-word-limit placeholder="例如：这周重点先稳血糖，不强调减重速度" class="ai-custom-textarea" />
                  </div>
                  <div class="ai-note-field">
                    <label>执行障碍</label>
                    <el-input v-model="noteForm.execution_barrier_note" type="textarea" :rows="2" maxlength="1500" show-word-limit placeholder="例如：晚餐经常外食，早餐相对可控" class="ai-custom-textarea" />
                  </div>
                  <div class="ai-note-field">
                    <label>作息/家庭背景</label>
                    <el-input v-model="noteForm.lifestyle_background_note" type="textarea" :rows="2" maxlength="1500" show-word-limit placeholder="例如：夜班、带娃、长期晚睡" class="ai-custom-textarea" />
                  </div>
                  <div class="ai-note-field">
                    <label>教练内部策略备注</label>
                    <el-input v-model="noteForm.coach_strategy_note" type="textarea" :rows="2" maxlength="1500" show-word-limit placeholder="例如：不要反复强调体重数字，先守习惯" class="ai-custom-textarea" />
                  </div>
                </div>
                <div class="ai-note-actions">
                  <el-button class="ai-note-btn-save" :loading="profileNoteSaving" type="primary" @click="onSaveNote">保存</el-button>
                  <el-button class="ai-note-btn-reset" @click="resetNoteForm">恢复上次内容</el-button>
                </div>
              </template>
            </div>
          </div>
        </transition>

        <!-- Main chat area -->
        <div class="ai-main">
          <div v-if="disabledReason" class="ai-disabled-state">
            <el-alert :title="disabledReason" type="warning" :closable="false" show-icon />
          </div>
          <div v-if="visibleDataGaps.length" class="ai-data-gaps">
            <el-alert v-for="g in visibleDataGaps" :key="g" :title="g" type="warning" :closable="true" show-icon @close="dismissDataGap(g)" />
          </div>

          <!-- Chat messages -->
          <div class="ai-messages" ref="messagesRef">
            <div class="ai-welcome-container" v-if="chatHistory.length === 0 && !disabledReason">
              <div class="ai-welcome-hero">
                <div class="ai-welcome-icon-wrap">
                  <img src="https://cdn.mengfugui.com/logo.png" alt="AI Coach" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;" />
                </div>
                <h3>我是您的 <span class="ai-text-gradient">AI 教练助手</span></h3>
                <p>准备好为{{ customerName || '客户' }}提供专业的健康建议</p>
              </div>
              <div class="ai-quick-section">
                <p class="ai-quick-label"><el-icon><MagicStick /></el-icon> 快捷指令</p>
                <div class="ai-quick-grid">
                  <div v-for="qp in quickPromptItems" :key="qp.text" class="ai-quick-card" @click="askQuick(qp.text)">
                    <span class="ai-quick-card__icon" :style="{ background: qp.color }">
                      <el-icon :size="15" color="#fff"><component :is="qp.icon" /></el-icon>
                    </span>
                    <span class="ai-quick-card__text">{{ qp.text }}</span>
                    <el-icon class="ai-quick-card__arrow"><ArrowRight /></el-icon>
                  </div>
                </div>
              </div>
            </div>
            <div v-for="(msg, i) in chatHistory" :key="i" class="ai-msg" :class="`ai-msg--${msg.role}`">
              <div v-if="msg.role === 'assistant'" class="ai-avatar ai-avatar--assistant">
                <img src="https://cdn.mengfugui.com/logo.png" alt="AI Coach" style="width: 100%; height: 100%; border-radius: inherit; object-fit: cover;" />
              </div>
              <div v-if="msg.role === 'user'" class="ai-avatar ai-avatar--user">
                <img v-if="userStore.user?.avatar_url || userStore.user?.role === 'admin'" :src="userStore.user?.avatar_url || '/images/admain.jpg'" style="width: 100%; height: 100%; object-fit: cover; border-radius: inherit;" />
                <span v-else class="ai-avatar-text">{{ (userStore.user?.display_name || userStore.user?.username || '我').substring(0, 1) }}</span>
              </div>
              <div class="ai-msg-content">
                <div class="ai-msg-bubble">
                  <div v-if="msg.role === 'assistant' && msg.thinkingVisible && (msg.thinkingContent || msg.streaming)" class="ai-thinking-box">
                    <div class="ai-thinking-box__header">
                      <el-icon class="ai-thinking-box__icon" :class="{ 'is-loading': msg.streaming && !msg.thinkingContent }"><MagicStick /></el-icon>
                      <span>思考过程</span>
                    </div>
                    <div class="ai-thinking-box__body" v-html="renderMarkdown(msg.thinkingContent || '正在整理当前客户的关键信息与回复思路...')" />
                  </div>
                  <div v-if="msg.content" class="ai-msg-text" v-html="renderMarkdown(msg.content)" />
                  <div v-else-if="msg.role === 'assistant' && msg.streaming" class="ai-msg-placeholder">正在生成正式回复...</div>
                  <div v-if="msg.safetyNotes?.length" class="ai-msg-safety">
                    <el-tag v-for="n in msg.safetyNotes" :key="n" type="warning" size="small" round>{{ n }}</el-tag>
                  </div>
                </div>
                <div v-if="msg.role === 'assistant' && msg.content && !msg.content.startsWith('[错误]')" class="ai-msg-actions">
                  <el-button v-if="!msg.requiresMedicalReview" size="small" text @click="copyText(msg.content)">
                    <el-icon><CopyDocument /></el-icon> 复制草稿
                  </el-button>
                  <el-button v-if="msg.requiresMedicalReview" size="small" text type="warning" @click="copyText(msg.content)">
                    <el-icon><CopyDocument /></el-icon> 复制供内部复核
                  </el-button>
                  <el-button size="small" text @click="onMarkMedicalReview(msg)">
                    <el-icon><Warning /></el-icon> 标记需医生确认
                  </el-button>
                </div>
                <div v-if="msg.requiresMedicalReview" class="ai-msg-review">
                  <el-tag type="danger" size="small" round>需要医疗审核 — 禁止直接发送给客户</el-tag>
                </div>
                <div v-if="msg.tokenUsage" class="ai-msg-tokens">Tokens: {{ msg.tokenUsage.total_tokens || 0 }}</div>
              </div>
            </div>
          </div>

          <!-- Input -->
          <div class="ai-input-wrapper">
            <div class="ai-input-card">
              <el-input v-model="input" type="textarea" :autosize="{ minRows: 1, maxRows: 6 }" placeholder="输入本次问题，例如：基于她最近一周血糖..." :disabled="loading || !!disabledReason" @keydown.enter.exact.prevent="send" class="ai-chat-input" />
              <div class="ai-input-footer">
                <span class="ai-hint">按 Enter 发送，Shift + Enter 换行</span>
                <div class="ai-input-actions">
                  <el-icon class="ai-magic-icon" title="使用结构化提示词" @click="askQuick('请帮我总结核心跟进点')"><MagicStick /></el-icon>
                  <el-button type="primary" class="ai-send-btn" :class="{ 'is-active': input.trim() }" :loading="loading" circle @click="send" :disabled="!input.trim() || !!disabledReason">
                    <el-icon :size="18"><Promotion /></el-icon>
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, nextTick, watch, onBeforeUnmount } from 'vue'
import { 
  CopyDocument, 
  Warning, 
  Monitor, 
  Clock,
  MagicStick, 
  Delete, 
  Close, 
  ChatDotSquare, 
  EditPen, 
  Search, 
  ChatLineRound, 
  Promotion, 
  ArrowRight, 
  InfoFilled, 
  Postcard, 
  Fold, 
  Expand, 
  Document, 
  Setting 
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '#/stores/user'
import { useAiCoach } from '../composables/useAiCoach'
import AiSessionHistoryList from './AiSessionHistoryList.vue'

const userStore = useUserStore()

const DRAWER_WIDTH_KEY = 'ai-coach-drawer-width'
const DEFAULT_WIDTH = 560
const MIN_WIDTH = 400
const MAX_WIDTH = 1200

const props = withDefaults(defineProps<{
  modelValue: boolean
  customerId: number | null
  customerName?: string
  usedModules?: string[]
  dataGaps?: string[]
  disabledReason?: string
}>(), {
  customerName: '',
  usedModules: () => [],
  dataGaps: () => [],
  disabledReason: '',
})

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
}>()

const visible = ref(props.modelValue)
watch(() => props.modelValue, v => { visible.value = v })
watch(visible, v => { emit('update:modelValue', v) })

// --- Resizable drawer ---
const savedWidth = Number(localStorage.getItem(DRAWER_WIDTH_KEY)) || DEFAULT_WIDTH
const drawerWidth = ref(Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, savedWidth)))
let resizing = false

const onResizeStart = (e: MouseEvent) => {
  resizing = true
  const startX = e.clientX
  const startWidth = drawerWidth.value
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'

  const onMouseMove = (ev: MouseEvent) => {
    if (!resizing) return
    const delta = startX - ev.clientX
    const newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidth + delta))
    drawerWidth.value = newWidth
  }

  const onMouseUp = () => {
    resizing = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    localStorage.setItem(DRAWER_WIDTH_KEY, String(drawerWidth.value))
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

onBeforeUnmount(() => { resizing = false })

const {
  loading, chatHistory, tokenDisplay, sessionId, sendChat, clearSession,
  markMedicalReview: markReviewApi,
  scenes, currentScene, outputStyle, profileNote, profileNoteSaving, configLoaded,
  sessionHistory, sessionHistoryLoading, loadSessionHistory, openHistorySession,
  loadAiConfig, saveProfileNote,
} = useAiCoach()

const input = ref('')
const messagesRef = ref<HTMLElement>()
const sidebarTab = ref<'history' | 'context' | 'notes' | null>(null)
const sidebarExpanded = ref(true)
const visibleDataGaps = ref<string[]>([])

const moduleLabelMap: Record<string, string> = {
  basic_profile: '基础档案',
  safety_profile: '安全档案',
  goals_preferences: '目标与偏好',
  health_summary_7d: '近7天健康摘要',
  body_comp_latest_30d: '近30天体成分',
  points_engagement_14d: '近14天积分与活跃',
  service_scope: '服务关系',
}
const usedModuleLabels = computed(() => props.usedModules.map(m => moduleLabelMap[m] || m))

const moduleColorMap: Record<string, string> = {
  basic_profile: '#10b981',
  safety_profile: '#ef4444',
  goals_preferences: '#3b82f6',
  health_summary_7d: '#14b8a6',
  body_comp_latest_30d: '#f59e0b',
  points_engagement_14d: '#f97316',
  service_scope: '#8b5cf6',
}

const usedModuleEntries = computed(() =>
  props.usedModules.map(m => ({
    key: m,
    label: moduleLabelMap[m] || m,
    color: moduleColorMap[m] || '#94a3b8',
  }))
)

const quickPromptItems = [
  { text: '总结服务重点', icon: EditPen, color: '#10b981' },
  { text: '列出跟进问题', icon: Search, color: '#6366f1' },
  { text: '生成交接备注', icon: ChatLineRound, color: '#8b5cf6' },
]

const noteForm = reactive({
  communication_style_note: '' as string,
  current_focus_note: '' as string,
  execution_barrier_note: '' as string,
  lifestyle_background_note: '' as string,
  coach_strategy_note: '' as string,
})

const noteHasContent = computed(() =>
  Object.values(noteForm).some(v => v && v.trim())
)

const resetNoteForm = () => {
  const n = profileNote.value
  noteForm.communication_style_note = n?.communication_style_note || ''
  noteForm.current_focus_note = n?.current_focus_note || ''
  noteForm.execution_barrier_note = n?.execution_barrier_note || ''
  noteForm.lifestyle_background_note = n?.lifestyle_background_note || ''
  noteForm.coach_strategy_note = n?.coach_strategy_note || ''
}

const onSaveNote = () => {
  if (!props.customerId) return
  saveProfileNote(props.customerId, { ...noteForm })
}

watch(() => props.customerId, (id) => {
  clearSession()
  visibleDataGaps.value = props.dataGaps.slice()
  startAutoDismiss()
  if (id) {
    loadAiConfig(id)
    loadSessionHistory(id)
  }
})

watch(visible, (v) => {
  if (v && props.customerId && !configLoaded.value) {
    loadAiConfig(props.customerId)
  }
  if (v && props.customerId) {
    loadSessionHistory(props.customerId)
  }
  if (v) {
    visibleDataGaps.value = props.dataGaps.slice()
    startAutoDismiss()
  }
})

watch(() => props.dataGaps, (gaps) => {
  if (visible.value) {
    visibleDataGaps.value = gaps.slice()
  }
}, { deep: true })

watch(profileNote, () => { resetNoteForm() }, { immediate: true })
watch(chatHistory, async () => {
  await nextTick()
  scrollBottom()
}, { deep: true })

const send = async () => {
  const msg = input.value.trim()
  if (!msg || !props.customerId) return
  input.value = ''
  visibleDataGaps.value = []
  await sendChat(props.customerId, msg)
  await nextTick()
  scrollBottom()
}

const askQuick = async (prompt: string) => {
  if (!props.customerId) return
  visibleDataGaps.value = []
  await sendChat(props.customerId, prompt, { entryScene: 'quick_prompt' })
  await nextTick()
  scrollBottom()
}

const dismissDataGap = (gap: string) => {
  visibleDataGaps.value = visibleDataGaps.value.filter(item => item !== gap)
}

let autoDismissTimers: ReturnType<typeof setTimeout>[] = []

const startAutoDismiss = () => {
  for (const t of autoDismissTimers) clearTimeout(t)
  autoDismissTimers = []
  const gaps = visibleDataGaps.value.slice()
  gaps.forEach((gap, idx) => {
    const timer = setTimeout(() => {
      visibleDataGaps.value = visibleDataGaps.value.filter(g => g !== gap)
    }, 3000 + idx * 500)
    autoDismissTimers.push(timer)
  })
}

const scrollBottom = () => {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

const copyText = (text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制到剪贴板')
  })
}

const onMarkMedicalReview = async (msg: any) => {
  if (!props.customerId || !msg.messageId) {
    ElMessage.warning('已标记需医生确认，请在内部流程中跟进')
    return
  }
  const ok = await markReviewApi(props.customerId, msg.messageId)
  if (ok) {
    ElMessage.warning('已标记需医生确认，请在内部流程中跟进')
  } else {
    ElMessage.error('标记失败，请重试')
  }
}

const onSelectHistorySession = async (targetSessionId: string) => {
  if (!props.customerId) return
  const ok = await openHistorySession(props.customerId, targetSessionId)
  if (ok) {
    sidebarTab.value = null
    await nextTick()
    scrollBottom()
  }
}

const onCreateNewSession = () => {
  clearSession()
  sidebarTab.value = null
  ElMessage.success('已切换到新对话')
}

const renderMarkdown = (text: string) => {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
}
</script>

<style scoped>
/* ==================== Resize Handle ==================== */
.ai-resize-handle {
  position: absolute;
  top: 0;
  left: 0;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ai-resize-handle:hover .ai-resize-handle__line,
.ai-resize-handle:active .ai-resize-handle__line {
  opacity: 1;
  background: #6366f1;
  width: 3px;
}
.ai-resize-handle__line {
  width: 2px;
  height: 40px;
  border-radius: 2px;
  background: #d1d5db;
  opacity: 0.5;
  transition: all 0.2s;
}

/* ==================== Panel Layout ==================== */
.ai-panel {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f8f7fc;
  overflow: hidden;
}

/* ==================== Panel Header ==================== */
.ai-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #fff;
  border-bottom: 1px solid #f3f4f6;
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}
.ai-panel-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ai-panel-logo {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: transparent;
  flex-shrink: 0;
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.15);
}
.ai-panel-header__title {
  font-size: 16px;
  font-weight: 700;
  color: #111827;
}
.ai-session-tag { font-size: 11px; }
.ai-panel-header__right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-panel-header__right .el-button { 
  color: #6b7280; 
  background: #f3f4f6;
}
.ai-panel-header__right .el-button:hover { 
  color: #6366f1; 
  background: #eef2ff;
}

/* ==================== Panel Body (sidebar + main) ==================== */
.ai-panel-body {
  display: flex;
  flex: 1;
  overflow: hidden;
  position: relative;
  background: #f8f9fa;
}

/* ==================== Sidebar ==================== */
.ai-sidebar {
  width: 76px;
  flex-shrink: 0;
  background: #fdfdff;
  border-right: 1px solid #eef0f4;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow-x: hidden;
  box-shadow: 2px 0 10px rgba(0,0,0,0.01);
  z-index: 20;
}
.ai-sidebar.is-expanded {
  width: 140px;
  align-items: flex-start;
}

/* Sidebar Brand (Top icon) */
.ai-sidebar-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 32px;
  cursor: pointer;
  width: 100%;
}
.ai-sidebar-brand-icon {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: #eef2ff;
  color: #6366f1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  transition: all 0.2s;
}
.ai-sidebar-brand:hover .ai-sidebar-brand-icon {
  background: #6366f1;
  color: #fff;
  box-shadow: 0 4px 14px rgba(99,102,241,0.25);
  transform: translateY(-2px);
}
.ai-sidebar-brand-text {
  font-size: 13px;
  font-weight: 600;
  color: #4b5563;
  opacity: 0;
  width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-align: center;
  transition: all 0.2s;
}
.ai-sidebar.is-expanded .ai-sidebar-brand-text {
  opacity: 1;
  width: auto;
}

/* Sidebar Menu */
.ai-sidebar-menu {
  display: flex;
  flex-direction: column;
  width: 100%;
  gap: 8px;
  padding: 0 8px;
}
.ai-sidebar-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 48px;
  padding: 0 16px;
  border-radius: 12px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  white-space: nowrap;
}
.ai-sidebar-menu-item:hover {
  color: #6366f1;
  background: #f5f3ff;
}
.ai-sidebar-menu-item.is-active {
  color: #6366f1;
  background: #eef2ff;
  font-weight: 600;
}
.ai-sidebar-icon {
  min-width: 18px;
  flex-shrink: 0;
  transition: all 0.2s;
}
.ai-sidebar-menu-text {
  font-size: 14px;
  opacity: 0;
  transform: translateX(-10px);
  transition: all 0.3s;
  pointer-events: none;
}
.ai-sidebar.is-expanded .ai-sidebar-menu-item {
  justify-content: flex-start;
}
.ai-sidebar.is-expanded .ai-sidebar-menu-text {
  opacity: 1;
  transform: translateX(0);
}
.ai-sidebar-dot {
  position: absolute;
  top: 14px;
  left: 32px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  border: 1px solid #fff;
}
.ai-sidebar-dot--green { background: #10b981; }

/* Sidebar Toggle */
.ai-sidebar-toggle {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  height: 48px;
  padding: 0 16px;
  border-radius: 12px;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
  width: calc(100% - 16px);
  box-sizing: border-box;
  margin-bottom: 8px;
}
.ai-sidebar.is-expanded .ai-sidebar-toggle {
  justify-content: flex-start;
}
.ai-sidebar-toggle:hover {
  color: #4f46e5;
  background: #f1f5f9;
}
.ai-sidebar-toggle .ai-sidebar-menu-text {
  font-size: 14px;
  opacity: 0;
  transform: translateX(-10px);
  transition: all 0.3s;
  pointer-events: none;
}
.ai-sidebar.is-expanded .ai-sidebar-toggle .ai-sidebar-menu-text {
  opacity: 1;
  transform: translateX(0);
}

/* ==================== Sidebar Panel ==================== */
.ai-sidebar-panel {
  width: 280px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #eeeef2;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ai-sidebar-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eeeef2;
  flex-shrink: 0;
}
.ai-sidebar-panel__title {
  font-size: 14px;
  font-weight: 700;
  color: #1f2937;
}
.ai-sidebar-panel__header .el-button { color: #9ca3af; }
.ai-sidebar-panel__header .el-button:hover { color: #6366f1; }
.ai-sidebar-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

/* Sidebar slide transition */
.ai-sidebar-slide-enter-active,
.ai-sidebar-slide-leave-active {
  transition: width 0.25s ease, opacity 0.2s ease;
  overflow: hidden;
}
.ai-sidebar-slide-enter-from,
.ai-sidebar-slide-leave-to {
  width: 0;
  opacity: 0;
}

/* ==================== Main chat area ==================== */
.ai-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  background: #f8f9fa; /* Light grey modern background */
}
.ai-disabled-state {
  padding: 12px 20px 0;
  flex-shrink: 0;
}

/* ==================== Context / Modules (inside sidebar) ==================== */
.ai-modules-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ai-modules-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}
.ai-modules {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.ai-module-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
  color: #374151;
  background: #f4f4f8;
  border: 1px solid #e5e7eb;
  white-space: nowrap;
}
.ai-module-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ai-token-hint {
  margin-top: 10px;
  font-size: 11px;
  color: #9ca3af;
  font-variant-numeric: tabular-nums;
}

/* ==================== Scene Selector (inside sidebar) ==================== */
.ai-scene-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #e5e7eb;
}
.ai-scene-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.ai-scene-select { width: 100%; }

/* ==================== Data Gaps ==================== */
.ai-data-gaps {
  padding: 8px 20px;
  flex-shrink: 0;
}
.ai-data-gaps .el-alert {
  border-radius: 10px;
  margin-bottom: 4px;
}

/* ==================== Profile Notes (inside sidebar) ==================== */
.ai-profile-note-hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: #6b7280;
  padding: 0 0 14px;
  margin: 0 0 16px;
  border-bottom: 1px dashed #e5e7eb;
  line-height: 1.5;
}
.ai-profile-note-hint .el-icon {
  margin-top: 2px;
  flex-shrink: 0;
  color: #9ca3af;
}
.ai-note-fields-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.ai-note-field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #4b5563;
  margin-bottom: 6px;
}
.ai-custom-textarea :deep(.el-textarea__inner) {
  border-radius: 8px;
  background: #f9fafb;
  border-color: #e5e7eb;
  padding: 8px 10px;
  font-size: 12px;
  color: #1f2937;
  transition: all 0.2s;
  line-height: 1.5;
  box-shadow: none;
}
.ai-custom-textarea :deep(.el-textarea__inner):focus {
  background: #fff;
  border-color: #10b981;
  box-shadow: 0 0 0 1px #10b981;
}
.ai-custom-textarea :deep(.el-textarea__inner)::placeholder {
  color: #9ca3af;
}
.ai-custom-textarea :deep(.el-input__count) {
  background: transparent;
  bottom: 4px;
  right: 8px;
  font-size: 10px;
}
.ai-note-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
.ai-note-btn-save {
  padding: 6px 20px;
  background: #10b981;
  border-color: #10b981;
  font-weight: 600;
  border-radius: 6px;
  font-size: 13px;
}
.ai-note-btn-save:hover {
  background: #059669;
  border-color: #059669;
}
.ai-note-btn-reset {
  padding: 6px 16px;
  color: #6b7280;
  background: #fff;
  border-color: #d1d5db;
  border-radius: 6px;
  font-size: 13px;
}
.ai-note-btn-reset:hover {
  color: #374151;
  border-color: #9ca3af;
  background: #f9fafb;
}

/* ==================== Welcome Hero ==================== */
.ai-welcome-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 32px 20px;
}
.ai-welcome-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 24px 20px 36px;
}
.ai-welcome-icon-wrap {
  width: 90px;
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  margin-bottom: 24px;
  position: relative;
  box-shadow: inset 0 2px 10px rgba(255,255,255,0.8), 0 4px 20px rgba(99,102,241,0.08);
}
.ai-welcome-icon {
  font-size: 40px;
  color: #6366f1;
}
.ai-welcome-hero h3 {
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 10px;
}
.ai-text-gradient {
  color: #6366f1;
}
.ai-welcome-hero p {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

/* ==================== Quick Prompt Cards ==================== */
.ai-quick-section {
  width: 100%;
  max-width: 560px;
  padding: 0 8px;
}
.ai-quick-label {
  font-size: 13px;
  font-weight: 600;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 14px;
  padding-left: 4px;
}
.ai-quick-label .el-icon { color: #6366f1; }
.ai-quick-grid {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.ai-quick-card {
  flex: 1 1 140px;
  min-width: 140px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #f0f2f5;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(0,0,0,0.02);
}
.ai-quick-card:hover {
  border-color: #6366f1;
  background: #fff;
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(99,102,241,0.08);
}
.ai-quick-card__icon {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  flex-shrink: 0;
}
.ai-quick-card__text {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  white-space: nowrap;
}
.ai-quick-card__arrow {
  color: #d1d5db;
  font-size: 13px;
  flex-shrink: 0;
  transition: color 0.2s, transform 0.2s;
}
.ai-quick-card:hover .ai-quick-card__arrow {
  color: #6366f1;
  transform: translateX(3px);
}

/* ==================== Chat Messages ==================== */
.ai-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 28px; /* Slightly wider gap */
  background: transparent;
}
.ai-msg {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  position: relative;
  animation: msg-in 0.25s ease-out;
  width: 100%;
}
@keyframes msg-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.ai-msg--user {
  flex-direction: row-reverse;
}
.ai-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.ai-avatar--assistant {
  background: transparent;
  box-shadow: 0 4px 10px rgba(99,102,241,0.15);
}
.ai-avatar--user {
  background: #e2e8f0;
  color: #475569;
  font-weight: 600;
  font-size: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.ai-avatar-text {
  display: inline-block;
  transform: translateY(-1px);
}
.ai-msg-content {
  max-width: 80%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ai-msg--user .ai-msg-content {
  align-items: flex-end;
}
.ai-msg-bubble {
  padding: 14px 18px;
  font-size: 14.5px;
  line-height: 1.65;
  word-break: break-word;
  transition: all 0.2s;
}
.ai-msg--assistant .ai-msg-bubble {
  background: #ffffff;
  color: #374151;
  border-radius: 4px 18px 18px 18px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.04);
  border: 1px solid #f0f2f5;
}
.ai-msg--user .ai-msg-bubble {
  background: #eef2ff; /* Crisp clean light blue matching user side */
  color: #312e81;
  border-radius: 18px 4px 18px 18px;
  box-shadow: 0 4px 16px rgba(99,102,241,0.06);
}
.ai-msg-bubble--loading {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-loading-text {
  font-size: 13px;
  color: #9ca3af;
}
:global(html.dark) .ai-msg--assistant .ai-msg-bubble {
  background: rgba(255, 255, 255, 0.06);
}
.ai-msg-text { word-break: break-word; }
.ai-msg-placeholder {
  font-size: 13px;
  color: #9ca3af;
}
.ai-thinking-box {
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px dashed #e5e7eb;
  max-width: 420px;
}
.ai-thinking-box__header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}
.ai-thinking-box__icon { font-size: 13px; }
.ai-thinking-box__icon.is-loading {
  color: #6366f1;
  animation: spin 2s linear infinite;
}
@keyframes spin { 100% { transform: rotate(360deg); } }
.ai-thinking-box__body {
  max-height: 120px;
  overflow-y: auto;
  font-size: 12px;
  line-height: 1.65;
  color: #6b7280;
  word-break: break-word;
}
.ai-msg-safety {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ai-msg-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  opacity: 0;
  transition: opacity 0.2s;
}
.ai-msg-content:hover .ai-msg-actions { opacity: 1; }
.ai-msg-actions .el-button { margin: 0; }
.ai-msg-review { margin-top: 6px; }
.ai-msg-tokens {
  margin-top: 6px;
  text-align: right;
  font-size: 11px;
  color: #d1d5db;
  font-variant-numeric: tabular-nums;
}

/* ==================== Input Area Floating Card ==================== */
.ai-input-wrapper {
  padding: 10px 24px 24px;
  background: transparent;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}
.ai-input-card {
  background: #fff;
  border-radius: 24px;
  padding: 12px 18px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.06);
  border: 1px solid #f0f2f5;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ai-input-card:focus-within {
  border-color: #a5b4fc;
  box-shadow: 0 12px 40px rgba(99,102,241,0.12);
  transform: translateY(-2px);
}
:deep(.ai-chat-input) {
  min-width: 0;
}
:deep(.ai-chat-input .el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding: 4px 8px !important;
  font-size: 14px;
  color: #1f2937;
  resize: none;
  min-height: 24px !important;
  line-height: 1.6;
}
:deep(.ai-chat-input .el-textarea__inner)::placeholder {
  color: #9ca3af;
}
.ai-input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
  padding-left: 8px;
}
.ai-hint {
  font-size: 13px;
  color: #9ca3af;
  margin: 0;
}
.ai-input-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}
.ai-magic-icon {
  color: #a5b4fc;
  font-size: 22px;
  cursor: pointer;
  transition: all 0.2s;
}
.ai-magic-icon:hover {
  color: #6366f1;
  transform: scale(1.1) rotate(-10deg);
}
.ai-send-btn.el-button.is-circle {
  width: 44px;
  height: 44px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  border: none;
  transition: all 0.2s;
  color: #94a3b8;
  flex-shrink: 0;
  font-size: 20px;
}
.ai-send-btn.el-button.is-circle.is-active {
  background: #6366f1;
  color: #fff;
  box-shadow: 0 4px 14px rgba(99,102,241,0.3);
}
.ai-send-btn.el-button.is-circle.is-active:hover {
  background: #4f46e5;
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(99,102,241,0.4);
}
</style>
