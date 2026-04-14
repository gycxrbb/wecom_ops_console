<template>
  <div class="send-center-container">
    <div class="page-header">
      <h2 class="page-title">发送中心</h2>
      <div class="page-desc">配置消息内容并选择群组进行即时推送或创建定时任务。</div>
    </div>

    <el-row :gutter="24">
      <!-- Left column: Message Compose -->
      <el-col :xs="24" :lg="14">
        <MessageForm
          :form="form"
          :groups="groups"
          :templates="templates"
          :selectedContentSource="selectedContentSource"
          :selectedContentId="selectedContentId"
          :selectedContentLabel="selectedContentLabel"
          :isPreviewing="isPreviewing"
          :isSending="isSending"
          :isTestSending="isTestSending"
          :isBatchMode="isBatchMode"
          :batchQueue="batchQueue"
          :isBatchSending="isBatchSending"
          :batchProgress="batchProgress"
          :activeBatchIndex="activeBatchIndex"
          :notifyEnabled="notifyEnabled"
          :notifyCustomText="notifyCustomText"
          :notifyAutoText="notifyAutoText"
          :notifySendStatus="notifySendStatus"
          :manualQueue="manualQueue"
          :isManualSending="isManualSending"
          @contentSelect="handleContentSelect"
          @clearContent="handleClearContent"
          @msgTypeChange="handleMsgTypeChange"
          @contentUpdate="handleContentUpdate"
          @variablesUpdate="handleVariablesUpdate"
          @preview="handlePreview"
          @send="handleSend"
          @sendTest="handleTestSend"
          @batchSelect="handleBatchSelect"
          @batchSend="handleBatchSend"
          @removeBatchItem="handleRemoveBatchItem"
          @clearBatch="clearBatch"
          @cancelBatchSend="cancelBatchSend"
          @selectBatchItem="selectBatchItem"
          @toggleRemark="toggleBatchItemRemark"
          @updateRemark="updateBatchItemRemark"
          @update:notifyEnabled="notifyEnabled = $event"
          @update:notifyCustomText="notifyCustomText = $event"
          @addToQueue="addToManualQueue"
          @removeQueueItem="removeFromManualQueue"
          @clearQueue="clearManualQueue"
          @sendQueue="handleSendQueue"
        />
      </el-col>

      <!-- Right column: Preview & Timeline -->
      <el-col :xs="24" :lg="10">
        <!-- 单条模式：常规预览和定时 -->
        <template v-if="!isBatchMode">
          <PreviewCard
            :previewData="previewData"
            :previewError="previewError"
            :msgType="form.msg_type"
            :isPreviewing="isPreviewing"
            :contentJson="form.contentJson"
          />
          <ScheduleCard
            :scheduleForm="scheduleForm"
            :isScheduling="isScheduling"
            @schedule="handleSchedule"
          />
        </template>

        <!-- 批量模式：选中项的编辑/预览/定时 -->
        <template v-else-if="activeBatchItem">
          <div class="batch-detail-scroll">
            <div class="card-panel">
              <div class="card-header">
                <div class="card-header-icon card-header-icon--blue">
                  <el-icon :size="16"><View /></el-icon>
                </div>
                <h3 class="card-header-title">{{ activeBatchItem.title }}</h3>
                <el-tag size="small" :type="tagTypeByMsgType(activeBatchItem.msg_type)">{{ msgTypeLabel(activeBatchItem.msg_type) }}</el-tag>
              </div>
              <div class="card-body">
                <MessageEditor
                  :model-value="activeBatchItem.contentJson"
                  @update:model-value="handleBatchItemContentUpdate"
                  :msg-type="activeBatchItem.msg_type"
                  :variables="activeBatchItem.variablesJson"
                  @update:variables="handleBatchItemVariablesUpdate"
                  :show-variables="true"
                  style="width: 100%"
                />
              </div>
            </div>

            <PreviewCard
              :previewData="batchItemPreviewData"
              :previewError="batchItemPreviewError"
              :msgType="activeBatchItem.msg_type"
              :isPreviewing="isBatchItemPreviewing"
              :contentJson="activeBatchItem.contentJson"
            />

            <div class="card-panel">
              <div class="card-header">
                <div class="card-header-icon card-header-icon--purple">
                  <el-icon :size="16"><Position /></el-icon>
                </div>
                <h3 class="card-header-title">操作</h3>
              </div>
              <div class="card-body">
                <div class="batch-item-actions">
                  <el-button @click="handleBatchItemPreview" :loading="isBatchItemPreviewing">
                    <template #icon><el-icon><View /></el-icon></template>
                    预览此条
                  </el-button>
                  <el-button type="primary" @click="handleBatchItemSend" :disabled="isBatchSending">
                    <template #icon><el-icon><Position /></el-icon></template>
                    单独发送此条
                  </el-button>
                </div>
              </div>
            </div>

            <ScheduleCard
              :scheduleForm="scheduleForm"
              :isScheduling="isScheduling"
              @schedule="handleBatchItemSchedule"
            />
          </div>
        </template>

        <!-- 批量模式但未选中项 -->
        <template v-else>
          <div class="card-panel">
            <div class="card-body">
              <div class="batch-empty-hint">
                <span>点击左侧队列中的条目查看内容、预览或创建定时任务</span>
              </div>
            </div>
          </div>
        </template>
      </el-col>
    </el-row>
  </div>
