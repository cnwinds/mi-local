<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch, type Component } from 'vue'
import { Droplet, Flame, Lightbulb, Minus, Plus, Power, Snowflake, Sparkles, Sun, Wind } from 'lucide-vue-next'
import type { AcMode, Device } from '../../api'
import { sendCommand } from '../../store'
import { isActive, lightsOf, quickToggle, roomDevices, roomSize, setRoomBrightness, shortName, toggleLights } from '../../rooms'
import { openRoom } from '../../router'
import DeviceIcon from '../DeviceIcon.vue'
import CurtainGlyph from './CurtainGlyph.vue'

const props = defineProps<{ room: string }>()

const MODE_ICONS: Record<AcMode, Component> = { cool: Snowflake, heat: Flame, dry: Droplet, fan: Wind, auto: Sparkles }
const MODE_ORDER: AcMode[] = ['cool', 'heat', 'dry', 'fan', 'auto']
const KEY_ORDER = ['lock', 'ac', 'light', 'curtain', 'bath_heater', 'airer', 'plug', 'other']
const TONES: Record<string, string> = { light: 'warm', airer: 'warm', bath_heater: 'heat', lock: 'heat', ac: 'cool' }

// Speakers and the doorbell have nothing to show or toggle here.
const list = computed(() => roomDevices(props.room).filter((d) => d.kind !== 'doorbell' && !d.model.includes('wifispeaker')))
const size = computed(() => roomSize(list.value))
const onlineLights = computed(() => lightsOf(list.value))
const litLights = computed(() => onlineLights.value.filter((d) => d.state.power))
const ac = computed(() => list.value.find((d) => d.kind === 'ac' && d.state.online) ?? list.value.find((d) => d.kind === 'ac'))
const acOn = computed(() => !!ac.value?.state.online && !!ac.value.state.power)
const acMode = computed<AcMode>(() => ac.value?.state.mode ?? 'auto')
const temp = computed(() => list.value.find((d) => d.state.online && d.state.temperature !== undefined)?.state.temperature)
const doorOpen = computed(() => list.value.some((d) => d.kind === 'lock' && d.state.online && d.state.door === 'open'))

// The big tile has a dedicated AC panel, so its AC does not get a key.
const keyDevices = computed(() =>
  list.value
    .filter((d) => !(size.value === 'l' && d.id === ac.value?.id))
    .sort((a, b) => KEY_ORDER.indexOf(a.kind) - KEY_ORDER.indexOf(b.kind)),
)

// Keys sit on a square grid sized to the tile; columns follow the available width.
const GAP = 8
const keysEl = ref<HTMLElement>()
const width = ref(0)
const observer = new ResizeObserver(([e]) => (width.value = e.contentRect.width))
watch(keysEl, (el, old) => {
  if (old) observer.unobserve(old)
  if (el) observer.observe(el)
})
onBeforeUnmount(() => observer.disconnect())
const cols = computed(() => Math.max(3, Math.floor((width.value + GAP) / ((size.value === 's' ? 40 : 52) + GAP))))
const cell = computed(() => (width.value ? (width.value - (cols.value - 1) * GAP) / cols.value : 48))

// Key shapes: 1 = square, 2 = wide, 4 = big square.
type Span = 1 | 2 | 4
const isMainLight = (d: Device) =>
  d.kind === 'light' && (/ceiling|吸顶|主灯/i.test(`${d.model} ${d.name}`) || list.value.filter((x) => x.kind === 'light').length === 1)
const growRank = (d: Device) => (d.kind === 'ac' ? 0 : isMainLight(d) ? 1 : d.kind === 'curtain' ? 2 : -1)

// Grow the most important keys so the rows end up as full as possible.
const keys = computed(() => {
  const spans = new Map<string, Span>(keyDevices.value.map((d) => [d.id, 1]))
  const growable = keyDevices.value.filter((d) => growRank(d) >= 0).sort((a, b) => growRank(a) - growRank(b))
  const used = () => [...spans.values()].reduce<number>((a, s) => a + s, 0)
  const rows = Math.ceil(keyDevices.value.length / cols.value)
  let free = rows * cols.value - used()
  for (const d of growable) {
    if (free < 1) break
    spans.set(d.id, 2)
    free -= 1
  }
  if (rows >= 2) {
    for (const d of growable) {
      if (free < 2) break
      spans.set(d.id, 4)
      free -= 2
    }
  }
  return keyDevices.value
    .map((d) => ({ d, span: spans.get(d.id)! }))
    .sort((a, b) => b.span - a.span)
})
const keyValue = (d: Device) => {
  const s = d.state
  if (!isActive(d)) return ''
  if (d.kind === 'light') return `${s.brightness ?? 100}%`
  if (d.kind === 'curtain') return `${s.position ?? 0}%`
  if (d.kind === 'plug' && s.load_power) return `${s.load_power}W`
  return ''
}

