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
              <span class="article-label">图文卡片 {{ idx + 1 }}：{{ article.title || '(未填写标题)' }}</span>
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
              <div class="cover-input-area">
                <el-input
                  :model-value="article.picurl"
                  @update:model-value="updateArticle(idx, 'picurl', $event)"
                  placeholder="请输入公网可访问的 https:// 图片地址"
                  style="flex: 1"
                />
              </div>
              <div class="cover-hint">
                企业微信图文封面必须是公网可访问的 `http(s)` 图片地址，本地上传或素材库相对地址不能直接用于 `picurl`。
              </div>
              <el-image
                v-if="article.picurl"
                :src="article.picurl"
                fit="cover"
                style="width: 200px; height: 120px; margin-top: 8px; border-radius: 4px; border: 1px solid #e4e7ed"
              />
            </el-form-item>
          </el-form>
        </el-collapse-item>
      </el-collapse>
    </div>

    <el-button
      style="width: 100%; margin-top: 12px"
      :disabled="articles.length >= 8"
      @click="addArticle"
    >
      <el-icon><Plus /></el-icon>
      添加图文卡片 ({{ articles.length }}/8)
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Top, Bottom, Delete, Plus } from '@element-plus/icons-vue'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const activeNames = ref<number[]>([])

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
.article-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.article-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
.cover-input-area {
  width: 100%;
}
.cover-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>
