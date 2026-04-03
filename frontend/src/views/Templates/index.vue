<template>
  <div class="plans-page" v-loading="loading || templatesLoading">
    <div class="plans-hero">
      <div>
        <div class="plans-hero__eyebrow">Operation Studio</div>
        <h1 class="plans-hero__title">运营编排中心</h1>
        <p class="plans-hero__desc">
          按“主题 / 天数 / 流程节点”组织运营内容。先看主题阶段，再进入每天固定的 6 个节点去配置实际发送内容。
        </p>
      </div>
      <div class="plans-hero__actions">
        <el-button plain size="large" @click="activeView = 'templates'">查看模板库</el-button>
        <el-button type="primary" size="large" @click="openCreatePlan">新建运营主题</el-button>
      </div>
    </div>

    <div class="view-switch">
      <button
        type="button"
        class="view-switch__item"
        :class="{ 'is-active': activeView === 'plans' }"
        @click="activeView = 'plans'"
      >
        运营编排
      </button>
      <button
        type="button"
        class="view-switch__item"
        :class="{ 'is-active': activeView === 'templates' }"
        @click="activeView = 'templates'"
      >
        模板库
      </button>
    </div>

    <template v-if="activeView === 'plans'">
      <div class="plan-summary">
        <div class="summary-card">
          <span class="summary-card__label">主题数</span>
          <strong>{{ plans.length }}</strong>
        </div>
        <div class="summary-card">
          <span class="summary-card__label">当前主题天数</span>
          <strong>{{ completionSummary.total }}</strong>
        </div>
        <div class="summary-card">
          <span class="summary-card__label">已完成天数</span>
          <strong>{{ completionSummary.completed }}</strong>
        </div>
      </div>

      <div class="planner-layout">
        <section class="planner-panel planner-panel--topics">
          <div class="planner-panel__header">
            <div>
              <h3>主题 / 阶段</h3>
              <p>每个主题对应一整段运营周期，例如 30 天编排。</p>
            </div>
          </div>
          <div v-if="plans.length" class="topic-list">
            <button
              v-for="plan in plans"
              :key="plan.id"
              type="button"
              class="topic-card"
              :class="{ 'is-active': currentPlan?.id === plan.id }"
              @click="selectPlan(plan.id)"
            >
              <div class="topic-card__head">
                <span class="topic-card__stage">{{ plan.stage || '未分阶段' }}</span>
                <el-button
                  text
                  type="danger"
                  size="small"
                  @click.stop="removePlan(plan)"
                >
                  删除
                </el-button>
              </div>
              <div class="topic-card__name">{{ plan.name }}</div>
              <div class="topic-card__meta">{{ plan.topic || '未设置主题标签' }}</div>
              <div class="topic-card__meta">{{ plan.day_count }} 天 · {{ plan.node_count }} 个节点</div>
            </button>
          </div>
          <el-empty v-else description="还没有运营主题，先创建一个 30 天运营主题。" :image-size="60" />
        </section>

        <section class="planner-panel planner-panel--days">
          <div class="planner-panel__header">
            <div>
              <h3>天数展开</h3>
              <p>固定 6 个流程节点，查看每天是否已经编排完成。</p>
            </div>
            <div class="header-actions">
              <el-button plain size="small" :disabled="days.length < 2 || !currentDay" @click="openCopyDay">
                从某天复制
              </el-button>
              <el-button plain size="small" :disabled="days.length < 2 || !currentDay" @click="openBatchCopyDay">
                复制到多天
              </el-button>
            </div>
          </div>
          <div v-if="days.length" class="day-list">
            <button
              v-for="day in days"
              :key="day.id"
              type="button"
              class="day-item"
              :class="{ 'is-active': currentDay?.id === day.id }"
              @click="selectDay(day.id)"
            >
              <div class="day-item__left">
                <strong>Day {{ day.day_number }}</strong>
                <span>{{ day.title }}</span>
              </div>
              <span class="day-item__status" :class="`status-${day.status}`">
                {{ day.status === 'draft' ? '待完善' : day.status }}
              </span>
            </button>
          </div>
          <el-empty v-else description="请选择一个运营主题" :image-size="60" />
        </section>

        <section class="planner-panel planner-panel--nodes">
          <div class="planner-panel__header">
            <div>
              <h3>流程节点</h3>
              <p>沿着当天固定流程逐条完善，运营同学不需要自己思考顺序。</p>
            </div>
          </div>
          <div v-if="nodes.length" class="node-list">
            <button
              v-for="node in nodes"
              :key="node.id"
              type="button"
              class="node-card"
              :class="{ 'is-active': currentNode?.id === node.id }"
              @click="selectNode(node.id)"
            >
              <div class="node-card__head">
                <span class="node-card__order">{{ node.sort_order }}</span>
                <span class="node-card__type">{{ msgTypeLabel(node.msg_type) }}</span>
              </div>
              <div class="node-card__title">{{ node.title }}</div>
              <div class="node-card__desc">{{ node.description }}</div>
            </button>
          </div>
          <el-empty v-else description="当前天还没有流程节点" :image-size="60" />
        </section>
      </div>

      <div class="editor-layout" v-if="currentNode">
        <section class="planner-panel planner-panel--editor">
            <div class="planner-panel__header">
              <div>
                <h3>节点编辑</h3>
                <p>当前编辑：{{ currentNode.title }}</p>
              </div>
            <div class="editor-quick-actions">
              <el-select
                v-model="selectedTemplateId"
                placeholder="从模板库快速套用"
                clearable
                filterable
                style="min-width: 220px"
              >
                <el-option
                  v-for="item in templateApplyOptions"
                  :key="item.id"
                  :label="item.label"
                  :value="item.id"
                />
              </el-select>
              <el-button plain :disabled="!selectedTemplateId" @click="handleApplyTemplate">
                套用模板
              </el-button>
              <el-button plain :disabled="!currentNode || days.length < 2" @click="openSyncNode">
                同步同类节点
              </el-button>
            </div>
          </div>

          <el-form label-width="96px" class="node-form">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="节点标题">
                  <el-input :model-value="currentNode.title" @update:model-value="updateNode({ title: $event })" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="消息类型">
                  <el-select :model-value="currentNode.msg_type" @update:model-value="updateNode({ msg_type: $event })">
                    <el-option v-for="item in msgTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="节点说明">
              <el-input
                :model-value="currentNode.description"
                @update:model-value="updateNode({ description: $event })"
                type="textarea"
                :rows="2"
              />
            </el-form-item>

            <el-form-item label="发送内容">
              <MessageEditor
                :model-value="currentNode.content_json"
                @update:model-value="updateNode({ content_json: $event })"
                :msg-type="currentNode.msg_type"
                :variables="currentNode.variables_json"
                @update:variables="updateNode({ variables_json: $event })"
                :show-variables="supportsVariables(currentNode.msg_type)"
                style="width: 100%"
              />
            </el-form-item>
          </el-form>
        </section>

        <section class="planner-panel planner-panel--context">
          <div class="planner-panel__header">
            <div>
              <h3>当天上下文</h3>
              <p>帮助运营同学确认今天的主题和重点。</p>
            </div>
          </div>

          <el-form label-width="88px">
            <el-form-item label="天标题">
              <el-input :model-value="currentDay?.title" @update:model-value="updateDayMeta({ title: $event })" />
            </el-form-item>
            <el-form-item label="当天重点">
              <el-input
                :model-value="currentDay?.focus"
                @update:model-value="updateDayMeta({ focus: $event })"
                type="textarea"
                :rows="4"
                placeholder="例如：今天聚焦早餐结构与餐后反馈记录"
              />
            </el-form-item>
          </el-form>

          <div class="preset-list">
            <div class="preset-list__title">系统预置流程</div>
            <div v-for="preset in presets" :key="preset.node_type" class="preset-item">
              <strong>{{ preset.title }}</strong>
              <span>{{ preset.description }}</span>
            </div>
          </div>
        </section>
      </div>
    </template>

    <template v-else>
      <div class="template-library">
        <div class="toolbar-panel">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索模板名称..."
            clearable
            :prefix-icon="Search"
          />
          <div class="type-filter">
            <button
              v-for="item in typeTabs"
              :key="item.value"
              type="button"
              class="type-filter__chip"
              :class="{ 'type-filter__chip--active': activeType === item.value }"
              @click="activeType = item.value"
            >
              {{ item.label }}
              <span class="type-filter__count">{{ item.count }}</span>
            </button>
          </div>
        </div>

        <div class="template-library__grid">
          <section class="planner-panel">
            <div class="planner-panel__header">
              <div>
                <h3>我的模板</h3>
                <p>适合作为运营计划节点的起点。</p>
              </div>
              <el-button type="primary" @click="openCreate">新增模板</el-button>
            </div>
            <div v-if="filteredMineTemplates.length" class="template-grid">
              <div
                v-for="tpl in filteredMineTemplates"
                :key="tpl.id"
                :data-template-id="tpl.id"
                class="template-card"
                :class="{ 'template-card--highlighted': highlightedTemplateId === tpl.id }"
              >
                <h4 class="template-card__name">{{ tpl.name }}</h4>
                <div class="template-card__meta">{{ msgTypeLabel(tpl.msg_type) }} · {{ tpl.category || '未分类' }}</div>
                <p class="template-card__desc">{{ tpl.description || contentSummary(tpl) }}</p>
                <div class="template-card__actions">
                  <el-button link type="primary" @click="editTemplate(tpl)">编辑</el-button>
                  <el-button link type="primary" @click="cloneTemplate(tpl)">复制</el-button>
                  <el-button link type="danger" @click="deleteTemplate(tpl)">删除</el-button>
                </div>
              </div>
            </div>
            <el-empty v-else :image-size="60" description="暂无符合条件的我的模板" />
          </section>

          <section class="planner-panel">
            <div class="planner-panel__header">
              <div>
                <h3>系统模板库</h3>
                <p>作为节点内容的复用母版。</p>
              </div>
            </div>
            <div v-if="filteredSystemTemplates.length" class="template-grid">
              <div v-for="tpl in filteredSystemTemplates" :key="tpl.id" class="template-card template-card--system">
                <h4 class="template-card__name">{{ tpl.name }}</h4>
                <div class="template-card__meta">{{ msgTypeLabel(tpl.msg_type) }} · {{ tpl.category || '未分类' }}</div>
                <p class="template-card__desc">{{ tpl.description || contentSummary(tpl) }}</p>
                <div class="template-card__actions">
                  <el-button link type="primary" @click="createFromTemplate(tpl)">基于此创建</el-button>
                  <el-button link type="primary" @click="cloneTemplate(tpl)">复制</el-button>
                </div>
              </div>
            </div>
            <el-empty v-else :image-size="60" description="暂无系统模板" />
          </section>
        </div>
      </div>
    </template>

    <el-dialog v-model="planDialogVisible" title="新建运营主题" width="520px">
      <el-form label-width="96px">
        <el-form-item label="主题名称">
          <el-input v-model="planForm.name" placeholder="例如：第一阶段：调整血糖·代谢优化" />
        </el-form-item>
        <el-form-item label="主题标签">
          <el-input v-model="planForm.topic" placeholder="例如：血糖管理 / 代谢优化" />
        </el-form-item>
        <el-form-item label="阶段名称">
          <el-input v-model="planForm.stage" placeholder="例如：第一阶段" />
        </el-form-item>
        <el-form-item label="运营天数">
          <el-input-number v-model="planForm.day_count" :min="1" :max="90" />
        </el-form-item>
        <el-form-item label="备注说明">
          <el-input v-model="planForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePlan">创建主题</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="copyDialogVisible" title="复制当天编排" width="520px">
      <el-form label-width="96px">
        <el-form-item label="复制来源">
          <el-select v-model="copyForm.sourceDayId" placeholder="请选择来源天" style="width: 100%">
            <el-option
              v-for="day in availableSourceDays"
              :key="day.id"
              :label="`Day ${day.day_number} · ${day.title}`"
              :value="day.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="copy-dialog__hint">
        会把来源天的节点内容、消息类型、变量和当天重点复制到当前这一天，适合快速铺排整周或整阶段内容。
      </div>
      <template #footer>
        <el-button @click="copyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="copyDayContent">确认复制</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchCopyDialogVisible" title="复制到多天" width="560px">
      <el-form label-width="96px">
        <el-form-item label="来源天">
          <div class="batch-copy__source">
            {{ currentDay ? `Day ${currentDay.day_number} · ${currentDay.title}` : '未选择' }}
          </div>
        </el-form-item>
        <el-form-item label="目标天">
          <el-select v-model="batchCopyForm.targetDayIds" multiple collapse-tags placeholder="请选择目标天" style="width: 100%">
            <el-option
              v-for="day in availableTargetDays"
              :key="day.id"
              :label="`Day ${day.day_number} · ${day.title}`"
              :value="day.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="copy-dialog__hint">
        会用当前这一天的整套流程节点覆盖目标天，适合先编好 Day 1，再批量铺到后续多天后微调。
      </div>
      <template #footer>
        <el-button @click="batchCopyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="batchCopyDayContent">开始复制</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="syncNodeDialogVisible" title="同步同类节点" width="560px">
      <el-form label-width="96px">
        <el-form-item label="当前节点">
          <div class="batch-copy__source">
            {{ currentNode ? `${currentNode.title} · ${msgTypeLabel(currentNode.msg_type)}` : '未选择' }}
          </div>
        </el-form-item>
        <el-form-item label="同步到">
          <el-select v-model="syncNodeForm.targetDayIds" multiple collapse-tags placeholder="请选择目标天" style="width: 100%">
            <el-option
              v-for="day in availableTargetDays"
              :key="day.id"
              :label="`Day ${day.day_number} · ${day.title}`"
              :value="day.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <div class="copy-dialog__hint">
        只会同步当前流程节点到其他天的同类节点，不会影响这些天的其他时间段内容，适合统一“午餐提醒”或“晚安总结”。
      </div>
      <template #footer>
        <el-button @click="syncNodeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="syncNodeToPeerDays">开始同步</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑模板' : '新增模板'" width="70%" top="5vh">
      <el-form label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="form.name" placeholder="输入模板名称" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="分类">
              <el-input v-model="form.category" placeholder="例如：训练营 / 日报 / 通知" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="描述">
              <el-input v-model="form.description" placeholder="给团队看的备注，可选" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="消息类型">
          <el-select v-model="form.msg_type" @change="handleMsgTypeChange" style="width: 220px">
            <el-option v-for="item in msgTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="模板内容">
          <MessageEditor
            v-model="form.contentJson"
            :msg-type="form.msg_type"
            v-model:variables="form.variablesJson"
            :show-variables="supportsVariables(form.msg_type)"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTemplate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import MessageEditor from '@/components/message-editor/index.vue'