// Ambient light: the warm glow grows with the share of lights on and their brightness.
const lit = computed(() => {
  if (!onlineLights.value.length) return 0
  const sum = litLights.value.reduce((a, d) => a + 0.4 + 0.6 * ((d.state.brightness ?? 100) / 100), 0)
  return Math.min(1, sum / onlineLights.value.length)
})
const tone = computed(() => (acOn.value ? (acMode.value === 'heat' ? 'heat' : 'cool') : ''))

const keyTone = (d: Device) => (d.kind === 'ac' && d.state.mode === 'heat' ? 'heat' : TONES[d.kind] ?? 'accent')
// Lit lights fill up from the bottom by brightness; everything else is all or nothing.
const keyFill = (d: Device) => (!isActive(d) ? 0 : d.kind === 'light' ? 50 + 0.5 * (d.state.brightness ?? 100) : 100)
const keyTitle = (d: Device) => `${d.name}${d.state.online ? '' : '（离线）'}`

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

function cycleMode() {
  const d = ac.value
  if (!d) return
  const modes = MODE_ORDER.filter((m) => d.state.caps?.modes?.includes(m) ?? true)
  const next = modes[(modes.indexOf(acMode.value) + 1) % modes.length]
  sendCommand(d.id, 'set_mode', next, { mode: next })
}

function tap(d: Device) {
  const run = quickToggle(d)
  if (run) run()
  else openRoom(props.room)
}
</script>

<template>
  <div class="room card" :class="[`size-${size}`, tone, { alert: doorOpen }]" :style="{ '--lit': lit }"
    :title="room" @click="openRoom(room)">
    <div class="glow" />

    <header>
      <div class="name">{{ room }}</div>
      <div v-if="temp !== undefined" class="temp num">{{ Math.round(temp) }}°</div>
      <button v-if="size !== 's' && onlineLights.length" class="master" :class="{ on: litLights.length }"
        :title="litLights.length ? '关掉全部灯' : '打开全部灯'" @click.stop="toggleLights(list)">
        <Lightbulb :size="18" :stroke-width="2.2" />
      </button>
    </header>

    <div class="body" @click.stop>
      <!-- Big tile: AC panel — mode dot cycles modes, −/+ set the temperature -->
      <div v-if="size === 'l' && ac" class="ac" :class="[tone, { off: !acOn, offline: !ac.state.online }]">
        <button class="mode" :disabled="!acOn" :title="ac.name" @click="cycleMode">
          <component :is="MODE_ICONS[acMode]" :size="18" :stroke-width="2.2" />
        </button>
        <button class="step" :disabled="!acOn" @click="bump(-1)"><Minus :size="16" /></button>
        <div class="target num">{{ target }}<small>°</small></div>
        <button class="step" :disabled="!acOn" @click="bump(1)"><Plus :size="16" /></button>
        <button class="power" :class="{ on: acOn }" :disabled="!ac.state.online" @click="tap(ac)">
          <Power :size="16" :stroke-width="2.4" />
        </button>
      </div>

      <!-- Big tile: one slider dims the whole room -->
      <div v-if="size === 'l' && onlineLights.length" class="dimmer" :class="{ off: !litLights.length }">
        <Sun :size="13" />
        <van-slider v-model="brightness" :min="1" :max="100" bar-height="6px" active-color="var(--warm)"
          @change="(v: number) => setRoomBrightness(list, v)" />
        <Sun :size="19" />
      </div>

      <div ref="keysEl" class="keys"
        :style="{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gridAutoRows: `${cell}px` }">
        <button v-for="{ d, span } in keys" :key="d.id" class="key"
          :class="[d.kind, keyTone(d), `span-${span}`, { on: isActive(d), offline: !d.state.online }]"
          :style="{ '--fill': `${keyFill(d)}%` }" :title="keyTitle(d)" :aria-label="shortName(d)" @click="tap(d)">
          <template v-if="d.kind === 'ac' && isActive(d)">
            <component :is="MODE_ICONS[d.state.mode ?? 'auto']" :size="span === 1 ? 15 : 20" :stroke-width="2.2" />
            <span class="key-num num">{{ d.state.target_temp }}°</span>
          </template>
          <template v-else>
            <CurtainGlyph v-if="d.kind === 'curtain'" :position="d.state.position ?? 0"
              :size="Math.round(cell * (span === 4 ? 0.8 : 0.48))" />
            <DeviceIcon v-else :kind="d.kind" :model="d.model" :name="d.name"
              :size="Math.round(cell * (span === 4 ? 1.6 : 0.96))" class="key-icon" />
            <span v-if="span > 1 && keyValue(d)" class="key-num num">{{ keyValue(d) }}</span>
          </template>
        </button>
      </div>
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
  gap: 14px;
  min-height: 140px;
  box-sizing: border-box;
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.3s ease;
}
.room:active {
  transform: scale(0.985);
}
.size-m {
  grid-column: span 2;
}
.size-l {
  grid-column: span 2;
}
/* Ambient layer: warm from the top left with the lights, AC tint from the top right */
.glow {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(130% 100% at 0% 0%, rgb(255 186 80 / calc(var(--lit) * 0.5)), transparent 65%),
    radial-gradient(90% 80% at 100% 0%, var(--tone-glow, transparent), transparent 70%);
  transition: background 0.6s;
}
.room.cool {
  --tone-glow: rgb(42 149 245 / 0.26);
}
.room.heat {
  --tone-glow: rgb(242 107 42 / 0.26);
}
.room.alert {
  box-shadow: 0 0 0 2px var(--heat), var(--shadow-1);
}
.room > *:not(.glow) {
  position: relative;
}

