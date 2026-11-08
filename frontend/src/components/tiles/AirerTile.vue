<script setup lang="ts">
import { computed } from 'vue'
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
  <div class="airer-tile" :class="{ offline: !online }">
    <TileHeader kind="airer" :name="device.name" :status="status" :active="online && s.motor !== 'stop' && !!s.motor" />
    <div v-if="online" class="buttons">
      <button @click="move('up')"><van-icon name="arrow-up" />升起</button>
      <button @click="move('stop')"><van-icon name="pause" />暂停</button>
      <button @click="move('down')"><van-icon name="arrow-down" />降下</button>
      <button :class="{ selected: s.light }" @click="light"><van-icon name="bulb-o" />照明</button>
    </div>
  </div>
</template>

<style scoped>
.airer-tile {
  background: #fff;
  border-radius: 18px;
  padding: 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.offline {
  opacity: 0.5;
}
.buttons {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 12px;
}
.buttons button {
  border: none;
  font: inherit;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 0;
  border-radius: 14px;
  background: #f0f1f4;
  color: #1f2329;
  font-size: 12px;
  -webkit-tap-highlight-color: transparent;
}
.buttons .van-icon {
  font-size: 20px;
}
.buttons button:active {
  background: #e3e6ea;
}
.buttons button.selected {
  background: #f5a623;
  color: #fff;
}
</style>
