<template>
  <div class="plans-page" v-loading="loading || templatesLoading">
    <div class="plans-hero">
      <div>
        <div class="plans-hero__eyebrow">Operation Studio</div>
        <h1 class="plans-hero__title">运营编排中心</h1>
        <!-- <p class="plans-hero__desc">
          按“主题 / 天数 / 流程节点”组织运营内容。先看主题阶段，再进入每天的固定流程节点去配置实际发送内容。
        </p> -->
      </div>
      <div class="plans-hero__actions">
        <el-button plain size="large" @click="handleSwitchView('templates')">查看模板库</el-button>
        <el-button plain size="large" @click="openSopImportDialog">导入 SOP</el-button>
        <el-button v-if="activeView === 'plans' && currentDay" plain size="large" @click="handlePublishToGroups">发送到群</el-button>
        <el-button type="primary" size="large" @click="openCreatePlan">新建运营主题</el-button>
      </div>
    </div>

    <div class="view-switch-bar">
      <div class="view-switch">
        <button
          type="button"
          class="view-switch__item"
          :class="{ 'is-active': activeView === 'plans' }"
          @click="handleSwitchView('plans')"
        >
          运营编排
        </button>
        <button
          type="button"
          class="view-switch__item"
          :class="{ 'is-active': activeView === 'templates' }"
          @click="handleSwitchView('templates')"
        >
          模板库
        </button>
      </div>
      <div v-if="activeView === 'plans'" class="summary-strip">
        <div class="summary-strip__item">
          <span>{{ plans.length }}</span> 主题
        </div>
        <div class="summary-strip__sep" />
        <div class="summary-strip__item">
          <span>{{ completionSummary.total }}</span> 天
        </div>
        <div class="summary-strip__item">
          <span>{{ completionSummary.completed }}</span> 已完成
        </div>
        <div class="summary-strip__item summary-strip__item--accent">
          <span>{{ currentPlanPendingDays }}</span> 待完善
        </div>
      </div>
    </div>

    <template v-if="activeView === 'plans'">

      <div class="plans-workbench" :class="{ 'is-mobile': isMobile }">
        <!-- 移动端面板切换 -->
        <div v-if="isMobile" class="mobile-panel-tabs">
          <button type="button" class="mobile-panel-tab" :class="{ 'is-active': activeMobilePanel === 'nav' }" @click="activeMobilePanel = 'nav'">主题/天</button>
          <button type="button" class="mobile-panel-tab" :class="{ 'is-active': activeMobilePanel === 'nodes' }" @click="activeMobilePanel = 'nodes'">节点列表</button>
          <button type="button" class="mobile-panel-tab" :class="{ 'is-active': activeMobilePanel === 'editor' }" @click="activeMobilePanel = 'editor'">编辑器</button>
        </div>

        <WorkbenchLeftNav
          v-show="!isMobile || activeMobilePanel === 'nav'"
          :plans="plans"
          :current-plan-id="currentPlan?.id ?? null"
          :days="days"
          :current-day-id="currentDay?.id ?? null"
          :is-campaign-mode="isCampaignMode"
          :day-label="dayLabel"
          :completed-count="workbench.completedCount"
          :completion-percent="workbench.completionPercent"
          @select-plan="handleSelectPlan"
          @select-day="handleSelectDay"
          @create-plan="openCreatePlan"
          @remove-plan="(plan: any) => removePlan(plan)"
          @rename-plan="renamePlan"
          @jump-pending="jumpToFirstPending"
          @add-day="addDay"
          @remove-day="removeDay"
          @export-plan="exportPlan"
        />

        <WorkbenchCenter
          v-show="!isMobile || activeMobilePanel === 'nodes'"
          :current-day="currentDay"
          :nodes="nodes"
          :current-node-id="currentNode?.id ?? null"
          :pending-count="currentDayPendingCount"
          :is-campaign-mode="isCampaignMode"
          :day-draft="dayDraft"
          :day-dirty="dayDirty"
          :day-saving="daySaving"
          @select-node="handleSelectNode"
          @patch-day="patchDayDraft"
          @save-day="saveDayDraft"
          @reset-day="resetDayDraft"
          @add-node="addNode"
          @add-node-after="addNode"
          @remove-node="removeNode"
        />

        <WorkbenchEditor
          v-show="!isMobile || activeMobilePanel === 'editor'"
          :current-node="currentNode"
          :node-draft="nodeDraft"
          :node-dirty="nodeDirty"
          :node-saving="nodeSaving"
          :template-options="templateApplyOptions"
          :selected-template-id="selectedTemplateId"
          :has-prev="workbench.hasPrevNode.value"
          :has-next="workbench.hasNextNode.value"
          @patch-draft="patchNodeDraft"
          @save="saveNodeDraft"
          @save-and-next="workbench.saveAndNext"
          @reset="resetNodeDraft"
          @apply-template="handleApplyTemplate"
          @sync-node="confirmAndOpenSyncNode"
          @copy-node="workbench.copyNode"
          @prev-node="workbench.goToPrevNode"
          @next-node="workbench.goToNextNode"
          @update:selected-template-id="(id: number) => selectedTemplateId = id"
        />
      </div>    </template>

    <template v-else>
      <div class="template-library">
        <div class="toolbar-panel">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索模板名称..."
            clearable
            :prefix-icon="Search"
          />
          <div class="source-filter">
            <button
              v-for="item in [
                { value: 'all', label: '全部来源' },
                { value: 'mine', label: '我的模板' },
                { value: 'system', label: '系统母版' }
              ]"
              :key="item.value"
              type="button"
              class="source-filter__chip"
              :class="{ 'source-filter__chip--active': activeSource === item.value }"
              @click="activeSource = item.value as 'all' | 'mine' | 'system'"
            >
              {{ item.label }}
            </button>
          </div>
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
          <div class="category-filter">
            <button
              v-for="item in categoryTabs"
              :key="item"
              type="button"
              class="category-filter__chip"
              :class="{ 'category-filter__chip--active': activeCategory === item }"
              @click="activeCategory = item"
            >
              {{ item === 'all' ? '全部分类' : item }}
            </button>
          </div>
        </div>

        <section v-if="showRecentSection" class="planner-panel planner-panel--recent">
          <div class="planner-panel__header">
            <div>
              <h3>最近更新</h3>
              <p>先从刚改过的模板继续，减少来回翻找。</p>
            </div>
          </div>
          <div class="recent-template-row">
            <button
              v-for="tpl in visibleRecentMineTemplates"
              :key="tpl.id"
              type="button"
              class="recent-template-card"
              @click="handleEditTemplate(tpl)"
            >
              <span class="recent-template-card__type">{{ msgTypeLabel(tpl.msg_type) }}</span>
              <strong>{{ tpl.name }}</strong>
              <span>{{ formatDate(tpl.updated_at) }}</span>
            </button>
          </div>
        </section>

        <div class="template-library__grid">
          <section v-if="showMineSection" class="planner-panel">
            <div class="planner-panel__header planner-panel__header--collapsible" @click="mineSectionCollapsed = !mineSectionCollapsed">
              <div>
                <h3>我的模板 <el-icon class="collapse-icon" :class="{ 'is-collapsed': mineSectionCollapsed }"><ArrowDown /></el-icon></h3>
                <p>适合作为运营计划节点的起点。</p>
              </div>
              <el-button type="primary" @click.stop="handleOpenCreateTemplate">新增模板</el-button>
            </div>
            <div v-show="!mineSectionCollapsed" v-if="visibleMineTemplates.length" class="template-grid">
              <div
                v-for="tpl in visibleMineTemplates"
                :key="tpl.id"
                :data-template-id="tpl.id"
                class="template-card"
                :class="{ 'template-card--highlighted': highlightedTemplateId === tpl.id }"
              >
                <div class="template-card__head">
                  <span class="template-card__badge">我的模板</span>
                  <span class="template-card__time">{{ formatDate(tpl.updated_at) }}</span>
                </div>
                <h4 class="template-card__name">{{ tpl.name }}</h4>
                <div class="template-card__meta">{{ msgTypeLabel(tpl.msg_type) }} · {{ tpl.category || '未分类' }}</div>
                <p class="template-card__desc">{{ tpl.description || contentSummary(tpl) }}</p>
                <div class="template-card__actions">
                  <el-button link type="primary" @click="openTemplatePreview(tpl)">预览</el-button>
                  <el-button link type="primary" @click="handleEditTemplate(tpl)">编辑</el-button>
                  <el-button link type="primary" @click="cloneTemplate(tpl)">复制</el-button>
                  <el-button link type="danger" @click="deleteTemplate(tpl)">删除</el-button>
                </div>
              </div>
            </div>
            <el-empty v-show="!mineSectionCollapsed" v-else :image-size="60" description="暂无符合条件的我的模板" />
          </section>

          <section v-if="showSystemSection" class="planner-panel">
            <div class="planner-panel__header planner-panel__header--collapsible" @click="systemSectionCollapsed = !systemSectionCollapsed">
              <div>
                <h3>系统模板库 <el-icon class="collapse-icon" :class="{ 'is-collapsed': systemSectionCollapsed }"><ArrowDown /></el-icon></h3>
                <p>作为节点内容的复用母版。</p>
              </div>
            </div>
            <div v-show="!systemSectionCollapsed" v-if="visibleSystemTemplates.length" class="template-grid">
              <div v-for="tpl in visibleSystemTemplates" :key="tpl.id" class="template-card template-card--system">
                <div class="template-card__head">
                  <span class="template-card__badge template-card__badge--system">系统母版</span>
                  <span class="template-card__time">{{ formatDate(tpl.updated_at) }}</span>
                </div>
                <h4 class="template-card__name">{{ tpl.name }}</h4>
                <div class="template-card__meta">{{ msgTypeLabel(tpl.msg_type) }} · {{ tpl.category || '未分类' }}</div>
                <p class="template-card__desc">{{ tpl.description || contentSummary(tpl) }}</p>
                <div class="template-card__actions">
                  <el-button link type="primary" @click="openTemplatePreview(tpl)">预览</el-button>
                  <el-button link type="primary" @click="handleCreateFromTemplate(tpl)">基于此创建</el-button>
                  <el-button link type="primary" @click="cloneTemplate(tpl)">复制</el-button>
                </div>
              </div>
            </div>
            <el-empty v-show="!systemSectionCollapsed" v-else :image-size="60" description="暂无系统模板" />
          </section>
        </div>
      </div>
    </template>

    <el-dialog v-model="planDialogVisible" title="新建运营主题" width="520px">
      <el-form label-width="96px">
        <el-form-item label="主题名称">
          <el-input v-model="planForm.name" placeholder="例如：第一阶段：调整血糖·代谢优化" />
        </el-form-item>
        <el-form-item label="计划模式">
          <el-select v-model="planForm.plan_mode" style="width: 100%">
            <el-option label="日程流程（Day Flow）" value="day_flow" />
            <el-option label="积分运营（Points Campaign）" value="points_campaign" />
          </el-select>
        </el-form-item>
        <el-form-item label="主题标签">
          <el-input v-model="planForm.topic" placeholder="例如：血糖管理 / 代谢优化" />
        </el-form-item>
        <el-form-item label="阶段名称">
          <el-input v-model="planForm.stage" placeholder="例如：第一阶段" />
        </el-form-item>
        <el-form-item v-if="planForm.plan_mode === 'day_flow'" label="运营天数">
          <el-input-number v-model="planForm.day_count" :min="1" :max="90" />
        </el-form-item>
        <el-form-item v-else label="阶段预览">
          <el-tag
            v-for="stage in campaignStages"
            :key="stage.stage_key"
            size="small"
            style="margin: 2px 4px 2px 0"
          >
            {{ stage.title }}
          </el-tag>
          <div style="color: var(--text-muted); font-size: 12px; margin-top: 4px">
            将自动创建 {{ campaignStages.length }} 个运营阶段
          </div>
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

    <el-dialog v-model="sopImportDialogVisible" title="导入 SOP" width="760px">
      <div class="sop-import-dialog">
        <div class="sop-import-dialog__intro">
          <strong>支持上传 SOP Excel 或阶段配置 JSON</strong>
          <span>Excel 会解析第一个 sheet（sheet1），JSON 会按当前第一阶段配置格式直接导入，都会先做预检查再确认入库。</span>
        </div>

        <el-upload
          class="sop-import-dialog__upload"
          drag
          :auto-upload="false"
          :limit="1"
          accept=".xlsx,.json,application/json"
          :on-change="handleSopFileChange"
          :on-remove="handleSopFileRemove"
        >
          <div>拖拽 `.xlsx` / `.json` 文件到这里，或点击选择文件</div>
          <div class="el-upload__tip">Excel 当前专门适配 sheet1；JSON 当前专门适配你整理的阶段配置格式。</div>
        </el-upload>

        <div class="sop-import-dialog__actions">
          <el-button :disabled="!sopImportFile" :loading="sopImportPreviewing" @click="previewSopImport">
            预检查
          </el-button>
          <el-button
            type="primary"
            :disabled="!sopImportPreview?.ok"
            :loading="sopImporting"
            @click="confirmSopImport"
          >
            确认导入
          </el-button>
        </div>

        <div v-if="sopImportPreview" class="sop-import-dialog__preview">
          <div class="sop-import-dialog__summary">
            <div class="summary-card">
              <span class="summary-card__label">主题名称</span>
              <strong>{{ sopImportPreview.plan.name }}</strong>
            </div>
            <div class="summary-card">
              <span class="summary-card__label">运营天数</span>
              <strong>{{ sopImportPreview.summary.day_count }}</strong>
            </div>
            <div class="summary-card">
              <span class="summary-card__label">节点总数</span>
              <strong>{{ sopImportPreview.summary.node_count }}</strong>
            </div>
          </div>

          <div v-if="sopImportPreview.errors?.length" class="sop-import-feedback sop-import-feedback--error">
            <strong>错误</strong>
            <span v-for="(item, idx) in sopImportPreview.errors" :key="`err-${idx}`">{{ item }}</span>
          </div>

          <div v-if="sopImportPreview.warnings?.length" class="sop-import-feedback sop-import-feedback--warning">
            <strong>提示</strong>
            <span v-for="(item, idx) in sopImportPreview.warnings" :key="`warn-${idx}`">{{ item }}</span>
          </div>

          <div class="sop-import-daylist">
            <div class="sop-import-daylist__title">预览前 5 天</div>
            <div v-for="day in sopImportPreview.days" :key="day.day_number" class="sop-import-day">
              <div class="sop-import-day__head">
                <strong>Day {{ day.day_number }}</strong>
                <span>{{ day.week_label || '未标注周次' }}</span>
              </div>
              <div class="sop-import-day__meta">{{ day.day_title }} · {{ day.node_count }} 个节点</div>
              <div class="sop-import-day__nodes">
                <span v-for="node in day.nodes" :key="`${day.day_number}-${node.node_type}`">{{ node.title }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="sopImportDialogVisible = false">关闭</el-button>
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
      <div class="copy-dialog__hint copy-dialog__hint--warning">
        <strong>覆盖提醒</strong>
        <span>会把来源天的节点内容、消息类型、变量和当天重点整体覆盖到当前这一天，当前天原有编排会被替换。</span>
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
      <div class="copy-dialog__hint copy-dialog__hint--warning">
        <strong>覆盖提醒</strong>
        <span>会用当前这一天的整套流程节点覆盖目标天，目标天原有内容会被整体替换，适合先铺后微调。</span>
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
      <div class="copy-dialog__hint copy-dialog__hint--info">
        <strong>同步范围</strong>
        <span>只会同步当前流程节点到其他天的同类节点，不会影响这些天的其他时间段内容，适合统一“午餐提醒”或“晚安总结”。</span>
      </div>
      <template #footer>
        <el-button @click="syncNodeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="syncNodeToPeerDays">开始同步</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="dialogVisible"
      :title="form.id ? '编辑模板' : '新增模板'"
      width="70%"
      top="5vh"
      :before-close="handleTemplateDialogBeforeClose"
    >
      <div class="template-dialog__status">
        <span class="editor-status" :class="{ 'is-dirty': templateDirty }">
          {{ templateDirty ? '模板草稿待保存' : '模板内容已同步' }}
        </span>
        <span class="template-dialog__tip">
          {{ form.id ? '正在编辑已有模板，保存后会更新模板库内容。' : '当前是本地草稿态，保存后才会进入模板库。' }}
        </span>
      </div>
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
        <el-button @click="handleCloseTemplateDialog">取消</el-button>
        <el-button type="primary" :disabled="!templateDirty" @click="handleSaveTemplate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewDialogVisible" title="模板预览" width="980px" top="6vh">
      <div v-if="previewTemplate" class="template-preview-dialog">
        <div class="template-preview-dialog__meta">
          <div class="template-preview-dialog__header">
            <div>
              <div class="template-preview-dialog__eyebrow">
                {{ previewTemplate.is_system ? '系统母版' : '我的模板' }}
              </div>
              <h3>{{ previewTemplate.name }}</h3>
            </div>
            <span class="template-card__time">{{ formatDate(previewTemplate.updated_at) }}</span>
          </div>
          <div class="template-preview-dialog__facts">
            <div class="template-preview-dialog__fact">
              <span>消息类型</span>
              <strong>{{ msgTypeLabel(previewTemplate.msg_type) }}</strong>
            </div>
            <div class="template-preview-dialog__fact">
              <span>分类</span>
              <strong>{{ previewTemplate.category || '未分类' }}</strong>
            </div>
          </div>
          <!-- <div class="template-preview-dialog__desc">
            {{ previewTemplate.description || '暂无补充描述，这里主要展示模板最终会被运营如何看到和复用。' }}
          </div>
          <div class="template-preview-dialog__tip">
            这是模板的只读模拟预览，用来帮助运营快速判断是否可复用，不会直接修改模板内容。
          </div> -->
        </div>
        <div class="template-preview-dialog__content">
          <PreviewCard
            :preview-data="previewTemplateData"
            :msg-type="previewTemplate.msg_type"
            :content-json="previewTemplateContent"
          />
        </div>
      </div>
    </el-dialog>

  </div>
</template>

<script lang="ts">
export default { name: 'Templates' }
</script>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Search, ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MessageEditor from '@/components/message-editor/index.vue'
import PreviewCard from '@/views/SendCenter/components/PreviewCard.vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { useTemplates, msgTypeLabel, msgTypeOptions, supportsVariables } from './composables/useTemplates'
import type { TemplateItem } from './composables/useTemplates'
import { useOperationPlans } from './composables/useOperationPlans'
import type { PlanDay, PlanNode } from './composables/useOperationPlans'
import { useWorkbenchActions } from './composables/useWorkbenchActions'
import WorkbenchLeftNav from './components/WorkbenchLeftNav.vue'
import WorkbenchCenter from './components/WorkbenchCenter.vue'
import WorkbenchEditor from './components/WorkbenchEditor.vue'
import request from '@/utils/request'
import { useMobile } from '@/composables/useMobile'

const storedView = typeof window !== 'undefined'
  ? window.localStorage.getItem('templates-active-view')
  : null
const activeView = ref<'plans' | 'templates'>(storedView === 'plans' || storedView === 'templates' ? storedView : 'templates')

const {
  plans,
  presets,
  campaignStages,
  loading,
  currentPlan,
  currentDay,
  currentNode,
  days,
  nodes,
  completionSummary,
  isCampaignMode,
  dayLabel,
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
  fetchPlans,
  selectPlan,
  selectDay,
  selectNode,
  addDay,
  removeDay,
  addNode,
  removeNode,
  openCreatePlan,
  openCopyDay,
  openBatchCopyDay,
  openSyncNode,
  savePlan,
  updateNode,
  updateDayMeta,
  removePlan,
  renamePlan,
  copyDayContent,
  batchCopyDayContent,
  syncNodeToPeerDays,
  exportPlan
} = useOperationPlans()

const {
  templates, loading: templatesLoading, dialogVisible, activeType, searchKeyword,
  highlightedTemplateId, form,
  typeTabs, filteredMineTemplates, filteredSystemTemplates, recentMineTemplates,
  openCreate: openCreateTemplateDialog,
  editTemplate: editTemplateDialog,
  createFromTemplate: createFromTemplateDialog,
  handleMsgTypeChange, cloneTemplate, deleteTemplate, saveTemplate,
  contentSummary, formatDate, focusTemplateCard
} = useTemplates()

const selectedTemplateId = ref<number | null>(null)
const templateDraftBaseline = ref('')
const activeCategory = ref('all')
const activeSource = ref<'all' | 'mine' | 'system'>('all')
const mineSectionCollapsed = ref(true)
const systemSectionCollapsed = ref(true)
const previewDialogVisible = ref(false)
const previewTemplate = ref<TemplateItem | null>(null)
const sopImportDialogVisible = ref(false)
const sopImportFile = ref<File | null>(null)
const sopImportPreview = ref<any | null>(null)
const sopImportPreviewing = ref(false)
const sopImporting = ref(false)
const nodeDraft = ref<Partial<PlanNode> | null>(null)
const dayDraft = ref<Partial<PlanDay> | null>(null)
const nodeDirty = ref(false)
const dayDirty = ref(false)
const nodeSaving = ref(false)
const daySaving = ref(false)

const router = useRouter()
const { isMobile } = useMobile()
const activeMobilePanel = ref<'nav' | 'nodes' | 'editor'>('nav')

const cloneJson = <T,>(value: T): T => JSON.parse(JSON.stringify(value))

const buildNodeDraft = (node: PlanNode | null) => {
  if (!node) return null
  return {
    title: node.title,
    description: node.description,
    msg_type: node.msg_type,
    content_json: cloneJson(node.content_json || {}),
    variables_json: cloneJson(node.variables_json || {}),
    template_id: node.template_id,
    status: node.status,
    enabled: node.enabled
  }
}

const buildDayDraft = (day: PlanDay | null) => {
  if (!day) return null
  return {
    title: day.title,
    focus: day.focus,
    trigger_rule_json: cloneJson(day.trigger_rule_json || {}),
    status: day.status
  }
}

const resetNodeDraft = () => {
  nodeDraft.value = buildNodeDraft(currentNode.value)
  nodeDirty.value = false
}

const resetDayDraft = () => {
  dayDraft.value = buildDayDraft(currentDay.value)
  dayDirty.value = false
}

const patchNodeDraft = (patch: Partial<PlanNode>) => {
  if (!nodeDraft.value) {
    resetNodeDraft()
  }
  nodeDraft.value = {
    ...(nodeDraft.value || {}),
    ...patch
  }
  nodeDirty.value = true
}

const patchDayDraft = (patch: Partial<PlanDay>) => {
  if (!dayDraft.value) {
    resetDayDraft()
  }
  dayDraft.value = {
    ...(dayDraft.value || {}),
    ...patch
  }
  dayDirty.value = true
}

const serializeTemplateDraft = () => JSON.stringify({
  id: form.id,
  name: form.name,
  description: form.description,
  msg_type: form.msg_type,
  category: form.category,
  contentJson: form.contentJson,
  variablesJson: form.variablesJson
})

const syncTemplateDraftBaseline = () => {
  templateDraftBaseline.value = serializeTemplateDraft()
}

const templateDirty = computed(() => dialogVisible.value && serializeTemplateDraft() !== templateDraftBaseline.value)

const categoryTabs = computed(() => {
  const categories = Array.from(new Set(
    templates.value
      .map(item => item.category?.trim())
      .filter((item): item is string => !!item)
  ))
  return ['all', ...categories]
})

const categoryMatched = (category?: string) =>
  activeCategory.value === 'all' || (category || '未分类') === activeCategory.value

const visibleMineTemplates = computed(() =>
  filteredMineTemplates.value.filter(item => categoryMatched(item.category || '未分类'))
)

const visibleSystemTemplates = computed(() =>
  filteredSystemTemplates.value.filter(item => categoryMatched(item.category || '未分类'))
)

const visibleRecentMineTemplates = computed(() =>
  recentMineTemplates.value.filter(item => categoryMatched(item.category || '未分类'))
)

const showMineSection = computed(() => activeSource.value === 'all' || activeSource.value === 'mine')
const showSystemSection = computed(() => activeSource.value === 'all' || activeSource.value === 'system')
const showRecentSection = computed(() => activeSource.value !== 'system' && visibleRecentMineTemplates.value.length > 0)

const pendingNodeCount = (day: PlanDay) => day.nodes?.filter(node => node.status === 'draft').length || 0

const currentPlanPendingDays = computed(() =>
  days.value.filter(day => pendingNodeCount(day) > 0).length
)

const currentDayPendingCount = computed(() => nodes.value.filter(node => node.status === 'draft').length)

const firstPendingDay = computed(() => days.value.find(day => pendingNodeCount(day) > 0) || null)
const previewTemplateContent = computed(() => parseTemplateJson(previewTemplate.value?.content_json ?? previewTemplate.value?.content))
const previewTemplateData = computed(() => ({
  rendered_content: previewTemplateContent.value
}))

const templateApplyOptions = computed(() =>
  templates.value.map(item => ({
    id: item.id,
    label: `${item.is_system ? '系统' : '我的'} · ${msgTypeLabel(item.msg_type)} · ${item.name}`
  }))
)

async function saveNodeDraft() {
  if (!currentNode.value || !nodeDraft.value || !nodeDirty.value) return true
  nodeSaving.value = true
  try {
    const payload = { ...nodeDraft.value, status: 'ready' as const }
    const saved = await updateNode(payload)
    if (!saved) return false
    resetNodeDraft()
    return true
  } finally {
    nodeSaving.value = false
  }
}

const saveDayDraft = async () => {
  if (!currentDay.value || !dayDraft.value || !dayDirty.value) return
  daySaving.value = true
  try {
    const saved = await updateDayMeta(dayDraft.value)
    if (!saved) return false
    resetDayDraft()
    return true
  } finally {
    daySaving.value = false
  }
}

const hasUnsavedChanges = computed(() => nodeDirty.value || dayDirty.value)

const discardCurrentDrafts = () => {
  resetNodeDraft()
  resetDayDraft()
}

const saveCurrentDrafts = async () => {
  if (nodeDirty.value) {
    const nodeSaved = await saveNodeDraft()
    if (!nodeSaved) return false
  }
  if (dayDirty.value) {
    const daySaved = await saveDayDraft()
    if (!daySaved) return false
  }
  return true
}

async function confirmDiscardDraft() {
  if (!hasUnsavedChanges.value) return true
  let action: 'confirm' | 'cancel' | 'close'
  try {
    await ElMessageBox.confirm('当前有未保存的改动，切换后会丢失。是否继续切换？', '放弃未保存内容', {
      confirmButtonText: '保存并切换',
      cancelButtonText: '放弃修改',
      distinguishCancelAndClose: true,
      closeOnClickModal: false,
      closeOnPressEscape: false,
      type: 'warning'
    })
    action = 'confirm'
  } catch (error) {
    action = error as 'cancel' | 'close'
  }

  if (action === 'close') {
    return false
  }

  if (action === 'cancel') {
    discardCurrentDrafts()
    return true
  }

  return await saveCurrentDrafts()
}

const workbench = useWorkbenchActions({
  nodes,
  days,
  currentNode,
  currentDay,
  nodeDirty,
  nodeSaving,
  selectNode,
  selectDay,
  addNode,
  saveNodeDraft,
  confirmDiscardDraft,
})

const handleSwitchView = async (view: 'plans' | 'templates') => {
  if (activeView.value === view) return
  if (!(await confirmDiscardDraft())) return
  activeView.value = view
  window.localStorage.setItem('templates-active-view', view)
}

const handleSelectPlan = async (planId: number) => {
  if (!(await confirmDiscardDraft())) return
  selectPlan(planId)
}

const handleSelectDay = async (dayId: number) => {
  if (!(await confirmDiscardDraft())) return
  selectDay(dayId)
  if (isMobile.value) activeMobilePanel.value = 'nodes'
}

const handleSelectNode = async (nodeId: number) => {
  if (!(await confirmDiscardDraft())) return
  selectNode(nodeId)
  if (isMobile.value) activeMobilePanel.value = 'editor'
}

const jumpToFirstPending = async () => {
  if (!firstPendingDay.value) return
  const targetDay = firstPendingDay.value
  const targetNode = targetDay.nodes?.find(node => node.status === 'draft') || targetDay.nodes?.[0]
  if (currentDay.value?.id !== targetDay.id) {
    await handleSelectDay(targetDay.id)
  }
  if (targetNode) {
    await handleSelectNode(targetNode.id)
  }
}

const openTemplatePreview = (template: TemplateItem) => {
  previewTemplate.value = template
  previewDialogVisible.value = true
}

const openSopImportDialog = () => {
  sopImportDialogVisible.value = true
  sopImportPreview.value = null
  sopImportFile.value = null
}

const handleSopFileChange = (uploadFile: any) => {
  sopImportFile.value = uploadFile.raw || null
  sopImportPreview.value = null
}

const handleSopFileRemove = () => {
  sopImportFile.value = null
  sopImportPreview.value = null
}

const previewSopImport = async () => {
  if (!sopImportFile.value) {
    ElMessage.warning('请先选择一个 SOP 文件')
    return
  }
  sopImportPreviewing.value = true
  try {
    const formData = new FormData()
    formData.append('file', sopImportFile.value)
    sopImportPreview.value = await request.post('/v1/operation-plans/import/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  } catch (error) {
    console.error(error)
    ElMessage.error('SOP 预检查失败')
  } finally {
    sopImportPreviewing.value = false
  }
}

const confirmSopImport = async () => {
  if (!sopImportFile.value || !sopImportPreview.value?.ok) return
  sopImporting.value = true
  try {
    const formData = new FormData()
    formData.append('file', sopImportFile.value)
    const result: any = await request.post('/v1/operation-plans/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    await fetchPlans()
    if (result?.plan_id) {
      activeView.value = 'plans'
      window.localStorage.setItem('templates-active-view', 'plans')
      await handleSelectPlan(result.plan_id)
    }
    sopImportDialogVisible.value = false
    sopImportPreview.value = null
    sopImportFile.value = null
    ElMessage.success('SOP 已成功导入到运营编排中心')
  } catch (error) {
    console.error(error)
    ElMessage.error('SOP 导入失败')
  } finally {
    sopImporting.value = false
  }
}

const confirmAndOpenCopyDay = async () => {
  if (!(await confirmDiscardDraft())) return
  openCopyDay()
}

const confirmAndOpenBatchCopyDay = async () => {
  if (!(await confirmDiscardDraft())) return
  openBatchCopyDay()
}

const confirmAndOpenSyncNode = async () => {
  if (!(await confirmDiscardDraft())) return
  openSyncNode()
}

const confirmDiscardTemplateDraft = async () => {
  if (!templateDirty.value) return true
  try {
    await ElMessageBox.confirm('模板弹窗里还有未保存内容，离开后会丢失。是否继续？', '放弃模板草稿', {
      confirmButtonText: '继续离开',
      cancelButtonText: '继续编辑',
      type: 'warning'
    })
    return true
  } catch {
    return false
  }
}

const handleOpenCreateTemplate = async () => {
  if (!(await confirmDiscardTemplateDraft())) return
  openCreateTemplateDialog()
  syncTemplateDraftBaseline()
}

const handleEditTemplate = async (template: (typeof templates.value)[number]) => {
  if (!(await confirmDiscardTemplateDraft())) return
  editTemplateDialog(template)
  syncTemplateDraftBaseline()
}

const handleCreateFromTemplate = async (template: (typeof templates.value)[number]) => {
  if (!(await confirmDiscardTemplateDraft())) return
  createFromTemplateDialog(template)
  syncTemplateDraftBaseline()
}

const handleCloseTemplateDialog = async () => {
  if (!(await confirmDiscardTemplateDraft())) return
  dialogVisible.value = false
}

const handleTemplateDialogBeforeClose = async (done: () => void) => {
  if (!(await confirmDiscardTemplateDraft())) return
  done()
}

const handleSaveTemplate = async () => {
  const saved = await saveTemplate()
  if (!saved) return
  syncTemplateDraftBaseline()
}

const parseTemplateJson = (raw: unknown) => {
  if (!raw) return {}
  if (typeof raw === 'string') {
    try {
      return JSON.parse(raw)
    } catch {
      return {}
    }
  }
  if (typeof raw === 'object') {
    return cloneJson(raw)
  }
  return {}
}

const handleApplyTemplate = async () => {
  if (!selectedTemplateId.value || !currentNode.value) return
  const template = templates.value.find(item => item.id === selectedTemplateId.value)
  if (!template) return
  patchNodeDraft({
    title: template.name || currentNode.value.title,
    description: template.description || currentNode.value.description,
    msg_type: template.msg_type,
    template_id: template.id,
    content_json: parseTemplateJson(template.content_json ?? template.content),
    variables_json: parseTemplateJson(template.variables_json ?? template.variable_schema)
  })
  ElMessage.success('模板内容已填入草稿，记得点击保存')
}

const handlePublishToGroups = () => {
  if (!currentDay.value) {
    ElMessage.warning('请先选择一天')
    return
  }
  const items: { id: number; title: string; msg_type: string; description: string; contentJson: any; variablesJson: any }[] = []
  for (const node of (nodes.value || [])) {
    if (node.enabled && node.status === 'ready') {
      items.push({
        id: node.id,
        title: node.title,
        msg_type: node.msg_type,
        description: node.description || '',
        contentJson: node.content_json,
        variablesJson: node.variables_json,
      })
    }
  }
  if (!items.length) {
    ElMessage.warning('当前天没有可发布的节点')
    return
  }
  sessionStorage.setItem('send-center-prefill', JSON.stringify(items))
  router.push('/send')
}

watch(() => currentNode.value?.id, () => {
  selectedTemplateId.value = currentNode.value?.template_id ?? null
  resetNodeDraft()
})

watch(() => currentDay.value?.id, () => {
  resetDayDraft()
})

watch(() => dialogVisible.value, (visible) => {
  if (visible) {
    syncTemplateDraftBaseline()
  }
})

const handleBeforeUnload = (event: BeforeUnloadEvent) => {
  if (!templateDirty.value && !hasUnsavedChanges.value) return
  event.preventDefault()
  event.returnValue = ''
}

window.addEventListener('beforeunload', handleBeforeUnload)

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

onBeforeRouteLeave(async () => {
  if (!(await confirmDiscardTemplateDraft())) return false
  return await confirmDiscardDraft()
})
</script>

<style scoped>
.plans-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  --tpl-accent-soft: rgba(34, 197, 94, 0.12);
  --tpl-accent-soft-strong: rgba(34, 197, 94, 0.18);
  --tpl-accent-border: rgba(34, 197, 94, 0.38);
  --tpl-accent-border-strong: rgba(34, 197, 94, 0.52);
  --tpl-accent-ring: rgba(34, 197, 94, 0.1);
  --tpl-surface-top: rgba(255, 255, 255, 0.96);
  --tpl-surface-bottom: rgba(248, 250, 252, 0.96);
  --tpl-card-top: rgba(248, 250, 252, 0.85);
  --tpl-card-bottom: rgba(255, 255, 255, 0.96);
  --tpl-shadow: 0 12px 24px rgba(15, 23, 42, 0.06);
  --tpl-badge-bg: rgba(59, 130, 246, 0.1);
  --tpl-badge-color: #2563eb;
  --tpl-warning-color: #f59e0b;
}

:global(html.dark) .plans-page {
  --tpl-accent-soft: rgba(34, 197, 94, 0.18);
  --tpl-accent-soft-strong: rgba(34, 197, 94, 0.24);
  --tpl-accent-border: rgba(74, 222, 128, 0.34);
  --tpl-accent-border-strong: rgba(74, 222, 128, 0.48);
  --tpl-accent-ring: rgba(74, 222, 128, 0.14);
  --tpl-surface-top: rgba(33, 34, 36, 0.96);
  --tpl-surface-bottom: rgba(26, 27, 29, 0.96);
  --tpl-card-top: rgba(39, 40, 42, 0.92);
  --tpl-card-bottom: rgba(29, 30, 31, 0.98);
  --tpl-shadow: 0 16px 28px rgba(0, 0, 0, 0.28);
  --tpl-badge-bg: rgba(96, 165, 250, 0.18);
  --tpl-badge-color: #93c5fd;
  --tpl-warning-color: #fbbf24;
}

.plans-hero,
.view-switch-bar,
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
  background: var(--card-bg);
  position: relative;
  overflow: hidden;
}

.plans-hero::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary-color), rgba(59, 130, 246, 0.6));
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
  flex-wrap: wrap;
}