header {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 36px;
}
.name {
  flex: 1;
  min-width: 0;
  font-size: 16px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.temp {
  font-size: 22px;
  font-weight: 300;
  color: var(--text-2);
}
.size-l .temp {
  font-size: 30px;
}
.master {
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 12px;
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

.body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 14px;
  cursor: default;
}

/* AC panel */
.ac {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px;
  border-radius: 18px;
  background: var(--surface-2);
  transition: background 0.3s;
}
.ac.cool {
  background: var(--cool-soft);
  color: var(--cool);
}
.ac.heat {
  background: var(--heat-soft);
  color: var(--heat);
}
.ac.off {
  color: var(--text-3);
}
.ac.offline {
  opacity: 0.4;
}
.mode,
.step,
.power {
  flex: none;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: inherit;
}
.mode {
  background: currentColor;
}
.mode > * {
  color: #fff;
}
.ac.off .mode {
  background: var(--surface);
}
.ac.off .mode > * {
  color: var(--text-3);
}
.step:disabled,
.mode:disabled {
  cursor: default;
}
.ac.off .step {
  opacity: 0.3;
}
.step:not(:disabled):active,
.mode:not(:disabled):active {
  transform: scale(0.9);
}
.target {
  flex: 1;
  text-align: center;
  font-size: 30px;
  font-weight: 400;
  line-height: 1;
  color: var(--text);
}
.ac.off .target {
  color: var(--text-3);
}
.target small {
  font-size: 15px;
  color: var(--text-3);
}
.power {
  background: var(--surface);
  color: var(--text-3);
  box-shadow: var(--shadow-1);
}
.power.on {
  background: currentColor;
}
.ac .power.on {
  color: inherit;
}
.power.on > * {
  color: #fff;
}

/* Room dimmer */
.dimmer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 6px;
  color: var(--warm-strong);
}
.dimmer.off {
  color: var(--text-3);
}
.dimmer .van-slider {
  flex: 1;
}

/* Device keys: color says what it is, fill says how much */
.keys {
  display: grid;
  grid-auto-flow: row dense;
  gap: 8px;
}
.key {
  --c: var(--accent);
  --c-soft: var(--accent-soft);
  --rest: var(--surface-2);
  position: relative;
  min-width: 0;
  overflow: hidden;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  color: var(--text-3);
  background: linear-gradient(to top, var(--c) var(--fill), var(--rest) var(--fill));
  transition: background 0.35s, color 0.2s, box-shadow 0.3s, transform 0.1s;
}
.key:active {
  transform: scale(0.92);
}
.key.warm {
  --c: var(--warm);
  --c-soft: var(--warm-soft);
}
.key.cool {
  --c: var(--cool);
  --c-soft: var(--cool-soft);
}
.key.heat {
  --c: var(--heat);
  --c-soft: var(--heat-soft);
}
.key.on {
  --rest: var(--c-soft);
  color: #fff;
}
.key.light.on {
  box-shadow: var(--shadow-warm);
}
.key.lock.on {
  animation: pulse 1.6s ease-in-out infinite;
}
.key.offline {
  opacity: 0.35;
}
.key-icon {
  background: transparent !important;
  box-shadow: none !important;
  color: inherit !important;
}
.key-num {
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}
@keyframes pulse {
  50% {
    box-shadow: 0 0 0 6px rgb(242 107 42 / 0.25);
  }
}

/* Wide and big keys: icon on the left, live value on the right */
.key.span-2 {
  grid-column: span 2;
  flex-direction: row;
  justify-content: space-between;
  padding: 0 14px 0 6px;
}
.key.span-4 {
  grid-column: span 2;
  grid-row: span 2;
  border-radius: 22px;
}
.key.ac.span-2 {
  justify-content: center;
  gap: 8px;
  padding: 0 12px;
}
.key.curtain.span-2 {
  padding-left: 14px;
}
.key.span-2 .key-num {
  font-size: 15px;
}
.key.ac.span-2 .key-num {
  font-size: 20px;
  font-weight: 500;
}
.key.span-4 .key-num {
  position: absolute;
  right: 12px;
  bottom: 10px;
  font-size: 16px;
}

@media (min-width: 900px) {
  .room {
    padding: 18px;
    min-height: 160px;
  }
}
</style>
