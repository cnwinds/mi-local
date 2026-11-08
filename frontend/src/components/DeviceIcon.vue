<script setup lang="ts">
import type { Kind } from '../api'

defineProps<{ kind: Kind; active?: boolean }>()
</script>

<template>
  <div class="icon" :class="[kind, { active }]">
    <svg v-if="kind === 'light'" viewBox="0 0 24 24"><path d="M9 21h6v-1H9v1zm3-19a7 7 0 0 0-4 12.7V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.3A7 7 0 0 0 12 2z" /></svg>
    <svg v-else-if="kind === 'curtain'" viewBox="0 0 24 24"><path d="M3 3h18v2h-1v16h-2V5h-3c0 6 2 9 4 12h-3c-1.5-2-3-5-3-12-.1 7-1.5 10-3 12H7c2-3 4-6 4-12H6v16H4V5H3V3z" /></svg>
    <svg v-else-if="kind === 'plug'" viewBox="0 0 24 24"><path d="M16 7V3h-2v4h-4V3H8v4a2 2 0 0 0-2 2v4l4 4v4h4v-4l4-4V9a2 2 0 0 0-2-2z" /></svg>
    <svg v-else-if="kind === 'switch'" viewBox="0 0 24 24"><path d="M6 3h12a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3zm6 5a4 4 0 1 0 0 8 4 4 0 0 0 0-8z" /></svg>
    <svg v-else-if="kind === 'doorbell'" viewBox="0 0 24 24"><path d="M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2zm6-6V11a6 6 0 0 0-5-5.9V4a1 1 0 0 0-2 0v1.1A6 6 0 0 0 6 11v5l-2 2v1h16v-1l-2-2z" /></svg>
    <svg v-else-if="kind === 'ac'" viewBox="0 0 24 24"><path d="M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5zm3 5h12V9H6v1zm1 5h2c0 2-1 3-2 5H5c1-2 2-3 2-5zm4 0h2v5h-2v-5zm4 0h2c0 2 1 3 2 5h-2c-1-2-2-3-2-5z" /></svg>
    <svg v-else-if="kind === 'bath_heater'" viewBox="0 0 24 24"><path d="M4 3h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm8 2.5a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM7 16h2c0 1.5-1 2.5-1 4H6c0-1.5 1-2.5 1-4zm4 0h2c0 1.5-1 2.5-1 4h-2c0-1.5 1-2.5 1-4zm4 0h2c0 1.5-1 2.5-1 4h-2c0-1.5 1-2.5 1-4z" /></svg>
    <svg v-else-if="kind === 'airer'" viewBox="0 0 24 24"><path d="M2 4h20v3H2V4zm3 4h2v4H5V8zm12 0h2v4h-2V8zM3 12h18l-2 9H5l-2-9zm9-10l2 2h-4l2-2z" /></svg>
    <svg v-else viewBox="0 0 24 24"><path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-6v2h3v2H7v-2h3v-2H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" /></svg>
  </div>
</template>

<style scoped>
.icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f1f4;
  transition: background 0.2s;
}
.icon svg {
  width: 24px;
  height: 24px;
  fill: #9aa0ab;
  transition: fill 0.2s;
}
.icon.active {
  background: #e8f0ff;
}
.icon.active svg {
  fill: #3e7bfa;
}
.icon.light.active {
  background: #fff3d6;
}
.icon.light.active svg,
.icon.bath_heater.active svg {
  fill: #f5a623;
}
.icon.bath_heater.active {
  background: #fff3d6;
}
.icon.ac.active {
  background: #e3f4ff;
}
.icon.ac.active svg {
  fill: #1e9bf0;
}
</style>
