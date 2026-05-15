<template>
  <el-drawer
    v-model="visible"
    direction="rtl"
    :size="isMobile ? '100%' : drawerWidth + 'px'"
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
      <!-- Body: sidebar + main (no header bar) -->
      <div class="ai-panel-body">
        <!-- Sidebar rail -->
        <div class="ai-sidebar" :class="{ 'is-expanded': sidebarExpanded }" @mouseenter="onSidebarEnter" @mouseleave="onSidebarLeave">
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
                  @search="onSearchSessions"
                  @rename="onRenameSession"
                  @toggle-pin="onTogglePinSession"
                  @delete="onDeleteSession"
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
                <div class="ai-scene-bar" v-if="styles.length">
                  <span class="ai-scene-label">输出模式</span>
                  <el-select v-model="outputStyle" size="small" class="ai-scene-select">
                    <el-option v-for="s in styles" :key="s.key" :label="s.label" :value="s.key" />
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
                <!-- RAG knowledge base index (admin only) -->
                <div v-if="isAdmin" class="ai-rag-section">
                  <span class="ai-scene-label">知识库索引</span>
                  <div class="ai-rag-status">
                    <span class="ai-rag-dot" :class="ragStatus.qdrant_available ? 'ai-rag-dot--ok' : 'ai-rag-dot--off'" />
                    <span>{{ ragStatus.qdrant_available ? 'Qdrant 已连接' : 'Qdrant 未连接' }}</span>
                  </div>
                  <el-button
                    size="small"
                    class="ai-preview-btn"
                    :loading="ragReindexing"
                    @click="triggerReindex"
                  >
                    {{ ragReindexing ? '索引中...' : '更新话术索引' }}
                  </el-button>
                  <div v-if="ragReindexResult" class="ai-rag-result">
                    <span v-if="ragReindexResult.speech_templates">
                      话术：{{ ragReindexResult.speech_templates.indexed }} 入库 / {{ ragReindexResult.speech_templates.skipped }} 跳过 / {{ ragReindexResult.speech_templates.errors }} 错误
                    </span>
                  </div>
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
        <div class="ai-main" @dragenter.prevent="onDragEnter" @dragover.prevent @dragleave="onDragLeave" @drop.prevent="onDrop">
          <!-- Drop zone overlay -->
          <transition name="ai-drop-fade">
            <div v-if="isDragging" class="ai-drop-zone">
              <div class="ai-drop-zone-inner">
                <el-icon :size="40" class="ai-drop-zone-icon"><Upload /></el-icon>
                <span class="ai-drop-zone-text">松开即可上传附件</span>
              </div>
            </div>
          </transition>
          <!-- Floating top bar (ChatGPT style) -->
          <div class="ai-floating-top">
            <div v-if="isMobile" class="ai-floating-left">
              <button class="ai-action-btn" @click="mobileMenuOpen = !mobileMenuOpen" title="菜单">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M1 3.5h12M1 7h12M1 10.5h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
              </button>
            </div>
            <span class="ai-floating-title">AI 教练助手</span>
            <div class="ai-floating-actions">
              <button class="ai-action-btn" :class="{ 'is-active': selectMode }" @click="toggleSelectMode" :title="selectMode ? '退出选择' : '选择消息发送'">
                <el-icon :size="14"><Select /></el-icon>
              </button>
              <button class="ai-action-btn" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏'">
                <el-icon :size="14"><FullScreen /></el-icon>
              </button>
              <button class="ai-action-btn" @click="clearSession()" title="清空会话">
                <el-icon :size="14"><Delete /></el-icon>
              </button>
              <button class="ai-action-btn" @click="visible = false" title="关闭">
                <el-icon :size="14"><Close /></el-icon>
              </button>
            </div>
          </div>

          <!-- Mobile tab bar -->
          <transition name="ai-mobile-menu">
            <div v-if="isMobile && mobileMenuOpen" class="ai-mobile-tab-bar">
              <div class="ai-mobile-tab-item" :class="{ 'is-active': sidebarTab === 'history' }" @click="setMobileTab('history')">
                <el-icon :size="16"><Clock /></el-icon>
                <span>历史</span>
              </div>
              <div class="ai-mobile-tab-item" :class="{ 'is-active': sidebarTab === 'context' }" @click="setMobileTab('context')">
                <el-icon :size="16"><Document /></el-icon>
                <span>参考</span>
              </div>
              <div class="ai-mobile-tab-item" :class="{ 'is-active': sidebarTab === 'notes' }" @click="setMobileTab('notes')">
                <el-icon :size="16"><Setting /></el-icon>
                <span>配置</span>
              </div>
            </div>
          </transition>

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
            :select-mode="selectMode"
            :selected-indices="selectedIndices"
            @copy="copyText"
            @mark-medical-review="onMarkMedicalReview"
            @quick-ask="askQuick"
            @dismiss-data-gap="dismissDataGap"
            @toggle-select="onToggleSelect"
            @send-to-center="sendAssetToCenter"
            @retry="onRetryLast"
            @feedback="onFeedback"
            @regenerate="onRegenerate"
            @quote="onQuote"
          />

          <!-- Select mode action bar -->
          <transition name="ai-action-bar">
            <div v-if="selectMode && selectedIndices.size" class="ai-select-action-bar">
              <span class="ai-select-count">已选 {{ selectedIndices.size }} 条消息</span>
              <el-button size="small" @click="selectedIndices = new Set()">清除</el-button>
              <el-button type="primary" size="small" @click="sendToCenter">发送到发送中心</el-button>
            </div>
          </transition>

          <!-- Input -->
          <div class="ai-input-wrapper">
            <div v-if="cacheStatusText" class="ai-cache-status" :class="{ 'is-blocking': cacheSendBlocked }">
              {{ cacheStatusText }}
            </div>
            <!-- Attachment preview strip -->
            <div v-if="pendingAttachments.length" class="ai-attachment-strip">
              <div v-for="(att, idx) in pendingAttachments" :key="att.attachment_id" class="ai-att-card" :class="{ 'is-uploading': att.uploading, 'is-file': !att.mime_type.startsWith('image/') }">
                <!-- Image Attachment -->
                <div
                  v-if="att.mime_type.startsWith('image/')"
                  class="ai-att-card-thumb"
                  :class="{ 'is-clickable': !!att.url }"
                  title="查看大图"
                  @click="openAttachmentPreview(att)"
                >
                  <img :src="att.url" class="ai-att-card-img" />
                </div>
                <!-- File Attachment -->
                <div v-else class="ai-att-card-file-body" :title="att.filename">
                  <div class="ai-att-card-file-icon" :class="getFileIconClass(att.filename)">
                    <el-icon :size="20"><Document /></el-icon>
                  </div>
                  <div class="ai-att-card-file-info">
                    <div class="ai-att-card-filename">{{ att.filename }}</div>
                    <div class="ai-att-card-fileformat">{{ getFileTypeLabel(att.filename) }}</div>
                  </div>
                </div>

                <div v-if="att.uploading" class="ai-att-card-status">
                  {{ (att.progress || 0) >= 90 ? '处理中' : `上传 ${Math.max(1, Math.round(att.progress || 1))}%` }}
                </div>
                <el-icon class="ai-att-card-remove" @click.stop="removeAttachment(idx)"><Close /></el-icon>
              </div>
            </div>
            <input ref="fileInputRef" type="file" accept="image/jpeg,image/png,image/webp,application/pdf,.docx,.xlsx,.txt,.md"
              style="display:none" @change="onFileSelected" />
            <!-- Quote bar for follow-up questions -->
            <div v-if="quotedMessage" class="ai-quote-bar">
              <div class="ai-quote-bar-content">
                <el-icon :size="14"><ChatLineRound /></el-icon>
                <span>正在追问 AI 回复：{{ truncateText(quotedMessage.content, 60) }}</span>
              </div>
              <el-icon class="ai-quote-bar-close" @click="clearQuote"><Close /></el-icon>
            </div>
            <div class="ai-input-card" @paste="onPaste">
              <el-input v-model="input" type="textarea" :autosize="{ minRows: 1, maxRows: 8 }" placeholder="输入本次问题，例如：基于她最近一周血糖..." :disabled="loading || !!disabledReason || cacheSendBlocked" @keydown.enter.exact.prevent="send" class="ai-chat-input" />
              <div class="ai-input-toolbar">
                <div class="ai-toolbar-left">
                  <el-icon class="ai-magic-icon" title="上传附件" @click="triggerFileInput"><Paperclip /></el-icon>
                  <el-icon class="ai-magic-icon" title="使用结构化提示词" @click="askQuick('请帮我总结核心跟进点')"><MagicStick /></el-icon>
                </div>
                <div class="ai-toolbar-right">
                  <el-popover v-if="availableModels.length" placement="top-end" :width="240" trigger="click" :teleported="true" popper-class="ai-model-popover" :offset="4">
                    <template #reference>
                      <span class="ai-model-tag">
                        <span class="ai-model-tag-name">{{ selectedModel }}</span>
                        <span class="ai-model-tag-badge">推荐</span>
                      </span>
                    </template>
                    <div class="ai-model-panel">
                      <div class="ai-model-panel-header">当前模型</div>
                      <div class="ai-model-panel-selected">
                        <span class="ai-model-panel-pill">{{ selectedModel }}</span>
                        <span class="ai-model-panel-badge">推荐</span>
                      </div>
                      <div class="ai-model-panel-body">
                        <template v-for="group in modelGroups" :key="group.label">
                          <div class="ai-model-group-label">{{ group.label }}</div>
                          <div v-for="m in group.models" :key="m" class="ai-model-item" :class="{ 'is-active': m === selectedModel }" @click="selectedModel = m">
                            <span class="ai-model-item-name">{{ m }}</span>
                            <el-icon v-if="m === selectedModel" class="ai-model-item-check" :size="14"><Check /></el-icon>
                            <span v-if="m === recommendedModel && m !== selectedModel" class="ai-model-item-badge">推荐</span>
                          </div>
                        </template>
                      </div>
                    </div>
                  </el-popover>
                  <el-button type="primary" class="ai-send-btn" :class="{ 'is-active': input.trim() }" :loading="loading" circle size="small" @click="send" :disabled="(!input.trim() && !pendingAttachments.length) || !!disabledReason || cacheSendBlocked">
                    <el-icon :size="16"><Promotion /></el-icon>
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
  <AiCoachFeedbackDialog
    ref="feedbackDialogRef"
    :user-question="feedbackTargetQuestion"
    :ai-answer="feedbackTargetMsg?.content || ''"
    @submit="onFeedbackDialogSubmit"
  />
  <el-dialog
    v-model="previewDialog.visible"
    :title="previewDialog.title"
    class="ai-attachment-preview-dialog"
    append-to-body
    destroy-on-close
    width="min(92vw, 860px)"
  >
    <img v-if="previewDialog.url" :src="previewDialog.url" class="ai-attachment-preview-img" />
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, nextTick, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
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
  Setting,
  FullScreen,
  Select,
  Paperclip,
  Loading,
  Check,
  Upload,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '#/stores/user'
