<script setup lang="ts">
import { computed } from 'vue'
import { showConfirmDialog } from 'vant'
import { connected, deviceList, sendCommand } from '../store'
import { AC_MODE_NAMES, isRunning, lightsOf, panelRooms, roomActive, roomDevices, roomSummary, toggleLights } from '../rooms'
import { openRoom } from '../router'

// Room order follows Mi Home and never shifts when something turns on, so cards stay where the thumb expects them.
const cards = computed(() =>
  panelRooms.value.map((room) => {
    const list = roomDevices(room)
    const lights = lightsOf(list)
    return {
      room,
      summary: roomSummary(room),
      active: roomActive(room),
      hasLights: list.some((d) => d.kind === 'light'),
      lightsOn: lights.some((d) => d.state.power),
      lightsOnline: lights.length > 0,
      list,
    }
  }),
)

const lightsOn = computed(() => deviceList.value.filter((d) => d.kind === 'light' && !d.hidden && isRunning(d)))
const acsOn = computed(() => deviceList.value.filter((d) => d.kind === 'ac' && !d.hidden && isRunning(d)))
const headline = computed(() => {
  const parts = [lightsOn.value.length ? `${lightsOn.value.length} 盏灯亮着` : '灯都关着']
  for (const ac of acsOn.value) parts.push(`${ac.room}空调${AC_MODE_NAMES[ac.state.mode ?? 'auto']} ${ac.state.target_temp}°`)
  return parts.join(' · ')
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
    <header class="hero">
      <div class="title">我的家 <span v-if="!connected" class="disconnected">连接中…</span></div>
      <div class="headline">{{ headline }}</div>
      <div class="hero-actions" v-if="lightsOn.length || acsOn.length">
        <van-button v-if="lightsOn.length" size="small" round plain type="primary" icon="bulb-o" @click="allLightsOff">全部关灯</van-button>
        <van-button v-if="acsOn.length" size="small" round plain type="primary" @click="allAcOff">关闭空调</van-button>
      </div>
    </header>

    <div class="rooms">
      <div v-for="c in cards" :key="c.room" class="room-card" :class="{ active: c.active }" @click="openRoom(c.room)">
        <div class="room-name">{{ c.room }}</div>
        <div class="room-summary">{{ c.summary.join(' · ') || `${c.list.length} 个设备` }}</div>
        <button
          v-if="c.hasLights"
          class="light-button"
          :class="{ on: c.lightsOn, disabled: !c.lightsOnline }"
          @click.stop="c.lightsOnline && toggleLights(c.list)"
        >
          <van-icon name="bulb-o" />
        </button>
        <van-icon name="arrow" class="go" />
      </div>
    </div>
    <van-empty v-if="!cards.length" description="还没有设备，去「设备」页同步米家" />
  </div>
</template>

<style scoped>
.hero {
  padding: calc(20px + env(safe-area-inset-top)) 20px 4px;
}
.title {
  font-size: 26px;
  font-weight: 700;
  color: #1f2329;
}
.disconnected {
  font-size: 12px;
  font-weight: 400;
  color: #ee0a24;
  margin-left: 8px;
}
.headline {
  margin-top: 6px;
  color: #646a73;
  font-size: 14px;
}
.hero-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.rooms {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
}
@media (min-width: 700px) {
  .rooms {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.room-card {
  position: relative;
  background: #fff;
  border-radius: 18px;
  padding: 14px 14px 56px;
  min-height: 84px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.1s, background 0.3s;
}
.room-card:active {
  transform: scale(0.98);
}
.room-card.active {
  background: linear-gradient(150deg, #fff6df, #fff 75%);
}
.room-name {
  font-size: 17px;
  font-weight: 600;
  color: #1f2329;
}
.room-summary {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #8f959e;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.light-button {
  position: absolute;
  left: 12px;
  bottom: 12px;
  width: 38px;
  height: 38px;
  border: none;
  border-radius: 50%;
  background: #f0f1f4;
  color: #9aa0ab;
  font-size: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  -webkit-tap-highlight-color: transparent;
}
.light-button.on {
  background: #f5a623;
  color: #fff;
  box-shadow: 0 2px 8px rgba(245, 166, 35, 0.4);
}
.light-button.disabled {
  opacity: 0.4;
}
.go {
  position: absolute;
  right: 14px;
  bottom: 22px;
  color: #c4c7cc;
}
</style>
