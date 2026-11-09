<script setup lang="ts">
import { computed } from 'vue'
import { showToast } from 'vant'
import type { Device } from '../../api'
import { sendCommand } from '../../store'
import { deviceStatus } from '../../rooms'
import DeviceIcon from '../DeviceIcon.vue'

// Compact tile: one tap does the device's main thing, anything else opens the detail sheet.
const props = defineProps<{ device: Device }>()
const emit = defineEmits<{ detail: [device: Device] }>()

const s = computed(() => props.device.state)
const online = computed(() => !!s.value.online)
const active = computed(() => online.value && !!s.value.power)

const status = computed(() => deviceStatus(props.device))

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
  <div class="small-tile card pressable" :class="{ active, offline: !online }" @click="tap">
    <DeviceIcon :kind="device.kind" :model="device.model" :name="device.name" :active="active" :size="36" />
    <div class="text">
      <div class="name">{{ device.name }}</div>
      <div class="status">{{ status }}</div>
    </div>
  </div>
</template>

<style scoped>
.small-tile {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: var(--radius);
  cursor: pointer;
  min-width: 0;
}
.text {
  min-width: 0;
}
.name {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.status {
  margin-top: 1px;
  font-size: 12px;
  color: var(--text-3);
}
.active .status {
  color: var(--accent-text);
}
.offline {
  opacity: 0.5;
}
</style>
