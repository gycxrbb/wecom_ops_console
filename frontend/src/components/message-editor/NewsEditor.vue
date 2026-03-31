<template>
  <div class="news-editor">
    <div class="article-list">
      <el-collapse v-model="activeNames">
        <el-collapse-item
          v-for="(article, idx) in articles"
          :key="idx"
          :name="idx"
        >
          <template #title>
            <div class="article-title-bar">
              <span>图文卡片 {{ idx + 1 }}：{{ article.title || '(未填写标题)' }}</span>
              <div class="article-actions" @click.stop>
                <el-button
                  size="small"
                  :icon="Top"
                  circle
                  :disabled="idx === 0"
                  @click="moveArticle(idx, -1)"
                />
                <el-button
                  size="small"
                  :icon="Bottom"
                  circle
                  :disabled="idx === articles.length - 1"
                  @click="moveArticle(idx, 1)"
                />
                <el-button
                  size="small"
                  type="danger"
                  :icon="Delete"
                  circle
                  @click="removeArticle(idx)"
                />
              </div>
            </div>
          </template>

          <el-form label-width="80px" size="small">
            <el-form-item label="标题" required>
              <el-input
                :model-value="article.title"
                @update:model-value="updateArticle(idx, 'title', $event)"
                placeholder="图文标题"
                maxlength="64"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="描述">
              <el-input
                type="textarea"
                :rows="2"
                :model-value="article.description"
                @update:model-value="updateArticle(idx, 'description', $event)"
                placeholder="图文描述（可选）"
                maxlength="128"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="链接" required>
              <el-input
                :model-value="article.url"
                @update:model-value="updateArticle(idx, 'url', $event)"
                placeholder="https://example.com"
              />
            </el-form-item>
            <el-form-item label="封面图">
              <div class="cover-row">
                <el-input
                  :model-value="article.picurl"
                  @update:model-value="updateArticle(idx, 'picurl', $event)"
                  placeholder="图片URL 或从素材库选择"
                  style="flex: 1"
                />
                <el-button type="primary" @click="openAssetPicker(idx)">选择素材</el-button>
              </div>
              <el-image
                v-if="article.picurl"
                :src="article.picurl"
                fit="cover"
                style="width: 200px; height: 120px; margin-top: 8px; border-radius: 4px"
              />
            </el-form-item>
          </el-form>
        </el-collapse-item>
      </el-collapse>
    </div>

    <el-button
      type="primary"
      plain
      style="width: 100%; margin-top: 12px"
      :disabled="articles.length >= 8"
      @click="addArticle"
    >
      + 添加图文卡片 ({{ articles.length }}/8)
    </el-button>

    <AssetPicker
      v-model:visible="assetPickerVisible"
      accept-type="image"
      @select="handleAssetSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Top, Bottom, Delete } from '@element-plus/icons-vue'
import AssetPicker from './AssetPicker.vue'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const activeNames = ref<number[]>([])
const assetPickerVisible = ref(false)
const currentEditIdx = ref(0)

const articles = computed(() => props.modelValue.articles || [])

// 默认展开第一张
watch(() => articles.value.length, (len) => {
  if (len > 0 && activeNames.value.length === 0) {
    activeNames.value = [0]
  }
}, { immediate: true })

const emitUpdate = (newArticles: any[]) => {
  emit('update:modelValue', { ...props.modelValue, articles: newArticles })
}

const addArticle = () => {
  const newArticles = [...articles.value, { title: '', description: '', url: '', picurl: '' }]
  emitUpdate(newArticles)
  activeNames.value = [newArticles.length - 1]
}

const removeArticle = (idx: number) => {
  const newArticles = articles.value.filter((_: any, i: number) => i !== idx)
  emitUpdate(newArticles)
}

const moveArticle = (idx: number, direction: number) => {
  const newArticles = [...articles.value]
  const targetIdx = idx + direction
  const temp = newArticles[idx]
  newArticles[idx] = newArticles[targetIdx]
  newArticles[targetIdx] = temp
  emitUpdate(newArticles)
}

const updateArticle = (idx: number, field: string, value: string) => {
  const newArticles = articles.value.map((a: any, i: number) =>
    i === idx ? { ...a, [field]: value } : a
  )
  emitUpdate(newArticles)
}

const openAssetPicker = (idx: number) => {
  currentEditIdx.value = idx
  assetPickerVisible.value = true
}

const handleAssetSelect = (asset: any) => {
  updateArticle(currentEditIdx.value, 'picurl', asset.url || '')
}
</script>

<style scoped>
.news-editor {
  padding: 0;
}
.article-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 8px;
}
.article-actions {
  display: flex;
  gap: 4px;
}
.cover-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
</style>
