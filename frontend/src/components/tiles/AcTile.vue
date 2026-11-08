<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch, type Component } from 'vue'
import { Droplet, Flame, Minus, MoveVertical, Plus, Power, Snowflake, Sparkles, Wind } from 'lucide-vue-next'
import type { AcCaps, AcMode, Device } from '../../api'
import { sendCommand } from '../../store'
import { AC_MODE_NAMES } from '../../rooms'
import TileHeader from './TileHeader.vue'

const props = defineProps<{ device: Device }>()

const DEFAULT_CAPS: AcCaps = { modes: ['cool', 'heat', 'dry', 'fan'], temp_min: 16, temp_max: 31, temp_step: 1, fan_levels: 3 }
const MODE_ICONS: Record<AcMode, Component> = { cool: Snowflake, heat: Flame, dry: Droplet, fan: Wind, auto: Sparkles }

const s = computed(() => props.device.state)
const caps = computed(() => s.value.caps ?? DEFAULT_CAPS)
const online = computed(() => !!s.value.online)
const on = computed(() => online.value && !!s.value.power)
const tone = computed(() => (s.value.mode === 'heat' ? 'heat' : 'cool'))

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
  <div class="ac-tile card" :class="[tone, { on, offline: !online }]">
    <TileHeader kind="ac" :name="device.name" :status="status" :active="on" :tone="tone">
      <button v-if="online" class="power" :class="{ on }" :title="on ? '关机' : '开机'" @click="power">
        <Power :size="20" :stroke-width="2.4" />
      </button>
    </TileHeader>

    <template v-if="on">
      <div class="dial">
        <button class="step" :disabled="target <= caps.temp_min" @click="bump(-1)"><Minus :size="22" /></button>
        <div class="temp num">{{ target }}<span class="unit">°C</span></div>
        <button class="step" :disabled="target >= caps.temp_max" @click="bump(1)"><Plus :size="22" /></button>
      </div>
      <div class="segmented">
        <button v-for="m in caps.modes" :key="m" :class="{ selected: s.mode === m }" @click="setMode(m)">
          <component :is="MODE_ICONS[m]" :size="16" />{{ AC_MODE_NAMES[m] }}
        </button>
      </div>
      <div class="fan-row">
        <span class="label"><Wind :size="14" />风速</span>
        <div class="fans">
          <button v-for="f in fanOptions" :key="f.value" :class="{ selected: s.fan_level === f.value }" @click="setFan(f.value)">
            {{ f.label }}
          </button>
        </div>
        <button class="swing" :class="{ selected: s.swing }" @click="setSwing"><MoveVertical :size="14" />摆风</button>
      </div>
    </template>
    <button v-else-if="online" class="start" @click="power">
      <Power :size="18" />开机 · {{ AC_MODE_NAMES[s.mode ?? 'cool'] }} <span class="num">{{ s.target_temp ?? '' }}°</span>
    </button>
  </div>
</template>

<style scoped>
.ac-tile {
  padding: 16px;
  transition: background 0.3s;
}
.ac-tile.on.cool {
  background: var(--cool-glow);
}
.ac-tile.on.heat {
  background: var(--heat-glow);
}
.offline {
  opacity: 0.5;
}
.power {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-3);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.cool .power.on {
  background: var(--cool);
  color: #fff;
  box-shadow: 0 6px 18px rgba(42, 149, 245, 0.35);
}
.heat .power.on {
  background: var(--heat);
  color: #fff;
  box-shadow: 0 6px 18px rgba(242, 107, 42, 0.35);
}
.dial {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 18px 8px 16px;
}
.step {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: var(--shadow-1);
  color: var(--text);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.1s;
}
.step:disabled {
  opacity: 0.3;
}
.step:active {
  transform: scale(0.92);
}
.temp {
  font-size: 56px;
  font-weight: 250;
  line-height: 1;
}
.unit {
  font-size: 18px;
  font-weight: 400;
  margin-left: 2px;
  color: var(--text-3);
  vertical-align: top;
}
.segmented {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: 14px;
  background: var(--surface-2);
}
.segmented button {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 36px;
  border-radius: 11px;
  font-size: 13px;
  color: var(--text-2);
  transition: all 0.2s;
}
.segmented button.selected {
  background: var(--surface);
  color: var(--text);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}
.cool .segmented button.selected svg {
  color: var(--cool);
}
.heat .segmented button.selected svg {
  color: var(--heat);
}
.fan-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-3);
  flex: none;
}
.fans {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  flex: 1;
  scrollbar-width: none;
}
.fans::-webkit-scrollbar {
  display: none;
}
.fans button,
.swing {
  flex: none;
  min-width: 34px;
  height: 30px;
  padding: 0 8px;
  border-radius: 10px;
  background: var(--surface-2);
  font-size: 12px;
  color: var(--text-2);
}
.swing {
  display: flex;
  align-items: center;
  gap: 3px;
}
.fans button.selected,
.swing.selected {
  background: var(--text);
  color: var(--surface);
  font-weight: 600;
}
.start {
  width: 100%;
  margin-top: 14px;
  height: 48px;
  border-radius: 14px;
  background: var(--cool-soft);
  color: var(--cool);
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.heat .start {
  background: var(--heat-soft);
  color: var(--heat);
}
</style>
