<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch, type Component } from 'vue'
import { Droplet, Flame, Lightbulb, Minus, Plus, Power, Snowflake, Sparkles, Wind } from 'lucide-vue-next'
import type { AcMode, Device } from '../../api'
import { sendCommand } from '../../store'
import {
  AC_MODE_NAMES, isActive, lightsOf, quickToggle, roomDevices, roomSize, roomSummary, setRoomBrightness, shortName,
  toggleLights,
} from '../../rooms'
import { openRoom } from '../../router'
import DeviceIcon from '../DeviceIcon.vue'
import CurtainGlyph from './CurtainGlyph.vue'

const props = defineProps<{ room: string }>()

const MODE_ICONS: Record<AcMode, Component> = { cool: Snowflake, heat: Flame, dry: Droplet, fan: Wind, auto: Sparkles }
const CHIP_ORDER = ['lock', 'light', 'curtain', 'bath_heater', 'airer', 'plug', 'other']

// Speakers and the doorbell have nothing to show or toggle here.
const list = computed(() => roomDevices(props.room).filter((d) => d.kind !== 'doorbell' && !d.model.includes('wifispeaker')))
const size = computed(() => roomSize(list.value))
const lights = computed(() => list.value.filter((d) => d.kind === 'light'))
const onlineLights = computed(() => lightsOf(list.value))
const litLights = computed(() => onlineLights.value.filter((d) => d.state.power))
const ac = computed(() => list.value.find((d) => d.kind === 'ac' && d.state.online) ?? list.value.find((d) => d.kind === 'ac'))
const acOn = computed(() => !!ac.value?.state.online && !!ac.value.state.power)
const temp = computed(() => list.value.find((d) => d.state.online && d.state.temperature !== undefined)?.state.temperature)
const doorOpen = computed(() => list.value.find((d) => d.kind === 'lock' && d.state.online && d.state.door === 'open'))

const chips = computed(() =>
  list.value
    .filter((d) => d.kind !== 'ac')
    .sort((a, b) => CHIP_ORDER.indexOf(a.kind) - CHIP_ORDER.indexOf(b.kind)),
)
const smallChips = computed(() => [...(ac.value ? [ac.value] : []), ...chips.value].slice(0, 3))

// Ambient light: the warm glow grows with the share of lights on and their brightness.
const lit = computed(() => {
  if (!onlineLights.value.length) return 0
  const sum = litLights.value.reduce((a, d) => a + 0.4 + 0.6 * ((d.state.brightness ?? 100) / 100), 0)
  return Math.min(1, sum / onlineLights.value.length)
})
const tone = computed(() => (acOn.value ? (ac.value!.state.mode === 'heat' ? 'heat' : 'cool') : ''))

const summary = computed(() => roomSummary(props.room).filter((s) => !s.startsWith('室温') && !s.endsWith('台设备在线')))
const headline = computed(() => {
  if (doorOpen.value) return `${shortName(doorOpen.value)}开着`
  if (lights.value.length) return litLights.value.length ? `${litLights.value.length}/${lights.value.length} 灯亮` : '灯都关着'
  const running = list.value.find((d) => isActive(d) && d.kind !== 'lock')
  if (running) return `${shortName(running)}运行中`
  return list.value.some((d) => d.state.online) ? '一切正常' : '设备离线'
})

// Room brightness slider: shows the brightest lit light, applies to every light.
const brightness = ref(0)
watch(
  litLights,
  (v) => (brightness.value = v.length ? Math.max(...v.map((d) => d.state.brightness ?? 100)) : 0),
  { immediate: true },
)

// AC temperature taps are collected briefly so several presses become one command.
const target = ref(26)
let timer: ReturnType<typeof setTimeout> | undefined
watch(
  () => ac.value?.state.target_temp,
  (v) => {
    if (!timer && v !== undefined) target.value = v
  },
  { immediate: true },
)
function bump(delta: number) {
  const d = ac.value
  if (!d) return
  const caps = d.state.caps ?? { temp_min: 16, temp_max: 31, temp_step: 1 }
  target.value = Math.min(caps.temp_max, Math.max(caps.temp_min, Math.round((target.value + delta * caps.temp_step) * 10) / 10))
  clearTimeout(timer)
  timer = setTimeout(() => {
    timer = undefined
    sendCommand(d.id, 'set_temp', target.value, { target_temp: target.value })
  }, 700)
}
onBeforeUnmount(() => clearTimeout(timer))

function tap(d: Device) {
  const run = quickToggle(d)
  if (run) run()
  else openRoom(props.room)
}
const chipLabel = (d: Device) => (d.kind === 'ac' && acOn.value ? `${AC_MODE_NAMES[d.state.mode ?? 'auto']} ${d.state.target_temp}°` : shortName(d))
const chipMeta = (d: Device) => {
  const s = d.state
  if (!s.online) return '离线'
  if (d.kind === 'plug' && s.power) return `${s.load_power ?? 0}W`
  if (d.kind === 'lock') return s.door === 'open' ? '开着' : s.door === 'closed' ? '已关' : ''
  if (size.value !== 'l') return ''
  if (d.kind === 'light') return s.power ? `${s.brightness ?? 100}%` : '关'
  if (d.kind === 'curtain') return `${s.position ?? 0}%`
  if (d.kind === 'airer') return s.light ? '灯亮' : ''
  return s.power === undefined ? '' : s.power ? '开' : '关'
}
</script>