import request from '#/utils/request'
import { useAiCoach } from '../composables/useAiCoach'
import type { AiChatMessage, AiAttachment } from '../composables/useAiCoach'
import type { AiProfileCacheStatus } from '../composables/useCrmProfile'
import { useAiFileUpload } from '../composables/useAiFileUpload'
import { useAiSessionAdmin } from '../composables/useAiSessionAdmin'
import AiSessionHistoryList from './AiSessionHistoryList.vue'
import AiCoachMessageList from './AiCoachMessageList.vue'
import AiCoachFeedbackDialog from './AiCoachFeedbackDialog.vue'

const userStore = useUserStore()
const router = useRouter()
const isAdmin = computed(() => userStore.user?.role === 'admin')
const isMobile = computed(() => window.innerWidth < 768)

const DRAWER_WIDTH_KEY = 'ai-coach-drawer-width'
const DEFAULT_WIDTH = 560
const MIN_WIDTH = Math.min(400, window.innerWidth - 16)
const MAX_WIDTH = 1200

const props = withDefaults(defineProps<{
  modelValue: boolean
  customerId: number | null
  customerName?: string
  usedModules?: string[]
  dataGaps?: string[]
  disabledReason?: string
  healthWindowDays?: number
  profileCacheStatus?: AiProfileCacheStatus | null
}>(), {
  customerName: '',
  usedModules: () => [],
  dataGaps: () => [],
  disabledReason: '',
  healthWindowDays: 7,
  profileCacheStatus: null,
})

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
}>()