</template>

<script lang="ts">
export default { name: 'SendCenter' }
</script>
<script setup lang="ts">
import { useSendLogic } from './composables/useSendLogic'
import MessageForm from './components/MessageForm.vue'
import MessageEditor from '@/components/message-editor/index.vue'
import PreviewCard from './components/PreviewCard.vue'
import ScheduleCard from './components/ScheduleCard.vue'
import { ElMessage } from 'element-plus'
import { View, Position } from '@element-plus/icons-vue'
import { msgTypeLabel } from '@/views/Templates/composables/useTemplates'
import request from '@/utils/request'
import './styles/SendCenter.css'

const {
  groups,
  templates,
  selectedContentSource,
  selectedContentId,
  selectedContentLabel,
  previewData,
  previewError,
  form,
  scheduleForm,
  isPreviewing,
  isSending,
  isTestSending,
  isScheduling,
  // 批量发送
  batchQueue,
  notifyEnabled,
  notifyCustomText,
  notifyAutoText,
  notifySendStatus,
  isBatchMode,
  isBatchSending,
  batchProgress,
  activeBatchIndex,
  activeBatchItem,
  batchItemPreviewData,
  batchItemPreviewError,
  isBatchItemPreviewing,
  selectBatchItem,
  handleBatchSelect,
  removeBatchItem,
  toggleBatchItemRemark,
  updateBatchItemRemark,
  clearBatch,
  cancelBatchSend,
  handleBatchSend,
  handleBatchItemContentUpdate,
  handleBatchItemVariablesUpdate,
  handleBatchItemPreview,
  handleBatchItemSchedule,
  // 单条操作
  handleMsgTypeChange,
  handleContentSelect,
  handleClearContent,
  handlePreview,
  handleSend,
  handleTestSend,
  handleSchedule,
  // 手动队列
  manualQueue,
  isManualSending,
  addToManualQueue,
  removeFromManualQueue,
  clearManualQueue,
  sendManualQueue
} = useSendLogic()

const handleContentUpdate = (val: Record<string, any>) => {
  form.contentJson = val
}

const handleVariablesUpdate = (val: Record<string, any>) => {
  form.variables = val
}

const handleSendQueue = (testGroupOnly = false) => {
  sendManualQueue(testGroupOnly)
}

const handleRemoveBatchItem = (index: number) => {
  removeBatchItem(index)
  if (activeBatchIndex.value != null) {
    if (batchQueue.value.length === 0) {
      selectBatchItem(null)
    } else if (activeBatchIndex.value >= batchQueue.value.length) {
      selectBatchItem(batchQueue.value.length - 1)
    }
  }
}

const tagTypeByMsgType = (msgType: string) => {
  const map: Record<string, string> = {
    text: '', markdown: 'success', image: 'warning', emotion: 'warning', news: 'danger', file: 'info', voice: 'info', template_card: ''
  }
  return map[msgType] || ''
}

const handleBatchItemSend = async () => {
  const item = activeBatchItem.value
  if (!item) return
  if (form.groups.length === 0) {
    return ElMessage.warning('请至少选择一个群组')
  }
  try {
    const res = await request.post('/v1/send', {
      group_ids: form.groups,
      msg_type: item.msg_type,
      content_json: item.contentJson,
      variables_json: item.variablesJson,
      test_group_only: false
    })
    const failed = Array.isArray(res?.results) ? res.results.filter((r: any) => r?.success === false) : []
    if (failed.length > 0) {
      ElMessage.error(`发送失败：${failed[0]?.response || '未知错误'}`)
      if (activeBatchIndex.value === -1) notifySendStatus.value = 'failed'
      else item.status = 'failed'
    } else {
      ElMessage.success('发送成功')
      if (activeBatchIndex.value === -1) notifySendStatus.value = 'success'
      else item.status = 'success'
    }
  } catch (e: any) {
    ElMessage.error('发送失败: ' + String(e))
    if (activeBatchIndex.value === -1) notifySendStatus.value = 'failed'
    else item.status = 'failed'
  }
}
</script>

<style scoped>
.batch-detail-scroll {
  max-height: calc(100vh - 160px);
  overflow-y: auto;
  overflow-x: auto;
  padding-right: 4px;
}

.batch-item-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.batch-empty-hint {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 14px;
}

.card-header-icon--blue {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
}

.card-header-icon--purple {
  background: rgba(144, 116, 255, 0.1);
  color: #9074ff;
}

@media (max-width: 767px) {
  .batch-detail-scroll {
    max-height: calc(100vh - 120px);
  }
}
</style>
