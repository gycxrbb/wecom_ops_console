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
          v-model:selectedTemplate="selectedTemplate"
          :isPreviewing="isPreviewing"
          :isSending="isSending"
          :isTestSending="isTestSending"
          @templateChange="handleTemplateChange"
          @msgTypeChange="handleMsgTypeChange"
          @contentUpdate="handleContentUpdate"
          @variablesUpdate="handleVariablesUpdate"
          @preview="handlePreview"
          @send="handleSend"
          @sendTest="handleTestSend"
        />
      </el-col>

      <!-- Right column: Preview & Timeline -->
      <el-col :xs="24" :lg="10">
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
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { useSendLogic } from './composables/useSendLogic'
import MessageForm from './components/MessageForm.vue'
import PreviewCard from './components/PreviewCard.vue'
import ScheduleCard from './components/ScheduleCard.vue'
import './styles/SendCenter.css'

const {
  groups,
  templates,
  selectedTemplate,
  previewData,
  previewError,
  form,
  scheduleForm,
  isPreviewing,
  isSending,
  isTestSending,
  isScheduling,
  handleMsgTypeChange,
  handleTemplateChange,
  handlePreview,
  handleSend,
  handleTestSend,
  handleSchedule
} = useSendLogic()

const handleContentUpdate = (val: Record<string, any>) => {
  form.contentJson = val
}

const handleVariablesUpdate = (val: Record<string, any>) => {
  form.variables = val
}
</script>
