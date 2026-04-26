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
                <div class="ai-context-preview-section">
                  <el-button size="small" class="ai-preview-btn" @click="loadContextPreview" :loading="contextPreviewLoading">
                    预览 AI 视角
                  </el-button>
                  <div v-if="contextPreviewText" class="ai-context-preview-box">
                    <div class="ai-context-preview-meta">
                      约 {{ contextPreviewTokens }} tokens · {{ contextPreviewChars }} 字符
                      <span v-if="selectedExpansions.length"> · 展开：{{ selectedExpansions.map(k => expansionOptions[k] || k).join('、') }}</span>
                    </div>
                    <pre class="ai-context-preview-text">{{ contextPreviewText }}</pre>
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
                <div class="ai-expansion-section" v-if="Object.keys(expansionOptions).length">
                  <span class="ai-scene-label">附加参考模块</span>
                  <div class="ai-expansion-checkboxes">
                    <el-checkbox-group v-model="selectedExpansions" size="small">
                      <el-checkbox v-for="(label, key) in expansionOptions" :key="key" :value="key" :label="label" />
                    </el-checkbox-group>
                  </div>
                  <div class="ai-expansion-hint">勾选后发送时自动展开详细数据</div>
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

          <AiCoachMessageList
            ref="messageListRef"
            :chat-history="chatHistory"
            :customer-name="customerName"
            :restored-session-meta="restoredSessionMeta"
            :session-id="sessionId"
            :loading="loading"
            :user-avatar="userStore.user?.avatar_url"
            :user-display-name="userStore.user?.display_name || userStore.user?.username"
            :is-admin="userStore.user?.role === 'admin'"
            :disabled-reason="disabledReason"
            :visible-data-gaps="visibleDataGaps"
            @copy="copyText"
            @mark-medical-review="onMarkMedicalReview"
            @quick-ask="askQuick"
            @dismiss-data-gap="dismissDataGap"
          />

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
  Clock,
  MagicStick,
  Delete,
  Close,
  ChatLineRound,
  Promotion,
  InfoFilled,
  Fold,
  Expand,
  Document,
  Setting
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '#/stores/user'
import request from '#/utils/request'
import { useAiCoach } from '../composables/useAiCoach'
import AiSessionHistoryList from './AiSessionHistoryList.vue'
import AiCoachMessageList from './AiCoachMessageList.vue'

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
  loadAiConfig, saveProfileNote, restoredSessionMeta,
  expansionOptions, selectedExpansions,
} = useAiCoach()

const input = ref('')
const messageListRef = ref<InstanceType<typeof AiCoachMessageList>>()
const sidebarTab = ref<'history' | 'context' | 'notes' | null>(null)
const sidebarExpanded = ref(true)
const contextPreviewText = ref('')
const contextPreviewTokens = ref(0)
const contextPreviewChars = ref(0)
const contextPreviewLoading = ref(false)
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

watch([currentScene, outputStyle], ([scene, style]) => {
  if (!restoredSessionMeta.value || !sessionId.value) return
  const meta = restoredSessionMeta.value
  if (scene !== meta.sceneKey || style !== meta.outputStyle) {
    ElMessage.warning('你正在修改这段历史会话的工作场景/输出模式，后续回复将按新策略继续生成。')
    restoredSessionMeta.value = null
  }
})

const loadContextPreview = async () => {
  if (!props.customerId) return
  contextPreviewLoading.value = true
  try {
    const params = new URLSearchParams({ scene_key: currentScene.value })
    if (selectedExpansions.value.length) {
      params.set('selected_expansions', selectedExpansions.value.join(','))
    }
    const res: any = await request.get(`/v1/crm-customers/${props.customerId}/ai/context-preview`, { params })
    contextPreviewText.value = res.context_text || ''
    contextPreviewTokens.value = res.estimated_tokens || 0
    contextPreviewChars.value = res.estimated_chars || 0
  } catch (e) {
    console.warn('Failed to load context preview', e)
  } finally {
    contextPreviewLoading.value = false
  }
}

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
  messageListRef.value?.scrollToBottom()
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
</script>

<style scoped>
@import './styles/aiCoachPanel.css';
</style>