const visible = ref(props.modelValue)
watch(() => props.modelValue, v => { visible.value = v })
watch(visible, v => { emit('update:modelValue', v) })

// --- Resizable drawer ---
const savedWidth = Number(localStorage.getItem(DRAWER_WIDTH_KEY)) || DEFAULT_WIDTH
const maxAllowed = Math.min(MAX_WIDTH, window.innerWidth)
const drawerWidth = ref(Math.max(MIN_WIDTH, Math.min(maxAllowed, savedWidth)))
const isFullscreen = ref(false)
let resizing = false

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
  if (isFullscreen.value) {
    drawerWidth.value = window.innerWidth
  } else {
    drawerWidth.value = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, savedWidth))
  }
}

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
  loading, chatHistory, tokenDisplay, sessionId, sendChat, clearSession, retryLast,
  markMedicalReview: markReviewApi,
  submitFeedback: submitFeedbackApi,
  regenerate: regenerateApi,
  quotedMessage, setQuote, clearQuote,
  scenes, styles, currentScene, outputStyle, profileNote, profileNoteSaving, configLoaded,
  sessionHistory, sessionHistoryLoading, sessionSearchKeyword, loadSessionHistory, openHistorySession,
  loadAiConfig, saveProfileNote, restoredSessionMeta,
  expansionOptions, selectedExpansions,
  availableModels, selectedModel,
  uploadAttachmentDirect,
} = useAiCoach()

