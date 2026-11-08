<script setup lang="ts">
import { computed, ref } from 'vue'
import { showConfirmDialog } from 'vant'
import type { Device } from '../api'
import { CONTROLLABLE, connected, deviceList, rooms, sendCommand } from '../store'
import DeviceCard from '../components/DeviceCard.vue'
import DeviceSheet from '../components/DeviceSheet.vue'

const activeRoom = ref('全部')
const detailId = ref<string | null>(null)

const visible = computed(() => deviceList.value.filter((d) => CONTROLLABLE.has(d.kind) && !d.hidden))
const roomTabs = computed(() => ['全部', ...rooms.value.filter((r) => visible.value.some((d) => d.room === r))])

const kindOrder: Record<string, number> = { light: 0, curtain: 1, plug: 2, other: 3 }
const shown = computed(() =>
  visible.value
    .filter((d) => activeRoom.value === '全部' || d.room === activeRoom.value)
    .sort((a, b) => kindOrder[a.kind] - kindOrder[b.kind] || Number(!!b.state.online) - Number(!!a.state.online)),
)

const lightsOn = computed(() => visible.value.filter((d) => d.kind === 'light' && d.state.online && d.state.power))

async function allOff() {
  await showConfirmDialog({ title: '关闭全部灯', message: `将关闭 ${lightsOn.value.length} 盏灯` })
  lightsOn.value.forEach((d) => sendCommand(d.id, 'turn_off', undefined, { power: false }))
}

function openDetail(d: Device) {
  detailId.value = d.id
}
</script>

<template>
  <div class="home">
    <header class="hero">
      <div class="title">我的家 <span v-if="!connected" class="disconnected">连接中…</span></div>
      <div class="summary">
        <span>{{ lightsOn.length ? `${lightsOn.length} 盏灯亮着` : '灯都关着' }}</span>
        <van-button v-if="lightsOn.length" size="small" round plain type="primary" @click="allOff">全部关灯</van-button>
      </div>
    </header>

    <van-tabs v-model:active="activeRoom" shrink sticky background="#f6f7f9" line-width="16px" color="#3e7bfa">
      <van-tab v-for="room in roomTabs" :key="room" :title="room" :name="room" />
    </van-tabs>

    <div class="grid">
      <DeviceCard v-for="d in shown" :key="d.id" :device="d" @detail="openDetail" />
    </div>
    <van-empty v-if="!shown.length" description="这个房间还没有设备" />

    <DeviceSheet :device-id="detailId" @close="detailId = null" />
  </div>
</template>

<style scoped>
.hero {
  padding: calc(20px + env(safe-area-inset-top)) 20px 8px;
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
.summary {
  margin-top: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #646a73;
  font-size: 14px;
  min-height: 32px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 12px 16px;
}
</style>
