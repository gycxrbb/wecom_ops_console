import { ref, onMounted, onBeforeUnmount } from 'vue'

export function useMobile(breakpoint = 768) {
  const isMobile = ref(typeof window !== 'undefined' ? window.innerWidth <= breakpoint : false)
  const update = () => { isMobile.value = window.innerWidth <= breakpoint }
  onMounted(() => window.addEventListener('resize', update))
  onBeforeUnmount(() => window.removeEventListener('resize', update))
  return { isMobile }
}