const input = ref('')

const recommendedModel = computed(() => availableModels.value[0] || '')

const modelGroups = computed(() => {
  const groups: { label: string; models: string[] }[] = []
  const prefixes: { prefix: string; label: string }[] = [
    { prefix: 'gpt', label: 'GPT 系列' },
    { prefix: 'deepseek', label: 'DeepSeek 系列' },
  ]
  const assigned = new Set<string>()
  for (const { prefix, label } of prefixes) {
    const models = availableModels.value.filter(m => m.toLowerCase().startsWith(prefix))
    if (models.length) {
      groups.push({ label, models })
      models.forEach(m => assigned.add(m))
    }
  }
  const others = availableModels.value.filter(m => !assigned.has(m))
  if (others.length) {
    groups.push({ label: '其他模型', models: others })
  }
  return groups
})

const {
  pendingAttachments, uploadingAttachment, fileInputRef, previewDialog,
  triggerFileInput, addAndUploadFile, onFileSelected, onPaste, removeAttachment, openAttachmentPreview,
  waitForUploads,
} = useAiFileUpload({
  loading,
  uploadAttachmentDirect,
  getCustomerId: () => props.customerId,
})

const { renameSession, togglePin, deleteSession } = useAiSessionAdmin()

const messageListRef = ref<InstanceType<typeof AiCoachMessageList>>()
const sidebarTab = ref<'history' | 'context' | 'notes' | null>(null)
const sidebarExpanded = ref(true)
let sidebarHoverTimer: ReturnType<typeof setTimeout> | null = null

const onSidebarEnter = () => {
  if (sidebarExpanded.value) return
  sidebarHoverTimer = setTimeout(() => { sidebarExpanded.value = true }, 200)
}
const onSidebarLeave = () => {
  if (sidebarHoverTimer) { clearTimeout(sidebarHoverTimer); sidebarHoverTimer = null }
}

const mobileMenuOpen = ref(false)
const selectMode = ref(false)
const isDragging = ref(false)
let dragEnterCount = 0

const onDragEnter = () => {
  dragEnterCount++
  isDragging.value = true
}
const onDragLeave = (e: DragEvent) => {
  dragEnterCount--
  if (dragEnterCount <= 0) {
    dragEnterCount = 0
    isDragging.value = false
  }
}
const onDrop = async (e: DragEvent) => {
  dragEnterCount = 0
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (!files?.length) return
  for (let i = 0; i < files.length; i++) {
    await addAndUploadFile(files[i])
  }
}
const selectedIndices = ref<Set<number>>(new Set())

const setMobileTab = (tab: 'history' | 'context' | 'notes') => {
  if (sidebarTab.value === tab) {
    sidebarTab.value = null
  } else {
    sidebarTab.value = tab
  }
  mobileMenuOpen.value = false
}

const toggleSelectMode = () => {
  selectMode.value = !selectMode.value
  if (!selectMode.value) selectedIndices.value = new Set()
}
const onToggleSelect = (index: number) => {
  const s = new Set(selectedIndices.value)
  if (s.has(index)) s.delete(index); else s.add(index)
  selectedIndices.value = s
}

