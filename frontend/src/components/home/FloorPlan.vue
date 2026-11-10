<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch, type Component } from 'vue'
import { showFailToast, showToast } from 'vant'
import { Cctv, Check, Droplet, Flame, Move, Snowflake, Sparkles, Wind, X } from 'lucide-vue-next'
import { api, type AcMode, type Camera, type Device, type FloorRoom, type PlanPoint } from '../../api'
import { deviceList, floorplan } from '../../store'
import { deviceStatus, isActive, panelRooms, quickToggle, shortName } from '../../rooms'
import { openRoom } from '../../router'
import DeviceIcon from '../DeviceIcon.vue'
import DeviceSheet from '../DeviceSheet.vue'
import CameraFeed from '../CameraFeed.vue'
import CurtainGlyph from './CurtainGlyph.vue'

const MODE_ICONS: Record<AcMode, Component> = { cool: Snowflake, heat: Flame, dry: Droplet, fan: Wind, auto: Sparkles }
const TONES: Record<string, string> = { light: 'warm', airer: 'warm', bath_heater: 'heat', lock: 'heat', ac: 'cool' }
// Switches, the gateway and speakers have no state worth a spot on the map.
const PLAN_KINDS = new Set(['light', 'ac', 'curtain', 'bath_heater', 'airer', 'plug', 'lock', 'other'])
const onPlan = (d: Device) => PLAN_KINDS.has(d.kind) && !d.hidden && !d.model.includes('wifispeaker')
/** Spacing, in plan units, for devices that have not been placed yet. */
const AUTO_GAP = 34
const LONG_PRESS_MS = 550

/**
 * compact: a phone-sized overview where devices shrink to dots and a tap opens the room.
 * wall: full screen on a wall tablet; devices work, but nothing leaves the plan or edits it.
 */
const props = defineProps<{ compact?: boolean; wall?: boolean }>()

const plan = computed(() => floorplan.value!)
const view = computed(() => plan.value.view)
const pct = ([x, y]: PlanPoint) => ({
  left: `${((x - view.value[0]) / view.value[2]) * 100}%`,
  top: `${((y - view.value[1]) / view.value[3]) * 100}%`,
})
const svgPoints = (r: FloorRoom) => r.points.map((p) => p.join(',')).join(' ')

function bbox(points: PlanPoint[]) {
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  const x = Math.min(...xs)
  const y = Math.min(...ys)
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y }
}
const labelAt = (r: FloorRoom): PlanPoint => r.label ?? ((b) => [b.x + 8, b.y + 8] as PlanPoint)(bbox(r.points))

function autoSpots(r: FloorRoom, n: number): PlanPoint[] {
  const b = bbox(r.points)
  const cols = Math.max(1, Math.min(n, Math.floor((b.w - 16) / AUTO_GAP)))
  const rows = Math.ceil(n / cols)
  return Array.from({ length: n }, (_, i) => {
    const row = Math.floor(i / cols)
    const inRow = Math.min(cols, n - row * cols)
    return [
      b.x + b.w / 2 + ((i % cols) - (inRow - 1) / 2) * AUTO_GAP,
      b.y + b.h / 2 + 8 + (row - (rows - 1) / 2) * AUTO_GAP,
    ] as PlanPoint
  })
}

const cameras = ref<Camera[]>([])
onMounted(async () => (cameras.value = await api.cameras().catch(() => [])))

type Marker = { key: string; room: string; pos: PlanPoint } & (
  | { type: 'device'; device: Device }
  | { type: 'camera'; camera: Camera }
)

/** Positions dragged in edit mode, keyed like markers; saved together. */
const draft = reactive<Record<string, PlanPoint>>({})
const editing = ref(false)

