<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { showConfirmDialog } from 'vant'
import { AirVent, Blinds, Lightbulb, Thermometer } from 'lucide-vue-next'
import { deviceList, sendCommand } from '../store'
import { AC_MODE_NAMES, isRunning, lightsOf, panelRooms, roomDevices, roomSummary, toggleLights } from '../rooms'
import { openRoom } from '../router'
import DeviceIcon from '../components/DeviceIcon.vue'
import PageHeader from '../components/PageHeader.vue'

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

// Main devices shown as icons on each room card, so state is readable at a glance.
const ICON_KINDS = ['light', 'ac', 'bath_heater', 'curtain', 'airer', 'plug']
const cards = computed(() =>
  panelRooms.value.map((room) => {
    const list = roomDevices(room)
    const lights = lightsOf(list)
    const temp = list.find((d) => d.state.online && d.state.temperature !== undefined)?.state.temperature
    const icons = list
      .filter((d) => ICON_KINDS.includes(d.kind))
      .sort((a, b) => ICON_KINDS.indexOf(a.kind) - ICON_KINDS.indexOf(b.kind))
      .slice(0, 6)
    const ac = list.find((d) => d.kind === 'ac' && isRunning(d))
    return {
      room,
      list,
      temp,
      icons,
      summary: roomSummary(room).filter((s) => !s.startsWith('室温')),
      hasLights: list.some((d) => d.kind === 'light'),
      lightsOn: lights.some((d) => d.state.power),
      lightsOnline: lights.length > 0,
      glow: lights.some((d) => d.state.power) ? 'warm' : ac ? (ac.state.mode === 'heat' ? 'heat' : 'cool') : '',
    }
  }),
)

const iconActive = (d: (typeof cards.value)[number]['icons'][number]) =>
  !!d.state.online && (d.kind === 'curtain' ? (d.state.position ?? 0) > 5 : !!d.state.power)

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
      <div v-for="c in cards" :key="c.room" class="room card pressable" :class="c.glow" @click="openRoom(c.room)">
        <div class="room-top">
          <div class="room-name">{{ c.room }}</div>
          <div v-if="c.temp !== undefined" class="room-temp num">{{ c.temp }}°</div>
        </div>
        <div class="room-icons">
          <DeviceIcon v-for="d in c.icons" :key="d.id" :kind="d.kind" :model="d.model" :active="iconActive(d)" :size="30" />
          <span v-if="!c.icons.length" class="room-count">{{ c.list.length }} 个设备</span>
        </div>
        <div class="room-bottom">
          <div class="room-summary">{{ c.summary.join(' · ') || '一切正常' }}</div>
          <button v-if="c.hasLights" class="light-toggle" :class="{ on: c.lightsOn, disabled: !c.lightsOnline }"
            :title="c.lightsOn ? '关灯' : '开灯'" @click.stop="c.lightsOnline && toggleLights(c.list)">
            <Lightbulb :size="18" :stroke-width="2.2" />
          </button>
        </div>
      </div>
    </div>
    <van-empty v-if="!cards.length" description="还没有设备，去「设备」页同步米家" />
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
.rooms {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 0 16px;
}
.room {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 150px;
  box-sizing: border-box;
  cursor: pointer;
}
.room.warm {
  background: var(--warm-glow);
}
.room.cool {
  background: var(--cool-glow);
}
.room.heat {
  background: var(--heat-glow);
}
.room-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.room-name {
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.room-temp {
  font-size: 18px;
  font-weight: 500;
  color: var(--text-2);
}
.room-icons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 30px;
}
.room-count {
  font-size: 12px;
  color: var(--text-3);
  align-self: center;
}
.room-bottom {
  margin-top: auto;
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.room-summary {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.light-toggle {
  flex: none;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  color: var(--text-3);
  transition: all 0.2s;
}
.light-toggle.on {
  background: var(--warm);
  color: #fff;
  box-shadow: var(--shadow-warm);
}
.light-toggle.disabled {
  opacity: 0.35;
}

@media (min-width: 640px) {
  .stats {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .rooms {
    grid-template-columns: repeat(3, minmax(0, 1fr));
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
  }
  .room {
    min-height: 170px;
    padding: 18px;
  }
}
@media (min-width: 1200px) {
  .rooms {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
</style>
