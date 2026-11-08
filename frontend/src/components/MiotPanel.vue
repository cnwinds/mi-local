<script setup lang="ts">
import { computed, reactive, watchEffect } from 'vue'
import { Minus, Plus, Power } from 'lucide-vue-next'
import type { Device, DeviceField, PropValue } from '../api'
import { deviceFields, ensureFields, sendCommand } from '../store'
import { formatValue, isNumeric, mainPowerKey, unitLabel } from '../miot'

const props = defineProps<{ device: Device }>()

watchEffect(() => ensureFields(props.device.id))

const fields = computed(() => deviceFields[props.device.id] ?? [])
const values = computed(() => props.device.state.props ?? {})
const powerKey = computed(() => mainPowerKey(fields.value))
const on = computed(() => (powerKey.value ? values.value[powerKey.value] === true : true))
const pending = reactive<Record<string, number>>({})
const timers: Record<string, ReturnType<typeof setTimeout>> = {}

const groups = computed(() => {
  const out: { service: string; items: DeviceField[] }[] = []
  for (const f of fields.value) {
    if (f.key === powerKey.value || values.value[f.key] === undefined) continue
    const g = out.find((x) => x.service === f.service) ?? out[out.push({ service: f.service, items: [] }) - 1]
    g.items.push(f)
  }
  return out
})

type Control = 'switch' | 'chips' | 'stepper' | 'slider' | 'text'
function control(f: DeviceField): Control {
  if (!f.writable) return 'text'
  if (f.format === 'bool') return 'switch'
  if (f.values.length) return 'chips'
  if (f.range && isNumeric(f)) return (f.range[1] - f.range[0]) / f.range[2] <= 60 ? 'stepper' : 'slider'
  return 'text'
}

function set(f: DeviceField, value: PropValue) {
  sendCommand(props.device.id, 'set_prop', { key: f.key, value }, { props: { ...values.value, [f.key]: value } })
}

function num(f: DeviceField) {
  return pending[f.key] ?? Number(values.value[f.key])
}

function step(f: DeviceField, dir: number) {
  const [lo, hi, st] = f.range!
  const next = Math.min(hi, Math.max(lo, Math.round((num(f) + dir * st) * 100) / 100))
  pending[f.key] = next
  clearTimeout(timers[f.key])
  timers[f.key] = setTimeout(() => {
    set(f, next)
    delete pending[f.key]
  }, 700)
}

function togglePower() {
  if (powerKey.value) set(fields.value[0], !on.value)
}
</script>

<template>
  <div class="miot">
    <button v-if="powerKey" class="power" :class="{ on }" @click="togglePower">
      <Power :size="36" :stroke-width="2" />
      <span>{{ on ? '已开启' : '已关闭' }}</span>
    </button>

    <div v-if="!fields.length" class="tip">正在读取设备能力…</div>

    <section v-for="g in groups" :key="g.service" class="group">
      <div class="section-label">{{ g.service }}</div>
      <div class="rows">
        <template v-for="f in g.items" :key="f.key">
          <div v-if="control(f) === 'chips'" class="row col">
            <span class="label">{{ f.name }}</span>
            <div class="chips">
              <button v-for="o in f.values" :key="String(o.value)" class="chip pressable"
                :class="{ on: values[f.key] === o.value }" @click="set(f, o.value)">{{ o.label }}</button>
            </div>
          </div>
          <div v-else-if="control(f) === 'slider'" class="row col">
            <span class="label">{{ f.name }} <b class="num">{{ formatValue(f, values[f.key]) }}</b></span>
            <van-slider :model-value="Number(values[f.key])" :min="f.range![0]" :max="f.range![1]" :step="f.range![2]"
              bar-height="28px" active-color="var(--accent)" @change="(v: number) => set(f, v)">
              <template #button><span /></template>
            </van-slider>
          </div>
          <div v-else class="row">
            <span class="label">{{ f.name }}</span>
            <van-switch v-if="control(f) === 'switch'" :model-value="!!values[f.key]" size="22px"
              active-color="var(--accent)" @update:model-value="(v: boolean) => set(f, v)" />
            <div v-else-if="control(f) === 'stepper'" class="stepper">
              <button class="pressable" :disabled="num(f) <= f.range![0]" @click="step(f, -1)"><Minus :size="18" /></button>
              <span class="num">{{ num(f) }}<small>{{ unitLabel(f.unit) }}</small></span>
              <button class="pressable" :disabled="num(f) >= f.range![1]" @click="step(f, 1)"><Plus :size="18" /></button>
            </div>
            <span v-else class="value num">{{ formatValue(f, values[f.key]) }}</span>
          </div>
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped>
.power {
  margin: 0 auto 20px;
  width: 112px;
  height: 112px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-3);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  transition: all 0.25s;
}
.power.on {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 0 0 9px var(--accent-soft);
}
.group + .group {
  margin-top: 16px;
}
.rows {
  background: var(--surface-2);
  border-radius: var(--radius);
  padding: 2px 14px;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 48px;
  padding: 6px 0;
}
.row + .row {
  border-top: 1px solid var(--line);
}
.row.col {
  flex-direction: column;
  align-items: stretch;
  padding: 12px 0;
}
.label {
  font-size: 14px;
  display: flex;
  justify-content: space-between;
}
.label b {
  font-weight: 500;
  color: var(--text-2);
}
.value {
  color: var(--text-2);
  font-size: 14px;
  text-align: right;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.chip {
  padding: 7px 14px;
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-2);
  font-size: 13px;
}
.chip.on {
  background: var(--accent);
  color: #fff;
}
.stepper {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stepper button {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--surface);
  color: var(--text);
  display: grid;
  place-items: center;
}
.stepper button:disabled {
  opacity: 0.35;
}
.stepper .num {
  min-width: 56px;
  text-align: center;
  font-size: 20px;
  font-weight: 600;
}
.stepper small {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-3);
  margin-left: 1px;
}
.van-slider {
  margin-top: 12px;
  border-radius: 12px;
  overflow: hidden;
}
.tip {
  text-align: center;
  color: var(--text-3);
  padding: 16px 0;
}
</style>