const markers = computed<Marker[]>(() => {
  const out: Marker[] = []
  for (const r of plan.value.rooms) {
    const items = [
      ...deviceList.value
        .filter((d) => d.room === r.name && onPlan(d))
        .map((d) => ({ key: `d:${d.id}`, saved: plan.value.devices[d.id], type: 'device' as const, device: d })),
      ...cameras.value
        .filter((c) => c.room === r.name && !c.hidden)
        .map((c) => ({ key: `c:${c.id}`, saved: plan.value.cameras[c.id], type: 'camera' as const, camera: c })),
    ]
    const spots = autoSpots(r, items.filter((i) => !i.saved).length)
    for (const { saved, ...item } of items) {
      out.push({ ...item, room: r.name, pos: draft[item.key] ?? saved ?? spots.shift()! })
    }
  }
  return out
})
const deviceMarkers = computed(() => markers.value.flatMap((m) => (m.type === 'device' ? [m] : [])))
const devicesIn = (room: string) => deviceMarkers.value.filter((m) => m.room === room)

/** Lit lights glow on the floor around them, stronger and wider with brightness. */
const glows = computed(() =>
  plan.value.rooms.map((r) =>
    devicesIn(r.name)
      .filter((m) => m.device.kind === 'light' && isActive(m.device))
      .map((m) => ({ key: m.key, pos: m.pos, level: (m.device.state.brightness ?? 100) / 100 })),
  ),
)
function roomTone(room: string) {
  const ac = devicesIn(room).find((m) => m.device.kind === 'ac' && isActive(m.device))?.device
  return ac ? (ac.state.mode === 'heat' ? 'heat' : 'cool') : ''
}
const roomTemp = (room: string) =>
  devicesIn(room).find((m) => m.device.state.online && m.device.state.temperature !== undefined)?.device.state.temperature
const roomAlert = (room: string) => devicesIn(room).some((m) => m.device.kind === 'lock' && isActive(m.device))
const clickable = (room: string) => !editing.value && !props.wall && panelRooms.value.includes(room)
const pickRoom = (room: string) => clickable(room) && openRoom(room)

const tone = (d: Device) => (d.kind === 'ac' && d.state.mode === 'heat' ? 'heat' : TONES[d.kind] ?? 'accent')
const fill = (d: Device) => (!isActive(d) ? 0 : d.kind === 'light' ? 50 + 0.5 * (d.state.brightness ?? 100) : 100)

const detailId = ref<string | null>(null)
const watching = ref<Camera | null>(null)

// Touch screens have no right click: holding a key opens its details instead.
let pressTimer: ReturnType<typeof setTimeout> | undefined
let longPressed = false
function pressStart(m: Marker, e: PointerEvent) {
  if (editing.value) return dragStart(m, e)
  longPressed = false
  clearTimeout(pressTimer)
  if (m.type === 'device') {
    pressTimer = setTimeout(() => {
      longPressed = true
      detailId.value = m.device.id
    }, LONG_PRESS_MS)
  }
}
function pressEnd() {
  clearTimeout(pressTimer)
  dragEnd()
}
onBeforeUnmount(() => clearTimeout(pressTimer))

function tapDevice(d: Device) {
  if (editing.value || longPressed) return
  const run = quickToggle(d)
  if (run) run()
  else detailId.value = d.id
}
function tapCamera(c: Camera) {
  if (editing.value || c.unsupported) return
  watching.value = watching.value?.id === c.id ? null : c
}
const watchingPos = computed(() => markers.value.find((m) => m.type === 'camera' && m.camera.id === watching.value?.id)?.pos)
const onKey = (e: KeyboardEvent) => e.key === 'Escape' && (watching.value = null)
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))

// Edit mode: markers follow the pointer; the plan is saved once on 保存.
const stage = ref<HTMLElement>()

