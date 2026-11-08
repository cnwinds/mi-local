<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { showToast } from 'vant'
import { api, type Device, type Scene } from '../api'
import { deviceList, devices, rules, loadRules, scenes } from '../store'
import { BUILTIN_ACTIONS, lightsOf, panelLayout, panelRooms, roomDevices, roomSummary } from '../rooms'
import { goHome, switchRoom, wallUrl } from '../router'
import { fullName } from '../naming'
import LightTile from '../components/tiles/LightTile.vue'
import AcTile from '../components/tiles/AcTile.vue'
import CurtainTile from '../components/tiles/CurtainTile.vue'
import BathHeaterTile from '../components/tiles/BathHeaterTile.vue'
import AirerTile from '../components/tiles/AirerTile.vue'
import SmallTile from '../components/tiles/SmallTile.vue'
import DeviceSheet from '../components/DeviceSheet.vue'
import PanelEditor from '../components/PanelEditor.vue'
import SceneEditor from '../components/SceneEditor.vue'

const props = defineProps<{ room: string; wall?: boolean }>()

const layout = computed(() => panelLayout(props.room).filter((i) => i.size !== 'hidden'))
const large = computed(() => layout.value.filter((i) => i.size === 'large'))
const small = computed(() => layout.value.filter((i) => i.size === 'small'))
const all = computed(() => roomDevices(props.room))
const lights = computed(() => large.value.filter((i) => i.device.kind === 'light').map((i) => i.device))
const summary = computed(() => roomSummary(props.room).join(' · ') || '没有可显示的状态')
const builtins = computed(() =>
  BUILTIN_ACTIONS.filter((a) => a.key === 'all_off' || lightsOf(all.value).length),
)
const roomScenes = computed(() => scenes.value.filter((s) => s.room === props.room))

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
onMounted(() => !rules.value.length && loadRules())

const showMenu = ref(false)
const menuActions = computed(() => [
  { name: '编辑面板' },
  { name: '新建快捷操作' },
  { name: props.wall ? '退出墙面模式' : '用作墙面面板', subname: props.wall ? '' : '把这台手机或平板固定在墙上，常亮显示这个房间' },
])

function onMenu(choice: { name: string }) {
  showMenu.value = false
  if (choice.name === '编辑面板') editingPanel.value = true
  else if (choice.name === '新建快捷操作') editingScene.value = { room: props.room, name: '', icon: '⭐', actions: [] }
  else if (props.wall) location.hash = `#/room/${encodeURIComponent(props.room)}`
  else {
    location.hash = new URL(wallUrl(props.room)).hash
    showToast({ message: '点一下屏幕进入全屏。\n点右上角「…」可以退出', duration: 3000 })
  }
}