const getFileIconClass = (filename?: string) => {
  if (!filename) return 'is-unknown'
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  if (['doc', 'docx'].includes(ext)) return 'is-doc'
  if (['xls', 'xlsx', 'csv'].includes(ext)) return 'is-excel'
  if (ext === 'pdf') return 'is-pdf'
  return 'is-unknown'
}

const getFileTypeLabel = (filename?: string) => {
  if (!filename) return '文件'
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  if (['doc', 'docx'].includes(ext)) return '文档'
  if (['xls', 'xlsx'].includes(ext)) return '表格'
  if (ext === 'pdf') return 'PDF'
  return ext.toUpperCase() || '文件'
}

const msgTypeMap: Record<string, string> = { image: 'image', video: 'file', meme: 'emotion', file: 'file' }

const sendToCenter = () => {
  const indices = [...selectedIndices.value].sort((a, b) => a - b)
  const items = indices.map((idx, i) => {
    const msg = chatHistory.value[idx]
    if (!msg) return null
    // 素材卡片 → 文件/图片消息
    if (msg.role === 'reference' && msg.messageType === 'rag_attachment') {
      const asset = msg.asset
      const mt = msgTypeMap[asset.material_type] || 'file'
      return {
        id: Date.now() + i,
        title: asset.title,
        msg_type: mt,
        description: `AI教练推荐素材${asset.reason ? ' — ' + asset.reason.substring(0, 60) : ''}`,
        contentJson: { asset_id: asset.material_id, asset_name: asset.source_filename, asset_url: asset.preview_url || '' },
        variablesJson: {},
      }
    }
    // 话术/知识卡片 → markdown 消息
    if (msg.role === 'reference' && msg.messageType === 'rag_reference') {
      const text = msg.snippet || msg.title
      if (!text?.trim()) return null
      return {
        id: Date.now() + i,
        title: msg.title,
        msg_type: 'markdown',
        description: `RAG 参考：${msg.content_kind === 'script' ? '话术' : '知识'}`,
        contentJson: { content: text },
        variablesJson: {},
      }
    }
    // 用户/AI 文本消息 → markdown
    if ('content' in msg && msg.content?.trim()) {
      return {
        id: Date.now() + i,
        title: msg.content.replace(/\n/g, ' ').substring(0, 40) || `消息 ${i + 1}`,
        msg_type: 'markdown',
        description: msg.role === 'user' ? '用户提问' : 'AI 教练回复',
        contentJson: { content: msg.content },
        variablesJson: {},
      }
    }
    return null
  }).filter(Boolean) as { id: number; title: string; msg_type: string; description: string; contentJson: Record<string, any>; variablesJson: Record<string, any> }[]

  if (!items.length) { ElMessage.warning('没有可发送的消息'); return }

  sessionStorage.setItem('send-center-prefill', JSON.stringify(items))
  selectMode.value = false
  selectedIndices.value = new Set()
  visible.value = false
  router.push('/send')
}

const sendAssetToCenter = (msg: AiChatMessage) => {
  if (msg.role !== 'reference' || msg.messageType !== 'rag_attachment') return
  const asset = msg.asset
  const msgType = msgTypeMap[asset.material_type] || 'file'
  const item = {
    id: Date.now(),
    title: asset.title,
    msg_type: msgType,
    description: `AI教练推荐素材${asset.reason ? ' — ' + asset.reason.substring(0, 60) : ''}`,
    contentJson: { asset_id: asset.material_id, asset_name: asset.source_filename, asset_url: asset.preview_url || '' },
    variablesJson: {},
  }
  sessionStorage.setItem('send-center-prefill', JSON.stringify([item]))
  visible.value = false
  router.push('/send')
}

const contextPreviewText = ref('')
const contextPreviewTokens = ref(0)
const contextPreviewChars = ref(0)
const contextPreviewLoading = ref(false)
const visibleDataGaps = ref<string[]>([])

const cacheSendBlocked = computed(() => {
  const status = props.profileCacheStatus
  if (!status || status.ready) return false
  return ['checking', 'scheduled', 'already_running', 'building', 'missing'].includes(status.status)
})

