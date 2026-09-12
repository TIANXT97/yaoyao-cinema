<script setup lang="ts">
/**
 * ActorsView —— 演员列表（圆形头像网格）。
 */
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'

import { listActors } from '@/api/actors'
import SearchInput from '@/components/browse/SearchInput.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import ActorCard from '@/components/media/ActorCard.vue'
import type { Actor } from '@/types/actor'

const router = useRouter()

const actors = ref<Actor[]>([])
const loading = ref(false)
const keyword = ref('')

const filtered = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  if (!query) return actors.value
  return actors.value.filter((actor) => {
    const name = actor.name?.toLowerCase() ?? ''
    const nameJa = actor.name_ja?.toLowerCase() ?? ''
    return name.includes(query) || nameJa.includes(query)
  })
})

async function load(): Promise<void> {
  loading.value = true
  try {
    actors.value = await listActors({ limit: 200 })
  } catch {
    actors.value = []
  } finally {
    loading.value = false
  }
}

function openActor(actor: Actor): void {
  void router.push({ name: 'ActorDetail', params: { id: actor.id } })
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeader
      title="演员"
      :subtitle="`馆藏共 ${actors.length} 位演员`"
      bordered
    />

    <section class="mx-auto max-w-[1600px] px-4 pt-6 pb-12 sm:px-6 lg:px-8">
      <div class="max-w-md">
        <SearchInput v-model="keyword" placeholder="搜索演员姓名" />
      </div>

      <div
        v-if="filtered.length > 0"
        class="mt-8 grid grid-cols-4 gap-5 sm:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10"
      >
        <ActorCard
          v-for="actor in filtered"
          :key="actor.id"
          :actor="actor"
          @click="openActor"
        />
      </div>

      <EmptyState
        v-else-if="!loading"
        :title="keyword ? '没有匹配的演员' : '暂无演员数据'"
        :description="
          keyword ? '换个关键词试试。' : '完成影片刮削后，演员信息会自动归档。'
        "
      />
    </section>
  </div>
</template>