.view-switch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  gap: 16px;
}

.view-switch {
  display: inline-flex;
  width: fit-content;
  padding: 4px;
  border-radius: 12px;
  background: var(--bg-color);
}

.view-switch__item {
  min-width: 100px;
  padding: 8px 16px;
  appearance: none;
  -webkit-appearance: none;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}

.view-switch__item.is-active {
  background: var(--tpl-accent-soft);
  color: var(--primary-color);
  font-weight: 700;
}

.summary-strip {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--text-muted);
}

.summary-strip__item span {
  font-weight: 700;
  color: var(--text-primary);
  margin-right: 2px;
}

.summary-strip__item--accent span {
  color: var(--primary-color);
}

.summary-strip__sep {
  width: 1px;
  height: 14px;
  background: var(--border-color);
}

.planner-layout {
  display: grid;
  grid-template-columns: 0.9fr 0.8fr 1fr;
  gap: 16px;
}

/* ===== 三栏工作台布局 ===== */
.plans-workbench {
  display: grid;
  grid-template-columns: 260px 280px minmax(0, 1fr);
  gap: 16px;
  min-height: calc(100vh - 320px);
}

@media (max-width: 1400px) {
  .plans-workbench {
    grid-template-columns: 220px 240px minmax(0, 1fr);
  }
}

