<script setup lang="ts">
/**
 * PlayerView —— 沉浸式全屏原画直解播放页。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { mediaUrl } from '@/api/client'
import CustomPlayer from '@/components/player/CustomPlayer.vue'
import { usePlayerStore } from '@/stores/player'
import { useVideoStore } from '@/stores/video'

const route = useRoute()
const router = useRouter()
const videoStore = useVideoStore()
const playerStore = usePlayerStore()

const videoId = String(route.params.id)
const ready = ref(false)
const poster = ref<string | null>(null)

function goBack(): void {
  playerStore.setControlsVisible(true)
  if (window.history.length > 1) router.back()
  else void router.push({ name: 'Home' })
}

onMounted(async () => {
  playerStore.reset()
  const detail = await videoStore.fetchVideoDetail(videoId)
  playerStore.setVideo(videoId, {
    title: detail?.title ?? '',
    resumeMs: detail?.resume_position ?? 0,
  })
  poster.value = mediaUrl(detail?.backdrop_path) || mediaUrl(detail?.poster_path) || null
  ready.value = true
})

onBeforeUnmount(() => {
  void playerStore.reportProgress(true)
})
</script>

<template>
  <div class="fixed inset-0 h-[100dvh] w-screen overflow-hidden bg-player">
    <CustomPlayer
      v-if="ready"
      :video-id="videoId"
      :title="playerStore.title"
      :poster="poster"
      :resume-ms="playerStore.resumePosition"
      autoplay
      @back="goBack"
      @ended="goBack"
    />
    <div v-else class="flex h-full items-center justify-center">
      <span class="h-8 w-8 animate-pulse rounded-full bg-white/15" />
    </div>
  </div>
</template>
