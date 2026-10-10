<script setup lang="ts">
/**
 * ActorCard —— 演员卡片（圆形头像 + 名字 + 作品数）。
 */
import { computed, ref } from 'vue'

import { mediaUrl } from '@/api/client'
import type { Actor } from '@/types/actor'

const props = defineProps<{ actor: Actor }>()

const emit = defineEmits<{ (e: 'click', actor: Actor): void }>()

const failed = ref(false)
const photo = computed(() => mediaUrl(props.actor.photo_path))
const initial = computed(() => props.actor.name?.trim()?.charAt(0) ?? '?')
</script>

<template>
  <button
    type="button"
    class="group flex w-full flex-col items-center gap-2 text-center"
    @click="emit('click', actor)"
  >
    <div
      class="relative aspect-square w-full overflow-hidden rounded-full bg-paper-mute transition-transform duration-300 ease-yy group-hover:scale-[1.03]"
    >
      <img
        v-if="photo && !failed"
        :src="photo"
        :alt="actor.name"
        loading="lazy"
        decoding="async"
        class="h-full w-full object-cover"
        @error="failed = true"
      />
      <span
        v-else
        class="flex h-full w-full items-center justify-center font-serif text-xl text-ink-mute"
      >
        {{ initial }}
      </span>
    </div>
    <div class="w-full">
      <p class="truncate text-[13px] text-ink">{{ actor.name }}</p>
      <p class="mt-0.5 text-[11px] tracking-bangou text-ink-faint">
        {{ actor.video_count }} 部作品
      </p>
    </div>
  </button>
</template>