// Labels that would spill over the walls are dropped on small screens.
const stagePx = ref(0)
const observer = new ResizeObserver(([e]) => (stagePx.value = e.contentRect.width))
watch(stage, (el, old) => {
  if (old) observer.unobserve(old)
  if (el) observer.observe(el)
})
onBeforeUnmount(() => observer.disconnect())
/** Nearest wall to the right of a point, so L-shaped rooms are measured where the label actually sits. */
function wallRightOf(r: FloorRoom, [x, y]: PlanPoint): number {
  let best = Infinity
  r.points.forEach(([x1, y1], i) => {
    const [x2, y2] = r.points[(i + 1) % r.points.length]
    if (y1 > y === y2 > y) return
    const hit = x1 + ((y - y1) / (y2 - y1)) * (x2 - x1)
    if (hit > x && hit < best) best = hit
  })
  return best === Infinity ? x : best
}
function labelFits(r: FloorRoom) {
  if (!props.compact) return true
  const [x, y] = labelAt(r)
  return ((wallRightOf(r, [x, y + 6]) - x) * stagePx.value) / view.value[2] >= r.name.length * 11 - 4
}
let dragging: { key: string; id: number } | null = null
function toPlan(e: PointerEvent): PlanPoint {
  const rect = stage.value!.getBoundingClientRect()
  const [vx, vy, vw, vh] = view.value
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
  return [
    Math.round(clamp(vx + ((e.clientX - rect.left) / rect.width) * vw, vx, vx + vw)),
    Math.round(clamp(vy + ((e.clientY - rect.top) / rect.height) * vh, vy, vy + vh)),
  ]
}
function dragStart(m: Marker, e: PointerEvent) {
  if (!editing.value) return
  dragging = { key: m.key, id: e.pointerId }
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}
// Holding Shift snaps the key onto another key's row or column, or its room's center lines, and draws the guide.
const SNAP_PX = 8
type Guide = { x1: number; y1: number; x2: number; y2: number }
const guides = ref<Guide[]>([])

function snap(key: string, [x, y]: PlanPoint): PlanPoint {
  const tolerance = (SNAP_PX * view.value[2]) / stagePx.value
  const self = markers.value.find((m) => m.key === key)
  const others = markers.value.filter((m) => m.key !== key).map((m) => m.pos)
  const room = plan.value.rooms.find((r) => r.name === self?.room)
  const box = room && bbox(room.points)
  const center = box ? [box.x + box.w / 2, box.y + box.h / 2] : null
  const nearest = (v: number, candidates: number[]) =>
    candidates.reduce<number | null>(
      (best, c) => (Math.abs(c - v) <= tolerance && (best === null || Math.abs(c - v) < Math.abs(best - v)) ? c : best),
      null,
    )
  const sx = nearest(x, [...others.map((p) => p[0]), ...(center ? [center[0]] : [])])
  const sy = nearest(y, [...others.map((p) => p[1]), ...(center ? [center[1]] : [])])
  const nx = sx ?? x
  const ny = sy ?? y

  // Each guide runs from the dragged key to the farthest key it lines up with, or across the room for a center line.
  const PAD = 14
  const out: Guide[] = []
  if (sx !== null) {
    const ys = [ny, ...others.filter((p) => p[0] === sx).map((p) => p[1])]
    if (box && center![0] === sx) ys.push(box.y, box.y + box.h)
    out.push({ x1: sx, x2: sx, y1: Math.min(...ys) - PAD, y2: Math.max(...ys) + PAD })
  }
  if (sy !== null) {
    const xs = [nx, ...others.filter((p) => p[1] === sy).map((p) => p[0])]
    if (box && center![1] === sy) xs.push(box.x, box.x + box.w)
    out.push({ y1: sy, y2: sy, x1: Math.min(...xs) - PAD, x2: Math.max(...xs) + PAD })
  }
  guides.value = out
  return [Math.round(nx), Math.round(ny)]
}

function dragMove(e: PointerEvent) {
  if (dragging?.id !== e.pointerId) return
  const p = toPlan(e)
  if (e.shiftKey) draft[dragging.key] = snap(dragging.key, p)
  else {
    guides.value = []
    draft[dragging.key] = p
  }
}
function dragEnd() {
  dragging = null
  guides.value = []
}

function startEdit() {
  watching.value = null
  editing.value = true
}
function cancelEdit() {
  for (const k of Object.keys(draft)) delete draft[k]
  editing.value = false
}
async function saveEdit() {
  const devices = { ...plan.value.devices }
  const cams = { ...plan.value.cameras }
  for (const m of markers.value) {
    if (m.type === 'device') devices[m.device.id] = m.pos
    else cams[m.camera.id] = m.pos
  }
  try {
    floorplan.value = await api.setFloorplan({ ...plan.value, devices, cameras: cams })
    cancelEdit()
    showToast('位置已保存')
  } catch {
    showFailToast('保存失败')
  }
}

