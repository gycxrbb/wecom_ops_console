<template>
  <div class="theme-toggle" @click="toggleTheme" ref="toggleRef">
    <div class="toggle-bg" ref="bgRef"></div>
    <div class="toggle-text" ref="textRef">{{ isDark ? "深色模式" : "浅色模式" }}</div>
    <div class="toggle-handle-container" ref="handleWrapperRef">
      <div class="toggle-handle" ref="handleRef"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from "vue"
import gsap from "gsap"

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(["update:modelValue", "change"])

const isDark = ref(props.modelValue)

const toggleRef = ref<HTMLElement | null>(null)
const bgRef = ref<HTMLElement | null>(null)
const textRef = ref<HTMLElement | null>(null)
const handleWrapperRef = ref<HTMLElement | null>(null)
const handleRef = ref<HTMLElement | null>(null)

const toggleTheme = () => {
  isDark.value = !isDark.value
  emit("update:modelValue", isDark.value)
  emit("change", isDark.value)
  animate()
}

const animate = () => {
  if (isDark.value) {
    gsap.to(handleWrapperRef.value, { x: 0, duration: 0.5, ease: "power2.out" })
    gsap.to(handleRef.value, {
      boxShadow: "inset 7px -3px 0 0 #00506A",
      backgroundColor: "transparent",
      duration: 0.5, 
      ease: "power2.out" 
    })
    gsap.to(bgRef.value, {
      background: "linear-gradient(90deg, #0ce2f7, #d6f5ff)",
      duration: 0.5
    })
    gsap.to(textRef.value, {
      x: 30,
      color: "#00506A",
      duration: 0.5
    })

  } else {
    gsap.to(handleWrapperRef.value, { x: 46, duration: 0.5, ease: "power2.out" })
    gsap.to(handleRef.value, {
      boxShadow: "inset 0 0 0 0 transparent",
      backgroundColor: "#ffffff",
      duration: 0.5,
      ease: "power2.out"
    })
    gsap.to(bgRef.value, {
      background: "linear-gradient(90deg, #008eb5, #003B52)",
      duration: 0.5
    })
    gsap.to(textRef.value, {
      x: 0,
      color: "#ffffff",
      duration: 0.5
    })
  }
}

watch(() => props.modelValue, (val) => {
  if (isDark.value !== val) {
    isDark.value = val
    animate()
  }
})

onMounted(() => {
  if (isDark.value) {
    gsap.set(handleWrapperRef.value, { x: 0 })
    gsap.set(handleRef.value, { boxShadow: "inset 7px -3px 0 0 #00506A", backgroundColor: "transparent" })
    gsap.set(bgRef.value, { background: "linear-gradient(90deg, #0ce2f7, #d6f5ff)" })
    gsap.set(textRef.value, { x: 30, color: "#00506A" })
  } else {
    gsap.set(handleWrapperRef.value, { x: 46 })
    gsap.set(handleRef.value, { boxShadow: "inset 0 0 0 0 transparent", backgroundColor: "#ffffff" })
    gsap.set(bgRef.value, { background: "linear-gradient(90deg, #008eb5, #003B52)" })
    gsap.set(textRef.value, { x: 0, color: "#ffffff" })
  }
})
</script>

<style scoped>
.theme-toggle {
  position: relative;
  width: 80px;
  height: 30px;
  border-radius: 15px;
  cursor: pointer;
  overflow: hidden;
  user-select: none;
  display: flex;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-right: 16px; /* spacing in header */
}

.toggle-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 20px;
  z-index: 1;
}

.toggle-text {
  position: absolute;
  z-index: 2;
  font-weight: 600;
  font-size: 10px;
  width: 50px;
  text-align: center;
  left: 0;
}

.toggle-handle-container {
  position: absolute;
  z-index: 3;
  left: 6px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.toggle-handle {
  width: 18px;
  height: 18px;
  border-radius: 50%;
}
</style>

