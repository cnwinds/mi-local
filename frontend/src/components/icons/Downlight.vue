<script setup lang="ts">
// A recessed downlight: ceiling line, round housing and rays falling straight down.
withDefaults(defineProps<{ size?: number | string; strokeWidth?: number | string }>(), { size: 24, strokeWidth: 2 })
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="strokeWidth"
    stroke-linecap="round" stroke-linejoin="round">
    <path d="M3 4h18" />
    <path d="M7.5 4v1.5a4.5 4.5 0 0 0 9 0V4" />
    <path d="M12 13.5v5" />
    <path d="M7.8 13l-2.3 4" />
    <path d="M16.2 13l2.3 4" />
  </svg>
</template>
