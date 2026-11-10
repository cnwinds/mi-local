<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { showConfirmDialog, showFailToast, showToast } from 'vant'
import { ImagePlus, LayoutGrid, MousePointer2, SquareDashed, Trash2, Undo2 } from 'lucide-vue-next'
import { api, type FloorBackground, type FloorRoom, type PlanPoint } from '../../api'
import { floorplan, rooms as homeRooms } from '../../store'
import { panelRooms, roomDevices } from '../../rooms'
import { autoLayout, bbox, fitView, labelAt, svgPoints } from '../../floorplan'

const emit = defineEmits<{ close: [] }>()

const SNAP_PX = 8
const HANDLE_PX = 7
// Very large photos are scaled so coordinates stay in a sensible range.
const BACKGROUND_MAX_UNITS = 2000

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
const existing = floorplan.value
const rooms = ref<FloorRoom[]>(existing ? clone(existing.rooms) : [])
const background = ref<FloorBackground | null>(existing?.background ? { ...existing.background } : null)
const bgStamp = ref(Date.now())
/** Set by an auto layout: old device spots belong to another drawing and are dropped on save. */
let relaidOut = false

function computeCanvas(withExisting: boolean): [number, number, number, number] {
  const pts: PlanPoint[] = rooms.value.flatMap((r) => r.points)
  if (background.value) pts.push([0, 0], [background.value.w, background.value.h])
  if (withExisting && existing) pts.push([existing.view[0], existing.view[1]], [existing.view[0] + existing.view[2], existing.view[1] + existing.view[3]])
  if (!pts.length) return [0, 0, 1000, 700]
  const b = bbox(pts)
  const pad = Math.max(b.w, b.h) * 0.06
  return [b.x - pad, b.y - pad, b.w + 2 * pad, b.h + 2 * pad]
}
const canvas = ref(computeCanvas(true))

// Screen ↔ plan
const svg = ref<SVGSVGElement>()
const box = ref({ w: 1, h: 1 })
const observer = new ResizeObserver(([e]) => (box.value = { w: e.contentRect.width || 1, h: e.contentRect.height || 1 }))
watch(svg, (el) => el && observer.observe(el))
onBeforeUnmount(() => observer.disconnect())
/** Plan units per screen pixel. */
const upp = computed(() => Math.max(canvas.value[2] / box.value.w, canvas.value[3] / box.value.h))
function toPlan(e: PointerEvent): PlanPoint {
  const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.value!.getScreenCTM()!.inverse())
  return [p.x, p.y]
}

// Undo: a snapshot of the rooms before every change.
const history = ref<string[]>([])
const changed = ref(false)
function remember() {
  history.value.push(JSON.stringify(rooms.value))
  if (history.value.length > 80) history.value.shift()
  changed.value = true
}
function undo() {
  const last = history.value.pop()
  if (!last) return
  rooms.value = JSON.parse(last)
  selected.value = null
  selVertex.value = null
}

const selected = ref<number | null>(null)
const selVertex = ref<number | null>(null)
const sel = computed(() => (selected.value === null ? null : rooms.value[selected.value]))
const tool = ref<'select' | 'rect'>('select')
const pendingName = ref('')

const nameOptions = computed(() => [...new Set([...panelRooms.value, ...homeRooms.value])].filter((n) => n !== '未分配'))
const undrawn = computed(() => nameOptions.value.filter((n) => !rooms.value.some((r) => r.name === n)))
const nextName = () => pendingName.value || undrawn.value[0] || `房间 ${rooms.value.length + 1}`
function drawRoom(name = '') {
  pendingName.value = name
  tool.value = 'rect'
  selected.value = null
}