// Wall mode: a clock, and keep the screen awake where the browser allows it.
const now = ref(new Date())
const clock = computed(() => now.value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))
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
      <van-icon v-if="!wall" name="arrow-left" class="back" @click="goHome" />
      <div class="titles">
        <div class="title">
          <van-icon name="arrow-left" class="nav" :class="{ hidden: !prevRoom }" @click="prevRoom && switchRoom(prevRoom)" />
          <span>{{ room }}</span>
          <van-icon name="arrow" class="nav" :class="{ hidden: !nextRoom }" @click="nextRoom && switchRoom(nextRoom)" />
        </div>
        <div class="summary">{{ summary }}</div>
      </div>
      <div v-if="wall" class="clock">{{ clock }}</div>
      <van-icon name="ellipsis" class="more" @click="showMenu = true" />
    </header>

    <div class="actions">
      <button v-for="a in builtins" :key="a.key" class="action" @click="a.run(all)">
        <van-icon :name="a.icon" /><span>{{ a.name }}</span>
      </button>
      <button v-for="s in roomScenes" :key="s.id" class="action scene" @pointerdown="scenePress(s)"
        @pointerup="sceneRelease(s)" @pointerleave="cancelPress" @contextmenu.prevent>
        <span class="emoji">{{ s.icon }}</span><span>{{ s.name }}</span>
      </button>
      <button class="action add" @click="editingScene = { room, name: '', icon: '⭐', actions: [] }">
        <van-icon name="plus" /><span>快捷</span>
      </button>
    </div>
    <div v-if="roomScenes.length" class="hint">长按快捷操作可以编辑</div>

    <div class="grid">
      <LightTile v-if="lights.length >= 3" :devices="lights" :title="`全部灯（${lights.length}）`" class="span2" />
      <template v-for="item in large" :key="item.id">
        <LightTile v-if="item.device.kind === 'light'" :devices="[item.device]" @detail="openDetail" />
        <AcTile v-else-if="item.device.kind === 'ac'" :device="item.device" class="span2" />
        <CurtainTile v-else-if="item.device.kind === 'curtain'" :device="item.device" class="span2" />
        <BathHeaterTile v-else-if="item.device.kind === 'bath_heater'" :device="item.device" class="span2" />
        <AirerTile v-else-if="item.device.kind === 'airer'" :device="item.device" class="span2" />
        <SmallTile v-else :device="item.device" @detail="openDetail" />
      </template>
    </div>

    <div v-if="small.length" class="section-title">其他设备</div>
    <div class="small-grid">
      <SmallTile v-for="item in small" :key="item.id" :device="item.device" @detail="openDetail" />
    </div>

    <van-empty v-if="!layout.length" description="这个房间没有可显示的设备" />

    <div v-if="switches.length && !wall" class="switches">
      <div class="section-title clickable" @click="showSwitches = !showSwitches">
        这个房间的无线开关（{{ switches.length }}）<van-icon :name="showSwitches ? 'arrow-up' : 'arrow-down'" />
      </div>
      <van-cell-group v-if="showSwitches" inset>
        <van-cell v-for="s in switches" :key="s.device.id" :title="s.device.name" :label="`按一下：${s.text}`" />
      </van-cell-group>
    </div>

    <van-action-sheet v-model:show="showMenu" :actions="menuActions" cancel-text="取消" close-on-click-action @select="onMenu" />
    <DeviceSheet :device-id="detailId" @close="detailId = null" />
    <PanelEditor :room="room" :show="editingPanel" @close="editingPanel = false" />
    <SceneEditor :room="room" :scene="editingScene" @close="editingScene = null" />
  </div>
</template>

<style scoped>
.room-panel {
  padding-bottom: 24px;
}
.header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: calc(14px + env(safe-area-inset-top)) 12px 6px;
}
.back,
.more {
  font-size: 22px;
  padding: 8px;
  color: #1f2329;
}
.titles {
  flex: 1;
  min-width: 0;
  text-align: center;
}
.title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 22px;
  font-weight: 700;
  color: #1f2329;
}
.nav {
  font-size: 16px;
  color: #8f959e;
  padding: 4px;
}
.nav.hidden {
  visibility: hidden;
}
.summary {
  margin-top: 4px;
  font-size: 13px;
  color: #646a73;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.clock {
  font-size: 22px;
  font-weight: 300;
  color: #1f2329;
  font-variant-numeric: tabular-nums;
}
.actions {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 10px 16px 4px;
  scrollbar-width: none;
}
.actions::-webkit-scrollbar {
  display: none;
}
.action {
  flex: none;
  display: flex;
  align-items: center;
  gap: 5px;
  border: none;
  font: inherit;
  font-size: 14px;
  padding: 9px 14px;
  border-radius: 20px;
  background: #fff;
  color: #1f2329;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  -webkit-tap-highlight-color: transparent;
}
.action:active {
  background: #eef3ff;
}
.action .van-icon {
  font-size: 16px;
  color: #3e7bfa;
}
.action.add {
  color: #8f959e;
  background: transparent;
  box-shadow: inset 0 0 0 1px #dcdee3;
}
.action.add .van-icon {
  color: #8f959e;
}
.emoji {
  font-size: 15px;
}
.hint {
  font-size: 11px;
  color: #b0b4ba;
  padding: 2px 20px 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 12px 16px;
}
.span2 {
  grid-column: span 2;
}
.section-title {
  font-size: 13px;
  color: #8f959e;
  padding: 8px 20px 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.small-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 8px 16px;
}
.switches {
  margin-top: 8px;
}

/* Wall mode: larger type, and wider screens get more columns. */
.wall .title {
  font-size: 28px;
}
.wall .summary {
  font-size: 15px;
}
@media (min-width: 700px) {
  .grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .small-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
  .room-panel {
    max-width: 1200px;
    margin: 0 auto;
  }
}
</style>
