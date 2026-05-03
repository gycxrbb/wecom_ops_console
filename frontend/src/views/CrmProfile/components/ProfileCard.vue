<template>
  <div class="crm-card" :class="{ 'crm-card--danger': variant === 'danger', 'crm-card--empty': card?.status !== 'ok' && card?.status !== 'partial' }">
    <div class="crm-card__header">
      <div class="crm-card__header-left">
        <slot name="title-icon" />
        <div class="crm-card__title-stack">
          <span v-if="kicker" class="crm-card-kicker" :class="{ 'crm-card-kicker--danger': variant === 'danger' }">
            {{ kicker }}
          </span>
          <h3 class="crm-card__title">{{ title }}</h3>
        </div>
      </div>
      <div class="crm-card__header-right">
        <slot name="header-extra" :card="card" />
        <el-tag v-if="card?.status === 'empty'" type="info" size="small" round>无数据</el-tag>
        <el-tag v-else-if="card?.status === 'error'" type="danger" size="small" round>加载失败</el-tag>
        <el-tag v-else-if="card?.status === 'timeout'" type="warning" size="small" round>超时</el-tag>
      </div>
    </div>

    <div v-if="card?.status === 'ok' || card?.status === 'partial'" class="crm-card__body">
      <slot :payload="card?.payload || {}" />
    </div>
    <div v-else-if="card?.status === 'empty'">
      <slot name="empty">
        <div class="crm-card-empty">暂无数据</div>
      </slot>
    </div>
    <div v-else-if="card?.status === 'error'" class="crm-card-empty">数据加载失败</div>
    <div v-else-if="card?.status === 'timeout'" class="crm-card-empty">查询超时</div>

    <div v-if="$slots.footer" class="crm-card__footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  kicker?: string
  card?: {
    key: string
    status: string
    payload: Record<string, any>
    freshness: string | null
    warnings: string[]
  }
  variant?: 'default' | 'danger'
}>()
</script>

<style scoped>
.crm-card__header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 0 1 auto;
}

.crm-card__title-stack {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  line-height: 1.3;
}

.crm-card__body {
  flex: 1;
  min-height: 0;
  overflow-y: scroll;
  margin: 0 -6px;
  padding: 0 6px;
}
.crm-card__body::-webkit-scrollbar {
  width: 5px;
}
.crm-card__body::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.04);
  border-radius: 4px;
}
.crm-card__body::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.18);
  border-radius: 4px;
}
.crm-card__body::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.28);
}

.crm-card__footer {
  flex-shrink: 0;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color, #f3f4f6);
}
</style>
