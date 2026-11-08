<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { AcCaps, AcMode, Device } from '../../api'
import { sendCommand } from '../../store'
import { AC_MODE_NAMES } from '../../rooms'
import TileHeader from './TileHeader.vue'

const props = defineProps<{ device: Device }>()

const DEFAULT_CAPS: AcCaps = { modes: ['cool', 'heat', 'dry', 'fan'], temp_min: 16, temp_max: 31, temp_step: 1, fan_levels: 3 }
const MODE_ICONS: Record<AcMode, string> = { cool: '❄', heat: '☀', dry: '💧', fan: '༄', auto: 'A' }

const s = computed(() => props.device.state)
const caps = computed(() => s.value.caps ?? DEFAULT_CAPS)
const online = computed(() => !!s.value.online)
const on = computed(() => online.value && !!s.value.power)

// Temperature taps are collected for a moment so several presses become one command.
const target = ref(s.value.target_temp ?? 26)
let timer: ReturnType<typeof setTimeout> | undefined
watch(
  () => s.value.target_temp,
  (v) => {
    if (!timer && v !== undefined) target.value = v
  },
)

function bump(delta: number) {
  const { temp_min, temp_max, temp_step } = caps.value
  target.value = Math.min(temp_max, Math.max(temp_min, Math.round((target.value + delta * temp_step) * 10) / 10))
  clearTimeout(timer)
  timer = setTimeout(() => {
    timer = undefined
    sendCommand(props.device.id, 'set_temp', target.value, { target_temp: target.value })
  }, 700)
}
onBeforeUnmount(() => clearTimeout(timer))

const status = computed(() => {
  if (!online.value) return '离线'
  const room = s.value.temperature !== undefined ? `室温 ${s.value.temperature}° · ` : ''
  return on.value ? `${room}${AC_MODE_NAMES[s.value.mode ?? 'auto']}中` : `${room}已关闭`
})

const fanOptions = computed(() => {
  const n = caps.value.fan_levels
  const names = n === 3 ? ['低', '中', '高'] : Array.from({ length: n }, (_, i) => `${i + 1}`)
  return [{ value: 0, label: '自动' }, ...names.map((label, i) => ({ value: i + 1, label }))]
})

function power() {
  sendCommand(props.device.id, on.value ? 'turn_off' : 'turn_on', undefined, { power: !on.value })
}
const setMode = (m: AcMode) => sendCommand(props.device.id, 'set_mode', m, { mode: m })
const setFan = (v: number) => sendCommand(props.device.id, 'set_fan', v, { fan_level: v })
const setSwing = () => sendCommand(props.device.id, 'set_swing', !s.value.swing, { swing: !s.value.swing })
</script>

<template>
  <div class="ac-tile" :class="[{ on, offline: !online }, on ? s.mode : '']">
    <TileHeader kind="ac" :name="device.name" :status="status" :active="on">
      <button v-if="online" class="power" :class="{ on }" @click="power">
        <svg viewBox="0 0 24 24"><path d="M11 3h2v10h-2V3zm5.6 2.4 1.4-1.4A9 9 0 1 1 6 4l1.4 1.4A7 7 0 1 0 16.6 5.4z" /></svg>
      </button>
    </TileHeader>

    <template v-if="on">
      <div class="temp-row">
        <button class="step" :disabled="target <= caps.temp_min" @click="bump(-1)">−</button>
        <div class="temp">
          {{ target }}<span class="unit">°C</span>
        </div>
        <button class="step" :disabled="target >= caps.temp_max" @click="bump(1)">+</button>
      </div>
      <div class="chips">
        <button v-for="m in caps.modes" :key="m" class="chip" :class="{ selected: s.mode === m }" @click="setMode(m)">
          <span class="mode-icon">{{ MODE_ICONS[m] }}</span>{{ AC_MODE_NAMES[m] }}
        </button>
      </div>
      <div class="chips fan">
        <span class="label">风速</span>
        <button v-for="f in fanOptions" :key="f.value" class="chip small" :class="{ selected: s.fan_level === f.value }"
          @click="setFan(f.value)">{{ f.label }}</button>
        <button class="chip small swing" :class="{ selected: s.swing }" @click="setSwing">摆风</button>
      </div>
    </template>
    <button v-else-if="online" class="start" @click="power">
      开机 · {{ AC_MODE_NAMES[s.mode ?? 'cool'] }} {{ s.target_temp ?? '' }}°
    </button>
  </div>
</template>

<style scoped>
.ac-tile {
  background: #fff;
  border-radius: 18px;
  padding: 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: background 0.3s;
}
.ac-tile.on.cool,
.ac-tile.on.dry,
.ac-tile.on.fan,
.ac-tile.on.auto {
  background: linear-gradient(160deg, #eaf6ff, #fff 70%);
}
.ac-tile.on.heat {
  background: linear-gradient(160deg, #fff1e6, #fff 70%);
}
.offline {
  opacity: 0.5;
}
button {
  border: none;
  font: inherit;
  -webkit-tap-highlight-color: transparent;
}
.power {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #f0f1f4;
  color: #9aa0ab;
  display: flex;
  align-items: center;
  justify-content: center;
}
.power svg {
  width: 20px;
  height: 20px;
  fill: currentColor;
}
.power.on {
  background: #1e9bf0;
  color: #fff;
}
.heat .power.on {
  background: #f57c23;
}
.temp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 14px 4px 10px;
}
.step {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  font-size: 26px;
  color: #1f2329;
}
.step:disabled {
  opacity: 0.3;
}
.step:active {
  transform: scale(0.94);
}
.temp {
  font-size: 48px;
  font-weight: 300;
  color: #1f2329;
  font-variant-numeric: tabular-nums;
}
.unit {
  font-size: 18px;
  margin-left: 2px;
  color: #8f959e;
}
.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.chip {
  flex: 1;
  min-width: 56px;
  padding: 8px 0;
  border-radius: 12px;
  background: #f0f1f4;
  color: #646a73;
  font-size: 13px;
}
.chip.selected {
  background: #1e9bf0;
  color: #fff;
}
.heat .chip.selected {
  background: #f57c23;
}
.mode-icon {
  margin-right: 3px;
}
.fan {
  align-items: center;
}
.label {
  font-size: 12px;
  color: #8f959e;
  margin-right: 2px;
}
.chip.small {
  flex: none;
  min-width: 40px;
  padding: 6px 8px;
}
.swing {
  margin-left: auto;
}
.start {
  width: 100%;
  margin-top: 12px;
  padding: 12px 0;
  border-radius: 14px;
  background: #f0f6ff;
  color: #3e7bfa;
  font-size: 15px;
}
</style>