@media (max-width: 1200px) {
  .plans-workbench {
    grid-template-columns: 1fr;
  }
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

.planner-panel__header--collapsible {
  cursor: pointer;
  border-radius: 12px;
  padding: 16px 20px;
  margin: -20px -20px 16px;
  transition: background 0.15s;
}
.planner-panel__header--collapsible:hover {
  background: rgba(0, 0, 0, 0.02);
}
html.dark .planner-panel__header--collapsible:hover {
  background: rgba(255, 255, 255, 0.03);
}

.collapse-icon {
  font-size: 14px;
  color: var(--text-muted);
  transition: transform 0.2s;
  vertical-align: middle;
  margin-left: 4px;
}
.collapse-icon.is-collapsed {
  transform: rotate(-90deg);
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

.context-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.editor-status {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(148, 163, 184, 0.08);
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1;
}

.editor-status.is-dirty {
  border-color: var(--tpl-accent-border);
  background: var(--tpl-accent-soft);
  color: var(--primary-color);
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
  appearance: none;
  -webkit-appearance: none;
  border: 1px solid var(--border-color);
  border-radius: 16px;
  background: linear-gradient(180deg, var(--tpl-card-top), var(--tpl-card-bottom));
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
  border-color: var(--tpl-accent-border);
  box-shadow: var(--tpl-shadow);
}

.topic-card.is-active,
.day-item.is-active,
.node-card.is-active,
.template-card--highlighted {
  border-color: var(--tpl-accent-border-strong);
  box-shadow: 0 0 0 3px var(--tpl-accent-ring);
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
  background: var(--tpl-badge-bg);
  color: var(--tpl-badge-color);
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
  color: var(--tpl-warning-color);
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
  display: grid;
  gap: 6px;
}

.copy-dialog__hint strong {
  color: var(--text-primary);
  font-size: 13px;
}

.copy-dialog__hint span {
  line-height: 1.65;
}

.copy-dialog__hint--warning {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.22);
}

.copy-dialog__hint--info {
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.18);
}

