<script setup lang="ts">
defineProps<{ title: string; subtitle?: string; eyebrow?: string }>()
</script>

<template>
  <header class="page-header">
    <div class="text">
      <div v-if="eyebrow" class="eyebrow">{{ eyebrow }}</div>
      <h1>{{ title }}</h1>
      <div v-if="subtitle" class="subtitle">{{ subtitle }}</div>
    </div>
    <div class="actions"><slot /></div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: calc(24px + env(safe-area-inset-top)) 20px 8px;
}
.text {
  min-width: 0;
}
.eyebrow {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-3);
  margin-bottom: 4px;
}
h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 750;
  letter-spacing: -0.02em;
  line-height: 1.15;
}
.subtitle {
  margin-top: 6px;
  font-size: 14px;
  color: var(--text-2);
}
.actions {
  display: flex;
  gap: 8px;
  flex: none;
}
@media (min-width: 900px) {
  .page-header {
    padding: 28px 4px 8px;
  }
  h1 {
    font-size: 34px;
  }
}
</style>
