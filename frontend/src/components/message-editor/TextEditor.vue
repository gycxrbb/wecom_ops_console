<template>
  <div class="text-editor">
    <el-form-item label="文本内容">
      <el-input
        type="textarea"
        :rows="8"
        :model-value="modelValue.content || ''"
        @update:model-value="updateField('content', $event)"
        placeholder="输入消息内容..."
      />
    </el-form-item>

    <el-form-item label="@指定人">
      <div class="mention-row">
        <el-input
          v-model="mentionInput"
          placeholder="输入 userid，如 zhangsan"
          size="small"
          @keyup.enter="addMention"
        />
        <el-button size="small" @click="addMention">添加</el-button>
        <el-button size="small" type="warning" @click="addMentionAll">@所有人</el-button>
      </div>
      <div class="tag-list" v-if="(modelValue.mentioned_list || []).length">
        <el-tag
          v-for="(item, idx) in modelValue.mentioned_list"
          :key="idx"
          closable
          size="small"
          @close="removeMention(idx)"
          class="mention-tag"
        >
          {{ item }}
        </el-tag>
      </div>
    </el-form-item>

    <el-form-item label="@手机号">
      <div class="mention-row">
        <el-input
          v-model="phoneInput"
          placeholder="输入手机号"
          size="small"
          @keyup.enter="addPhone"
        />
        <el-button size="small" @click="addPhone">添加</el-button>
      </div>
      <div class="tag-list" v-if="(modelValue.mentioned_mobile_list || []).length">
        <el-tag
          v-for="(item, idx) in modelValue.mentioned_mobile_list"
          :key="idx"
          type="success"
          closable
          size="small"
          @close="removePhone(idx)"
          class="mention-tag"
        >
          {{ item }}
        </el-tag>
      </div>
    </el-form-item>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', val: Record<string, any>): void }>()

const mentionInput = ref('')
const phoneInput = ref('')

const updateField = (field: string, value: any) => {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}

const addMention = () => {
  const val = mentionInput.value.trim()
  if (!val) return
  const list = [...(props.modelValue.mentioned_list || [])]
  if (list.includes(val)) {
    ElMessage.warning('已存在该用户')
    return
  }
  list.push(val)
  emit('update:modelValue', { ...props.modelValue, mentioned_list: list })
  mentionInput.value = ''
}

const addMentionAll = () => {
  const list = [...(props.modelValue.mentioned_list || [])]
  if (list.includes('@all')) {
    ElMessage.warning('已添加@所有人')
    return
  }
  list.push('@all')
  emit('update:modelValue', { ...props.modelValue, mentioned_list: list })
}

const removeMention = (idx: number) => {
  const list = [...(props.modelValue.mentioned_list || [])]
  list.splice(idx, 1)
  emit('update:modelValue', { ...props.modelValue, mentioned_list: list })
}

const addPhone = () => {
  const val = phoneInput.value.trim()
  if (!val) return
  if (!/^1\d{10}$/.test(val)) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  const list = [...(props.modelValue.mentioned_mobile_list || [])]
  if (list.includes(val)) {
    ElMessage.warning('已存在该手机号')
    return
  }
  list.push(val)
  emit('update:modelValue', { ...props.modelValue, mentioned_mobile_list: list })
  phoneInput.value = ''
}

const removePhone = (idx: number) => {
  const list = [...(props.modelValue.mentioned_mobile_list || [])]
  list.splice(idx, 1)
  emit('update:modelValue', { ...props.modelValue, mentioned_mobile_list: list })
}
</script>

<style scoped>
.text-editor {
  padding: 0;
}
.mention-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.mention-row .el-input {
  flex: 1;
}
.tag-list {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.mention-tag {
  margin: 0;
}
</style>
