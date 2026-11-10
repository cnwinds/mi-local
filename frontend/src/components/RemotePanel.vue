<script setup lang="ts">
import { computed, onMounted, ref, type Component } from 'vue'
import {
  ArrowLeftRight, ChevronDown, ChevronUp, Power, PowerOff, Thermometer, TvMinimalPlay, Volume, Volume1, Volume2,
  VolumeX, Wind,
} from 'lucide-vue-next'
import type { Device, DeviceField } from '../api'
import { deviceFields, ensureFields, sendCommand } from '../store'

// An infrared remote's buttons. There is no state to show: the blaster just sends the code.
const props = defineProps<{ device: Device }>()
onMounted(() => ensureFields(props.device.id))

const ORDER = [
  'temperature-down', 'temperature-up', 'fan-speed-down', 'fan-speed-up', 'channel-down', 'channel-up',
  'volume-down', 'volume-up', 'mute-on', 'mute-off', 'horizontal-swing-on', 'horizontal-swing-off', 'input-source-switch',
]
const ICONS: Record<string, Component> = {
  'temperature-down': Thermometer, 'temperature-up': Thermometer, 'fan-speed-down': Wind, 'fan-speed-up': Wind,
  'channel-down': ChevronDown, 'channel-up': ChevronUp, 'volume-down': Volume1, 'volume-up': Volume2,
  'mute-on': VolumeX, 'mute-off': Volume, 'horizontal-swing-on': ArrowLeftRight, 'horizontal-swing-off': ArrowLeftRight,
  'input-source-switch': TvMinimalPlay,
}

const actions = computed(() => (deviceFields[props.device.id] ?? []).filter((f) => f.format === 'action'))
const on = computed(() => actions.value.find((a) => a.prop === 'turn-on'))
const off = computed(() => actions.value.find((a) => a.prop === 'turn-off'))
const rank = (a: DeviceField) => (ORDER.includes(a.prop) ? ORDER.indexOf(a.prop) : ORDER.length)
const buttons = computed(() =>
  actions.value.filter((a) => a !== on.value && a !== off.value).sort((a, b) => rank(a) - rank(b)),
)

const flashing = ref('')
function press(a: DeviceField) {
  flashing.value = a.key
  setTimeout(() => flashing.value === a.key && (flashing.value = ''), 300)
  sendCommand(props.device.id, 'run_action', { key: a.key })
}
</script>

<template>
  <div class="remote">
    <div v-if="on || off" class="power">
      <button v-if="on" class="big on" :class="{ flash: flashing === on.key }" @click="press(on)">
        <Power :size="22" />{{ on.name }}
      </button>
      <button v-if="off" class="big" :class="{ flash: flashing === off.key }" @click="press(off)">
        <PowerOff :size="22" />{{ off.name }}
      </button>
    </div>
    <div v-if="buttons.length" class="grid">
      <button v-for="a in buttons" :key="a.key" class="key" :class="{ flash: flashing === a.key }" @click="press(a)">
        <component :is="ICONS[a.prop]" v-if="ICONS[a.prop]" :size="17" />{{ a.name }}
      </button>
    </div>
    <div v-if="!actions.length" class="tip">正在读取遥控按键…</div>
    <div class="tip">红外遥控只负责发送按键，看不到电器当前的状态。</div>
  </div>
</template>

<style scoped>
.remote {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.power {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.big {
  height: 64px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 650;
  background: var(--surface-2);
  color: var(--text-2);
  transition: transform 0.1s, background 0.2s, color 0.2s;
}
.big.on {
  background: var(--accent-soft);
  color: var(--accent-text);
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.key {
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  background: var(--surface-2);
  color: var(--text);
  transition: transform 0.1s, background 0.2s, color 0.2s;
}
.big:active,
.key:active {
  transform: scale(0.96);
}
.flash {
  background: var(--accent) !important;
  color: #fff !important;
}
.tip {
  font-size: 12px;
  color: var(--text-3);
  text-align: center;
}
</style>
