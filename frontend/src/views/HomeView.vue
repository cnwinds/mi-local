<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { showConfirmDialog } from 'vant'
import { AirVent, Blinds, Lightbulb, Thermometer } from 'lucide-vue-next'
import { deviceList, sendCommand } from '../store'
import { AC_MODE_NAMES, isRunning, panelRooms } from '../rooms'
import PageHeader from '../components/PageHeader.vue'
import RoomTile from '../components/home/RoomTile.vue'

const now = ref(new Date())
const timer = setInterval(() => (now.value = new Date()), 60_000)
onBeforeUnmount(() => clearInterval(timer))
const greeting = computed(() => {
  const h = now.value.getHours()
  return h < 5 ? '夜深了' : h < 11 ? '早上好' : h < 13 ? '中午好' : h < 18 ? '下午好' : '晚上好'
})
const dateText = computed(() => now.value.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }))

const visible = computed(() => deviceList.value.filter((d) => !d.hidden && d.state.online))
const lightsOn = computed(() => visible.value.filter((d) => d.kind === 'light' && isRunning(d)))
const acsOn = computed(() => visible.value.filter((d) => d.kind === 'ac' && isRunning(d)))
const curtainsOpen = computed(() => visible.value.filter((d) => d.kind === 'curtain' && (d.state.position ?? 0) > 5))
const temps = computed(() => visible.value.map((d) => d.state.temperature).filter((t): t is number => t !== undefined))
const avgTemp = computed(() => (temps.value.length ? Math.round((temps.value.reduce((a, b) => a + b, 0) / temps.value.length) * 10) / 10 : null))

const headline = computed(() => {
  if (!lightsOn.value.length && !acsOn.value.length) return '家里很安静，灯和空调都关着'
  const parts = []
  if (lightsOn.value.length) parts.push(`${lightsOn.value.length} 盏灯亮着`)
  for (const ac of acsOn.value) parts.push(`${ac.room}空调在${AC_MODE_NAMES[ac.state.mode ?? 'auto']}`)
  return parts.join('，')
})
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
  <div class="home">
    <PageHeader :eyebrow="dateText" :title="greeting" :subtitle="headline" />

    <div class="stats">
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

    <div class="section-label rooms-label">房间</div>
    <div class="rooms">
      <RoomTile v-for="room in panelRooms" :key="room" :room="room" />
    </div>
    <van-empty v-if="!panelRooms.length" description="还没有设备，去「设备」页同步米家" />
  </div>
</template>

<style scoped>
.home {
  padding-bottom: 8px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  padding: 14px 16px 0;
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
.rooms-label {
  padding: 0 16px;
}
/* Bento grid: tiles span 1, 2 or 2×2 cells by content, dense packing fills the gaps */
.rooms {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: minmax(150px, auto);
  grid-auto-flow: row dense;
  gap: 12px;
  padding: 0 16px;
}

@media (min-width: 640px) {
  .stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .rooms {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
@media (min-width: 900px) {
  .stats,
  .rooms,
  .rooms-label {
    padding-left: 0;
    padding-right: 0;
  }
  .stats {
    gap: 14px;
  }
  .stat {
    padding: 16px;
  }
  .rooms {
    gap: 16px;
    grid-auto-rows: minmax(170px, auto);
  }
}
@media (min-width: 1500px) {
  .rooms {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}
</style>
