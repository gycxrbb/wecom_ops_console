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
              <div class="desc-expandable" @click="openDescDialog(idx)">
                <el-input
                  :model-value="article.description"
                  type="textarea"
                  :rows="2"
                  readonly
                  class="desc-expandable__input"
                  placeholder="点击编辑描述（可选）"
                />
                <div class="desc-expandable__hint">
                  <el-icon :size="14"><FullScreen /></el-icon>
                </div>
              </div>
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
                <el-button @click="openAssetPicker(idx)" class="cover-asset-btn">
                  <el-icon><Picture /></el-icon>
                  从素材库
                </el-button>
              </div>
              <div class="cover-hint">
                <p><strong>链接</strong>：填写你想要推送的内容的公网 https 网址（如文章链接）。</p>
                <p><strong>封面图</strong>：可直接输入公网 https 图片地址，也可从素材库选择（素材库已接入七牛云，均为公网 https 地址）。</p>
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

    <!-- 描述展开编辑弹窗 -->
    <el-dialog
      v-model="descDialogVisible"
      title="编辑描述"
      width="600px"
      :close-on-click-modal="false"
      append-to-body
      destroy-on-close
    >
      <el-input
        ref="descDialogInputRef"
        v-model="descDialogValue"
        type="textarea"
        :rows="10"
        maxlength="128"
        show-word-limit
        placeholder="输入图文描述（可选）"
      />
      <template #footer>
        <el-button @click="descDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmDescDialog">确定</el-button>
      </template>
    </el-dialog>

    <!-- 封面图素材选择器 -->
    <AssetPicker
      v-model:visible="assetPickerVisible"
      accept-type="image"
      @select="handleAssetSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Top, Bottom, Delete, Plus, FullScreen, Picture } from '@element-plus/icons-vue'
import AssetPicker from './AssetPicker.vue'

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

// ---- 描述展开编辑 ----
const descDialogVisible = ref(false)
const descDialogValue = ref('')
const descDialogIdx = ref(0)
const descDialogInputRef = ref<InstanceType<typeof import('element-plus')['ElInput']>>()

const openDescDialog = (idx: number) => {
  descDialogIdx.value = idx
  descDialogValue.value = articles.value[idx]?.description || ''
  descDialogVisible.value = true
  nextTick(() => descDialogInputRef.value?.focus())
}

const confirmDescDialog = () => {
  updateArticle(descDialogIdx.value, 'description', descDialogValue.value)
  descDialogVisible.value = false
}

// ---- 封面图素材选择 ----
const assetPickerVisible = ref(false)
const assetPickerIdx = ref(0)

const openAssetPicker = (idx: number) => {
  assetPickerIdx.value = idx
  assetPickerVisible.value = true
}

const handleAssetSelect = (asset: any) => {
  const url = asset.url || asset.preview_url || ''
  updateArticle(assetPickerIdx.value, 'picurl', url)
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
  display: flex;
  gap: 8px;
  align-items: center;
}
.cover-asset-btn {
  flex-shrink: 0;
}
.cover-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}
.cover-hint p {
  margin: 0 0 4px;
}
.cover-hint strong {
  color: var(--el-text-color-regular);
}

/* 描述展开编辑 */
.desc-expandable {
  position: relative;
  cursor: pointer;
  border-radius: 4px;
  overflow: hidden;
}
.desc-expandable:hover {
  box-shadow: 0 0 0 1px var(--el-color-primary-light-5);
}
.desc-expandable__input :deep(.el-textarea__inner) {
  cursor: pointer;
  padding-right: 28px;
}
.desc-expandable__hint {
  position: absolute;
  right: 6px;
  bottom: 6px;
  color: var(--el-text-color-placeholder);
  opacity: 0;
  transition: opacity 0.2s ease;
  pointer-events: none;
}
.desc-expandable:hover .desc-expandable__hint {
  opacity: 1;
}
</style>
