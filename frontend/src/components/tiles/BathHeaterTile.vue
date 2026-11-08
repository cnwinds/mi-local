<script setup lang="ts">
import { computed } from 'vue'
import type { Device } from '../../api'
import { sendCommand } from '../../store'
import TileHeader from './TileHeader.vue'

const props = defineProps<{ device: Device }>()

const FUNCTIONS = [
  { key: 'light', name: '照明', icon: 'bulb-o' },
  { key: 'heating', name: '暖风', icon: 'fire-o' },
  { key: 'blow', name: '吹风', icon: 'filter-o' },
  { key: 'ventilation', name: '换气', icon: 'replay' },
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
  <div class="heater-tile" :class="{ offline: !online, on: online && s.power }">
    <TileHeader kind="bath_heater" :name="device.name" :status="status" :active="online && !!s.power" />
    <template v-if="online">
      <div class="functions">
        <button v-for="f in FUNCTIONS" :key="f.key" :class="{ selected: s[f.key] }" @click="flip(f.key)">
          <van-icon :name="f.icon" />
          <span>{{ f.name }}</span>
        </button>
      </div>
      <div v-if="s.heating" class="target">
        <span>目标温度</span>
        <button @click="bump(-1)">−</button>
        <b>{{ s.target_temp }}°</b>
        <button @click="bump(1)">+</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.heater-tile {
  background: #fff;
  border-radius: 18px;
  padding: 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.heater-tile.on {
  background: linear-gradient(160deg, #fff4e5, #fff 70%);
}
.offline {
  opacity: 0.5;
}
button {
  border: none;
  font: inherit;
  -webkit-tap-highlight-color: transparent;
}
.functions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-top: 12px;
}
.functions button {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 0;
  border-radius: 14px;
  background: #f0f1f4;
  color: #646a73;
  font-size: 12px;
}
.functions .van-icon {
  font-size: 22px;
}
.functions button.selected {
  background: #f5a623;
  color: #fff;
}
.target {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  font-size: 13px;
  color: #646a73;
}
.target span {
  flex: 1;
}
.target button {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: #f0f1f4;
  font-size: 18px;
}
.target b {
  font-size: 18px;
  color: #1f2329;
  min-width: 36px;
  text-align: center;
}
</style>
