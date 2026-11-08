<script setup lang="ts">
import { computed } from 'vue'
import { Fan, Flame, Lightbulb, Minus, Plus, Wind } from 'lucide-vue-next'
import type { Device } from '../../api'
import { sendCommand } from '../../store'
import TileHeader from './TileHeader.vue'

const props = defineProps<{ device: Device }>()

const FUNCTIONS = [
  { key: 'light', name: '照明', icon: Lightbulb },
  { key: 'heating', name: '暖风', icon: Flame },
  { key: 'blow', name: '吹风', icon: Wind },
  { key: 'ventilation', name: '换气', icon: Fan },
] as const

const s = computed(() => props.device.state)
const online = computed(() => !!s.value.online)
const status = computed(() => {
  if (!online.value) return '离线'
  const temp = s.value.temperature !== undefined ? `室温 ${s.value.temperature}° · ` : ''
  const on = FUNCTIONS.filter((f) => s.value[f.key]).map((f) => f.name)
  return `${temp}${on.length ? on.join('、') : '已关闭'}`
})

function flip(key: (typeof FUNCTIONS)[number]['key']) {
  const value = !s.value[key]
  const others = FUNCTIONS.some((f) => f.key !== key && s.value[f.key])
  sendCommand(props.device.id, `set_${key}`, value, { [key]: value, power: value || others })
}

function bump(delta: number) {
  const value = Math.min(35, Math.max(25, (s.value.target_temp ?? 30) + delta))
  sendCommand(props.device.id, 'set_temp', value, { target_temp: value })
}
</script>

<template>
  <div class="heater-tile card" :class="{ offline: !online, on: online && s.heating }">
    <TileHeader kind="bath_heater" :name="device.name" :status="status" :active="online && !!s.power" />
    <template v-if="online">
      <div class="functions">
        <button v-for="f in FUNCTIONS" :key="f.key" :class="[f.key, { selected: s[f.key] }]" @click="flip(f.key)">
          <component :is="f.icon" :size="22" />
          <span>{{ f.name }}</span>
        </button>
      </div>
      <div v-if="s.heating" class="target">
        <span>目标温度</span>
        <button @click="bump(-1)"><Minus :size="16" /></button>
        <b class="num">{{ s.target_temp }}°</b>
        <button @click="bump(1)"><Plus :size="16" /></button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.heater-tile {
  padding: 16px;
  transition: background 0.3s;
}
.heater-tile.on {
  background: var(--heat-glow);
}
.offline {
  opacity: 0.5;
}
.functions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 16px;
}
.functions button {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 0 12px;
  border-radius: 16px;
  background: var(--surface-2);
  color: var(--text-2);
  font-size: 12px;
  transition: all 0.2s;
}
.functions button.selected {
  color: #fff;
  font-weight: 600;
}
.functions .light.selected {
  background: var(--warm);
  box-shadow: var(--shadow-warm);
}
.functions .heating.selected {
  background: var(--heat);
}
.functions .blow.selected,
.functions .ventilation.selected {
  background: var(--cool);
}
.target {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
  font-size: 13px;
  color: var(--text-2);
}
.target span {
  flex: 1;
}
.target button {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: var(--shadow-1);
  display: flex;
  align-items: center;
  justify-content: center;
}
.target b {
  font-size: 20px;
  font-weight: 600;
  min-width: 40px;
  text-align: center;
}
</style>
