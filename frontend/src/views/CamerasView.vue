<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Cctv, Maximize, Minimize, VideoOff, X } from 'lucide-vue-next'
import PageHeader from '../components/PageHeader.vue'
import CameraEvents from '../components/CameraEvents.vue'
import CameraFeed from '../components/CameraFeed.vue'
import { api, type Camera } from '../api'
import type { PlayerState } from '../cameraPlayer'
import { rooms } from '../store'

const cameras = ref<Camera[]>([])
const loaded = ref(false)
const states = ref<Record<string, PlayerState>>({})
const showHidden = ref(false)
const rechecking = ref<string | null>(null)
const viewing = ref<Camera | null>(null)
const viewMode = ref<'live' | 'events'>('live')
const wall = ref(false)
const root = ref<HTMLElement>()

const roomIndex = (room: string) => {
  const i = rooms.value.indexOf(room)
  return i < 0 ? rooms.value.length : i
}
const byRoom = (a: Camera, b: Camera) => roomIndex(a.room) - roomIndex(b.room)
const visible = computed(() => cameras.value.filter((c) => !c.hidden && !c.unsupported).sort(byRoom))
const unsupportedList = computed(() => cameras.value.filter((c) => !c.hidden && c.unsupported).sort(byRoom))
const hidden = computed(() => cameras.value.filter((c) => c.hidden))
const liveCount = computed(() => visible.value.filter((c) => states.value[c.id] === 'live').length)
const subtitle = computed(() =>
  visible.value.length ? `${visible.value.length} 个摄像头 · ${liveCount.value} 个在播放` : '',
)
// The wall fills the screen with as square a grid as the count allows.
const wallGrid = computed(() => {
  const n = visible.value.length
  const cols = n <= 1 ? 1 : n <= 4 ? 2 : 3
  return { gridTemplateColumns: `repeat(${cols}, 1fr)`, gridTemplateRows: `repeat(${Math.ceil(n / cols)}, 1fr)` }
})
const showRoom = (c: Camera) => c.room && !c.name.includes(c.room)

// The hub marks a camera unsupported when go2rtc refuses its model; reload so it leaves the wall.
async function onState(id: string, state: PlayerState, error: { fatal: boolean } | null) {
  states.value[id] = state
  if (error?.fatal) cameras.value = await api.cameras()
}

async function setHidden(camera: Camera, value: boolean) {
  cameras.value = await api.updateCamera(camera.id, { hidden: value })
  if (value && viewing.value?.id === camera.id) viewing.value = null
}

async function recheck(camera: Camera) {
  rechecking.value = camera.id
  try {
    cameras.value = await api.updateCamera(camera.id, { unsupported: false })
  } finally {
    rechecking.value = null
  }
}

// The viewer opens on the SD stream the wall is already playing, which shows within a second or two.
// HD needs its own camera session, so it connects underneath once SD plays (connecting both at once
// slows SD down) and takes over when it plays. Level 3 is tried first: it is the HD stream on models
// that ignore level 2, and the quicker one elsewhere. Cameras whose SD is already full resolution keep
// it, since some of them allow a single session and an HD attempt would knock SD out.
type HdLevel = 'hd' | 'hd3'
const HD_LEVELS: HdLevel[] = ['hd3', 'hd']
const FULL_RES_HEIGHT = 1000
const hdTrying = ref<HdLevel | null>(null)
const hdShown = ref(false)
let hdQueue: HdLevel[] = []
let hdWanted = false
const hdMemo = (id: string) => `mi-local:camera-hd:${id}`

function startHd(id: string) {
  const known = localStorage.getItem(hdMemo(id)) as HdLevel | null
  hdQueue = known && HD_LEVELS.includes(known) ? [known, ...HD_LEVELS.filter((l) => l !== known)] : [...HD_LEVELS]
  hdShown.value = false
  hdTrying.value = hdQueue.shift() ?? null
}

function onHdState(state: PlayerState) {
  const id = viewing.value?.id
  if (!id || !hdTrying.value) return
  if (state === 'live') {
    hdShown.value = true
    localStorage.setItem(hdMemo(id), hdTrying.value)
  } else if (state === 'error') {
    if (localStorage.getItem(hdMemo(id)) === hdTrying.value) localStorage.removeItem(hdMemo(id))
    hdShown.value = false
    hdTrying.value = hdQueue.shift() ?? null
  }
}

function onSdViewState(state: PlayerState, error: { fatal: boolean } | null) {
  if (error?.fatal) {
    viewing.value = null
    api.cameras().then((list) => (cameras.value = list))
  } else if (state === 'live' && hdWanted && viewing.value) {
    hdWanted = false
    startHd(viewing.value.id)
  }
}

