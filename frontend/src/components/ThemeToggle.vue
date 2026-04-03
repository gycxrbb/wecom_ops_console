<template>
  <div class="theme-toggle-wrapper" @click="toggleTheme" :class="{ 'is-dark': isDark }">
    <div class="theme-toggle-bg" ref="bgRef"></div>
    
    <!-- 状态文字 -->
    <div class="theme-toggle-text-container">
      <span ref="textLightRef" class="toggle-text text-light">浅色</span>
      <span ref="textDarkRef" class="toggle-text text-dark">深色</span>
    </div>

    <!-- 滑块与内部图标 -->
    <div class="theme-toggle-thumb" ref="thumbRef">
      <!-- 太阳图标 (Light) -->
      <svg ref="sunRef" class="thumb-icon sun-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
      <svg ref="moonRef" class="thumb-icon moon-icon" viewBox="0 0 24 24" fill="currentColor">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue"
import gsap from "gsap"

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(["update:modelValue", "change"])
const isDark = ref(props.modelValue)

// Refs for animation
const bgRef = ref<HTMLElement | null>(null)
const thumbRef = ref<HTMLElement | null>(null)
const sunRef = ref<HTMLElement | null>(null)
const moonRef = ref<HTMLElement | null>(null)
const textLightRef = ref<HTMLElement | null>(null)
const textDarkRef = ref<HTMLElement | null>(null)

const animate = (immediate = false) => {
  if (!bgRef.value || !thumbRef.value || !sunRef.value || !moonRef.value || !textLightRef.value || !textDarkRef.value) {
    return
  }
  const tl = gsap.timeline({ defaults: { duration: immediate ? 0 : 0.4, ease: "back.out(1.2)" } })

  if (isDark.value) {
    // 深色模式动画
    tl.to(thumbRef.value, { x: 44 }, 0)
      .to(sunRef.value, { opacity: 0, rotate: -90, scale: 0.5, duration: immediate ? 0 : 0.25, ease: "power2.in" }, 0)
      .to(moonRef.value, { opacity: 1, rotate: 0, scale: 1, duration: immediate ? 0 : 0.25, ease: "power2.out" }, 0.1)
      .to(bgRef.value, { background: "linear-gradient(135deg, #1e293b, #0f172a)" }, 0)
      .to(textLightRef.value, { opacity: 0, x: -10 }, 0)
      .to(textDarkRef.value, { opacity: 1, x: 0 }, 0.1)
  } else {
    // 浅色模式动画
    tl.to(thumbRef.value, { x: 0 }, 0)
      .to(moonRef.value, { opacity: 0, rotate: 90, scale: 0.5, duration: immediate ? 0 : 0.25, ease: "power2.in" }, 0)
      .to(sunRef.value, { opacity: 1, rotate: 0, scale: 1, duration: immediate ? 0 : 0.25, ease: "power2.out" }, 0.1)
      .to(bgRef.value, { background: "linear-gradient(135deg, #e0f2fe, #bae6fd)" }, 0)
      .to(textDarkRef.value, { opacity: 0, x: 10 }, 0)
      .to(textLightRef.value, { opacity: 1, x: 0 }, 0.1)
  }
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  emit("update:modelValue", isDark.value)
  emit("change", isDark.value)
  animate()
}

watch(() => props.modelValue, (val) => {
  if (isDark.value !== val) {
    isDark.value = val
    animate()
  }
})

onMounted(() => {
  animate(true) // 初始化状态，不带延迟
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
}

.text-light {
  right: 10px; /* 浅色模式时右边显示文字 */
  color: #0c4a6e;
}

.text-dark {
  left: 12px; /* 深色模式时左边显示文字 */
  color: #f8fafc;
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
}

.is-dark .theme-toggle-thumb {
  background: #1e293b;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
}

.thumb-icon {
  position: absolute;
  width: 14px;
  height: 14px;
}

.sun-icon {
  color: #f59e0b;
}

.moon-icon {
  color: #fbbf24;
}
</style>
