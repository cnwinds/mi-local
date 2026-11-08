<script setup lang="ts">
import { computed } from 'vue'
import type { Device } from '../api'
import { sendCommand } from '../store'
import DeviceIcon from './DeviceIcon.vue'

const props = defineProps<{ device: Device }>()
const emit = defineEmits<{ detail: [device: Device] }>()

const s = computed(() => props.device.state)
const active = computed(() => !!s.value.online && (s.value.power || (props.device.kind === 'curtain' && (s.value.position ?? 0) > 0)))

const status = computed(() => {
  if (!s.value.online) return '离线'
  switch (props.device.kind) {
    case 'light':
      return s.value.power ? `已开启 · ${s.value.brightness}%` : '已关闭'
    case 'plug':
      return s.value.power ? `已开启 · ${s.value.load_power ?? 0}W` : '已关闭'
    case 'curtain':
      return `开合 ${s.value.position ?? 0}%`
    default:
      return '在线'
  }
})

function tap() {
  const d = props.device
  if (s.value.online && (d.kind === 'light' || d.kind === 'plug')) {
    const on = !s.value.power
    sendCommand(d.id, on ? 'turn_on' : 'turn_off', undefined, { power: on })
  } else {
    emit('detail', d)
  }
}
</script>

<template>
  <div class="card" :class="{ active, offline: !s.online }" @click="tap">
    <div class="top">
      <DeviceIcon :kind="device.kind" :active="active" />
      <van-icon name="arrow" class="more" @click.stop="emit('detail', device)" />
    </div>
    <div class="name">{{ device.name }}</div>
    <div class="status">{{ status }}</div>
  </div>
</template>

<style scoped>
.card {
  background: #fff;
  border-radius: 16px;
  padding: 14px;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.1s, box-shadow 0.2s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.card:active {
  transform: scale(0.97);
}
.card.offline {
  opacity: 0.55;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.more {
  color: #c4c7cc;
  padding: 4px;
  margin: -4px;
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
  margin-top: 4px;
  font-size: 12px;
  color: #8f959e;
}
.card.active .status {
  color: #3e7bfa;
}
</style>
