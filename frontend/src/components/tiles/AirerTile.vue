<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown, ArrowUp, Lightbulb, Pause } from 'lucide-vue-next'
import type { Device } from '../../api'
import { sendCommand } from '../../store'
import TileHeader from './TileHeader.vue'

const props = defineProps<{ device: Device }>()

const s = computed(() => props.device.state)
const online = computed(() => !!s.value.online)
const status = computed(() => {
  if (!online.value) return '离线'
  const motor = { up: '上升中', down: '下降中', stop: '' }[s.value.motor ?? 'stop']
  return [motor, s.value.light ? '照明开' : ''].filter(Boolean).join(' · ') || '待机'
})
const move = (action: 'up' | 'down' | 'stop') => sendCommand(props.device.id, action, undefined, { motor: action })
const light = () => sendCommand(props.device.id, 'set_light', !s.value.light, { light: !s.value.light, power: !s.value.light })
</script>

<template>
  <div class="airer-tile card" :class="{ offline: !online }">
    <TileHeader kind="airer" :name="device.name" :status="status" :active="online && !!s.motor && s.motor !== 'stop'" />
    <div v-if="online" class="buttons">
      <button :class="{ moving: s.motor === 'up' }" @click="move('up')"><ArrowUp :size="22" />升起</button>
      <button @click="move('stop')"><Pause :size="22" />暂停</button>
      <button :class="{ moving: s.motor === 'down' }" @click="move('down')"><ArrowDown :size="22" />降下</button>
      <button class="light" :class="{ selected: s.light }" @click="light"><Lightbulb :size="22" />照明</button>
    </div>
  </div>
</template>

<style scoped>
.airer-tile {
  padding: 16px;
}
.offline {
  opacity: 0.5;
}
.buttons {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 16px;
}
.buttons button {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 0 12px;
  border-radius: 16px;
  background: var(--surface-2);
  font-size: 12px;
  color: var(--text-2);
  transition: all 0.2s;
}
.buttons button:active {
  background: var(--surface-3);
}
.buttons button.moving {
  background: var(--accent);
  color: #fff;
}
.buttons .light.selected {
  background: var(--warm);
  color: #fff;
  box-shadow: var(--shadow-warm);
}
</style>