const cacheStatusText = computed(() => {
  const status = props.profileCacheStatus
  if (!status) return ''
  if (status.ready) {
    return status.source === 'l2_stale' ? '客户档案缓存可用，后台会继续刷新' : ''
  }
  if (['checking', 'scheduled', 'already_running', 'building'].includes(status.status)) {
    return '客户档案正在准备，稍后即可提问'
  }
  if (status.status === 'missing') {
    return '客户档案缓存未就绪，系统正在准备'
  }
  return status.message || ''
})

// RAG admin
const ragStatus = ref<{ rag_enabled: boolean; qdrant_available: boolean }>({ rag_enabled: false, qdrant_available: false })
const ragReindexing = ref(false)
const ragReindexResult = ref<Record<string, { indexed: number; skipped: number; errors: number }> | null>(null)

const loadRagStatus = async () => {
  try {
    ragStatus.value = await request.get('/v1/rag/status') as any
  } catch { /* ignore */ }
}

const triggerReindex = async () => {
  ragReindexing.value = true
  ragReindexResult.value = null
  try {
    const res: any = await request.post('/v1/rag/reindex', null, { params: { force: true } })
    ragReindexResult.value = res.results || null
    await loadRagStatus()
    ElMessage.success('知识库索引更新完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '索引更新失败')
  } finally {
    ragReindexing.value = false
  }
}

const moduleLabelMap: Record<string, string> = {
  basic_profile: '基础档案',
  safety_profile: '安全档案',
  goals_preferences: '目标与偏好',
  health_summary_7d: '健康摘要',
  body_comp_latest_30d: '近30天体成分',
  points_engagement_14d: '近14天积分与活跃',
  service_scope: '服务关系',
  habit_adherence_14d: '近14天习惯执行',
  plan_progress_14d: '近14天计划推进',
  learning_engagement_30d: '近30天学习吸收',
  service_issues: '用户阻碍',
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
  habit_adherence_14d: '#db2777',
  plan_progress_14d: '#0ea5e9',
  learning_engagement_30d: '#84cc16',
  service_issues: '#64748b',
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
  selectMode.value = false
  selectedIndices.value = new Set()
  visibleDataGaps.value = props.dataGaps.slice()
  startAutoDismiss()
  if (id) {
    loadAiConfig(id)
    loadSessionHistory(id)
  }
})

watch(sidebarTab, () => { mobileMenuOpen.value = false })

