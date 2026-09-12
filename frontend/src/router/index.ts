/**
 * 夭夭影社 · Vue Router 路由表
 *
 * 对齐 ARCHITECTURE.md 3.2.1 页面路由与第 5 章目录树；
 * 播放页为独立全屏路由（不套主布局）。
 */

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { APP_NAME } from '@/utils/constants'

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题（用于 document.title）。 */
    title?: string
    /** 全屏路由（隐藏主布局）。 */
    fullscreen?: boolean
    /** 隐藏底部 TabBar。 */
    hideTabBar?: boolean
  }
}

const AppLayout = () => import('@/components/layout/AppLayout.vue')

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('@/views/HomeView.vue'),
        meta: { title: '首页' },
      },
      {
        path: 'library',
        name: 'Library',
        component: () => import('@/views/LibraryView.vue'),
        meta: { title: '片库' },
      },
      {
        path: 'favorites',
        name: 'Favorites',
        component: () => import('@/views/FavoritesView.vue'),
        meta: { title: '私房收藏' },
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/HistoryView.vue'),
        meta: { title: '播放历史' },
      },
      {
        path: 'actors',
        name: 'Actors',
        component: () => import('@/views/ActorsView.vue'),
        meta: { title: '演员' },
      },
      {
        path: 'actor/:id',
        name: 'ActorDetail',
        component: () => import('@/views/ActorDetailView.vue'),
        meta: { title: '演员详情' },
      },
      {
        path: 'search',
        name: 'Search',
        component: () => import('@/views/SearchView.vue'),
        meta: { title: '搜索' },
      },
      {
        path: 'video/:id',
        name: 'VideoDetail',
        component: () => import('@/views/VideoDetailView.vue'),
        meta: { title: '影片详情' },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '设置' },
      },
    ],
  },
  {
    path: '/play/:id',
    name: 'Player',
    component: () => import('@/views/PlayerView.vue'),
    meta: { fullscreen: true, hideTabBar: true, title: '原画播放' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    redirect: { name: 'Home' },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0 }
  },
})

router.afterEach((to) => {
  const title = to.meta.title
  document.title = title ? `${title} · ${APP_NAME}` : APP_NAME
})

export default router
