<template>
  <div class="page-container">
    <div class="page-header">
      <h2 class="page-title">知识库管理</h2>
      <p class="page-desc">管理 RAG 向量知识库，查看已索引资源、标签词汇、检索日志。</p>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="概览" name="overview">
        <OverviewTab />
      </el-tab-pane>
      <el-tab-pane label="资源管理" name="resources">
        <ResourceTable />
      </el-tab-pane>
      <el-tab-pane label="标签管理" name="tags">
        <TagManager />
      </el-tab-pane>
      <el-tab-pane label="检索日志" name="logs">
        <RetrievalLogTable />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import OverviewTab from './components/OverviewTab.vue'
import ResourceTable from './components/ResourceTable.vue'
import TagManager from './components/TagManager.vue'
import RetrievalLogTable from './components/RetrievalLogTable.vue'

const activeTab = ref('overview')
</script>

<style scoped>
.page-container {
  max-width: 1200px;
  margin: 0 auto;
}
.page-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}
</style>