function onSdResolution(_width: number, height: number) {
  if (height >= FULL_RES_HEIGHT) hdWanted = false
}

function resetHd() {
  hdTrying.value = null
  hdShown.value = false
  hdWanted = true
}

function open(camera: Camera) {
  viewing.value = camera
  viewMode.value = 'live'
  resetHd()
}

watch(viewMode, (mode) => mode === 'live' && resetHd())

let wakeLock: WakeLockSentinel | null = null
async function enterWall() {
  wall.value = true
  await root.value?.requestFullscreen?.().catch(() => {})
  wakeLock = (await navigator.wakeLock?.request('screen').catch(() => null)) ?? null
}
function exitWall() {
  wall.value = false
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
  wakeLock?.release().catch(() => {})
  wakeLock = null
}
const onFullscreenChange = () => !document.fullscreenElement && wall.value && exitWall()
const onKey = (e: KeyboardEvent) => e.key === 'Escape' && (viewing.value ? (viewing.value = null) : wall.value && exitWall())

onMounted(async () => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  window.addEventListener('keydown', onKey)
  try {
    cameras.value = await api.cameras()
  } finally {
    loaded.value = true
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  window.removeEventListener('keydown', onKey)
  wakeLock?.release().catch(() => {})
})
</script>

<template>
  <div ref="root" class="cameras" :class="{ wall }">
    <PageHeader v-if="!wall" title="监控" :subtitle="subtitle">
      <button v-if="visible.length" class="round-button" title="全屏监控墙" @click="enterWall">
        <Maximize :size="19" />
      </button>
    </PageHeader>

    <div v-if="loaded && !cameras.length" class="empty">
      <Cctv :size="34" :stroke-width="1.6" />
      <div>还没有摄像头</div>
      <small>同步米家后，摄像头会自动出现在这里</small>
    </div>

    <div class="grid" :style="wall ? wallGrid : undefined">
      <button v-for="c in visible" :key="c.id" class="tile" @click="open(c)">
        <CameraFeed :camera-id="c.id" quality="sd" @state="(s, e) => onState(c.id, s, e)" />
        <div class="label">
          <span class="live-dot" :class="{ on: states[c.id] === 'live' }" />
          <span class="name">{{ c.name }}</span>
          <span v-if="showRoom(c)" class="room">{{ c.room }}</span>
        </div>
      </button>
    </div>

    <section v-if="unsupportedList.length && !wall" class="unsupported">
      <div class="section-label">暂不支持</div>
      <div class="card unsupported-list">
        <div v-for="c in unsupportedList" :key="c.id" class="unsupported-row">
          <span class="off-icon"><VideoOff :size="18" /></span>
          <div class="unsupported-text">
            <div>{{ c.name }}</div>
            <small>这个型号还不能在本地查看，米家 App 里照常能看</small>
          </div>
          <button :disabled="rechecking === c.id" @click="recheck(c)">{{ rechecking === c.id ? '检测中' : '重新检测' }}</button>
        </div>
      </div>
    </section>

    <button v-if="wall" class="round-button wall-exit" title="退出全屏" @click="exitWall"><Minimize :size="19" /></button>

    <section v-if="hidden.length && !wall" class="hidden-section">
      <button class="hidden-toggle" @click="showHidden = !showHidden">已隐藏 {{ hidden.length }} 个摄像头</button>
      <div v-if="showHidden" class="hidden-list card">
        <div v-for="c in hidden" :key="c.id" class="hidden-row">
          <span>{{ c.name }}</span>
          <button @click="setHidden(c, false)">显示</button>
        </div>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="viewing" class="viewer" @click.self="viewing = null">
        <div class="viewer-bar">
          <div class="viewer-title">
            <span v-if="viewMode === 'live'" class="live-dot" :class="{ on: states[`view:${viewing.id}`] === 'live' }" />
            <span class="viewer-name">{{ viewing.name }}</span>
            <span v-if="viewMode === 'live'" class="quality">{{ hdShown ? '高清' : '标清' }}</span>
          </div>
          <div class="mode-switch">
            <button :class="{ on: viewMode === 'live' }" @click="viewMode = 'live'">实时</button>
            <button :class="{ on: viewMode === 'events' }" @click="viewMode = 'events'">回看</button>
          </div>
          <button class="round-button dark" title="关闭" @click="viewing = null"><X :size="20" /></button>
        </div>
        <div class="viewer-stage">
          <template v-if="viewMode === 'live'">
            <CameraFeed v-if="!hdShown" :camera-id="viewing.id" quality="sd" fit="contain" @resolution="onSdResolution"
              @state="(s, e) => { onState(`view:${viewing!.id}`, s, null); onSdViewState(s, e) }" />
            <CameraFeed v-if="hdTrying" :key="hdTrying" class="hd-layer" :class="{ shown: hdShown }" :camera-id="viewing.id"
              :quality="hdTrying" fit="contain" :retry="false"
              @state="(s) => { onHdState(s); if (hdShown) onState(`view:${viewing!.id}`, s, null) }" />
          </template>
          <CameraEvents v-else :camera-id="viewing.id" />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 8px 16px 0;
}
.tile {
  position: relative;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius);
  overflow: hidden;
  background: #0d0f13;
  box-shadow: var(--shadow-1);
  padding: 0;
  border: 0;
  cursor: pointer;
}
.label {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 18px 10px 7px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.6), transparent);
  color: #fff;
  font-size: 12px;
  text-align: left;
  pointer-events: none;
}
.name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.room {
  opacity: 0.7;
  flex: none;
}
.live-dot {
  flex: none;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
}
.live-dot.on {
  background: #ff4d4f;
  box-shadow: 0 0 0 3px rgba(255, 77, 79, 0.25);
}
.unsupported {
  padding: 20px 16px 0;
}
.section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-3);
  padding: 0 4px 8px;
}
.unsupported-list {
  overflow: hidden;
}
.unsupported-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
}
.unsupported-row + .unsupported-row {
  border-top: 1px solid var(--line);
}
.off-icon {
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
  background: var(--surface-2);
}
.unsupported-text {
  flex: 1;
  min-width: 0;
  font-size: 14px;
}
.unsupported-text small {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-3);
}
.unsupported-row button {
  flex: none;
  font-size: 13px;
  color: var(--accent);
}
.unsupported-row button:disabled {
  color: var(--text-3);
}
.round-button {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text);
  background: var(--surface-glass);
  box-shadow: var(--shadow-1);
}
.round-button.dark {
  color: #fff;
  background: rgba(255, 255, 255, 0.14);
  box-shadow: none;
}
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 72px 24px;
  color: var(--text-2);
}
.empty svg {
  color: var(--text-3);
}
.empty small {
  color: var(--text-3);
}
.hidden-section {
  padding: 16px;
}
.hidden-toggle {
  font-size: 13px;
  color: var(--text-3);
}
.hidden-list {
  margin-top: 10px;
  overflow: hidden;
}
.hidden-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  font-size: 14px;
}
.hidden-row + .hidden-row {
  border-top: 1px solid var(--line);
}
.hidden-row button {
  color: var(--accent);
  font-size: 14px;
}

