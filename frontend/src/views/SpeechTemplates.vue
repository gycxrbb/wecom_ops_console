<template>
  <div class="speech-page">
    <div class="speech-header">
      <div>
        <h2>话术管理</h2>
        <p class="speech-header__desc">管理积分运营场景话术模板，修改后立即生效于积分排行推送</p>
      </div>
    </div>

    <div v-loading="loading" class="speech-body">
      <div v-if="!loading && scenes.length" class="speech-layout">
        <div class="speech-sidebar">
          <div
            v-for="scene in scenes"
            :key="scene.key"
            class="speech-scene-item"
            :class="{ 'is-active': activeScene === scene.key }"
            @click="activeScene = scene.key"
          >
            <span class="speech-scene-item__label">{{ scene.label }}</span>
            <span class="speech-scene-item__key">{{ scene.key }}</span>
          </div>
        </div>

        <div class="speech-editor" v-if="currentTemplates.length">
          <div class="speech-editor__title">
            {{ currentSceneLabel }}
            <el-tag size="small" type="info">{{ activeScene }}</el-tag>
          </div>

          <div v-for="tpl in currentTemplates" :key="tpl.id || `${tpl.style}`" class="speech-tpl-card">
            <div class="speech-tpl-card__head">
              <el-tag :type="styleTagType(tpl.style)" size="small">{{ styleLabel(tpl.style) }}</el-tag>
              <el-tag v-if="tpl.is_builtin" size="small" type="info">内置</el-tag>
              <el-tag v-else size="small" type="success">自定义</el-tag>
            </div>
            <el-input
              v-model="tpl._editContent"
              type="textarea"
              :rows="5"
              placeholder="话术内容（支持 {name} {rank} {detail} {activity} 占位符）"
            />
            <div class="speech-tpl-card__foot">
              <span class="speech-tpl-card__hint">占位符: {name} {rank} {detail} {activity}</span>
              <el-button
                size="small"
                type="primary"
                :loading="tpl._saving"
                :disabled="tpl._editContent === tpl.content"
                @click="saveTemplate(tpl)"
              >
                保存
              </el-button>
            </div>
          </div>

          <div v-if="!currentTemplates.length" class="speech-empty">
            该场景暂无模板
          </div>
        </div>
      </div>

      <div v-if="!loading && !scenes.length" class="speech-empty">
        暂无话术数据
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '#/utils/request'

type Template = {
  id: number
  scene_key: string
  style: string
  label: string
  content: string
  is_builtin: number
  _editContent: string
  _saving: boolean
}

type Scene = {
  key: string
  label: string
  styles: string[]
}

const loading = ref(true)
const scenes = ref<Scene[]>([])
const templatesMap = ref<Record<string, Template[]>>({})
const activeScene = ref('')

const currentSceneLabel = computed(() => {
  const s = scenes.value.find(s => s.key === activeScene.value)
  return s?.label || activeScene.value
})

const currentTemplates = computed(() => {
  return templatesMap.value[activeScene.value] || []
})

const styleLabel = (style: string) => {
  const map: Record<string, string> = {
    professional: '专业风格',
    encouraging: '鼓励风格',
    competitive: '竞争风格',
  }
  return map[style] || style
}

const styleTagType = (style: string) => {
  const map: Record<string, string> = {
    professional: '',
    encouraging: 'success',
    competitive: 'danger',
  }
  return map[style] || 'info'
}

const fetchData = async () => {
  loading.value = true
  try {
    const [scenesData, templatesData]: [any[], any] = await Promise.all([
      request.get('/v1/speech-templates/scenes'),
      request.get('/v1/speech-templates'),
    ])
    scenes.value = scenesData
    const map: Record<string, Template[]> = {}
    for (const [key, list] of Object.entries(templatesData as Record<string, any[]>)) {
      map[key] = list.map((t: any) => ({
        ...t,
        _editContent: t.content,
        _saving: false,
      }))
    }
    templatesMap.value = map
    if (scenes.value.length && !activeScene.value) {
      activeScene.value = scenes.value[0].key
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('加载话术模板失败')
  } finally {
    loading.value = false
  }
}

const saveTemplate = async (tpl: Template) => {
  if (!tpl.id) return
  tpl._saving = true
  try {
    const result = await request.put(`/v1/speech-templates/${tpl.id}`, {
      content: tpl._editContent,
      label: tpl.label,
    })
    tpl.content = tpl._editContent
    ElMessage.success('话术已保存')
  } catch (e) {
    console.error(e)
    ElMessage.error('保存失败')
  } finally {
    tpl._saving = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.speech-page {
  padding: 0;
}
.speech-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.speech-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}
.speech-header__desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 4px 0 0;
}
.speech-body {
  min-height: 300px;
}
.speech-layout {
  display: flex;
  gap: 20px;
}
.speech-sidebar {
  width: 220px;
  flex-shrink: 0;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--card-bg);
  overflow: hidden;
}
.speech-scene-item {
  padding: 10px 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
}
.speech-scene-item:last-child {
  border-bottom: none;
}
.speech-scene-item:hover {
  background: var(--fill-color-light, #f5f7fa);
}
html.dark .speech-scene-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.speech-scene-item.is-active {
  background: rgba(34, 197, 94, 0.08);
  border-left: 3px solid #22c55e;
}
.speech-scene-item__label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}
.speech-scene-item__key {
  font-size: 11px;
  color: var(--text-muted);
}
.speech-editor {
  flex: 1;
  min-width: 0;
}
.speech-editor__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.speech-tpl-card {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--card-bg);
  padding: 14px;
  margin-bottom: 12px;
}
.speech-tpl-card__head {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}
.speech-tpl-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.speech-tpl-card__hint {
  font-size: 12px;
  color: var(--text-muted);
}
.speech-empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary);
  font-size: 14px;
}
@media (max-width: 768px) {
  .speech-layout {
    flex-direction: column;
  }
  .speech-sidebar {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    gap: 0;
  }
  .speech-scene-item {
    flex: 0 0 auto;
    border-bottom: none;
    border-right: 1px solid var(--border-color);
  }
}
</style>