<template>
  <div class="room card" :class="[`size-${size}`, tone, { lit: lit > 0, alert: doorOpen }]" :style="{ '--lit': lit }"
    @click="openRoom(room)">
    <div class="glow" />

    <header>
      <div class="title">
        <div class="name">{{ room }}</div>
        <div class="headline">{{ size === 's' ? headline : summary.join(' · ') || headline }}</div>
      </div>
      <div v-if="temp !== undefined" class="temp num">{{ temp }}<sup>°</sup></div>
      <button v-if="size !== 's' && onlineLights.length" class="master" :class="{ on: litLights.length }"
        :title="litLights.length ? '关掉全部灯' : '打开全部灯'" @click.stop="toggleLights(list)">
        <Lightbulb :size="20" :stroke-width="2.2" />
      </button>
    </header>

    <!-- Big tile: the AC gets a real control strip -->
    <div v-if="size === 'l' && ac" class="ac" :class="[tone, { off: !acOn }]" @click.stop>
      <template v-if="acOn">
        <div class="ac-mode">
          <component :is="MODE_ICONS[ac.state.mode ?? 'auto']" :size="16" />{{ AC_MODE_NAMES[ac.state.mode ?? 'auto'] }}
        </div>
        <button class="step" @click="bump(-1)"><Minus :size="16" /></button>
        <div class="target num">{{ target }}<small>°</small></div>
        <button class="step" @click="bump(1)"><Plus :size="16" /></button>
      </template>
      <div v-else class="ac-mode">{{ ac.state.online ? `${shortName(ac)}已关闭` : `${shortName(ac)}离线` }}</div>
      <button v-if="ac.state.online" class="ac-power" :class="{ on: acOn }" @click="tap(ac)"><Power :size="16" :stroke-width="2.4" /></button>
    </div>

    <!-- Big tile: one slider dims the whole room -->
    <div v-if="size === 'l' && onlineLights.length" class="dimmer" @click.stop>
      <Lightbulb :size="15" class="dim-icon" />
      <van-slider v-model="brightness" :min="1" :max="100" bar-height="8px" active-color="var(--warm)"
        @change="(v: number) => setRoomBrightness(list, v)" />
      <span class="num dim-value">{{ litLights.length ? `${brightness}%` : '关' }}</span>
    </div>

    <!-- Small tile: up to three round buttons -->
    <div v-if="size === 's'" class="dots" @click.stop>
      <button v-for="d in smallChips" :key="d.id" class="dot" :class="[d.kind, { on: isActive(d), offline: !d.state.online }]"
        :title="d.name" @click="tap(d)">
        <CurtainGlyph v-if="d.kind === 'curtain'" :position="d.state.position ?? 0" :size="20" />
        <DeviceIcon v-else :kind="d.kind" :model="d.model" :size="40" class="dot-icon" />
      </button>
    </div>

    <!-- Wide and big tiles: a chip per device -->
    <div v-else class="chips" @click.stop>
      <button v-if="size === 'm' && ac" class="chip ac-chip" :class="[tone, { on: acOn, offline: !ac.state.online }]" @click="tap(ac)">
        <component :is="acOn ? MODE_ICONS[ac.state.mode ?? 'auto'] : Power" :size="15" />
        <span class="chip-name">{{ chipLabel(ac) }}</span>
      </button>
      <button v-for="d in chips" :key="d.id" class="chip" :class="[d.kind, { on: isActive(d), offline: !d.state.online }]"
        :title="d.name" @click="tap(d)">
        <CurtainGlyph v-if="d.kind === 'curtain'" :position="d.state.position ?? 0" :size="16" />
        <DeviceIcon v-else :kind="d.kind" :model="d.model" :size="22" class="chip-icon" />
        <span class="chip-name">{{ chipLabel(d) }}</span>
        <span v-if="chipMeta(d)" class="chip-meta num">{{ chipMeta(d) }}</span>
        <span v-if="d.kind === 'light' && d.state.online && d.state.power" class="level" :style="{ width: `${d.state.brightness ?? 100}%` }" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.room {
  position: relative;
  overflow: hidden;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.2s ease;
  min-height: 150px;
  box-sizing: border-box;
}
.room:active {
  transform: scale(0.985);
}
.size-m {
  grid-column: span 2;
}
.size-l {
  grid-column: span 2;
  grid-row: span 2;
}
/* Ambient layer: warm from the top left with the lights, AC tint from the top right */
.glow {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(130% 100% at 0% 0%, rgb(255 186 80 / calc(var(--lit) * 0.55)), transparent 65%),
    radial-gradient(90% 80% at 100% 0%, var(--tone-glow, transparent), transparent 70%);
  transition: background 0.6s;
}
.room.cool {
  --tone-glow: rgb(42 149 245 / 0.28);
}
.room.heat {
  --tone-glow: rgb(242 107 42 / 0.28);
}
.room.alert {
  box-shadow: 0 0 0 2px var(--heat), var(--shadow-1);
}
.room > *:not(.glow) {
  position: relative;
}

