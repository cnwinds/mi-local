<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, type Component } from 'vue'
import { showToast } from 'vant'
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Ellipsis, Moon, Plus, Power, Sun, Sunset, ToggleRight } from 'lucide-vue-next'
import { api, type Device, type Scene } from '../api'
import { can, deviceList, devices, rules, loadRules, scenes } from '../store'
import { BUILTIN_ACTIONS, lightsOf, panelLayout, panelRooms, roomDevices, roomSummary } from '../rooms'
import { goHome, switchRoom, wallUrl } from '../router'
import { fullName } from '../naming'
import LightTile from '../components/tiles/LightTile.vue'
import AcTile from '../components/tiles/AcTile.vue'
import CurtainTile from '../components/tiles/CurtainTile.vue'
import BathHeaterTile from '../components/tiles/BathHeaterTile.vue'
import AirerTile from '../components/tiles/AirerTile.vue'
import SmallTile from '../components/tiles/SmallTile.vue'
import DeviceCard from '../components/tiles/DeviceCard.vue'
import DeviceSheet from '../components/DeviceSheet.vue'
import PanelEditor from '../components/PanelEditor.vue'
import SceneEditor from '../components/SceneEditor.vue'

const props = defineProps<{ room: string; wall?: boolean }>()
const admin = can('admin')

const ACTION_ICONS: Record<string, Component> = { all_off: Power, bright: Sun, soft: Sunset, night: Moon }

const layout = computed(() => panelLayout(props.room).filter((i) => i.size !== 'hidden'))
const large = computed(() => layout.value.filter((i) => i.size === 'large'))
const small = computed(() => layout.value.filter((i) => i.size === 'small'))
const all = computed(() => roomDevices(props.room))
const lights = computed(() => large.value.filter((i) => i.device.kind === 'light').map((i) => i.device))
const summary = computed(() => roomSummary(props.room).join(' · ') || '没有可显示的状态')
const builtins = computed(() => BUILTIN_ACTIONS.filter((a) => a.key === 'all_off' || lightsOf(all.value).length))
const roomScenes = computed(() => scenes.value.filter((s) => s.room === props.room))
const newScene = (): Scene => ({ room: props.room, name: '', icon: '⭐', actions: [] })

// Neighbouring rooms, for the arrows and the header swipe.
const index = computed(() => panelRooms.value.indexOf(props.room))
const prevRoom = computed(() => panelRooms.value[index.value - 1])
const nextRoom = computed(() => panelRooms.value[index.value + 1])
let swipeX = 0
const swipeStart = (e: TouchEvent) => (swipeX = e.touches[0].clientX)
function swipeEnd(e: TouchEvent) {
  const dx = e.changedTouches[0].clientX - swipeX
  if (dx > 60 && prevRoom.value) switchRoom(prevRoom.value)
  else if (dx < -60 && nextRoom.value) switchRoom(nextRoom.value)
}

const detailId = ref<string | null>(null)
const openDetail = (d: Device) => (detailId.value = d.id)
const editingPanel = ref(false)
const editingScene = ref<Scene | null>(null)

async function runScene(scene: Scene) {
  await api.runScene(scene.id!)
  showToast(`已执行「${scene.name}」`)
}

let pressTimer: ReturnType<typeof setTimeout> | undefined
let pressed = false
function scenePress(scene: Scene) {
  pressed = false
  if (!admin) return
  pressTimer = setTimeout(() => {
    pressed = true
    editingScene.value = scene
  }, 550)
}
function sceneRelease(scene: Scene) {
  clearTimeout(pressTimer)
  if (!pressed) runScene(scene)
  pressed = true
}
function cancelPress() {
  clearTimeout(pressTimer)
  pressed = true
}

// Wireless switches in this room and what their single press does.
const switches = computed(() =>
  deviceList.value
    .filter((d) => d.kind === 'switch' && d.room === props.room)
    .map((d) => {
      const rule = rules.value.find((r) => r.trigger.device === d.id && r.trigger.event === 'click')
      const targets = (rule?.actions ?? []).map((a) => devices[a.device]).filter(Boolean)
      return { device: d, text: targets.length ? targets.map(fullName).join('、') : '还没设置' }
    }),
)
const showSwitches = ref(false)
onMounted(() => admin && !rules.value.length && loadRules())

const showMenu = ref(false)
const menuActions = computed(() => [
  ...(admin ? [{ name: '编辑面板' }, { name: '新建快捷操作' }] : []),
  { name: props.wall ? '退出墙面模式' : '用作墙面面板', subname: props.wall ? '' : '把这台手机或平板固定在墙上，常亮显示这个房间' },
])

