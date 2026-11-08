<script setup lang="ts">
import type { Kind } from '../../api'
import DeviceIcon from '../DeviceIcon.vue'

defineProps<{ kind: Kind; name: string; status: string; active?: boolean }>()
</script>

<template>
  <div class="tile-header">
    <DeviceIcon :kind="kind" :active="active" class="icon" />
    <div class="text">
      <div class="name">{{ name }}</div>
      <div class="status" :class="{ active }">{{ status }}</div>
    </div>
    <slot />
  </div>
</template>

<style scoped>
.tile-header {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.icon {
  flex: none;
}
.text {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 15px;
  font-weight: 500;
  color: #1f2329;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.status {
  margin-top: 2px;
  font-size: 12px;
  color: #8f959e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.status.active {
  color: #3e7bfa;
}
</style>
