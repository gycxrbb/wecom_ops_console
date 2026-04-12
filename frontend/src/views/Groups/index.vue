<template>
  <div class="groups-page">
    <div class="groups-hero">
      <div>
        <div class="groups-hero__eyebrow">Group Management</div>
        <h1 class="groups-hero__title">群管理</h1>
      </div>
      <div class="view-switch">
        <button
          class="view-switch__item"
          :class="{ 'is-active': activeView === 'internal' }"
          @click="switchView('internal')"
        >内部群</button>
        <button
          class="view-switch__item"
          :class="{ 'is-active': activeView === 'crm' }"
          @click="switchView('crm')"
        >外部群视图</button>
      </div>
    </div>
    <InternalGroups v-if="activeView === 'internal'" />
    <CrmGroupView v-if="activeView === 'crm'" />
  </div>
</template>

<script lang="ts">
export default { name: 'Groups' }
</script>

<script setup lang="ts">
import { ref } from 'vue'
import InternalGroups from './InternalGroups.vue'
import CrmGroupView from './CrmGroupView.vue'

const storedView = typeof window !== 'undefined'
  ? window.localStorage.getItem('groups-active-view')
  : null
const activeView = ref<'internal' | 'crm'>(
  storedView === 'crm' ? 'crm' : 'internal'
)

const switchView = (view: 'internal' | 'crm') => {
  activeView.value = view
  window.localStorage.setItem('groups-active-view', view)
}
</script>

<style scoped>
.groups-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.groups-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  padding: 24px 28px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
}

.groups-hero__eyebrow {
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.groups-hero__title {
  margin: 10px 0 0;
  font-size: 32px;
  color: var(--text-primary);
}

.view-switch {
  display: inline-flex;
  padding: 4px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  flex-shrink: 0;
  margin-top: 8px;
}

.view-switch__item {
  appearance: none;
  border: none;
  padding: 8px 18px;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.view-switch__item.is-active {
  background: rgba(34, 197, 94, 0.1);
  color: var(--primary-color);
  font-weight: 600;
}

.view-switch__item:hover:not(.is-active) {
  color: var(--text-primary);
}

:global(html.dark) .groups-hero {
  background: #1d1e1f !important;
  border-color: #414243 !important;
}

:global(html.dark) .view-switch {
  background: #1d1e1f;
  border-color: #414243;
}

:global(html.dark) .view-switch__item.is-active {
  background: rgba(34, 197, 94, 0.14);
  border-color: rgba(74, 222, 128, 0.34);
}

@media (max-width: 768px) {
  .groups-hero {
    flex-direction: column;
    padding: 18px 16px;
  }
  .groups-hero__title {
    font-size: 24px;
  }
}
</style>