function onMenu(choice: { name: string }) {
  showMenu.value = false
  if (choice.name === '编辑面板') editingPanel.value = true
  else if (choice.name === '新建快捷操作') editingScene.value = newScene()
  else if (props.wall) location.hash = `#/room/${encodeURIComponent(props.room)}`
  else {
    location.hash = new URL(wallUrl(props.room)).hash
    showToast({ message: '点一下屏幕进入全屏。\n点右上角「…」可以退出', duration: 3000 })
  }
}

// Wall mode: a clock, and keep the screen awake where the browser allows it.
const now = ref(new Date())
const clock = computed(() => now.value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))
const dateText = computed(() => now.value.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }))
let clockTimer: ReturnType<typeof setInterval> | undefined
let wakeLock: { release: () => Promise<void> } | null = null
async function keepAwake() {
  try {
    wakeLock = await (navigator as any).wakeLock?.request('screen')
  } catch {
    wakeLock = null
  }
}
function enterFullscreen() {
  if (props.wall && !document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {})
}
watch(
  () => props.wall,
  (wall) => {
    clearInterval(clockTimer)
    if (wall) {
      clockTimer = setInterval(() => (now.value = new Date()), 10_000)
      keepAwake()
    } else {
      wakeLock?.release()
      wakeLock = null
    }
  },
  { immediate: true },
)
const onVisible = () => props.wall && document.visibilityState === 'visible' && keepAwake()
document.addEventListener('visibilitychange', onVisible)
onBeforeUnmount(() => {
  clearInterval(clockTimer)
  clearTimeout(pressTimer)
  wakeLock?.release()
  document.removeEventListener('visibilitychange', onVisible)
})
</script>

<template>
  <div class="room-panel" :class="{ wall }" @click.capture="enterFullscreen">
    <header class="header" @touchstart.passive="swipeStart" @touchend="swipeEnd">
      <button v-if="!wall" class="icon-button back" title="返回" @click="goHome"><ChevronLeft :size="22" /></button>
      <div class="titles">
        <div v-if="wall" class="eyebrow">{{ dateText }}</div>
        <div class="title-row">
          <h1>{{ room }}</h1>
          <div class="room-nav">
            <button class="icon-button small" :disabled="!prevRoom" :title="prevRoom" @click="prevRoom && switchRoom(prevRoom)">
              <ChevronLeft :size="18" />
            </button>
            <button class="icon-button small" :disabled="!nextRoom" :title="nextRoom" @click="nextRoom && switchRoom(nextRoom)">
              <ChevronRight :size="18" />
            </button>
          </div>
        </div>
        <div class="summary">{{ summary }}</div>
      </div>
      <div v-if="wall" class="clock num">{{ clock }}</div>
      <button class="icon-button" title="更多" @click="showMenu = true"><Ellipsis :size="22" /></button>
    </header>

    <div class="layout">
      <section class="main-col">
        <div class="actions">
          <button v-for="a in builtins" :key="a.key" class="action" :class="a.key" @click="a.run(all)">
            <component :is="ACTION_ICONS[a.key]" :size="17" /><span>{{ a.name }}</span>
          </button>
          <button v-for="s in roomScenes" :key="s.id" class="action scene" :title="admin ? '长按编辑' : s.name" @pointerdown="scenePress(s)"
            @pointerup="sceneRelease(s)" @pointerleave="cancelPress" @contextmenu.prevent>
            <span class="emoji">{{ s.icon }}</span><span>{{ s.name }}</span>
          </button>
          <button v-if="admin" class="action add" @click="editingScene = newScene()"><Plus :size="17" /><span>快捷操作</span></button>
        </div>

        <div class="grid">
          <LightTile v-if="lights.length >= 3" :devices="lights" :title="`全部灯 · ${lights.length} 盏`" class="span2" />
          <template v-for="item in large" :key="item.id">
            <LightTile v-if="item.device.kind === 'light'" :devices="[item.device]" @detail="openDetail" />
            <AcTile v-else-if="item.device.kind === 'ac'" :device="item.device" class="span2" />
            <CurtainTile v-else-if="item.device.kind === 'curtain'" :device="item.device" class="span2" />
            <BathHeaterTile v-else-if="item.device.kind === 'bath_heater'" :device="item.device" class="span2" />
            <AirerTile v-else-if="item.device.kind === 'airer'" :device="item.device" class="span2" />
            <DeviceCard v-else :device="item.device" class="span2" @detail="openDetail" />
          </template>
        </div>
        <van-empty v-if="!layout.length" description="这个房间没有可显示的设备" />
      </section>

      <aside class="side-col">
        <template v-if="small.length">
          <div class="section-label">其他设备</div>
          <div class="small-grid">
            <SmallTile v-for="item in small" :key="item.id" :device="item.device" @detail="openDetail" />
          </div>
        </template>

        <template v-if="admin && switches.length && !wall">
          <button class="section-label toggle" @click="showSwitches = !showSwitches">
            <ToggleRight :size="15" />无线开关 · {{ switches.length }}
            <component :is="showSwitches ? ChevronUp : ChevronDown" :size="15" />
          </button>
          <div v-if="showSwitches" class="switch-list card">
            <div v-for="s in switches" :key="s.device.id" class="switch-row">
              <div class="switch-name">{{ s.device.name }}</div>
              <div class="switch-target">按一下 → {{ s.text }}</div>
            </div>
          </div>
        </template>
        <div v-if="admin && roomScenes.length" class="hint">长按快捷操作可以编辑或删除</div>
      </aside>
    </div>

    <van-action-sheet v-model:show="showMenu" :actions="menuActions" cancel-text="取消" close-on-click-action @select="onMenu" />
    <DeviceSheet :device-id="detailId" @close="detailId = null" />
    <PanelEditor :room="room" :show="editingPanel" @close="editingPanel = false" />
    <SceneEditor :room="room" :scene="editingScene" @close="editingScene = null" />
  </div>