import { useTemplates, msgTypeLabel, msgTypeOptions, supportsVariables } from './composables/useTemplates'
import { useOperationPlans } from './composables/useOperationPlans'

const activeView = ref<'plans' | 'templates'>('plans')

const {
  plans,
  presets,
  loading,
  currentPlan,
  currentDay,
  currentNode,
  days,
  nodes,
  completionSummary,
  planDialogVisible,
  copyDialogVisible,
  batchCopyDialogVisible,
  syncNodeDialogVisible,
  planForm,
  copyForm,
  batchCopyForm,
  syncNodeForm,
  availableSourceDays,
  availableTargetDays,
  selectPlan,
  selectDay,
  selectNode,
  openCreatePlan,
  openCopyDay,
  openBatchCopyDay,
  openSyncNode,
  savePlan,
  updateNode,
  applyTemplateToNode,
  updateDayMeta,
  removePlan,
  copyDayContent,
  batchCopyDayContent,
  syncNodeToPeerDays
} = useOperationPlans()

const {
  templates, loading: templatesLoading, dialogVisible, activeType, searchKeyword,
  highlightedTemplateId, form,
  typeTabs, filteredMineTemplates, filteredSystemTemplates,
  openCreate, editTemplate, createFromTemplate,
  handleMsgTypeChange, cloneTemplate, deleteTemplate, saveTemplate,
  contentSummary, focusTemplateCard
} = useTemplates()

