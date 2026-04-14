<template>
  <div class="template-card-editor">
    <el-form label-width="90px" size="small">
      <div class="template-card-guide">
        <div class="template-card-guide__title">模板卡片快速上手</div>
        <div class="template-card-guide__desc">
          文本通知适合提醒、截止、任务确认；图文展示适合运营拿一张配图配一段说明直接复用。
        </div>
        <div class="template-card-guide__actions">
          <el-button size="small" @click="applyPreset('text_notice')">套用完整文本通知示例</el-button>
          <el-button size="small" @click="applyPreset('news_notice')">套用完整图文展示示例</el-button>
        </div>
      </div>

      <el-form-item label="卡片类型">
        <el-select :model-value="cardType" @update:model-value="changeCardType">
          <el-option label="文本通知" value="text_notice" />
          <el-option label="图文展示" value="news_notice" />
          <el-option label="按钮交互" value="button_interaction" />
          <el-option label="投票选择" value="vote_interaction" />
        </el-select>
      </el-form-item>

      <el-form-item label="主标题">
        <el-input
          :model-value="mainTitle"
          @update:model-value="updateNested('main_title', 'title', $event)"
          placeholder="卡片主标题"
        />
      </el-form-item>

      <el-form-item label="强调内容">
        <div style="display: flex; gap: 8px; width: 100%">
          <el-input
            :model-value="emphasisTitle"
            @update:model-value="updateNested('emphasis_content', 'title', $event)"
            placeholder="数字/关键信息"
            style="flex: 1"
          />
          <el-input
            :model-value="emphasisDesc"
            @update:model-value="updateNested('emphasis_content', 'desc', $event)"
            placeholder="说明文字"
            style="flex: 1"
          />
        </div>
      </el-form-item>

      <el-form-item label="副标题">
        <el-input
          :model-value="subTitleText"
          @update:model-value="updateField('sub_title_text', $event)"
          placeholder="卡片副标题"
        />
      </el-form-item>

      <el-form-item v-if="cardType === 'news_notice'" label="卡片大图">
        <el-input
          :model-value="cardImageUrl"
          @update:model-value="updateCardImageUrl"
          placeholder="https://example.com/card-cover.png"
        />
      </el-form-item>

      <el-form-item v-if="cardType === 'news_notice'" label="图文区">
        <div class="image-text-area">
          <el-input
            :model-value="imageTextTitle"
            @update:model-value="updateNested('image_text_area', 'title', $event)"
            placeholder="图文标题"
          />
          <el-input
            :model-value="imageTextDesc"
            @update:model-value="updateNested('image_text_area', 'desc', $event)"
            type="textarea"
            :rows="3"
            placeholder="图文说明，适合告诉运营同学这张卡要怎么用"
          />
          <el-input
            :model-value="imageTextImageUrl"
            @update:model-value="updateNested('image_text_area', 'image_url', $event)"
            placeholder="图文区配图 https://example.com/thumb.png"
          />
          <el-input
            :model-value="imageTextUrl"
            @update:model-value="updateNested('image_text_area', 'url', $event)"
            placeholder="点击图文区后的跳转链接"
          />
        </div>
      </el-form-item>

      <!-- 水平内容列表 -->
      <el-form-item label="内容列表">
        <div class="horizontal-list">
          <div v-for="(item, idx) in horizontalList" :key="idx" class="horizontal-item">
            <el-input
              :model-value="item.keyname"
              @update:model-value="updateHorizontalItem(idx, 'keyname', $event)"
              placeholder="标签名"
              style="width: 100px"
            />
            <el-input
              :model-value="item.value"
              @update:model-value="updateHorizontalItem(idx, 'value', $event)"
              placeholder="值"
              style="flex: 1"
            />
            <el-button
              type="danger"
              :icon="Delete"
              circle
              size="small"
              @click="removeHorizontalItem(idx)"
            />
          </div>
          <el-button size="small" @click="addHorizontalItem">+ 添加一行</el-button>
        </div>
      </el-form-item>

      <!-- 跳转链接 -->
      <el-form-item label="跳转链接">
        <el-input
          :model-value="cardUrl"
          @update:model-value="updateNested('card_action', 'url', $event)"
          placeholder="https://example.com"
        />
      </el-form-item>

      <!-- 按钮列表 -->
      <el-form-item label="按钮">
        <div class="button-list">
          <div v-for="(btn, idx) in buttonList" :key="idx" class="button-item">
            <el-input
              :model-value="btn.text"
              @update:model-value="updateButton(idx, 'text', $event)"
              placeholder="按钮文字"
              style="width: 120px"
            />
            <el-select
              :model-value="btn.style || 1"
              @update:model-value="updateButton(idx, 'style', $event)"
              style="width: 100px"
            >
              <el-option :label="s.label" :value="s.value" v-for="s in btnStyles" :key="s.value" />
            </el-select>
            <el-input
              :model-value="btn.url"
              @update:model-value="updateButton(idx, 'url', $event)"
              placeholder="链接 (可选)"
              style="flex: 1"
            />
            <el-button
              type="danger"
              :icon="Delete"
              circle
              size="small"
              @click="removeButton(idx)"
            />
          </div>
          <el-button size="small" @click="addButton">+ 添加按钮</el-button>
        </div>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Delete } from '@element-plus/icons-vue'