</template>

<style scoped>
.room-panel {
  padding-bottom: 16px;
}
.header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: calc(18px + env(safe-area-inset-top)) 12px 4px;
}
.icon-button {
  flex: none;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text);
  background: var(--surface-glass);
  box-shadow: var(--shadow-1);
}
.icon-button.small {
  width: 30px;
  height: 30px;
  border-radius: 10px;
  color: var(--text-2);
  box-shadow: none;
  background: var(--surface-2);
}
.icon-button:disabled {
  opacity: 0.3;
}
.titles {
  flex: 1;
  min-width: 0;
  padding: 0 6px;
}
.eyebrow {
  font-size: 14px;
  color: var(--text-3);
  font-weight: 600;
}
.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 750;
  letter-spacing: -0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.room-nav {
  display: flex;
  gap: 4px;
}
.summary {
  margin-top: 4px;
  font-size: 14px;
  color: var(--text-2);
}
.clock {
  font-size: 40px;
  font-weight: 300;
  line-height: 1;
  padding: 4px 8px 0;
}
.layout {
  padding: 0 16px;
}
.actions {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 14px 2px 6px;
  margin: 0 -2px;
  scrollbar-width: none;
}
.actions::-webkit-scrollbar {
  display: none;
}
.action {
  flex: none;
  display: flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 16px;
  border-radius: 14px;
  background: var(--surface);
  box-shadow: var(--shadow-1);
  font-size: 14px;
  font-weight: 500;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  transition: transform 0.1s, background 0.15s;
}
.action:active {
  transform: scale(0.96);
  background: var(--surface-2);
}
.action svg {
  color: var(--accent);
}
.action.all_off svg {
  color: var(--danger);
}
.action.bright svg,
.action.soft svg {
  color: var(--warm-strong);
}
.action.add {
  background: transparent;
  box-shadow: inset 0 0 0 1.5px var(--surface-3);
  color: var(--text-3);
}
.action.add svg {
  color: var(--text-3);
}
.emoji {
  font-size: 16px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-flow: dense;
  gap: 12px;
  margin-top: 10px;
}
.span2 {
  grid-column: span 2;
}
.small-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.toggle {
  width: 100%;
  text-align: left;
}
.switch-list {
  padding: 4px 16px;
}
.switch-row {
  padding: 12px 0;
}
.switch-row + .switch-row {
  border-top: 1px solid var(--line);
}
.switch-name {
  font-size: 14px;
  font-weight: 500;
}
.switch-target {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 2px;
}
.hint {
  font-size: 12px;
  color: var(--text-3);
  padding: 16px 4px 0;
}

/* Wider screens (tablets on the wall included) fit as many columns as the width allows. */
@media (min-width: 640px) {
  .grid {
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  }
  .small-grid {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  }
}
@media (min-width: 900px) {
  .header {
    padding: 28px 0 4px;
  }
  .layout {
    padding: 0;
  }
  .grid {
    gap: 16px;
  }
  .side-col {
    padding-top: 10px;
  }
  h1 {
    font-size: 34px;
  }
}
@media (min-width: 1280px) {
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: 28px;
    align-items: start;
  }
  .side-col {
    position: sticky;
    top: 20px;
    padding-top: 6px;
  }
  .small-grid {
    grid-template-columns: 1fr;
  }
}

/* Wall mode fills the screen on its own, without the app shell. */
.wall {
  min-height: 100vh;
  box-sizing: border-box;
  padding: 8px 8px 24px;
}
.wall h1 {
  font-size: 36px;
}
.wall .summary {
  font-size: 16px;
}
@media (min-width: 900px) {
  .wall {
    padding: 8px 32px 32px;
  }
  .wall .header {
    padding-top: 24px;
  }
}
</style>
