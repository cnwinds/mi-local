<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { ChevronDown, Minus, Plus, Power } from 'lucide-vue-next'
import type { Device, DeviceField } from '../api'
import { cardModel, formatValue, unitLabel } from '../miot'
import { controlOf as control, useMiot } from '../useMiot'

const props = defineProps<{ device: Device }>()

const { fields, values, powerKey, on, set, num, step, togglePower } = useMiot(toRef(props, 'device'))

const hero = computed(() =>
  cardModel(fields.value, values.value, powerKey.value).metrics.map((m) => {
    const hit = /^(-?[\d.]+)\s*(.*)$/.exec(m.text)
    return { label: m.field.name, value: hit ? hit[1] : m.text, unit: hit ? hit[2] : '', text: !hit }
  }),
)

const showMore = ref(false)

function groupBy(list: DeviceField[]) {
  const out: { service: string; items: DeviceField[] }[] = []
  for (const f of list) {
    if (f.key === powerKey.value || (values.value[f.key] === undefined && control(f) !== 'chips')) continue
    const g = out.find((x) => x.service === f.service) ?? out[out.push({ service: f.service, items: [] }) - 1]
    g.items.push(f)
  }
  return out
}

// Manufacturer extensions go behind "更多" so the standard properties stay readable.
const mainGroups = computed(() => groupBy(fields.value.filter((f) => !f.vendor)))
const moreGroups = computed(() => groupBy(fields.value.filter((f) => f.vendor)))
const moreCount = computed(() => moreGroups.value.reduce((n, g) => n + g.items.length, 0))
const groups = computed(() => [...mainGroups.value, ...(showMore.value ? moreGroups.value : [])])

function label(f: DeviceField, group: DeviceField[]) {
  return f.prop === 'on' && group.length === 1 ? f.service : f.name
}
</script>

<template>
  <div class="miot">
    <div v-if="hero.length || powerKey" class="hero" :class="{ on: powerKey && on }">
      <div v-if="!hero.length" class="hero-state">
        <b>{{ on ? '运行中' : '已关闭' }}</b>
        <span>{{ on ? '点右侧按钮关闭' : '点右侧按钮开启' }}</span>
      </div>
      <div v-else class="hero-metrics">
        <div v-for="m in hero" :key="m.label" class="metric">
          <div class="value num" :class="{ text: m.text }">{{ m.value }}<small v-if="m.unit">{{ m.unit }}</small></div>
          <div class="metric-label">{{ m.label }}</div>
        </div>
      </div>
      <button v-if="powerKey" class="power" :class="{ on }" @click="togglePower">
        <Power :size="26" :stroke-width="2.2" />
        <span>{{ on ? '已开启' : '已关闭' }}</span>
      </button>
    </div>

    <div v-if="!fields.length" class="tip">正在读取设备能力…</div>

    <section v-for="g in groups" :key="g.service" class="group">
      <div v-if="g.items.length > 1 || g.items[0].prop !== 'on'" class="section-label">{{ g.service }}</div>
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
            <span class="label">{{ label(f, g.items) }}</span>
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

    <button v-if="moreCount" class="more pressable" :class="{ open: showMore }" @click="showMore = !showMore">
      {{ showMore ? '收起' : `更多 ${moreCount} 项` }}
      <ChevronDown :size="16" />
    </button>
  </div>
</template>

<style scoped>
.hero {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
  margin-bottom: 20px;
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-1);
  transition: background 0.3s;
}
.hero.on {
  background: var(--accent-glow);
}
.hero-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hero-state b {
  font-size: 26px;
  font-weight: 500;
}
.hero-state span {
  font-size: 12px;
  color: var(--text-3);
}
.hero-metrics {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.metric .value {
  font-size: 30px;
  font-weight: 400;
  line-height: 1.1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.metric .value.text {
  font-size: 20px;
  line-height: 33px;
}
.metric small {
  font-size: 14px;
  color: var(--text-3);
  margin-left: 2px;
}
.metric-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.power {
  flex: none;
  width: 76px;
  height: 76px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-3);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  font-size: 11px;
  transition: all 0.25s;
}
.power.on {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 0 0 7px var(--accent-soft);
}
.group + .group {
  margin-top: 16px;
}
.rows {
  background: var(--surface);
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
  background: var(--surface-2);
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
  background: var(--surface-2);
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
.more {
  margin: 16px auto 0;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-2);
  font-size: 13px;
}
.more svg {
  transition: transform 0.2s;
}
.more.open svg {
  transform: rotate(180deg);
}
.tip {
  text-align: center;
  color: var(--text-3);
  padding: 16px 0;
}
</style>