import { createTemplateCardExample } from './templateCardPresets'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const btnStyles = [
  { label: '蓝色', value: 1 },
  { label: '红色', value: 2 },
  { label: '绿色', value: 3 },
  { label: '灰色', value: 4 },
]

const cardContent = computed(() => props.modelValue.template_card || props.modelValue || {})
const cardType = computed(() => cardContent.value.card_type || 'text_notice')
const mainTitle = computed(() => cardContent.value.main_title?.title || '')
const emphasisTitle = computed(() => cardContent.value.emphasis_content?.title || '')
const emphasisDesc = computed(() => cardContent.value.emphasis_content?.desc || '')
const subTitleText = computed(() => cardContent.value.sub_title_text || '')
const horizontalList = computed(() => cardContent.value.horizontal_content_list || [])
const cardUrl = computed(() => cardContent.value.card_action?.url || '')
const buttonList = computed(() => cardContent.value.button_list || [])
const cardImageUrl = computed(() => cardContent.value.card_image?.url || '')
const imageTextTitle = computed(() => cardContent.value.image_text_area?.title || '')
const imageTextDesc = computed(() => cardContent.value.image_text_area?.desc || '')
const imageTextImageUrl = computed(() => cardContent.value.image_text_area?.image_url || '')
const imageTextUrl = computed(() => cardContent.value.image_text_area?.url || '')

const emitUpdate = (partial: Record<string, any>) => {
  emit('update:modelValue', { template_card: { ...cardContent.value, ...partial } })
}

const updateField = (field: string, value: any) => {
  emitUpdate({ [field]: value })
}

const updateNested = (parent: string, child: string, value: any) => {
  emitUpdate({ [parent]: { ...(cardContent.value[parent] || {}), [child]: value } })
}

const applyPreset = (type: 'text_notice' | 'news_notice') => {
  emit('update:modelValue', createTemplateCardExample(type))
}

const changeCardType = (val: string) => {
  if (val === 'text_notice' || val === 'news_notice') {
    emit('update:modelValue', createTemplateCardExample(val))
    return
  }
  emitUpdate({ card_type: val })
}

const updateCardImageUrl = (value: string) => {
  emitUpdate({
    card_image: {
      ...(cardContent.value.card_image || {}),
      url: value,
      aspect_ratio: cardContent.value.card_image?.aspect_ratio || 1.3,
    },
  })
}

// 水平列表操作
const addHorizontalItem = () => {
  const list = [...horizontalList.value, { keyname: '', value: '' }]
  emitUpdate({ horizontal_content_list: list })
}

const removeHorizontalItem = (idx: number) => {
  const list = horizontalList.value.filter((_: any, i: number) => i !== idx)
  emitUpdate({ horizontal_content_list: list })
}

const updateHorizontalItem = (idx: number, field: string, value: string) => {
  const list = horizontalList.value.map((item: any, i: number) =>
    i === idx ? { ...item, [field]: value } : item
  )
  emitUpdate({ horizontal_content_list: list })
}

// 按钮操作
const addButton = () => {
  const list = [...buttonList.value, { text: '', style: 1, url: '' }]
  emitUpdate({ button_list: list })
}

const removeButton = (idx: number) => {
  const list = buttonList.value.filter((_: any, i: number) => i !== idx)
  emitUpdate({ button_list: list })
}

const updateButton = (idx: number, field: string, value: any) => {
  const list = buttonList.value.map((item: any, i: number) =>
    i === idx ? { ...item, [field]: value } : item
  )
  emitUpdate({ button_list: list })
}
</script>

<style scoped>
.template-card-editor {
  padding: 0;
}
.template-card-guide {
  margin-bottom: 16px;
  padding: 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(14, 165, 233, 0.05));
  border: 1px solid rgba(37, 99, 235, 0.12);
}
.template-card-guide__title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}
.template-card-guide__desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}
.template-card-guide__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.horizontal-list, .button-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.image-text-area {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.horizontal-item, .button-item {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
