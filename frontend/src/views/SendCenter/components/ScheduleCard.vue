<template>
  <div class="card-panel">
    <div class="card-header">
      <el-icon color="#f59e0b"><Timer /></el-icon>
      <h3 class="card-header-title">定时任务</h3>
    </div>
    <div class="card-body">
      <el-form label-width="100px" label-position="left">
        <el-form-item label="任务标题" required>
          <el-input v-model="scheduleForm.title" placeholder="如: 每日早报推送" />
        </el-form-item>
        
        <el-form-item label="任务类型">
          <el-radio-group v-model="scheduleForm.schedule_type">
            <el-radio-button label="once">一次性</el-radio-button>
            <el-radio-button label="cron">周期性</el-radio-button>
          </el-radio-group>
        </el-form-item>
        
        <transition name="el-zoom-in-top" mode="out-in">
          <el-form-item label="执行时间" v-if="scheduleForm.schedule_type === 'once'" required>
            <el-date-picker 
              v-model="scheduleForm.run_at" 
              type="datetime" 
              placeholder="选择未来执行时间" 
              value-format="YYYY-MM-DDTHH:mm:ss"
              style="width: 100%" 
            />
          </el-form-item>
          <el-form-item label="Cron表达式" v-else required>
            <el-input v-model="scheduleForm.cron_expr" placeholder="如: 0 9 * * * (每天上午9点)" />
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px; line-height: 1.4;">
              Cron格式: 分 时 日 月 周。例如 0 12 * * * 表示每天中午12点触发。
            </div>
          </el-form-item>
        </transition>

        <div class="action-footer">
          <el-button type="success" @click="$emit('schedule')" :loading="isScheduling">
            <template #icon><el-icon><Clock /></el-icon></template>
            创建计划任务
          </el-button>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Timer, Clock } from '@element-plus/icons-vue'

defineProps({
  scheduleForm: { type: Object, required: true },
  isScheduling: { type: Boolean, default: false }
})

defineEmits(['schedule'])
</script>