/* Wall: the whole screen is cameras, edge to edge. */
.cameras.wall {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: #000;
}
.wall .grid {
  height: 100%;
  padding: 2px;
  gap: 2px;
  box-sizing: border-box;
}
.wall .tile {
  aspect-ratio: auto;
  border-radius: 0;
  box-shadow: none;
}
.wall-exit {
  position: fixed;
  top: calc(12px + env(safe-area-inset-top));
  right: 12px;
  z-index: 101;
  color: #fff;
  background: rgba(0, 0, 0, 0.35);
  box-shadow: none;
  opacity: 0.6;
}

.viewer {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  background: #000;
}
.viewer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(10px + env(safe-area-inset-top)) 14px 10px;
  color: #fff;
}
.viewer-bar {
  gap: 12px;
}
.viewer-title {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
}
.viewer-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hd-layer {
  position: absolute;
  inset: 0;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.35s;
}
.hd-layer.shown {
  opacity: 1;
  pointer-events: auto;
}
.mode-switch {
  flex: none;
  display: flex;
  padding: 3px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
}
.mode-switch button {
  padding: 6px 14px;
  border-radius: 9px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  transition: background 0.2s, color 0.2s;
}
.mode-switch button.on {
  background: rgba(255, 255, 255, 0.92);
  color: #111;
  font-weight: 600;
}
.quality {
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.16);
}
.viewer-stage {
  position: relative;
  flex: 1;
  min-height: 0;
  padding-bottom: env(safe-area-inset-bottom);
}

@media (min-width: 900px) {
  .grid {
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 14px;
    padding: 8px 0 0;
  }
  .hidden-section {
    padding: 16px 0;
  }
  .unsupported {
    padding: 24px 0 0;
  }
}
</style>
