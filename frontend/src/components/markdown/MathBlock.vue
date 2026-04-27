<template>
  <div v-if="renderedHtml" class="md-math-block" v-html="renderedHtml" />
  <pre v-else class="md-math-fallback">{{ code }}</pre>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = defineProps<{
  code: string
}>()

let katexPromise: Promise<any> | null = null
const renderedHtml = ref('')

function getKatex() {
  if (!katexPromise) {
    katexPromise = import('katex')
  }
  return katexPromise
}

onMounted(async () => {
  try {
    const katex = await getKatex()
    renderedHtml.value = katex.default.renderToString(props.code, {
      displayMode: true,
      throwOnError: false,
    })
  } catch {
    // fallback to plain <pre>
  }
})
</script>