// Ctrl (⌘) snaps onto other rooms' corners and shows where.
const guides = ref<{ x?: number; y?: number }[]>([])
function otherCorners(skip: (ri: number, qi: number) => boolean) {
  const xs: number[] = []
  const ys: number[] = []
  rooms.value.forEach((r, ri) => r.points.forEach(([x, y], qi) => !skip(ri, qi) && (xs.push(x), ys.push(y))))
  return { xs, ys }
}
function nearest(v: number, list: number[]) {
  const tol = SNAP_PX * upp.value
  return list.reduce<number | null>((best, c) => (Math.abs(c - v) <= tol && (best === null || Math.abs(c - v) < Math.abs(best - v)) ? c : best), null)
}
function snapPoint(p: PlanPoint, e: PointerEvent, skip: (ri: number, qi: number) => boolean = () => false): PlanPoint {
  guides.value = []
  let [x, y] = [Math.round(p[0]), Math.round(p[1])]
  if (!(e.ctrlKey || e.metaKey)) return [x, y]
  const { xs, ys } = otherCorners(skip)
  const sx = nearest(x, xs)
  const sy = nearest(y, ys)
  if (sx !== null) guides.value.push({ x: (x = sx) })
  if (sy !== null) guides.value.push({ y: (y = sy) })
  return [x, y]
}
function snapShift(orig: PlanPoint[], d: PlanPoint, e: PointerEvent, room: number): PlanPoint {
  guides.value = []
  let [dx, dy] = [Math.round(d[0]), Math.round(d[1])]
  if (!(e.ctrlKey || e.metaKey)) return [dx, dy]
  const { xs, ys } = otherCorners((ri) => ri === room)
  const tol = SNAP_PX * upp.value
  let bx: { diff: number; at: number } | null = null
  let by: { diff: number; at: number } | null = null
  for (const [x, y] of orig) {
    for (const c of xs) if (Math.abs(c - (x + dx)) <= tol && (!bx || Math.abs(c - (x + dx)) < Math.abs(bx.diff))) bx = { diff: c - (x + dx), at: c }
    for (const c of ys) if (Math.abs(c - (y + dy)) <= tol && (!by || Math.abs(c - (y + dy)) < Math.abs(by.diff))) by = { diff: c - (y + dy), at: c }
  }
  if (bx) (dx += bx.diff), guides.value.push({ x: bx.at })
  if (by) (dy += by.diff), guides.value.push({ y: by.at })
  return [dx, dy]
}

// Pointer gestures on the canvas, told apart by what was pressed.
type Drag =
  | { kind: 'vertex'; room: number; index: number }
  | { kind: 'move'; room: number; start: PlanPoint; orig: PlanPoint[]; label: PlanPoint | null }
  | { kind: 'label'; room: number; start: PlanPoint; orig: PlanPoint }
  | { kind: 'rect'; start: PlanPoint }
let drag: Drag | null = null
let downAt = { x: 0, y: 0 }
let moved = false
const rectDraft = ref<[PlanPoint, PlanPoint] | null>(null)

function onDown(e: PointerEvent) {
  if (e.button !== 0) return
  const t = (e.target as SVGElement).dataset
  downAt = { x: e.clientX, y: e.clientY }
  moved = false
  const p = toPlan(e)
  if (tool.value === 'rect') {
    const start = snapPoint(p, e)
    drag = { kind: 'rect', start }
    rectDraft.value = [start, start]
  } else if (t.vertex !== undefined && selected.value !== null) {
    remember()
    selVertex.value = Number(t.vertex)
    drag = { kind: 'vertex', room: selected.value, index: Number(t.vertex) }
  } else if (t.mid !== undefined && selected.value !== null) {
    remember()
    const r = rooms.value[selected.value]
    const i = Number(t.mid)
    const [a, b] = [r.points[i], r.points[(i + 1) % r.points.length]]
    r.points.splice(i + 1, 0, [Math.round((a[0] + b[0]) / 2), Math.round((a[1] + b[1]) / 2)])
    selVertex.value = i + 1
    drag = { kind: 'vertex', room: selected.value, index: i + 1 }
    moved = true
  } else if (t.label !== undefined) {
    const ri = Number(t.label)
    remember()
    selected.value = ri
    selVertex.value = null
    drag = { kind: 'label', room: ri, start: p, orig: labelAt(rooms.value[ri]) }
  } else if (t.room !== undefined) {
    const ri = Number(t.room)
    remember()
    if (selected.value !== ri) selVertex.value = null
    selected.value = ri
    drag = { kind: 'move', room: ri, start: p, orig: clone(rooms.value[ri].points), label: rooms.value[ri].label ?? null }
  } else {
    selected.value = null
    selVertex.value = null
  }
  if (drag) svg.value!.setPointerCapture(e.pointerId)
}

function onMove(e: PointerEvent) {
  if (!drag) return
  if (!moved && Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) < 3) return
  moved = true
  const p = toPlan(e)
  if (drag.kind === 'rect') {
    rectDraft.value = [drag.start, snapPoint(p, e)]
  } else if (drag.kind === 'vertex') {
    const { room, index } = drag
    rooms.value[room].points[index] = snapPoint(p, e, (ri, qi) => ri === room && qi === index)
  } else if (drag.kind === 'move') {
    const { room, start, orig, label } = drag
    const [dx, dy] = snapShift(orig, [p[0] - start[0], p[1] - start[1]], e, room)
    const r = rooms.value[room]
    r.points = orig.map(([x, y]) => [x + dx, y + dy] as PlanPoint)
    if (label) r.label = [label[0] + dx, label[1] + dy]
  } else if (drag.kind === 'label') {
    rooms.value[drag.room].label = [Math.round(drag.orig[0] + p[0] - drag.start[0]), Math.round(drag.orig[1] + p[1] - drag.start[1])]
  }
}

