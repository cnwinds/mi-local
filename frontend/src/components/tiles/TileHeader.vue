<script setup lang="ts">
import type { Kind } from '../../api'
import DeviceIcon from '../DeviceIcon.vue'

defineProps<{ kind: Kind; model?: string; name: string; status: string; active?: boolean; tone?: 'warm' | 'cool' | 'heat' | 'accent' }>()
</script>

<template>
  <div class="tile-header">
    <DeviceIcon :kind="kind" :model="model" :active="active" :tone="tone" :size="42" />
    <div class="text">
      <div class="name">{{ name }}</div>
      <div class="status">{{ status }}</div>
    </div>
    <slot />
  </div>
</template>

<style scoped>
.tile-header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.text {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.status {
  margin-top: 2px;
  font-size: 13px;
  color: var(--text-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