.batch-copy__source {
  width: 100%;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--tpl-accent-soft);
  color: var(--text-primary);
}

.template-dialog__status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 18px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: linear-gradient(135deg, var(--tpl-card-top), var(--tpl-card-bottom));
}

.template-dialog__tip {
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
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
  appearance: none;
  -webkit-appearance: none;
  border: none;
  border-radius: 999px;
  padding: 10px 14px;
  background: var(--bg-color);
  color: var(--text-secondary);
  cursor: pointer;
}

.type-filter__chip--active {
  background: var(--tpl-accent-soft);
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

.summary-card--accent {
  position: relative;
  background: transparent;
  border-left: 3px solid var(--primary-color);
}

.category-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-filter__chip {
  appearance: none;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 8px 12px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.source-filter__chip--active {
  border-color: var(--tpl-accent-border);
  background: var(--tpl-accent-soft);
  color: var(--primary-color);
}

.category-filter__chip {
  appearance: none;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 8px 12px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.category-filter__chip--active {
  border-color: var(--tpl-accent-border);
  background: var(--tpl-accent-soft);
  color: var(--primary-color);
}

.recent-template-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.recent-template-card {
  appearance: none;
  text-align: left;
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: linear-gradient(135deg, var(--tpl-card-top), var(--tpl-card-bottom));
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.recent-template-card:hover {
  transform: translateY(-1px);
  border-color: var(--tpl-accent-border);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
}

.recent-template-card__type {
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 600;
}

.template-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.template-card__badge {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--tpl-accent-soft);
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 600;
}

.template-card__badge--system {
  background: var(--tpl-badge-bg);
  color: var(--tpl-badge-color);
}

.template-card__time {
  color: var(--text-muted);
  font-size: 12px;
}

.template-preview-dialog {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
}

.template-preview-dialog__meta {
  display: grid;
  gap: 14px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: linear-gradient(135deg, var(--tpl-card-top), var(--tpl-card-bottom));
}

.template-preview-dialog__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.template-preview-dialog__header h3 {
  margin: 6px 0 0;
  color: var(--text-primary);
  font-size: 22px;
}

.template-preview-dialog__eyebrow {
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.template-preview-dialog__facts {
  display: grid;
  gap: 10px;
}

.template-preview-dialog__fact {
  display: grid;
  gap: 4px;
}

.template-preview-dialog__fact span {
  color: var(--text-muted);
  font-size: 12px;
}

.template-preview-dialog__fact strong {
  color: var(--text-primary);
  font-size: 14px;
}

.template-preview-dialog__desc {
  color: var(--text-secondary);
  line-height: 1.7;
}

.template-preview-dialog__tip {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.18);
  color: var(--text-muted);
  line-height: 1.65;
}

.template-preview-dialog__content {
  min-width: 0;
}

.sop-import-dialog {
  display: grid;
  gap: 18px;
}

.sop-import-dialog__intro {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: linear-gradient(135deg, var(--tpl-card-top), var(--tpl-card-bottom));
  color: var(--text-secondary);
}

.sop-import-dialog__intro strong {
  color: var(--text-primary);
}

.sop-import-dialog__actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.sop-import-dialog__preview {
  display: grid;
  gap: 14px;
}

.sop-import-feedback {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.65;
}

.sop-import-feedback strong {
  color: var(--text-primary);
}

.sop-import-feedback--error {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.18);
}

.sop-import-feedback--warning {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.sop-import-daylist {
  display: grid;
  gap: 12px;
}

.sop-import-daylist__title {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.sop-import-day {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border-color);
  background: linear-gradient(135deg, var(--tpl-card-top), var(--tpl-card-bottom));
}

.sop-import-day__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.sop-import-day__head strong {
  color: var(--text-primary);
}

.sop-import-day__head span,
.sop-import-day__meta {
  color: var(--text-muted);
  font-size: 13px;
}

.sop-import-day__nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sop-import-day__nodes span {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--tpl-accent-soft);
  color: var(--primary-color);
  font-size: 12px;
}

.day-item__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.day-item__pending {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.12);
  color: var(--tpl-warning-color);
  font-size: 12px;
  font-weight: 600;
}

.node-card__badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.node-card__state {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
}

.node-card__state.is-draft {
  background: rgba(245, 158, 11, 0.12);
  color: var(--tpl-warning-color);
}

@media (max-width: 1200px) {
  .plans-workbench,
  .template-library__grid {
    grid-template-columns: 1fr;
  }

  .template-preview-dialog {
    grid-template-columns: 1fr;
  }
}

.mobile-panel-tabs {
  display: flex;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  background: var(--card-bg);
}
.mobile-panel-tab {
  flex: 1;
  padding: 10px 8px;
  text-align: center;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.mobile-panel-tab.is-active {
  color: var(--primary-color);
  font-weight: 700;
  background: var(--tpl-accent-soft);
}

@media (max-width: 760px) {
  .plans-hero {
    flex-direction: column;
    padding: 18px 16px;
  }
  .plans-hero__title {
    font-size: 24px;
  }
  .plans-hero__actions {
    width: 100%;
  }

  .plans-workbench {
    grid-template-columns: 1fr;
    min-height: auto;
  }
  .plans-workbench.is-mobile {
    gap: 10px;
  }

  .editor-quick-actions {
    width: 100%;
  }

  .header-actions {
    width: 100%;
  }

  .view-switch-bar {
    flex-direction: column;
    gap: 8px;
  }

  .summary-strip {
    flex-wrap: wrap;
  }
  .template-preview-dialog {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .plans-hero {
    padding: 16px 14px;
  }
  .plans-page {
    gap: 12px;
  }
  .wb-node-item__body {
    padding: 12px;
  }
}
</style>

<style>
/* ===== 暗黑模式 — 容器级覆盖（非 scoped，确保命中） ===== */
html.dark .plans-page .plans-hero,
html.dark .plans-page .view-switch-bar,
html.dark .plans-page .planner-panel,
html.dark .plans-page .toolbar-panel {
  background: #1d1e1f !important;
  border-color: #414243 !important;
}

html.dark .plans-page .plans-hero {
  background: #1d1e1f !important;
}

html.dark .plans-page .plans-hero::after {
  background: linear-gradient(90deg, #4ade80, #60a5fa) !important;
}

html.dark .plans-page .summary-strip__item--accent span {
  color: #4ade80 !important;
}

html.dark .plans-page .recent-template-card {
  background: rgba(34, 197, 94, 0.14) !important;
}

html.dark .plans-page .recent-template-card:hover {
  box-shadow: 0 16px 30px rgba(0, 0, 0, 0.24) !important;
}

html.dark .plans-page .topic-card,
html.dark .plans-page .day-item,
html.dark .plans-page .node-card,
html.dark .plans-page .template-card {
  background-color: #232527 !important;
  background-image: linear-gradient(180deg, rgba(39, 40, 42, 0.92), rgba(29, 30, 31, 0.98)) !important;
  border-color: rgba(74, 222, 128, 0.24) !important;
  color: var(--text-primary) !important;
}

html.dark .plans-page .template-dialog__status {
  background: linear-gradient(135deg, rgba(39, 40, 42, 0.96), rgba(29, 30, 31, 0.98)) !important;
  border-color: rgba(255, 255, 255, 0.08) !important;
}

html.dark .plans-page .editor-status {
  border-color: rgba(148, 163, 184, 0.18) !important;
  background: rgba(148, 163, 184, 0.06) !important;
}

html.dark .plans-page .node-card__state {
  background: rgba(148, 163, 184, 0.1) !important;
}

html.dark .plans-page .node-card__state.is-draft {
  background: rgba(245, 158, 11, 0.16) !important;
}

html.dark .plans-page .day-item__pending {
  background: rgba(245, 158, 11, 0.16) !important;
}

html.dark .plans-page .preset-item,
html.dark .plans-page .copy-dialog__hint,
html.dark .plans-page .type-filter__chip {
  background: rgba(255, 255, 255, 0.04) !important;
}

html.dark .plans-page .category-filter__chip--active,
html.dark .plans-page .source-filter__chip--active {
  background: rgba(34, 197, 94, 0.14) !important;
}

html.dark .plans-page .template-preview-dialog__meta {
  background: linear-gradient(135deg, rgba(39, 40, 42, 0.96), rgba(29, 30, 31, 0.98)) !important;
}

html.dark .plans-page .template-preview-dialog__tip {
  background: rgba(59, 130, 246, 0.14) !important;
  border-color: rgba(96, 165, 250, 0.24) !important;
}

html.dark .plans-page .sop-import-dialog__intro,
html.dark .plans-page .sop-import-day {
  background: linear-gradient(135deg, rgba(39, 40, 42, 0.96), rgba(29, 30, 31, 0.98)) !important;
}

html.dark .plans-page .sop-import-feedback--warning {
  background: rgba(245, 158, 11, 0.14) !important;
  border-color: rgba(251, 191, 36, 0.22) !important;
}

html.dark .plans-page .sop-import-feedback--error {
  background: rgba(239, 68, 68, 0.14) !important;
  border-color: rgba(248, 113, 113, 0.22) !important;
}

html.dark .plans-page .copy-dialog__hint--warning {
  background: rgba(245, 158, 11, 0.14) !important;
  border-color: rgba(251, 191, 36, 0.22) !important;
}

html.dark .plans-page .copy-dialog__hint--info {
  background: rgba(59, 130, 246, 0.14) !important;
  border-color: rgba(96, 165, 250, 0.24) !important;
}

html.dark .plans-page .batch-copy__source {
  background: rgba(34, 197, 94, 0.18) !important;
  border-color: rgba(74, 222, 128, 0.24) !important;
}

html.dark .plans-page .type-filter__chip--active {
  background: rgba(34, 197, 94, 0.18) !important;
}

html.dark .plans-page .topic-card__stage,
html.dark .plans-page .node-card__type {
  background: rgba(96, 165, 250, 0.18) !important;
  color: #93c5fd !important;
}

html.dark .plans-page .day-item__status {
  color: #fbbf24 !important;
}

html.dark .plans-page .topic-card:hover,
html.dark .plans-page .day-item:hover,
html.dark .plans-page .node-card:hover,
html.dark .plans-page .template-card:hover {
  border-color: rgba(74, 222, 128, 0.34) !important;
  box-shadow: 0 16px 28px rgba(0, 0, 0, 0.28) !important;
}

html.dark .plans-page .topic-card.is-active,
html.dark .plans-page .day-item.is-active,
html.dark .plans-page .node-card.is-active,
html.dark .plans-page .template-card--highlighted {
  border-color: rgba(74, 222, 128, 0.48) !important;
  box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.14) !important;
}
</style>
