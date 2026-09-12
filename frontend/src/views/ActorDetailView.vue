<script setup lang="ts">
/**
 * ActorDetailView —— 演员详情 + 作品海报墙。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getActor, type ActorDetail } from '@/api/actors'
import { mediaUrl } from '@/api/client'
import EmptyState from '@/components/common/EmptyState.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import VideoGrid from '@/components/media/VideoGrid.vue'
import type { Video } from '@/types/video'

const route = useRoute()
const router = useRouter()

const id = computed(() => String(route.params.id))
const actor = ref<ActorDetail | null>(null)
const loading = ref(false)

const photo = computed(() => mediaUrl(actor.value?.photo_path))

const attributes = computed(() => {
  const item = actor.value
  if (!item) return []
  return [
    { label: '出生日期', value: item.birth_date || '—' },
    { label: '身高', value: item.height ? `${item.height} cm` : '—' },
    { label: '罩杯', value: item.cup_size || '—' },
    { label: '三围', value: item.measurements || '—' },
  ]
})

function openVideo(video: Video): void {
  void router.push({ name: 'VideoDetail', params: { id: video.id } })
}

async function load(): Promise<void> {
  loading.value = true
  try {
    actor.value = await getActor(id.value)
  } catch {
    actor.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(
  () => route.params.id,
  () => {
    if (route.name === 'ActorDetail') void load()
  },
)
</script>

<template>
  <div>
    <PageHeader
      :title="actor?.name ?? '演员详情'"
      :subtitle="actor ? `${actor.video_count} 部作品` : ''"
      back
      bordered
    />

    <section class="mx-auto max-w-[1600px] px-4 pt-8 pb-12 sm:px-6 lg:px-8">
      <div v-if="actor" class="flex flex-col gap-8 sm:flex-row sm:items-start">
        <div class="w-32 shrink-0 sm:w-44">
          <div class="aspect-square w-full overflow-hidden rounded-full bg-paper-mute">
            <img
              v-if="photo"
              :src="photo"
              :alt="actor.name"
              class="h-full w-full object-cover"
            />
            <span
              v-else
              class="flex h-full w-full items-center justify-center font-serif text-3xl text-ink-mute"
            >
              {{ actor.name.charAt(0) }}
            </span>
          </div>
        </div>

        <div class="min-w-0 flex-1">
          <h2 class="font-serif text-2xl text-ink">{{ actor.name }}</h2>
          <p v-if="actor.name_ja" class="mt-1 text-sm text-ink-faint">
            {{ actor.name_ja }}
          </p>

          <div class="mt-6 grid grid-cols-2 gap-x-8 gap-y-4 text-xs sm:max-w-md">
            <div v-for="attribute in attributes" :key="attribute.label">
              <p class="text-ink-faint">{{ attribute.label }}</p>
              <p class="mt-1 text-ink-soft">{{ attribute.value }}</p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="actor && actor.videos.length > 0" class="mt-12">
        <h2 class="mb-5 text-sm text-ink">作品</h2>
        <VideoGrid
          :videos="actor.videos"
          :infinite="false"
          :has-more="false"
          @card-click="openVideo"
        />
      </div>

      <EmptyState
        v-else-if="!loading && actor"
        title="暂无作品"
        description="该演员名下还没有已刮削的影片。"
      />

      <div
        v-else-if="!loading && !actor"
        class="py-24"
      >
        <EmptyState title="演员不存在" description="该记录可能已被移除。" />
      </div>
    </section>
  </div>
</template>