watch(visible, (v) => {
  if (!v) {
    selectMode.value = false
    selectedIndices.value = new Set()
  }
  if (v && props.customerId && !configLoaded.value) {
    loadAiConfig(props.customerId)
  }
  if (v && props.customerId) {
    loadSessionHistory(props.customerId)
  }
  if (v && isAdmin) {
    loadRagStatus()
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
    params.set('health_window_days', String(props.healthWindowDays || 7))
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
  if ((!msg && !pendingAttachments.value.length) || !props.customerId) return
  if (cacheSendBlocked.value) {
    ElMessage.warning('客户档案正在准备，稍后再问')
    return
  }
  // 等待附件上传完成（最多 3s），超时则只用已完成的附件
  if (uploadingAttachment.value) {
    const ok = await waitForUploads(3000)
    if (!ok) {
      const uploading = pendingAttachments.value.filter(a => a.uploading)
      if (uploading.length === pendingAttachments.value.length && !msg) return
      pendingAttachments.value = pendingAttachments.value.filter(a => !a.uploading)
      ElMessage.info('部分附件尚未上传完成，已跳过')
    }
  }
  input.value = ''
  visibleDataGaps.value = []
  const readyAttachments = pendingAttachments.value.filter(a => !a.uploading)
  const attachmentIds = readyAttachments.map(a => a.attachment_id).filter((id): id is string => typeof id === 'string' && !id.startsWith('temp_'))
  const attachments = [...readyAttachments]
  pendingAttachments.value = []
  await sendChat(props.customerId, msg || '请分析上传的附件', {
    healthWindowDays: props.healthWindowDays,
    attachmentIds,
    attachments,
  })
  await nextTick()
  forceScrollBottom()
}

const onRetryLast = async () => {
  if (!props.customerId || loading.value) return
  await retryLast(props.customerId)
  await nextTick()
  forceScrollBottom()
}

const askQuick = async (prompt: string) => {
  if (!props.customerId) return
  if (cacheSendBlocked.value) {
    ElMessage.warning('客户档案正在准备，稍后再问')
    return
  }
  visibleDataGaps.value = []
  await sendChat(props.customerId, prompt, {
    entryScene: 'quick_prompt',
    healthWindowDays: props.healthWindowDays,
  })
  await nextTick()
  forceScrollBottom()
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

const forceScrollBottom = () => {
  messageListRef.value?.forceScrollToBottom()
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

const feedbackDialogRef = ref<InstanceType<typeof AiCoachFeedbackDialog>>()
const feedbackTargetMsg = ref<any>(null)
const feedbackTargetQuestion = computed(() => {
  if (!feedbackTargetMsg.value) return ''
  const idx = chatHistory.value.findIndex((m: any) => m === feedbackTargetMsg.value)
  if (idx > 0) {
    for (let i = idx - 1; i >= 0; i--) {
      if (chatHistory.value[i].role === 'user') {
        return (chatHistory.value[i] as any).content
      }
    }
  }
  return ''
})

const onFeedback = async (msg: any, rating: 'like' | 'dislike') => {
  if (!props.customerId || !msg.messageId) return
  if (rating === 'like') {
    try {
      await submitFeedbackApi(props.customerId, msg.messageId, { rating: 'like' })
      ElMessage.success('感谢反馈')
    } catch {
      ElMessage.error('反馈提交失败')
    }
  } else {
    feedbackTargetMsg.value = msg
    feedbackDialogRef.value?.open(props.customerId, msg.messageId)
  }
}

const onFeedbackDialogSubmit = async (data: { reason_category: string; reason_text: string; expected_answer: string }) => {
  const msg = feedbackTargetMsg.value
  if (!props.customerId || !msg?.messageId) return
  try {
    await submitFeedbackApi(props.customerId, msg.messageId, {
      rating: 'dislike',
      reason_category: data.reason_category,
      reason_text: data.reason_text,
      expected_answer: data.expected_answer,
    })
    ElMessage.success('感谢反馈，我们会持续改进')
  } catch {
    ElMessage.error('反馈提交失败')
  }
}

const onRegenerate = async (msg: any) => {
  if (!props.customerId || !msg.messageId) return
  await regenerateApi(props.customerId, msg.messageId)
  await nextTick()
  forceScrollBottom()
}

const onQuote = (msg: any) => {
  setQuote(msg)
  // Focus the input
  const inputEl = document.querySelector('.ai-chat-input textarea') as HTMLElement
  inputEl?.focus()
}

const truncateText = (text: string, limit: number) => {
  if (!text) return ''
  return text.length > limit ? text.slice(0, limit) + '...' : text
}

const onSelectHistorySession = async (targetSessionId: string) => {
  if (!props.customerId) return
  const ok = await openHistorySession(props.customerId, targetSessionId)
  if (ok) {
    sidebarTab.value = null
    await nextTick()
    forceScrollBottom()
  }
}

const onCreateNewSession = () => {
  clearSession()
  sidebarTab.value = null
  ElMessage.success('已切换到新对话')
}

const onSearchSessions = (keyword: string) => {
  if (!props.customerId) return
  sessionSearchKeyword.value = keyword
  loadSessionHistory(props.customerId, { keyword, silent: true })
}

const onRenameSession = async (sessionId: string, title: string) => {
  if (!props.customerId) return
  const ok = await renameSession(props.customerId, sessionId, title)
  if (ok) {
    ElMessage.success('已重命名')
    loadSessionHistory(props.customerId, { silent: true })
  }
}

const onTogglePinSession = async (sessionId: string) => {
  if (!props.customerId) return
  const session = sessionHistory.value.find(s => s.session_id === sessionId)
  if (!session) return
  const ok = await togglePin(props.customerId, sessionId, !session.is_pinned)
  if (ok) {
    loadSessionHistory(props.customerId, { silent: true })
  }
}

const onDeleteSession = async (targetSessionId: string) => {
  if (!props.customerId) return
  const ok = await deleteSession(props.customerId, targetSessionId)
  if (ok) {
    ElMessage.success('对话已删除')
    if (targetSessionId === sessionId.value) clearSession()
    loadSessionHistory(props.customerId, { silent: true })
  }
}
</script>

<style>
@import './styles/aiCoachPanel.css';
</style>
