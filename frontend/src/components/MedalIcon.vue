<template>
  <span class="medal-icon">
    <svg viewBox="0 0 36 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <!-- 左缎带 -->
      <path d="M10 0L5 18L11 15L14 25L18 15L15 0L12.5 3L10 0Z"
            :fill="ribbonColor" fill-opacity="0.85" />
      <!-- 右缎带 -->
      <path d="M21 0L16 18L22 15L25 25L29 15L26 0L23.5 3L21 0Z"
            :fill="ribbonColor" fill-opacity="0.85" />
      <!-- 奖牌阴影 -->
      <circle cx="17" cy="28" r="10.5" :fill="shadowColor" />
      <!-- 奖牌外圈 -->
      <circle cx="17" cy="27" r="10.5" :fill="outerColor" />
      <!-- 奖牌内圈 -->
      <circle cx="17" cy="27" r="8" :fill="innerColor" />
      <!-- 高光 -->
      <ellipse cx="14.5" cy="24" rx="3.5" ry="2" fill="white" fill-opacity="0.4" />
      <!-- 数字 -->
      <text x="17" y="31" text-anchor="middle" fill="white"
            font-size="11" font-weight="800" font-family="system-ui, sans-serif">{{ rank }}</text>
    </svg>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ rank: 1 | 2 | 3 }>()

const palettes: Record<number, { outer: string; inner: string; ribbon: string; shadow: string }> = {
  1: { outer: '#D4A017', inner: '#FFD700', ribbon: '#FFD700', shadow: '#B8860B' },
  2: { outer: '#9CA3AF', inner: '#D1D5DB', ribbon: '#C0C0C0', shadow: '#6B7280' },
  3: { outer: '#B87333', inner: '#E8A862', ribbon: '#CD7F32', shadow: '#8B5E3C' },
}

const c = computed(() => palettes[props.rank] ?? palettes[3])
const outerColor = computed(() => c.value.outer)
const innerColor = computed(() => c.value.inner)
const ribbonColor = computed(() => c.value.ribbon)
const shadowColor = computed(() => c.value.shadow)
</script>

<style scoped>
.medal-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 32px;
}
.medal-icon svg {
  width: 100%;
  height: 100%;
}
</style>