function onUp() {
  if (drag?.kind === 'rect' && rectDraft.value) {
    const [[x1, y1], [x2, y2]] = rectDraft.value
    if (Math.abs(x2 - x1) > 10 * upp.value && Math.abs(y2 - y1) > 10 * upp.value) {
      remember()
      const [l, r, t, b] = [Math.min(x1, x2), Math.max(x1, x2), Math.min(y1, y2), Math.max(y1, y2)]
      rooms.value.push({ name: nextName(), points: [[l, t], [r, t], [r, b], [l, b]] })
      selected.value = rooms.value.length - 1
      selVertex.value = null
      pendingName.value = ''
      tool.value = 'select'
    }
    rectDraft.value = null
  } else if (drag && drag.kind !== 'rect' && !moved) {
    history.value.pop()
  }
  drag = null
  guides.value = []
}

function deleteVertex(index: number) {
  const r = sel.value
  if (!r || r.points.length <= 3) return showToast('房间至少要 3 个顶点')
  remember()
  r.points.splice(index, 1)
  selVertex.value = null
}
async function deleteRoom() {
  if (selected.value === null) return
  remember()
  rooms.value.splice(selected.value, 1)
  selected.value = null
  selVertex.value = null
}

function onKey(e: KeyboardEvent) {
  if ((e.target as HTMLElement).closest('input, textarea')) return
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
    e.preventDefault()
    undo()
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    e.preventDefault()
    if (selVertex.value !== null) deleteVertex(selVertex.value)
    else deleteRoom()
  } else if (e.key === 'Escape') {
    if (tool.value === 'rect') tool.value = 'select'
    else selected.value = selVertex.value = null
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

// Background image
const fileInput = ref<HTMLInputElement>()
const uploading = ref(false)
async function pickBackground(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  try {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.src = url
    await img.decode()
    URL.revokeObjectURL(url)
    const scale = Math.min(1, BACKGROUND_MAX_UNITS / Math.max(img.naturalWidth, img.naturalHeight))
    await api.uploadFloorplanBackground(file)
    background.value = { w: Math.round(img.naturalWidth * scale), h: Math.round(img.naturalHeight * scale), opacity: background.value?.opacity ?? 0.4 }
    bgStamp.value = Date.now()
    changed.value = true
    canvas.value = computeCanvas(false)
  } catch (err) {
    showFailToast((err as Error).message || '图片读不出来')
  } finally {
    uploading.value = false
  }
}
async function removeBackground() {
  await showConfirmDialog({ title: '移除户型底图', message: '画好的房间会保留。' })
  await api.deleteFloorplanBackground()
  background.value = null
  changed.value = true
}

async function relayout() {
  if (rooms.value.length) {
    await showConfirmDialog({ title: '自动布局', message: '会用按房间自动生成的方块替换现在的房间形状，设备位置也会重新排。' })
  }
  remember()
  rooms.value = autoLayout(panelRooms.value.map((name) => ({ name, devices: roomDevices(name).length })))
  relaidOut = true
  selected.value = selVertex.value = null
  canvas.value = computeCanvas(false)
}

const saving = ref(false)
async function save() {
  const list = rooms.value.filter((r) => r.points.length >= 3 && r.name.trim())
  if (!list.length) return showFailToast('至少画一个房间')
  const dupe = list.find((r, i) => list.findIndex((x) => x.name === r.name) !== i)
  if (dupe) return showFailToast(`「${dupe.name}」画了两次，每个房间只能画一块`)
  saving.value = true
  try {
    const plan = {
      rooms: list.map((r) => ({ ...r, name: r.name.trim() })),
      devices: relaidOut ? {} : existing?.devices ?? {},
      cameras: relaidOut ? {} : existing?.cameras ?? {},
      background: background.value,
    }
    floorplan.value = await api.setFloorplan({ ...plan, view: fitView(plan) })
    showToast('户型已保存')
    emit('close')
  } catch (err) {
    showFailToast((err as Error).message)
  } finally {
    saving.value = false
  }
}
async function cancel() {
  if (changed.value) await showConfirmDialog({ title: '放弃修改', message: '这次的改动不会保存。' })
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div class="editor">
      <div class="stage">
        <svg ref="svg" :viewBox="canvas.join(' ')" class="canvas" :class="tool" @pointerdown="onDown" @pointermove="onMove"
          @pointerup="onUp" @pointercancel="onUp">
          <image v-if="background" :href="`/api/floorplan/background?v=${bgStamp}`" x="0" y="0" :width="background.w"
            :height="background.h" :opacity="background.opacity" preserveAspectRatio="none" />
          <polygon v-for="(r, i) in rooms" :key="i" :points="svgPoints(r)" :data-room="i" class="room"
            :class="{ selected: i === selected, outdoor: r.outdoor }" />
          <text v-for="(r, i) in rooms" :key="`l${i}`" :x="labelAt(r)[0]" :y="labelAt(r)[1]" :font-size="13 * upp"
            :data-label="i" class="label" dominant-baseline="hanging">{{ r.name }}</text>
          <template v-if="sel">
            <circle v-for="(p, j) in sel.points" :key="`m${j}`" :data-mid="j" class="mid" :r="HANDLE_PX * 0.6 * upp"
              :cx="(p[0] + sel.points[(j + 1) % sel.points.length][0]) / 2"
              :cy="(p[1] + sel.points[(j + 1) % sel.points.length][1]) / 2" />
            <circle v-for="(p, j) in sel.points" :key="`v${j}`" :data-vertex="j" class="vertex" :class="{ on: selVertex === j }"
              :r="HANDLE_PX * upp" :cx="p[0]" :cy="p[1]" @dblclick.stop="deleteVertex(j)" />
          </template>
          <rect v-if="rectDraft" class="draft" :x="Math.min(rectDraft[0][0], rectDraft[1][0])" :y="Math.min(rectDraft[0][1], rectDraft[1][1])"
            :width="Math.abs(rectDraft[1][0] - rectDraft[0][0])" :height="Math.abs(rectDraft[1][1] - rectDraft[0][1])" />
          <template v-for="(g, i) in guides" :key="`g${i}`">
            <line v-if="g.x !== undefined" class="guide" :x1="g.x" :x2="g.x" :y1="canvas[1]" :y2="canvas[1] + canvas[3]" />
            <line v-else class="guide" :y1="g.y" :y2="g.y" :x1="canvas[0]" :x2="canvas[0] + canvas[2]" />
          </template>
        </svg>
        <div v-if="tool === 'rect'" class="banner">拖出一个矩形：{{ nextName() }}　·　Esc 取消</div>
        <div v-else-if="!rooms.length" class="banner">
          {{ background ? '点右侧「画房间」，沿着墙内侧描出每个房间' : '上传户型图描出房间，或者先点「自动布局」' }}
        </div>
      </div>

      <aside class="side">
        <div class="side-title">编辑户型</div>

        <section>
          <div class="label-row">户型底图</div>
          <div class="row">
            <button class="btn" :disabled="uploading" @click="fileInput?.click()">
              <ImagePlus :size="16" />{{ uploading ? '上传中…' : background ? '更换图片' : '上传户型图' }}
            </button>
            <button v-if="background" class="btn ghost" @click="removeBackground">移除</button>
          </div>
          <div v-if="background" class="opacity">
            <span>透明度</span>
            <van-slider v-model="background.opacity" :min="0.1" :max="0.9" :step="0.05" bar-height="4px" />
          </div>
          <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden @change="pickBackground" />
        </section>

        <section>
          <div class="label-row">房间</div>
          <div class="row tools">
            <button class="tool" :class="{ on: tool === 'select' }" title="选择、拖动" @click="tool = 'select'"><MousePointer2 :size="16" /></button>
            <button class="tool" :class="{ on: tool === 'rect' }" title="画房间" @click="drawRoom()"><SquareDashed :size="16" /></button>
            <button class="tool" title="自动布局" @click="relayout"><LayoutGrid :size="16" /></button>
            <button class="tool" title="撤销（Ctrl+Z）" :disabled="!history.length" @click="undo"><Undo2 :size="16" /></button>
          </div>
          <div class="rooms">
            <button v-for="(r, i) in rooms" :key="i" class="room-chip" :class="{ on: i === selected }"
              @click="(selected = i), (selVertex = null), (tool = 'select')">{{ r.name || '未命名' }}</button>
          </div>
          <template v-if="undrawn.length">
            <div class="hint">还没画（点一下开始画）：</div>
            <div class="rooms">
              <button v-for="n in undrawn" :key="n" class="room-chip todo" @click="drawRoom(n)">{{ n }}</button>
            </div>
          </template>
        </section>

        <section v-if="sel" class="selected">
          <div class="label-row">选中的房间</div>
          <input v-model="sel.name" class="name" list="fp-room-names" maxlength="12" placeholder="房间名" />
          <datalist id="fp-room-names">
            <option v-for="n in nameOptions" :key="n" :value="n" />
          </datalist>
          <label class="check"><input v-model="sel.outdoor" type="checkbox" />室外（虚线框，比如门口）</label>
          <button class="btn danger" @click="deleteRoom"><Trash2 :size="15" />删除这个房间</button>
          <div class="hint">
            拖动房间整体移动，拖动顶点改形状；点边上的小圆点加顶点，双击顶点删除。拖动房间名可以挪位置。按住 Ctrl 对齐其他房间的角。
          </div>
        </section>

        <div class="footer">
          <button class="btn ghost" @click="cancel">取消</button>
          <button class="btn primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.editor {
  position: fixed;
  inset: 0;
  z-index: 1500;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  grid-template-rows: minmax(0, 1fr);
  background: var(--bg);
}
.stage {
  position: relative;
  padding: 20px;
  min-width: 0;
  min-height: 0;
}
.canvas {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-1);
  touch-action: none;
  user-select: none;
}
.canvas.rect {
  cursor: crosshair;
}
.room {
  fill: color-mix(in srgb, var(--accent) 10%, transparent);
  stroke: var(--text-3);
  stroke-width: 1.5px;
  vector-effect: non-scaling-stroke;
  stroke-linejoin: round;
  cursor: move;
}
.room.outdoor {
  fill: transparent;
  stroke-dasharray: 5 4;
}
.room.selected {
  fill: color-mix(in srgb, var(--accent) 22%, transparent);
  stroke: var(--accent);
  stroke-width: 2px;
}
.canvas.rect .room {
  cursor: crosshair;
}
.label {
  fill: var(--text);
  font-weight: 650;
  cursor: grab;
  paint-order: stroke;
  stroke: var(--surface);
  stroke-width: 3px;
  vector-effect: non-scaling-stroke;
}
.vertex {
  fill: var(--surface);
  stroke: var(--accent);
  stroke-width: 2px;
  vector-effect: non-scaling-stroke;
  cursor: grab;
}
.vertex.on {
  fill: var(--accent);
}
.mid {
  fill: var(--accent);
  opacity: 0.45;
  cursor: copy;
}
.mid:hover {
  opacity: 1;
}
.draft {
  fill: color-mix(in srgb, var(--accent) 18%, transparent);
  stroke: var(--accent);
  stroke-width: 1.5px;
  stroke-dasharray: 6 4;
  vector-effect: non-scaling-stroke;
}
.guide {
  stroke: var(--accent);
  stroke-width: 1px;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
}
.banner {
  position: absolute;
  top: 32px;
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 13px;
  background: var(--surface-glass);
  box-shadow: var(--shadow-2);
  pointer-events: none;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 20px;
  border-left: 1px solid var(--line);
  background: var(--surface-glass);
  overflow-y: auto;
}
.side-title {
  font-size: 20px;
  font-weight: 750;
}
section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.label-row {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-3);
}
.row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  background: var(--surface-2);
  color: var(--text);
}
.btn:disabled {
  opacity: 0.5;
}
.btn.ghost {
  background: transparent;
  color: var(--text-2);
}
.btn.primary {
  background: var(--accent);
  color: #fff;
}
.btn.danger {
  align-self: flex-start;
  color: var(--danger);
}
.opacity {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-3);
}
.opacity .van-slider {
  flex: 1;
}
.tool {
  width: 38px;
  height: 36px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  color: var(--text-2);
}
.tool.on {
  background: var(--accent);
  color: #fff;
}
.tool:disabled {
  opacity: 0.4;
}
.rooms {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.room-chip {
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 12px;
  background: var(--surface-2);
  color: var(--text-2);
}
.room-chip.on {
  background: var(--accent);
  color: #fff;
}
.room-chip.todo {
  background: transparent;
  box-shadow: inset 0 0 0 1px var(--line);
  border: 1px dashed var(--text-3);
}
.hint {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-3);
}
.name {
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 14px;
  outline: none;
}
.name:focus {
  border-color: var(--accent);
}
.check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-2);
}
.footer {
  margin-top: auto;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
