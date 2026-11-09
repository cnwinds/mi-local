<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import type { Device } from '../../api'
import { sendCommand } from '../../store'
import { lightsOf, toggleLights } from '../../rooms'
import DeviceIcon from '../DeviceIcon.vue'

// One light, or a whole room's lights acting as a group.
const props = defineProps<{ devices: Device[]; title?: string }>()
const emit = defineEmits<{ detail: [device: Device] }>()

const single = computed(() => (props.devices.length === 1 ? props.devices[0] : null))
const online = computed(() => lightsOf(props.devices))
const lit = computed(() => online.value.filter((d) => d.state.power))
const on = computed(() => lit.value.length > 0)
const brightness = computed(() =>
  lit.value.length ? Math.round(lit.value.reduce((sum, d) => sum + (d.state.brightness ?? 100), 0) / lit.value.length) : 0,
)
const preview = ref<number | null>(null)
const level = computed(() => preview.value ?? brightness.value)
const shownOn = computed(() => (preview.value !== null ? preview.value > 0 : on.value))

const name = computed(() => props.title ?? single.value?.name ?? '')
const sub = computed(() => {
  if (!online.value.length) return '离线'
  if (!single.value) return lit.value.length ? `${lit.value.length}/${props.devices.length} 盏亮着` : '全部关闭'
  return shownOn.value ? '' : '关闭'
})

const el = ref<HTMLElement>()
let startX = 0
let startY = 0
let startLevel = 0
let pressed = false
let dragging = false
let longPressed = false
let pressTimer: ReturnType<typeof setTimeout> | undefined

function down(e: PointerEvent) {
  if (e.button !== 0) return
  pressed = true
  startX = e.clientX
  startY = e.clientY
  startLevel = brightness.value
  dragging = false
  longPressed = false
  clearTimeout(pressTimer)
  pressTimer = setTimeout(() => {
    if (dragging) return
    longPressed = true
    if (single.value) emit('detail', single.value)
  }, 550)
}

function move(e: PointerEvent) {
  // A mouse sends move events while just hovering; only a held button counts as a drag.
  if (!pressed || (e.pointerType === 'mouse' && !(e.buttons & 1))) return
  const dx = e.clientX - startX
  const dy = e.clientY - startY
  if (!dragging && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) && online.value.length && !longPressed) {
    dragging = true
    clearTimeout(pressTimer)
    el.value?.setPointerCapture(e.pointerId)
  } else if (!dragging && Math.abs(dy) > 10) {
    clearTimeout(pressTimer)
  }
  if (dragging) {
    const width = el.value?.offsetWidth ?? 160
    preview.value = Math.max(0, Math.min(100, Math.round(startLevel + (dx / width) * 120)))
  }
}

function up() {
  if (!pressed) return
  pressed = false
  clearTimeout(pressTimer)
  if (dragging && preview.value !== null) {
    const value = preview.value
    for (const d of online.value) {
      if (value === 0) sendCommand(d.id, 'turn_off', undefined, { power: false })
      else sendCommand(d.id, 'set_brightness', value, { power: true, brightness: value })
    }
  } else if (!longPressed) {
    if (!online.value.length) {
      if (single.value) emit('detail', single.value)
    } else {
      toggleLights(props.devices)
    }
  }
  dragging = false
  preview.value = null
}

function cancel() {
  pressed = false
  clearTimeout(pressTimer)
  dragging = false
  preview.value = null
}

onBeforeUnmount(() => clearTimeout(pressTimer))
</script>

<template>
  <div
    ref="el"
    class="light-tile card pressable"
    :class="{ on: shownOn, offline: !online.length, dragging: preview !== null }"
    @pointerdown="down"
    @pointermove="move"
    @pointerup="up"
    @pointercancel="cancel"
    @contextmenu.prevent
  >
    <div class="fill" :style="{ width: `${shownOn ? level : 0}%` }" />
    <div class="content">
      <div class="top">
        <DeviceIcon kind="light" :model="single?.model" :name="single?.name" :active="shownOn" :size="42" />
        <div v-if="shownOn && online.length" class="level num">{{ level }}<small>%</small></div>
      </div>
      <div class="name">{{ name }}</div>
      <div class="sub">{{ sub || '左右滑动调亮度' }}</div>
    </div>
  </div>
</template>

<style scoped>
.light-tile {
  position: relative;
  overflow: hidden;
  padding: 16px;
  min-height: 132px;
  box-sizing: border-box;
  -webkit-touch-callout: none;
  touch-action: pan-y;
  cursor: pointer;
}
.fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--warm-glow);
  transition: width 0.18s ease;
}
.light-tile.on .fill {
  background: linear-gradient(90deg, rgba(255, 210, 120, 0.55), rgba(255, 225, 160, 0.35));
}
.dragging .fill {
  transition: none;
}
.content {
  position: relative;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.level {
  font-size: 26px;
  font-weight: 600;
  color: var(--warm-strong);
}
.level small {
  font-size: 13px;
  margin-left: 1px;
}
.name {
  margin-top: 14px;
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-3);
}
.on .sub {
  color: var(--text-2);
}
.offline {
  opacity: 0.5;
}
@media (prefers-color-scheme: dark) {
  .light-tile.on .fill {
    background: linear-gradient(90deg, rgba(247, 168, 35, 0.35), rgba(247, 168, 35, 0.15));
  }
  .level {
    color: var(--warm);
  }
}
</style>