const stageWidth = computed(() =>
  props.compact ? '100%' : `min(100%, calc((100vh - ${props.wall ? 64 : 210}px) * ${view.value[2] / view.value[3]}))`,
)
</script>

<template>
  <div class="fp">
    <div ref="stage" class="stage" :class="{ editing, compact }"
      :style="{ width: stageWidth, aspectRatio: `${view[2]} / ${view[3]}` }" @click.self="watching = null">
      <svg :viewBox="view.join(' ')" class="map" @click="watching = null">
        <defs>
          <clipPath v-for="(r, i) in plan.rooms" :id="`fp-clip-${i}`" :key="r.name">
            <polygon :points="svgPoints(r)" />
          </clipPath>
          <radialGradient id="fp-glow">
            <stop offset="0" stop-color="#ffb43f" stop-opacity="0.85" />
            <stop offset="0.45" stop-color="#ffb43f" stop-opacity="0.35" />
            <stop offset="1" stop-color="#ffb43f" stop-opacity="0" />
          </radialGradient>
        </defs>
        <g class="floors">
          <polygon v-for="r in plan.rooms" :key="r.name" :points="svgPoints(r)" class="floor"
            :class="{ outdoor: r.outdoor, clickable: clickable(r.name), alert: roomAlert(r.name) }"
            @click.stop="pickRoom(r.name)" />
        </g>
        <g v-for="(r, i) in plan.rooms" :key="r.name" :clip-path="`url(#fp-clip-${i})`" class="ambient">
          <polygon :points="svgPoints(r)" class="tint" :class="roomTone(r.name)" />
          <circle v-for="g in glows[i]" :key="g.key" :cx="g.pos[0]" :cy="g.pos[1]" :r="55 + 55 * g.level"
            fill="url(#fp-glow)" :opacity="0.45 + 0.55 * g.level" />
        </g>
        <g v-if="guides.length" class="guides">
          <line v-for="(g, i) in guides" :key="i" :x1="g.x1" :y1="g.y1" :x2="g.x2" :y2="g.y2" />
        </g>
      </svg>

      <div class="layer">
        <template v-for="r in plan.rooms" :key="r.name">
          <button v-if="labelFits(r)" class="label" :class="{ clickable: clickable(r.name), outdoor: r.outdoor }"
            :style="pct(labelAt(r))" :tabindex="clickable(r.name) ? 0 : -1" @click="pickRoom(r.name)">
            <span class="label-name">{{ r.name }}</span>
            <span v-if="!compact && roomTemp(r.name) !== undefined" class="label-temp num">
              {{ Math.round(roomTemp(r.name)!) }}°
            </span>
          </button>
        </template>

        <template v-if="compact">
          <span v-for="m in deviceMarkers" :key="m.key" class="dot" :style="pct(m.pos)"
            :class="[tone(m.device), { on: isActive(m.device), offline: !m.device.state.online }]" />
        </template>
        <template v-for="m in markers" v-else :key="m.key">
          <button v-if="m.type === 'device'" class="mk" :style="{ ...pct(m.pos), '--fill': `${fill(m.device)}%` }"
            :class="[m.device.kind, tone(m.device), { on: isActive(m.device), offline: !m.device.state.online }]"
            :aria-label="m.device.name" @click="tapDevice(m.device)" @contextmenu.prevent="detailId = m.device.id"
            @pointerdown="pressStart(m, $event)" @pointermove="dragMove" @pointerup="pressEnd" @pointercancel="pressEnd"
            @pointerleave="pressEnd">
            <template v-if="m.device.kind === 'ac' && isActive(m.device)">
              <component :is="MODE_ICONS[m.device.state.mode ?? 'auto']" :size="17" :stroke-width="2.2" />
              <span class="mk-badge num">{{ m.device.state.target_temp }}°</span>
            </template>
            <CurtainGlyph v-else-if="m.device.kind === 'curtain'" :position="m.device.state.position ?? 0" :size="18" />
            <DeviceIcon v-else :kind="m.device.kind" :model="m.device.model" :name="m.device.name" :size="34" class="mk-icon" />
            <span class="mk-tip">
              <b>{{ shortName(m.device) }}</b><span>{{ deviceStatus(m.device) }}</span>
            </span>
          </button>
          <button v-else class="mk camera accent"
            :class="{ on: watching?.id === m.camera.id, offline: m.camera.unsupported }" :style="pct(m.pos)"
            :aria-label="m.camera.name" @click.stop="tapCamera(m.camera)"
            @pointerdown="dragStart(m, $event)" @pointermove="dragMove" @pointerup="dragEnd" @pointercancel="dragEnd">
            <Cctv :size="17" :stroke-width="2" />
            <span class="mk-tip"><b>{{ m.camera.name }}</b><span>{{ m.camera.unsupported ? '暂不支持' : '点击查看画面' }}</span></span>
          </button>
        </template>

        <div v-if="watching && watchingPos" class="peek"
          :class="{ left: (watchingPos[0] - view[0]) / view[2] > 0.55, up: (watchingPos[1] - view[1]) / view[3] > 0.55 }"
          :style="pct(watchingPos)">
          <CameraFeed :key="watching.id" :camera-id="watching.id" quality="sd" />
          <div class="peek-name">{{ watching.name }}</div>
        </div>
      </div>

      <div v-if="!compact && !wall" class="tools">
        <template v-if="editing">
          <span class="hint">拖动图标调整位置，按住 Shift 对齐</span>
          <button class="tool" title="取消" @click="cancelEdit"><X :size="16" /></button>
          <button class="tool primary" title="保存" @click="saveEdit"><Check :size="16" /></button>
        </template>
        <button v-else class="tool" title="调整设备位置" @click="startEdit"><Move :size="16" /></button>
      </div>
    </div>

    <DeviceSheet :device-id="detailId" @close="detailId = null" />
  </div>
