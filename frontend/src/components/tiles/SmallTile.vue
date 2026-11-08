<script setup lang="ts">
import { computed } from 'vue'
import { showToast } from 'vant'
import type { Device } from '../../api'
import { sendCommand } from '../../store'
import { AC_MODE_NAMES } from '../../rooms'
import DeviceIcon from '../DeviceIcon.vue'

// Compact tile: one tap does the device's main thing, anything else opens the detail sheet.
const props = defineProps<{ device: Device }>()
const emit = defineEmits<{ detail: [device: Device] }>()

const s = computed(() => props.device.state)
const online = computed(() => !!s.value.online)
const active = computed(() => online.value && !!s.value.power)

const status = computed(() => {
  if (!online.value) return '离线'
  switch (props.device.kind) {
    case 'light':
      return s.value.power ? `${s.value.brightness}%` : '关闭'
    case 'plug':
      return s.value.power ? `${s.value.load_power ?? 0}W` : '关闭'
    case 'curtain':
      return `开合 ${s.value.position ?? 0}%`
    case 'ac':
      return s.value.power ? `${AC_MODE_NAMES[s.value.mode ?? 'auto']} ${s.value.target_temp}°` : '关闭'
    case 'doorbell':
      return '点击响铃'
    default:
      return s.value.power === undefined ? '在线' : s.value.power ? '开启' : '关闭'
  }
})

function tap() {
  const d = props.device
  if (!online.value) return emit('detail', d)
  if (d.kind === 'doorbell') {
    sendCommand(d.id, 'ring')
    showToast('叮咚')
  } else if (['light', 'plug', 'ac', 'bath_heater'].includes(d.kind)) {
    sendCommand(d.id, s.value.power ? 'turn_off' : 'turn_on', undefined, { power: !s.value.power })
  } else {
    emit('detail', d)
  }
}
</script>

<template>
  <div class="small-tile" :class="{ active, offline: !online }" @click="tap">
    <DeviceIcon :kind="device.kind" :active="active" class="icon" />
    <div class="name">{{ device.name }}</div>
    <div class="status">{{ status }}</div>
  </div>
</template>

<style scoped>
.small-tile {
  background: #fff;
  border-radius: 16px;
  padding: 10px;
  text-align: center;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: transform 0.1s;
}
.small-tile:active {
  transform: scale(0.96);
}
.icon {
  margin: 0 auto;
  transform: scale(0.85);
}
.name {
  margin-top: 4px;
  font-size: 13px;
  color: #1f2329;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.status {
  margin-top: 2px;
  font-size: 11px;
  color: #8f959e;
}
.active .status {
  color: #3e7bfa;
}
.offline {
  opacity: 0.5;
}
</style>
