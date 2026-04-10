<template>
  <div class="theme-toggle-wrapper" @click="toggleTheme" :class="{ 'is-dark': isDark }">
    <div class="theme-toggle-bg"></div>

    <!-- 状态文字 -->
    <div class="theme-toggle-text-container">
      <span class="toggle-text text-light" :class="{ 'is-hidden': isDark }">浅色</span>
      <span class="toggle-text text-dark" :class="{ 'is-hidden': !isDark }">深色</span>
    </div>

    <!-- 滑块与内部图标 -->
    <div class="theme-toggle-thumb" :class="{ 'is-dark-thumb': isDark }">
      <!-- 太阳图标 (Light) -->
      <svg class="thumb-icon sun-icon" :class="{ 'icon-hidden': isDark }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="5" />
        <line x1="12" y1="1" x2="12" y2="3" />
        <line x1="12" y1="21" x2="12" y2="23" />
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
        <line x1="1" y1="12" x2="3" y2="12" />
        <line x1="21" y1="12" x2="23" y2="12" />
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
      </svg>

      <!-- 月亮图标 (Dark) -->
      <svg class="thumb-icon moon-icon" :class="{ 'icon-hidden': !isDark }" viewBox="0 0 24 24" fill="currentColor">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(["update:modelValue", "change"])
const isDark = ref(props.modelValue)

const toggleTheme = () => {
  isDark.value = !isDark.value
  emit("update:modelValue", isDark.value)
  emit("change", isDark.value)
}

watch(() => props.modelValue, (val) => {
  if (isDark.value !== val) {
    isDark.value = val
  }
})
</script>

<style scoped>
.theme-toggle-wrapper {
  position: relative;
  width: 76px;
  height: 32px;
  border-radius: 16px;
  cursor: pointer;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  user-select: none;
  margin-right: 16px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: border-color 0.3s, box-shadow 0.3s;
}

.is-dark.theme-toggle-wrapper {
  border-color: rgba(0, 0, 0, 0.3);
  box-shadow: inset 0 1px 4px rgba(0, 0, 0, 0.4);
}

.theme-toggle-bg {
  position: absolute;
  inset: 0;
  border-radius: 16px;
  z-index: 1;
  background: linear-gradient(135deg, #e0f2fe, #bae6fd);
  transition: background 0.4s ease;
}

.is-dark .theme-toggle-bg {
  background: linear-gradient(135deg, #1e293b, #0f172a);
}

.theme-toggle-text-container {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 600;
  pointer-events: none;
}

.toggle-text {
  position: absolute;
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.text-light {
  right: 10px;
  color: #0c4a6e;
  opacity: 1;
  transform: translateX(0);
}

.text-dark {
  left: 12px;
  color: #f8fafc;
  opacity: 0;
  transform: translateX(10px);
}

.text-light.is-hidden {
  opacity: 0;
  transform: translateX(-10px);
}

.text-dark.is-hidden {
  opacity: 0;
  transform: translateX(10px);
}

.text-dark:not(.is-hidden) {
  opacity: 1;
  transform: translateX(0);
}

.text-light:not(.is-hidden) {
  opacity: 1;
  transform: translateX(0);
}

.theme-toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: white;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  transition: transform 0.4s cubic-bezier(0.68, -0.2, 0.27, 1.2),
              background 0.3s ease,
              box-shadow 0.3s ease;
}

.theme-toggle-thumb.is-dark-thumb {
  transform: translateX(44px);
  background: #1e293b;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
}

.thumb-icon {
  position: absolute;
  width: 14px;
  height: 14px;
  transition: opacity 0.25s ease, transform 0.3s ease;
}

.sun-icon {
  color: #f59e0b;
  opacity: 1;
  transform: rotate(0deg) scale(1);
}

.moon-icon {
  color: #fbbf24;
  opacity: 0;
  transform: rotate(90deg) scale(0.5);
}

.icon-hidden {
  opacity: 0;
}

.sun-icon.icon-hidden {
  opacity: 0;
  transform: rotate(-90deg) scale(0.5);
}

.moon-icon:not(.icon-hidden) {
  opacity: 1;
  transform: rotate(0deg) scale(1);
}

.sun-icon:not(.icon-hidden) {
  opacity: 1;
  transform: rotate(0deg) scale(1);
}
</style>
