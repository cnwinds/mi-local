<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, type Stats } from '../api'
import { devices } from '../store'
import DeviceIcon from './DeviceIcon.vue'

const emit = defineEmits<{ edit: [id: string] }>()

const RANGES: [number | null, string][] = [[7, '7 天'], [30, '30 天'], [90, '90 天'], [null, '全部']]
const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

const days = ref<number | null>(7)
const stats = ref<Stats | null>(null)
const loading = ref(false)
const failed = ref(false)
let request = 0

async function load() {
  const id = ++request
  loading.value = true
  failed.value = false
  try {
    const result = await api.stats(days.value)
    if (id === request) stats.value = result
  } catch {
    if (id === request) failed.value = true
  } finally {
    if (id === request) loading.value = false
  }
}

watch(days, load, { immediate: true })

const dateFmt = new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' })
const name = (id: string) => devices[id]?.name ?? id
const hours = (s: number) => (s >= 36000 ? Math.round(s / 3600) : Math.round(s / 360) / 10)
const duration = (s: number) => (s >= 3600 ? `${hours(s)} 小时` : s >= 60 ? `${Math.round(s / 60)} 分钟` : s > 0 ? '不到 1 分钟' : '0')
const perDay = (n: number) => {
  const v = n / (stats.value?.days || 1)
  return v >= 10 ? Math.round(v) : Math.round(v * 10) / 10
}
const hourRange = (h: number) => `${h}:00–${h + 1}:00`

const daily = computed(() => stats.value?.daily.slice(-(days.value ?? 30)) ?? [])
const dailyMax = computed(() => Math.max(1, ...daily.value.map((d) => d.presses + d.turn_ons + d.doors)))
const heatMax = computed(() => Math.max(1, ...(stats.value?.heatmap.flat() ?? [])))
const usage = computed(() => (stats.value?.usage ?? []).filter((u) => devices[u.device]).slice(0, 10))
const usageMax = computed(() => Math.max(1, ...usage.value.map((u) => u.on_seconds)))
const switches = computed(() => (stats.value?.switches ?? []).slice(0, 8))
const switchMax = computed(() => Math.max(1, ...switches.value.map((s) => s.count)))

// A few plain sentences that say what the numbers mean.
const insights = computed(() => {
  const s = stats.value
  if (!s) return []
  const out: string[] = []
  const top = usage.value[0]
  if (top && top.on_seconds > 0) out.push(`用得最多的是「${name(top.device)}」，平均每天开 ${duration(top.on_seconds / s.days)}`)
  if (s.peak_hour !== null) out.push(`一天里最忙的是 ${hourRange(s.peak_hour)}`)
  const week = s.heatmap.slice(0, 5).flat().reduce((a, b) => a + b, 0) / 5
  const weekend = s.heatmap.slice(5).flat().reduce((a, b) => a + b, 0) / 2
  if (week + weekend >= 20 && Math.abs(weekend - week) / Math.max(week, 1) > 0.2) {
    out.push(weekend > week ? `周末每天的操作比工作日多 ${Math.round((weekend / week - 1) * 100)}%` : `工作日每天的操作比周末多 ${Math.round((week / Math.max(weekend, 1) - 1) * 100)}%`)
  }
  const sw = s.switches[0]
  if (sw) out.push(`按得最多的开关是「${name(sw.device)}」，共 ${sw.count} 次`)
  const night = s.heatmap.reduce((a, row) => a + row.slice(0, 6).reduce((x, y) => x + y, 0), 0)
  const total = s.heatmap.flat().reduce((a, b) => a + b, 0)
  if (total >= 20 && night / total > 0.1) out.push(`有 ${Math.round((night / total) * 100)}% 的操作发生在凌晨 0–6 点`)
  return out
})
</script>