const selectedTemplateId = ref<number | null>(null)

const templateApplyOptions = computed(() =>
  templates.value.map(item => ({
    id: item.id,
    label: `${item.is_system ? '系统' : '我的'} · ${msgTypeLabel(item.msg_type)} · ${item.name}`
  }))
)

const handleApplyTemplate = async () => {
  if (!selectedTemplateId.value) return
  const template = templates.value.find(item => item.id === selectedTemplateId.value)
  if (!template) return
  await applyTemplateToNode(template)
}

watch(() => currentNode.value?.id, () => {
  selectedTemplateId.value = currentNode.value?.template_id ?? null
})
</script>

<style scoped>
.plans-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.plans-hero,
.view-switch,
.plan-summary,
.planner-panel,
.toolbar-panel {
  border: 1px solid var(--border-color);
  border-radius: 20px;
  background: var(--card-bg);
}

.plans-hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px;
  background:
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.12), transparent 34%),
    linear-gradient(135deg, rgba(255,255,255,0.96), rgba(248,250,252,0.96));
}

.plans-hero__eyebrow {
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.plans-hero__title {
  margin: 10px 0 8px;
  font-size: 32px;
  color: var(--text-primary);
}

.plans-hero__desc {
  max-width: 62ch;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.plans-hero__actions {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.view-switch {
  display: inline-flex;
  width: fit-content;
  padding: 6px;
}

.view-switch__item {
  min-width: 120px;
  padding: 10px 16px;
  border: none;
  border-radius: 14px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.view-switch__item.is-active {
  background: rgba(34, 197, 94, 0.12);
  color: var(--primary-color);
  font-weight: 700;
}

.plan-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  overflow: hidden;
}

.summary-card {
  padding: 18px 20px;
  border-right: 1px solid var(--border-color);
}

.summary-card:last-child {
  border-right: none;
}

.summary-card__label {
  display: block;
  margin-bottom: 8px;
  color: var(--text-muted);
  font-size: 12px;
}

.summary-card strong {
  font-size: 28px;
  color: var(--text-primary);
}

.planner-layout {
  display: grid;
  grid-template-columns: 0.9fr 0.8fr 1fr;
  gap: 16px;
}

.editor-layout {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr;
  gap: 16px;
}

.planner-panel {
  padding: 20px;
}

.planner-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.planner-panel__header h3 {
  margin: 0 0 6px;
  color: var(--text-primary);
  font-size: 20px;
}

.planner-panel__header p {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.editor-quick-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.topic-list,
.day-list,
.node-list,
.template-grid,
.template-library__grid {
  display: grid;
  gap: 12px;
}

.template-library__grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.topic-card,
.day-item,
.node-card,
.template-card {
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(248,250,252,0.85), rgba(255,255,255,0.96));
  padding: 16px;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.topic-card:hover,
.day-item:hover,
.node-card:hover,
.template-card:hover {
  transform: translateY(-1px);
  border-color: rgba(34, 197, 94, 0.38);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.06);
}

.topic-card.is-active,
.day-item.is-active,
.node-card.is-active,
.template-card--highlighted {
  border-color: rgba(34, 197, 94, 0.52);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.1);
}

.topic-card__head,
.day-item,
.node-card__head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}

.topic-card__stage,
.node-card__type {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 12px;
}

.topic-card__name,
.node-card__title {
  margin-top: 10px;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 700;
}

.topic-card__meta,
.node-card__desc,
.template-card__meta,
.template-card__desc {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.day-item__left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.day-item__left strong {
  color: var(--text-primary);
}

.day-item__left span {
  color: var(--text-muted);
  font-size: 12px;
}

.day-item__status {
  font-size: 12px;
  color: #f59e0b;
}

.node-card__order {
  color: var(--text-muted);
  font-size: 12px;
}

.node-form {
  margin-top: 4px;
}

.preset-list {
  margin-top: 18px;
  display: grid;
  gap: 10px;
}

.preset-list__title {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.preset-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--bg-color);
}

.preset-item strong {
  color: var(--text-primary);
  font-size: 13px;
}

.preset-item span {
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.copy-dialog__hint {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--bg-color);
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.7;
}

.batch-copy__source {
  width: 100%;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: rgba(34, 197, 94, 0.06);
  color: var(--text-primary);
}

.toolbar-panel {
  padding: 16px;
  display: grid;
  gap: 14px;
}

.type-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.type-filter__chip {
  border: none;
  border-radius: 999px;
  padding: 10px 14px;
  background: var(--bg-color);
  color: var(--text-secondary);
  cursor: pointer;
}

.type-filter__chip--active {
  background: rgba(34, 197, 94, 0.12);
  color: var(--primary-color);
  font-weight: 700;
}

.type-filter__count {
  margin-left: 6px;
  color: var(--text-muted);
}

.template-card__name {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
}

.template-card__actions {
  margin-top: 10px;
  display: flex;
  gap: 10px;
}

@media (max-width: 1200px) {
  .planner-layout,
  .editor-layout,
  .template-library__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .plans-hero {
    flex-direction: column;
  }

  .editor-quick-actions {
    width: 100%;
  }

  .header-actions {
    width: 100%;
  }

  .plan-summary {
    grid-template-columns: 1fr;
  }

  .summary-card {
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }

  .summary-card:last-child {
    border-bottom: none;
  }
}
</style>
