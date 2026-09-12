<script setup lang="ts">
/**
 * AppLayout —— 主布局壳（纯白顶栏 + 内容 + 底部 TabBar）。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import Navbar from '@/components/layout/Navbar.vue'
import TabBar from '@/components/layout/TabBar.vue'

const route = useRoute()

const hideTabBar = computed(() => route.meta.hideTabBar === true)
</script>

<template>
  <div class="flex min-h-screen flex-col bg-paper">
    <Navbar />

    <main class="flex-1 pb-20 md:pb-0">
      <router-view v-slot="{ Component }">
        <transition name="yy-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <TabBar v-if="!hideTabBar" />
  </div>
</template>
