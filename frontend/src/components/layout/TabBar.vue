<script setup lang="ts">
/**
 * TabBar —— 底部固定导航（iOS 风格，5 tab）。
 * 纯白 + backdrop-blur，无背景遮罩；移动端显示。
 */
import { Clock, Heart, Home, LayoutGrid, Settings } from 'lucide-vue-next'
import type { Component } from 'vue'
import { useRoute } from 'vue-router'

import { TAB_ITEMS, type TabItem } from '@/utils/constants'

const route = useRoute()

const icons: Record<TabItem['icon'], Component> = {
  home: Home,
  library: LayoutGrid,
  favorite: Heart,
  history: Clock,
  settings: Settings,
}

function isActive(name: string): boolean {
  return route.name === name
}
</script>

<template>
  <nav
    class="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-paper/88 pb-safe backdrop-blur-xl md:hidden"
  >
    <div class="mx-auto flex max-w-lg items-stretch justify-around px-2">
      <router-link
        v-for="item in TAB_ITEMS"
        :key="item.name"
        :to="{ name: item.name }"
        class="flex flex-1 flex-col items-center gap-1 py-2.5 transition-colors duration-150 ease-yy"
        :class="isActive(item.name) ? 'text-ink' : 'text-ink-faint'"
      >
        <component
          :is="icons[item.icon]"
          :size="20"
          :stroke-width="1.5"
          :class="isActive(item.name) ? 'text-accent' : ''"
        />
        <span class="text-[10px] tracking-wide">{{ item.label }}</span>
      </router-link>
    </div>
  </nav>
</template>