</template>

<style scoped>
.fp {
  display: flex;
  justify-content: center;
}
.stage {
  position: relative;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}
.map {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}

/* Rooms are cards; the gaps between them read as walls */
.floors {
  filter: drop-shadow(0 1px 2px rgb(17 24 39 / 0.05)) drop-shadow(0 6px 18px rgb(17 24 39 / 0.07));
}
.floor {
  fill: var(--surface);
  stroke: var(--surface);
  stroke-width: 3;
  stroke-linejoin: round;
  transition: fill 0.2s, stroke 0.2s;
}
.floor.clickable {
  cursor: pointer;
}
.floor.clickable:hover {
  fill: color-mix(in srgb, var(--surface) 94%, var(--accent));
  stroke: color-mix(in srgb, var(--surface) 94%, var(--accent));
}
.floor.outdoor {
  fill: transparent;
  stroke: var(--text-3);
  stroke-opacity: 0.45;
  stroke-width: 1.2;
  stroke-dasharray: 4 4;
}
.floor.alert {
  stroke: var(--heat);
  stroke-width: 3;
}
.ambient {
  pointer-events: none;
}
.tint {
  fill: transparent;
  transition: fill 0.5s;
}
.tint.cool {
  fill: rgb(42 149 245 / 0.13);
}
.tint.heat {
  fill: rgb(242 107 42 / 0.13);
}
.guides {
  pointer-events: none;
}
.guides line {
  stroke: var(--accent);
  stroke-width: 1.5px;
  vector-effect: non-scaling-stroke;
}
.ambient circle {
  transition: r 0.5s, opacity 0.5s;
}

/* HTML layer on top: labels and device keys stay a fixed size however big the map is */
.layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.layer > * {
  pointer-events: auto;
}
.label {
  position: absolute;
  display: flex;
  align-items: baseline;
  gap: 6px;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 650;
  color: var(--text-2);
  cursor: default;
}
.label.clickable {
  cursor: pointer;
}
.label.clickable:hover .label-name {
  color: var(--accent-text);
}
.label.outdoor {
  font-weight: 500;
  color: var(--text-3);
}
.label-temp {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-3);
}

