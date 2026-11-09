<script setup lang="ts">
import { computed, toRef } from 'vue'
import { showToast } from 'vant'
import { BellRing, ChevronRight, Minus, Plus, Power } from 'lucide-vue-next'
import type { Device } from '../../api'
import { sendCommand } from '../../store'
import { cardLabel, cardModel, unitLabel } from '../../miot'
import { useMiot } from '../../useMiot'
import DeviceIcon from '../DeviceIcon.vue'

// Wall-panel card for appliances: the key readings at a glance, the common controls in reach,
// a tap anywhere else opens the full sheet.
const props = defineProps<{ device: Device }>()
const emit = defineEmits<{ detail: [device: Device] }>()

const device = toRef(props, 'device')
const { fields, values, powerKey, on, set, num, step, togglePower } = useMiot(device)
const s = computed(() => props.device.state)
const online = computed(() => !!s.value.online)
const isPlug = computed(() => props.device.kind === 'plug')
const hasPower = computed(() => online.value && (!!powerKey.value || isPlug.value))
const powered = computed(() => (isPlug.value ? !!s.value.power : on.value))
const active = computed(() => online.value && hasPower.value && powered.value)

const model = computed(() => cardModel(fields.value, values.value, powerKey.value))

const metrics = computed(() => {
  if (isPlug.value) return online.value ? [{ label: '当前功率', value: String(s.value.load_power ?? 0), unit: 'W', text: false }] : []
  return model.value.metrics.map((m) => {
    const hit = /^(-?[\d.]+)\s*(.*)$/.exec(m.text)
    return { label: m.field.name, value: hit ? hit[1] : m.text, unit: hit ? hit[2] : '', text: !hit }
  })
})

const status = computed(() => {
  if (!online.value) return '离线'
  if (hasPower.value) return powered.value ? '已开启' : '已关闭'
  return '在线'
})

function power() {
  if (isPlug.value) sendCommand(props.device.id, powered.value ? 'turn_off' : 'turn_on', undefined, { power: !powered.value })
  else togglePower()
}

function ring() {
  sendCommand(props.device.id, 'ring')
  showToast('叮咚')
}
</script>

<template>
  <div class="device-card card" :class="{ active, offline: !online }" @click="emit('detail', device)">
    <header>
      <DeviceIcon :kind="device.kind" :model="device.model" :active="active" :size="42" />
      <div class="text">
        <div class="name">{{ device.name }}</div>
        <div class="status">{{ status }}<ChevronRight :size="13" /></div>
      </div>
      <button v-if="hasPower" class="power" :class="{ on: powered }" :title="powered ? '关闭' : '打开'" @click.stop="power">
        <Power :size="20" :stroke-width="2.4" />
      </button>
      <button v-else-if="online && device.kind === 'doorbell'" class="power" title="响铃" @click.stop="ring">
        <BellRing :size="19" />
      </button>
    </header>

    <template v-if="online">
      <div v-if="metrics.length" class="metrics">
        <div v-for="m in metrics" :key="m.label" class="metric">
          <div class="value num" :class="{ text: m.text }">{{ m.value }}<small v-if="m.unit">{{ m.unit }}</small></div>
          <div class="label">{{ m.label }}</div>
        </div>
      </div>

      <div v-for="f in model.controls" :key="f.key" class="control" @click.stop>
        <span class="label">{{ cardLabel(f, fields) }}</span>
        <div v-if="f.values.length" class="segmented">
          <button v-for="o in f.values" :key="String(o.value)" :class="{ selected: values[f.key] === o.value }"
            @click="set(f, o.value)">{{ o.label }}</button>
        </div>
        <div v-else-if="(f.range![1] - f.range![0]) / f.range![2] <= 60" class="stepper">
          <button :disabled="num(f) <= f.range![0]" @click="step(f, -1)"><Minus :size="18" /></button>
          <b class="num">{{ num(f) }}<small>{{ unitLabel(f.unit) }}</small></b>
          <button :disabled="num(f) >= f.range![1]" @click="step(f, 1)"><Plus :size="18" /></button>
        </div>
        <van-slider v-else :model-value="Number(values[f.key])" :min="f.range![0]" :max="f.range![1]" :step="f.range![2]"
          bar-height="6px" active-color="var(--accent)" class="slider" @change="(v: number) => set(f, v)" />
      </div>

      <div v-if="model.toggles.length" class="toggles" @click.stop>
        <button v-for="f in model.toggles" :key="f.key" :class="{ selected: values[f.key] === true }"
          @click="set(f, !values[f.key])">
          <span class="dot" />{{ cardLabel(f, fields) }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.device-card {
  padding: 16px;
  cursor: pointer;
  transition: background 0.3s;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.device-card.active {
  background: var(--accent-glow);
}
.offline {
  opacity: 0.5;
}
header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.text {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.status {
  display: flex;
  align-items: center;
  gap: 1px;
  margin-top: 2px;
  font-size: 13px;
  color: var(--text-3);
}
.power {
  flex: none;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-3);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.power.on {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 6px 18px rgba(75, 103, 245, 0.35);
}
.metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.metric {
  min-width: 0;
}
.metric .value {
  font-size: 26px;
  font-weight: 500;
  line-height: 1.1;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.metric .value.text {
  font-size: 19px;
  line-height: 29px;
}
.metric small {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-3);
  margin-left: 2px;
}
.metric .label,
.control .label {
  font-size: 12px;
  color: var(--text-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.metric .label {
  margin-top: 3px;
}
.control {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: default;
}
.control .label {
  flex: none;
  min-width: 48px;
}
.segmented {
  flex: 1;
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: 14px;
  background: var(--surface-2);
}
.segmented button {
  flex: 1;
  height: 34px;
  border-radius: 11px;
  font-size: 13px;
  color: var(--text-2);
  transition: all 0.2s;
}
.segmented button.selected {
  background: var(--surface);
  color: var(--accent-text);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}
.stepper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
}
.stepper button {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: var(--shadow-1);
  color: var(--text);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.1s;
}
.stepper button:active {
  transform: scale(0.92);
}
.stepper button:disabled {
  opacity: 0.3;
}
.stepper b {
  min-width: 64px;
  text-align: center;
  font-size: 30px;
  font-weight: 400;
}
.stepper small {
  font-size: 14px;
  color: var(--text-3);
  margin-left: 1px;
}
.slider {
  flex: 1;
  margin: 0 8px;
}
.toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  cursor: default;
}
.toggles button {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 36px;
  padding: 0 14px;
  border-radius: 12px;
  background: var(--surface-2);
  color: var(--text-2);
  font-size: 13px;
  transition: all 0.2s;
}
.toggles .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-3);
  opacity: 0.5;
}
.toggles button.selected {
  background: var(--accent-soft);
  color: var(--accent-text);
  font-weight: 600;
}
.toggles button.selected .dot {
  background: var(--accent);
  opacity: 1;
  box-shadow: 0 0 0 3px rgba(75, 103, 245, 0.2);
}
</style>
