<template>
  <div class="template-card-editor">
    <el-form label-width="90px" size="small">
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

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const btnStyles = [
  { label: '蓝色', value: 1 },
  { label: '红色', value: 2 },
  { label: '绿色', value: 3 },
  { label: '灰色', value: 4 },
]

const cardType = computed(() => props.modelValue.card_type || 'text_notice')
const mainTitle = computed(() => props.modelValue.main_title?.title || '')
const emphasisTitle = computed(() => props.modelValue.emphasis_content?.title || '')
const emphasisDesc = computed(() => props.modelValue.emphasis_content?.desc || '')
const subTitleText = computed(() => props.modelValue.sub_title_text || '')
const horizontalList = computed(() => props.modelValue.horizontal_content_list || [])
const cardUrl = computed(() => props.modelValue.card_action?.url || '')
const buttonList = computed(() => props.modelValue.button_list || [])

const emitUpdate = (partial: Record<string, any>) => {
  emit('update:modelValue', { ...props.modelValue, ...partial })
}

const updateField = (field: string, value: any) => {
  emitUpdate({ [field]: value })
}

const updateNested = (parent: string, child: string, value: any) => {
  emitUpdate({ [parent]: { ...(props.modelValue[parent] || {}), [child]: value } })
}

const changeCardType = (val: string) => {
  emitUpdate({ card_type: val })
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
.horizontal-list, .button-list {
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