header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.title {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.headline {
  margin-top: 3px;
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.size-s .headline {
  margin-top: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}
.size-s.lit .headline {
  color: var(--warm-strong);
}
.alert .headline {
  color: var(--heat);
  font-weight: 600;
}
.temp {
  font-size: 26px;
  font-weight: 300;
  line-height: 1;
  color: var(--text);
}
.temp sup {
  font-size: 0.55em;
  color: var(--text-3);
  vertical-align: top;
  margin-left: 1px;
}
.size-l .temp {
  font-size: 40px;
}
.master {
  flex: none;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  color: var(--text-3);
  transition: all 0.2s;
}
.master.on {
  background: var(--warm);
  color: #fff;
  box-shadow: var(--shadow-warm);
}

/* AC strip */
.ac {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 8px 8px 14px;
  border-radius: 16px;
  background: var(--surface-2);
  cursor: default;
}
.ac-mode {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}
.ac.cool .ac-mode {
  color: var(--cool);
}
.ac.heat .ac-mode {
  color: var(--heat);
}
.step {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: var(--shadow-1);
  display: flex;
  align-items: center;
  justify-content: center;
}
.step:active {
  transform: scale(0.9);
}
.target {
  min-width: 56px;
  text-align: center;
  font-size: 28px;
  font-weight: 400;
}
.target small {
  font-size: 15px;
  color: var(--text-3);
}
.ac-power {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-3);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ac-power.on {
  background: var(--cool);
  color: #fff;
}
.ac.heat .ac-power.on {
  background: var(--heat);
}

/* Room dimmer */
.dimmer {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px;
  cursor: default;
}
.dim-icon {
  color: var(--warm-strong);
  flex: none;
}
.dimmer .van-slider {
  flex: 1;
}
.dim-value {
  flex: none;
  min-width: 36px;
  text-align: right;
  font-size: 13px;
  color: var(--text-2);
}

/* Small tile buttons */
.dots {
  margin-top: auto;
  display: flex;
  gap: 8px;
  cursor: default;
}
.dot {
  width: 44px;
  height: 44px;
  border-radius: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  color: var(--text-3);
  overflow: hidden;
  transition: all 0.2s;
}
.dot-icon {
  background: transparent !important;
  box-shadow: none !important;
  color: inherit !important;
}
.dot.on {
  background: var(--accent);
  color: #fff;
}
.dot.light.on {
  background: var(--warm);
  box-shadow: var(--shadow-warm);
}
.dot.bath_heater.on,
.dot.lock.on {
  background: var(--heat);
}
.dot.ac.on {
  background: var(--cool);
}

/* Chips */
.chips {
  margin-top: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  cursor: default;
}
.chip {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: 5px;
  height: 36px;
  max-width: 100%;
  padding: 0 11px 0 6px;
  border-radius: 12px;
  background: var(--surface-2);
  color: var(--text-2);
  font-size: 13px;
  transition: all 0.2s;
}
.chip.curtain,
.chip.ac-chip {
  padding-left: 10px;
}
.chip-icon {
  background: transparent !important;
  box-shadow: none !important;
  color: inherit !important;
}
.chip-name {
  min-width: 0;
  max-width: 10em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip-meta {
  font-size: 11px;
  color: var(--text-3);
}
.chip.on {
  background: var(--accent-soft);
  color: var(--accent-text);
  font-weight: 600;
}
.chip.light.on {
  background: var(--warm-soft);
  color: var(--warm-strong);
}
.chip.bath_heater.on,
.chip.lock.on {
  background: var(--heat-soft);
  color: var(--heat);
}
.chip.ac-chip.on {
  background: var(--cool-soft);
  color: var(--cool);
}
.chip.ac-chip.heat.on {
  background: var(--heat-soft);
  color: var(--heat);
}
.chip.offline,
.dot.offline {
  opacity: 0.4;
}
.level {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 3px;
  background: var(--warm);
  border-radius: 0 2px 2px 0;
}
/* Big tile: devices become a grid of keys with their live state */
.size-l .chips {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-auto-rows: 76px;
  gap: 8px;
}
.size-l .chip {
  height: auto;
  flex-direction: column;
  align-items: flex-start;
  justify-content: space-between;
  gap: 4px;
  padding: 10px 12px 12px;
  border-radius: 16px;
}
.size-l .chip-name {
  max-width: 100%;
}
.size-l .chip-icon {
  margin: -6px 0 0 -6px;
}
.size-l .chip.curtain {
  padding-left: 12px;
}
.size-l .chip-meta {
  position: absolute;
  top: 10px;
  right: 11px;
  font-size: 12px;
  font-weight: 500;
}
.size-l .level {
  height: 4px;
}

@media (min-width: 900px) {
  .room {
    padding: 18px;
    min-height: 170px;
  }
}
</style>
