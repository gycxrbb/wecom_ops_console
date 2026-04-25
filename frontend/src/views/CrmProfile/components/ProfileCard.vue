<template>
  <div class="crm-card" :class="{ 'crm-card--danger': variant === 'danger', 'crm-card--empty': card?.status !== 'ok' && card?.status !== 'partial' }">
    <div class="crm-card__header">
      <div class="crm-card__header-left">
        <span class="crm-card-kicker" :class="{ 'crm-card-kicker--danger': variant === 'danger' }">
          {{ kicker }}
        </span>
        <h3 class="crm-card__title">{{ title }}</h3>
      </div>
      <div class="crm-card__header-right">
        <slot name="header-extra" :card="card" />
        <el-tag v-if="card?.status === 'empty'" type="info" size="small" round>无数据</el-tag>
        <el-tag v-else-if="card?.status === 'error'" type="danger" size="small" round>加载失败</el-tag>
        <el-tag v-else-if="card?.status === 'timeout'" type="warning" size="small" round>超时</el-tag>
      </div>
    </div>

    <div v-if="card?.status === 'ok' || card?.status === 'partial'">
      <slot :payload="card?.payload || {}" />
    </div>
    <div v-else-if="card?.status === 'empty'" class="crm-card-empty">暂无数据</div>
    <div v-else-if="card?.status === 'error'" class="crm-card-empty">数据加载失败</div>
    <div v-else-if="card?.status === 'timeout'" class="crm-card-empty">查询超时</div>

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