.mk {
  --c: var(--accent);
  --c-soft: var(--accent-soft);
  position: absolute;
  width: 34px;
  height: 34px;
  margin: -17px 0 0 -17px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
  background: var(--surface-2);
  box-shadow: 0 0 0 1px var(--line);
  transition: background 0.35s, color 0.2s, box-shadow 0.3s, transform 0.1s;
}
.mk:hover {
  z-index: 2;
}
.mk:active {
  transform: scale(0.9);
}
.warm {
  --c: var(--warm);
  --c-soft: var(--warm-soft);
}
.cool {
  --c: var(--cool);
  --c-soft: var(--cool-soft);
}
.heat {
  --c: var(--heat);
  --c-soft: var(--heat-soft);
}
.mk.on {
  color: #fff;
  background: linear-gradient(to top, var(--c) var(--fill, 100%), var(--c-soft) var(--fill, 100%));
  box-shadow: none;
}
.mk.light.on {
  box-shadow: var(--shadow-warm);
}
.mk.camera.on {
  background: var(--accent);
}
.mk.offline {
  opacity: 0.35;
}
.mk.lock.on {
  animation: pulse 1.6s ease-in-out infinite;
}
.mk-icon {
  background: transparent !important;
  box-shadow: none !important;
  color: inherit !important;
}
.mk-badge {
  position: absolute;
  top: -7px;
  right: -9px;
  padding: 1px 5px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 650;
  background: var(--surface);
  color: var(--c);
  box-shadow: var(--shadow-1);
}
.mk-tip {
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 5px 9px;
  border-radius: 9px;
  white-space: nowrap;
  font-size: 11px;
  line-height: 1.4;
  color: var(--text-3);
  background: var(--surface);
  box-shadow: var(--shadow-2);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s;
}
.mk-tip b {
  font-size: 12px;
  font-weight: 650;
  color: var(--text);
}
.mk:hover .mk-tip {
  opacity: 1;
}
@keyframes pulse {
  50% {
    box-shadow: 0 0 0 6px rgb(242 107 42 / 0.25);
  }
}

/* Compact overview: a dot per device, colored only while it runs */
.compact .label {
  font-size: 11px;
  font-weight: 600;
}
.dot {
  position: absolute;
  width: 7px;
  height: 7px;
  margin: -3.5px 0 0 -3.5px;
  border-radius: 50%;
  background: var(--surface-3);
  pointer-events: none !important;
  transition: background 0.3s, box-shadow 0.3s;
}
.dot.on {
  background: var(--c, var(--accent));
  box-shadow: 0 0 0 3px var(--c-soft, var(--accent-soft));
}
.dot.offline {
  opacity: 0.4;
}

/* Edit mode: every key can be grabbed */
.editing .mk {
  cursor: grab;
  touch-action: none;
  box-shadow: 0 0 0 2px var(--accent-soft), 0 0 0 1px var(--accent);
}
.editing .mk:active {
  cursor: grabbing;
  transform: scale(1.1);
}
.editing .mk-tip {
  opacity: 1;
  top: calc(100% + 3px);
  padding: 1px 6px;
  box-shadow: none;
  background: transparent;
}
.editing .mk-tip > :not(b) {
  display: none;
}

/* Camera peek: a small live view next to the camera */
.peek {
  position: absolute;
  z-index: 5;
  width: 300px;
  margin: 24px 0 0 -40px;
  border-radius: var(--radius);
  overflow: hidden;
  background: #000;
  box-shadow: var(--shadow-2);
  aspect-ratio: 16 / 9;
}
.peek.left {
  margin-left: -260px;
}
.peek.up {
  transform: translateY(calc(-100% - 48px));
}
.peek-name {
  position: absolute;
  left: 10px;
  bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 1px 3px rgb(0 0 0 / 0.6);
}

.tools {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.hint {
  font-size: 12px;
  color: var(--text-3);
}
.tool {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  color: var(--text-2);
  box-shadow: var(--shadow-1);
}
.tool:hover {
  color: var(--text);
}
.tool.primary {
  background: var(--accent);
  color: #fff;
}
</style>
