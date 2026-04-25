<template>
  <div class="sop-stat-card" :class="`sop-stat-card--${color}`">
    <span class="sop-stat-card__value">{{ value }}</span>
    <span class="sop-stat-card__label">{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  value: number | string
  color: 'green' | 'orange' | 'red' | 'blue'
}>()
</script>
