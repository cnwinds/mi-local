<script setup lang="ts">
import { computed } from 'vue'

// A window whose two curtain panels close in as the position drops (0 = closed, 100 = open).
const props = defineProps<{ position: number; size?: number }>()
const panel = computed(() => 10 * (1 - Math.min(100, Math.max(0, props.position)) / 100) + 1.2)
</script>

<template>
  <svg :width="size ?? 18" :height="size ?? 18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
    stroke-linecap="round">
    <path d="M2 3h20" />
    <rect x="3" y="5" width="18" height="16" rx="1.5" stroke-opacity="0.35" />
    <rect x="3" y="5" :width="panel" height="16" rx="1" fill="currentColor" fill-opacity="0.55" stroke="none" />
    <rect :x="21 - panel" y="5" :width="panel" height="16" rx="1" fill="currentColor" fill-opacity="0.55" stroke="none" />
  </svg>
</template>
