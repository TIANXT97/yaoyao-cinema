<script setup lang="ts">
/**
 * Navbar —— 纯白顶栏（极简搜索与导航）。
 * 桌面端：品牌 + 内联导航 + 搜索 + 设置；
 * 移动端：品牌 + 搜索入口 + 设置（底部另有 TabBar）。
 */
import { Search, Settings } from 'lucide-vue-next'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { APP_NAME, APP_TAGLINE } from '@/utils/constants'

const router = useRouter()
const route = useRoute()

const keyword = ref('')

const NAV_LINKS = [
  { name: 'Home', label: '首页' },
  { name: 'Library', label: '片库' },
  { name: 'Actors', label: '演员' },
  { name: 'Favorites', label: '收藏' },
  { name: 'History', label: '历史' },
] as const

function submitSearch(): void {
  const query = keyword.value.trim()
  void router.push({ name: 'Search', query: query ? { q: query } : {} })
  keyword.value = ''
}

function isActive(name: string): boolean {
  return route.name === name
}
</script>

<template>
  <header
    class="sticky top-0 z-40 border-b border-line bg-paper/85 pt-safe backdrop-blur-xl"
  >
    <div
      class="mx-auto flex h-14 max-w-[1600px] items-center gap-3 px-4 sm:px-6 lg:px-8"
    >
      <!-- 品牌 -->
      <router-link
        :to="{ name: 'Home' }"
        class="flex shrink-0 items-center gap-2"
        :title="APP_TAGLINE"
      >
        <span class="h-1.5 w-1.5 rounded-full bg-accent" />
        <span class="font-serif text-[15px] tracking-wide text-ink">{{ APP_NAME }}</span>
      </router-link>

      <!-- 主导航 -->
      <nav class="ml-4 hidden items-center gap-0.5 md:flex">
        <router-link
          v-for="link in NAV_LINKS"
          :key="link.name"
          :to="{ name: link.name }"
          class="rounded-md px-3 py-1.5 text-[13px] transition-colors duration-150 ease-yy"
          :class="isActive(link.name) ? 'text-ink' : 'text-ink-soft hover:text-ink'"
        >
          {{ link.label }}
        </router-link>
      </nav>

      <div class="ml-auto flex items-center gap-1.5">
        <!-- 桌面搜索 -->
        <form class="hidden items-center sm:flex" @submit.prevent="submitSearch">
          <div
            class="flex items-center gap-2 rounded-full border border-line bg-paper-soft px-3 py-1.5 transition-colors duration-150 ease-yy focus-within:border-accent/60"
          >
            <Search :size="14" :stroke-width="1.5" class="text-ink-faint" />
            <input
              v-model="keyword"
              type="search"
              placeholder="搜索番号 / 标题 / 演员"
              class="w-40 bg-transparent text-[13px] text-ink placeholder:text-ink-mute focus:outline-none lg:w-56"
            />
          </div>
        </form>

        <!-- 移动搜索入口 -->
        <router-link
          :to="{ name: 'Search' }"
          class="flex h-9 w-9 items-center justify-center rounded-full text-ink-soft transition-colors duration-150 ease-yy hover:bg-paper-mute hover:text-ink sm:hidden"
          aria-label="搜索"
        >
          <Search :size="17" :stroke-width="1.5" />
        </router-link>

        <!-- 设置 -->
        <router-link
          :to="{ name: 'Settings' }"
          class="flex h-9 w-9 items-center justify-center rounded-full transition-colors duration-150 ease-yy hover:bg-paper-mute"
          :class="isActive('Settings') ? 'text-ink' : 'text-ink-faint hover:text-ink'"
          aria-label="设置"
        >
          <Settings :size="17" :stroke-width="1.5" />
        </router-link>
      </div>
    </div>
  </header>
</template>