<template>
  <div class="stats">
    <div class="ranges">
      <button v-for="[value, label] in RANGES" :key="label" :class="{ on: days === value }" @click="days = value">{{ label }}</button>
    </div>

    <template v-if="stats">
      <div class="kpis">
        <div class="kpi card">
          <div class="kpi-value num">{{ stats.total_presses }}</div>
          <div class="kpi-label">开关按键 · 日均 {{ perDay(stats.total_presses) }}</div>
        </div>
        <div class="kpi card">
          <div class="kpi-value num warm">{{ stats.total_turn_ons }}</div>
          <div class="kpi-label">设备开启 · 日均 {{ perDay(stats.total_turn_ons) }}</div>
        </div>
        <div class="kpi card">
          <div class="kpi-value num heat">{{ stats.total_doors }}</div>
          <div class="kpi-label">开门 · 日均 {{ perDay(stats.total_doors) }}</div>
        </div>
        <div class="kpi card">
          <div class="kpi-value num accent">{{ stats.peak_hour === null ? '—' : `${stats.peak_hour}点` }}</div>
          <div class="kpi-label">最忙时段</div>
        </div>
      </div>

      <div v-if="insights.length" class="card insights">
        <div v-for="t in insights" :key="t" class="insight">{{ t }}</div>
      </div>

      <section class="card block">
        <div class="block-head">
          <span class="block-title">每日活动</span>
          <span class="legend"><i class="accent" />按键<i class="warm" />开设备<i class="heat" />开门</span>
        </div>
        <div class="bars">
          <div v-for="d in daily" :key="d.day" class="bar-col"
            :title="`${dateFmt.format(new Date(d.day * 1000))}：按键 ${d.presses}，开设备 ${d.turn_ons}，开门 ${d.doors}`">
            <div class="stack" :style="{ height: `${((d.presses + d.turn_ons + d.doors) / dailyMax) * 100}%` }">
              <span class="heat" :style="{ flex: d.doors }" />
              <span class="warm" :style="{ flex: d.turn_ons }" />
              <span class="accent" :style="{ flex: d.presses }" />
            </div>
          </div>
        </div>
        <div class="axis">
          <span>{{ daily.length ? dateFmt.format(new Date(daily[0].day * 1000)) : '' }}</span>
          <span>今天</span>
        </div>
      </section>

      <section class="card block">
        <div class="block-head"><span class="block-title">热点时段</span><span class="hint">颜色越深，那个时段操作越多</span></div>
        <div class="heat-grid">
          <template v-for="(row, w) in stats.heatmap" :key="w">
            <span class="wd">{{ WEEKDAYS[w] }}</span>
            <span v-for="(n, h) in row" :key="h" class="cell" :title="`周${WEEKDAYS[w]} ${hourRange(h)}：${n} 次`"
              :style="{ '--a': n ? 0.15 + 0.85 * (n / heatMax) : 0 }" />
          </template>
          <span />
          <span v-for="h in 24" :key="`h${h}`" class="hr">{{ (h - 1) % 6 === 0 ? h - 1 : '' }}</span>
        </div>
      </section>

      <section class="card block">
        <div class="block-head"><span class="block-title">设备使用时长</span><span class="hint">开着的累计时间</span></div>
        <div v-if="!usage.length" class="empty">设备开关时长从这个版本起开始记录，过一阵再来看</div>
        <button v-for="u in usage" :key="u.device" class="rank" @click="emit('edit', u.device)">
          <DeviceIcon :kind="devices[u.device].kind" :model="devices[u.device].model" :name="devices[u.device].name" :size="32" />
          <div class="rank-body">
            <div class="rank-top">
              <span class="rank-name">{{ name(u.device) }}</span>
              <span class="rank-value num">{{ duration(u.on_seconds) }}</span>
            </div>
            <div class="track"><span class="fill warm" :style="{ width: `${(u.on_seconds / usageMax) * 100}%` }" /></div>
            <div class="rank-meta">使用率 {{ Math.round(u.rate * 100) }}% · 开了 {{ u.turn_ons }} 次</div>
          </div>
        </button>
      </section>

      <section class="card block">
        <div class="block-head">
          <span class="block-title">开关按键排行</span>
          <span class="hint">单击 {{ stats.press_types.click ?? 0 }} · 双击 {{ stats.press_types.double_click ?? 0 }} · 长按 {{ stats.press_types.long_click_press ?? 0 }}</span>
        </div>
        <div v-if="!switches.length" class="empty">这段时间还没有按过开关</div>
        <button v-for="s in switches" :key="s.device" class="rank" @click="emit('edit', s.device)">
          <div class="rank-body">
            <div class="rank-top">
              <span class="rank-name">{{ name(s.device) }}</span>
              <span class="rank-value num">{{ s.count }} 次</span>
            </div>
            <div class="track"><span class="fill accent" :style="{ width: `${(s.count / switchMax) * 100}%` }" /></div>
          </div>
        </button>
      </section>

      <div class="since">
        数据从 {{ stats.first ? dateFmt.format(new Date(stats.first * 1000)) : '今天' }} 开始记录，全部永久保存
      </div>
    </template>
    <van-loading v-else-if="loading" class="loading" />
    <button v-else-if="failed" class="loading retry" @click="load">统计加载失败，点击重试</button>
  </div>
