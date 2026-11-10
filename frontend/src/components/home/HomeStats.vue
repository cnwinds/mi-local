<script setup lang="ts">
import { showConfirmDialog } from 'vant'
import { AirVent, Blinds, Lightbulb, Thermometer } from 'lucide-vue-next'
import { sendCommand } from '../../store'
import { acsOn, avgTemp, curtainsOpen, lightsOn } from '../../home'

/** column: stacked in one column beside the floor plan instead of a 2 or 4 wide grid. */
defineProps<{ column?: boolean }>()

async function allLightsOff() {
  await showConfirmDialog({ title: '关闭全部灯', message: `将关闭 ${lightsOn.value.length} 盏灯` })
  lightsOn.value.forEach((d) => sendCommand(d.id, 'turn_off', undefined, { power: false }))
}
async function allAcOff() {
  await showConfirmDialog({ title: '关闭全部空调', message: acsOn.value.map((d) => d.name).join('、') })
  acsOn.value.forEach((d) => sendCommand(d.id, 'turn_off', undefined, { power: false }))
}
</script>

<template>
  <div class="stats" :class="{ column }">
    <div class="stat card" :class="{ warm: lightsOn.length }">
      <div class="stat-icon warm"><Lightbulb :size="18" /></div>
      <div class="stat-body">
        <div class="stat-value num">{{ lightsOn.length }}<small>盏</small></div>
        <div class="stat-label">灯亮着</div>
      </div>
      <button v-if="lightsOn.length" class="stat-action" @click="allLightsOff">全关</button>
    </div>
    <div class="stat card" :class="{ cool: acsOn.length }">
      <div class="stat-icon cool"><AirVent :size="18" /></div>
      <div class="stat-body">
        <div class="stat-value num">{{ acsOn.length }}<small>台</small></div>
        <div class="stat-label">空调运行</div>
      </div>
      <button v-if="acsOn.length" class="stat-action" @click="allAcOff">全关</button>
    </div>
    <div class="stat card">
      <div class="stat-icon heat"><Thermometer :size="18" /></div>
      <div class="stat-body">
        <div class="stat-value num">{{ avgTemp ?? '--' }}<small>°C</small></div>
        <div class="stat-label">室内温度</div>
      </div>
    </div>
    <div class="stat card">
      <div class="stat-icon accent"><Blinds :size="18" /></div>
      <div class="stat-body">
        <div class="stat-value num">{{ curtainsOpen.length }}<small>个</small></div>
        <div class="stat-label">窗帘开着</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.stat {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: var(--radius);
  min-width: 0;
  transition: background 0.3s;
}
.stat.warm {
  background: var(--warm-glow);
}
.stat.cool {
  background: var(--cool-glow);
}
.stat-icon {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.stat-icon.warm {
  background: var(--warm-soft);
  color: var(--warm-strong);
}
.stat-icon.cool {
  background: var(--cool-soft);
  color: var(--cool);
}
.stat-icon.heat {
  background: var(--heat-soft);
  color: var(--heat);
}
.stat-icon.accent {
  background: var(--accent-soft);
  color: var(--accent);
}
.stat-body {
  flex: 1;
  min-width: 0;
}
.stat-value {
  font-size: 22px;
  font-weight: 650;
  line-height: 1.1;
}
.stat-value small {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-3);
  margin-left: 2px;
}
.stat-label {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 2px;
}
.stat-action {
  font-size: 12px;
  font-weight: 600;
  padding: 6px 10px;
  border-radius: 10px;
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-1);
}

@media (min-width: 640px) {
  .stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
@media (min-width: 900px) {
  .stats {
    gap: 14px;
  }
  .stat {
    padding: 16px;
  }
}
.stats.column {
  grid-template-columns: 1fr;
}
</style>
