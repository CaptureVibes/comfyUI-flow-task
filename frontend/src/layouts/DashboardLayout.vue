<template>
  <div class="dashboard-layout" :class="{ 'sidebar-collapsed': isCollapsed, 'investor-mode': isInvestorMode }">
    <AppSidebar v-if="!isInvestorMode" :collapsed="isCollapsed" @toggle="toggle" />

    <div
      class="dashboard-main"
      :style="{ marginLeft: isInvestorMode ? '0' : (isCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)') }"
    >
      <AppHeader v-if="!isInvestorMode" @toggle-sidebar="toggle" />

      <main class="dashboard-content">
        <router-view v-slot="{ Component, route: viewRoute }">
          <transition name="page-fade" mode="out-in">
            <div :key="viewRoute.path" class="page-wrapper">
              <component :is="Component" />
            </div>
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
import AppSidebar from '../components/AppSidebar.vue'
import AppHeader from '../components/AppHeader.vue'
import { useSidebar } from '../composables/useSidebar'
import { useInvestorMode } from '../composables/useInvestorMode'

const { isCollapsed, toggle } = useSidebar()
const { isInvestorMode } = useInvestorMode()
</script>

<style scoped>
.dashboard-layout {
  display: flex;
  min-height: 100vh;
  background: var(--surface-secondary);
}

.dashboard-main {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-width: 0;
  flex: 1;
  overflow: hidden;
  transition: margin-left var(--sidebar-transition);
}

.dashboard-content {
  position: relative;
  flex: 1;
  padding: var(--space-6);
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--surface-secondary);
}

.page-wrapper {
  min-height: 100%;
  width: 100%;
  position: relative;
}

.page-fade-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.page-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
  position: absolute;
  inset: 0;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-3px);
}

@media (max-width: 768px) {
  .dashboard-content {
    padding: var(--space-4);
  }
}
</style>