</template>

<style scoped>
.stats {
  padding: 4px 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ranges {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 12px;
  background: var(--surface-2);
  align-self: flex-start;
}
.ranges button {
  padding: 6px 14px;
  border-radius: 9px;
  font-size: 13px;
  color: var(--text-3);
}
.ranges button.on {
  background: var(--surface);
  color: var(--text);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}
.kpis {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.kpi {
  padding: 14px 16px;
}
.kpi-value {
  font-size: 28px;
  font-weight: 600;
  line-height: 1.1;
}
.kpi-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-3);
}
.warm {
  color: var(--warm-strong);
}
.heat {
  color: var(--heat);
}
.accent {
  color: var(--accent);
}
.insights {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.insight {
  position: relative;
  padding-left: 14px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-2);
}
.insight::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 0.6em;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
}
.block {
  padding: 14px 16px;
}
.block-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}
.block-title {
  font-size: 15px;
  font-weight: 600;
}
.hint,
.legend {
  font-size: 11px;
  color: var(--text-3);
}
.legend {
  display: flex;
  align-items: center;
  gap: 4px;
}
.legend i {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-left: 6px;
  background: currentColor;
}
.legend i.accent {
  background: var(--accent);
}
.legend i.warm {
  background: var(--warm);
}
.legend i.heat {
  background: var(--heat);
}

/* Daily stacked bars */
.bars {
  height: 120px;
  display: flex;
  align-items: flex-end;
  gap: 2px;
}
.bar-col {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: flex-end;
}
.stack {
  width: 100%;
  min-height: 2px;
  display: flex;
  flex-direction: column;
  border-radius: 3px 3px 1px 1px;
  overflow: hidden;
  background: var(--surface-3);
}
.stack span {
  min-height: 0;
}
.stack .accent {
  background: var(--accent);
}
.stack .warm {
  background: var(--warm);
}
.stack .heat {
  background: var(--heat);
}
.axis {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-3);
}

/* Weekday x hour heatmap */
.heat-grid {
  display: grid;
  grid-template-columns: 18px repeat(24, minmax(0, 1fr));
  gap: 2px;
  align-items: center;
}
.cell {
  aspect-ratio: 1;
  border-radius: 3px;
  background: color-mix(in srgb, var(--accent) calc(var(--a) * 100%), var(--surface-2));
}
.wd,
.hr {
  font-size: 10px;
  color: var(--text-3);
  text-align: center;
}

/* Rankings */
.rank {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  text-align: left;
}
.rank + .rank {
  border-top: 1px solid var(--line);
}
.rank-body {
  flex: 1;
  min-width: 0;
}
.rank-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 14px;
}
.rank-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rank-value {
  flex: none;
  color: var(--text-2);
  font-weight: 600;
}
.track {
  height: 6px;
  margin-top: 6px;
  border-radius: 3px;
  background: var(--surface-2);
  overflow: hidden;
}
.fill {
  display: block;
  height: 100%;
  border-radius: 3px;
}
.fill.warm {
  background: var(--warm);
}
.fill.accent {
  background: var(--accent);
}
.rank-meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-3);
}
.empty {
  font-size: 13px;
  color: var(--text-3);
  padding: 8px 0;
}
.since {
  text-align: center;
  font-size: 12px;
  color: var(--text-3);
}
.loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.retry {
  width: 100%;
  border: 0;
  background: none;
  font-size: 13px;
  color: var(--text-3);
  cursor: pointer;
}
@media (min-width: 900px) {
  .stats {
    padding: 4px 0 24px;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }
  .ranges,
  .kpis,
  .insights,
  .since,
  .loading {
    grid-column: 1 / -1;
  }
  .kpis {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>
