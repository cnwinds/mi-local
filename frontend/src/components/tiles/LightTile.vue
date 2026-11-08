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

const name = computed(() => props.title ?? single.value?.name ?? '')
const status = computed(() => {
  if (!online.value.length) return '离线'
  if (preview.value !== null) return preview.value ? `${preview.value}%` : '关闭'
  if (!single.value) return lit.value.length ? `${lit.value.length}/${props.devices.length} 亮 · ${brightness.value}%` : '全部关闭'
  return on.value ? `${brightness.value}%` : '关闭'
})

const el = ref<HTMLElement>()
let startX = 0
let startY = 0
let startLevel = 0
let dragging = false
let longPressed = false
let pressTimer: ReturnType<typeof setTimeout> | undefined

function down(e: PointerEvent) {
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
  clearTimeout(pressTimer)
  dragging = false
  preview.value = null
}

onBeforeUnmount(() => clearTimeout(pressTimer))
</script>

<template>
  <div
    ref="el"
    class="light-tile"
    :class="{ on: on || (preview ?? 0) > 0, offline: !online.length, group: !single }"
    @pointerdown="down"
    @pointermove="move"
    @pointerup="up"
    @pointercancel="cancel"
    @contextmenu.prevent
  >
    <div class="fill" :style="{ width: `${on || preview !== null ? level : 0}%` }" />
    <div class="content">
      <DeviceIcon kind="light" :active="on || (preview ?? 0) > 0" />
      <div class="name">{{ name }}</div>
      <div class="status">{{ status }}</div>
    </div>
  </div>
</template>

<style scoped>
.light-tile {
  position: relative;
  overflow: hidden;
  background: #fff;
  border-radius: 18px;
  padding: 14px;
  min-height: 112px;
  box-sizing: border-box;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
  -webkit-tap-highlight-color: transparent;
  touch-action: pan-y;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: transform 0.1s;
}
.light-tile:active {
  transform: scale(0.98);
}
.fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: linear-gradient(90deg, #fff1cc, #ffe39a);
  transition: width 0.15s;
}
.content {
  position: relative;
}
.name {
  margin-top: 12px;
  font-size: 15px;
  font-weight: 500;
  color: #1f2329;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.status {
  margin-top: 2px;
  font-size: 12px;
  color: #8f959e;
}
.on .status {
  color: #b9770e;
}
.offline {
  opacity: 0.5;
}
.group .name {
  font-weight: 600;
}
</style>
