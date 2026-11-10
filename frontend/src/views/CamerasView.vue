<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Cctv, EyeOff, Maximize, Minimize, X } from 'lucide-vue-next'
import PageHeader from '../components/PageHeader.vue'
import CameraFeed from '../components/CameraFeed.vue'
import { api, type Camera } from '../api'
import type { PlayerState } from '../cameraPlayer'
import { rooms } from '../store'

const cameras = ref<Camera[]>([])
const loaded = ref(false)
const states = ref<Record<string, PlayerState>>({})
const unsupported = ref<Record<string, boolean>>({})
const showHidden = ref(false)
const viewing = ref<Camera | null>(null)
const viewQuality = ref<'sd' | 'hd'>('hd')
const viewDowngraded = ref(false)
const wall = ref(false)
const root = ref<HTMLElement>()

const roomIndex = (room: string) => {
  const i = rooms.value.indexOf(room)
  return i < 0 ? rooms.value.length : i
}
const visible = computed(() =>
  cameras.value.filter((c) => !c.hidden).sort((a, b) => roomIndex(a.room) - roomIndex(b.room)),
)
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

function onState(id: string, state: PlayerState, error: { fatal: boolean } | null) {
  states.value[id] = state
  if (error?.fatal) unsupported.value[id] = true
}

async function setHidden(camera: Camera, value: boolean) {
  cameras.value = await api.setCameraHidden(camera.id, value)
  if (value && viewing.value?.id === camera.id) viewing.value = null
}

function open(camera: Camera) {
  viewing.value = camera
  viewQuality.value = 'hd'
  viewDowngraded.value = false
}

// Some cameras only answer in SD; drop to it once rather than retrying HD forever.
function onViewState(state: PlayerState, error: { fatal: boolean } | null) {
  if (state === 'error' && error && !error.fatal && viewQuality.value === 'hd' && !viewDowngraded.value) {
    viewQuality.value = 'sd'
    viewDowngraded.value = true
  }
}

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
        <CameraFeed v-if="viewing?.id !== c.id" :camera-id="c.id" quality="sd" @state="(s, e) => onState(c.id, s, e)" />
        <div class="label">
          <span class="live-dot" :class="{ on: states[c.id] === 'live' }" />
          <span class="name">{{ c.name }}</span>
          <span v-if="showRoom(c)" class="room">{{ c.room }}</span>
        </div>
        <span v-if="unsupported[c.id] && !wall" class="hide-chip" role="button" @click.stop="setHidden(c, true)">
          <EyeOff :size="13" />隐藏
        </span>
      </button>
    </div>

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
            <span class="live-dot" :class="{ on: states[`view:${viewing.id}`] === 'live' }" />{{ viewing.name }}
            <span class="quality">{{ viewQuality === 'hd' ? '高清' : '标清' }}</span>
          </div>
          <button class="round-button dark" title="关闭" @click="viewing = null"><X :size="20" /></button>
        </div>
        <div class="viewer-stage">
          <CameraFeed :camera-id="viewing.id" :quality="viewQuality" fit="contain"
            @state="(s, e) => { onState(`view:${viewing!.id}`, s, null); onViewState(s, e) }" />
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
.hide-chip {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 12px;
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(8px);
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
.viewer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
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
}
</style>
