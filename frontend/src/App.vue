<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Cctv, House, LayoutGrid, ToggleRight, Wifi, WifiOff } from 'lucide-vue-next'
import CamerasView from './views/CamerasView.vue'
import HomeView from './views/HomeView.vue'
import RoomPanel from './views/RoomPanel.vue'
import WallHome from './views/WallHome.vue'
import SwitchesView from './views/SwitchesView.vue'
import DevicesView from './views/DevicesView.vue'
import { connected } from './store'
import { panelRooms, roomActive } from './rooms'
import { goHome, openRoom, route, switchRoom } from './router'

const tab = ref('home')
watch(
  () => route.value.name,
  (name) => name !== 'home' && (tab.value = 'home'),
)

const TABS = [
  { name: 'home', label: '家', icon: House },
  { name: 'cameras', label: '监控', icon: Cctv },
  { name: 'switches', label: '开关', icon: ToggleRight },
  { name: 'devices', label: '设备', icon: LayoutGrid },
]

function select(name: string) {
  if (name === 'home' && tab.value === 'home' && route.value.name === 'room') goHome()
  tab.value = name
}

const currentRoom = computed(() => (route.value.name === 'room' && tab.value === 'home' ? route.value.room : null))
function pickRoom(room: string) {
  tab.value = 'home'
  if (route.value.name === 'room') switchRoom(room)
  else openRoom(room)
}
</script>

<template>
  <RoomPanel v-if="route.name === 'wall'" :room="route.room" wall />
  <WallHome v-else-if="route.name === 'wall-home'" />
  <div v-else class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="logo"><House :size="18" :stroke-width="2.2" /></div>
        <div>
          <div class="brand-name">我的家</div>
          <div class="brand-sub" :class="{ off: !connected }">
            <component :is="connected ? Wifi : WifiOff" :size="12" />{{ connected ? '本地已连接' : '连接中…' }}
          </div>
        </div>
      </div>
      <nav class="nav">
        <button v-for="t in TABS" :key="t.name" class="nav-item" :class="{ selected: tab === t.name && !currentRoom }" @click="select(t.name)">
          <component :is="t.icon" :size="19" />{{ t.label }}
        </button>
      </nav>
      <div class="rooms-label">房间</div>
      <nav class="nav rooms">
        <button v-for="r in panelRooms" :key="r" class="nav-item room" :class="{ selected: currentRoom === r }" @click="pickRoom(r)">
          <span class="dot" :class="{ on: roomActive(r) }" />{{ r }}
        </button>
      </nav>
    </aside>

    <main class="main">
      <template v-if="tab === 'home'">
        <RoomPanel v-if="route.name === 'room'" :key="route.room" :room="route.room" />
        <HomeView v-else />
      </template>
      <CamerasView v-if="tab === 'cameras'" />
      <SwitchesView v-if="tab === 'switches'" />
      <DevicesView v-if="tab === 'devices'" />
    </main>

    <nav class="tabbar">
      <button v-for="t in TABS" :key="t.name" class="tab" :class="{ selected: tab === t.name }" @click="select(t.name)">
        <component :is="t.icon" :size="22" :stroke-width="tab === t.name ? 2.3 : 1.8" />
        <span>{{ t.label }}</span>
      </button>
    </nav>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
}
.main {
  padding-bottom: calc(96px + env(safe-area-inset-bottom));
}
.sidebar {
  display: none;
}
.tabbar {
  position: fixed;
  left: 50%;
  bottom: calc(12px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  z-index: 50;
  display: flex;
  gap: 4px;
  padding: 6px;
  border-radius: 26px;
  background: var(--surface-glass);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  box-shadow: var(--shadow-2);
  border: 1px solid var(--line);
}
.tab {
  width: 76px;
  height: 52px;
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  font-size: 11px;
  color: var(--text-3);
  transition: background 0.2s, color 0.2s;
}
.tab.selected {
  background: var(--accent-soft);
  color: var(--accent-text);
  font-weight: 600;
}

@media (min-width: 900px) {
  .shell {
    display: grid;
    grid-template-columns: 248px minmax(0, 1fr);
  }
  .tabbar {
    display: none;
  }
  .main {
    padding: 8px 32px 48px;
    max-width: 1360px;
    width: 100%;
    margin: 0 auto;
    box-sizing: border-box;
  }
  .sidebar {
    display: flex;
    flex-direction: column;
    position: sticky;
    top: 0;
    height: 100vh;
    box-sizing: border-box;
    padding: 28px 16px;
    border-right: 1px solid var(--line);
    background: var(--surface-glass);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    overflow-y: auto;
  }
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 10px 24px;
}
.logo {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: linear-gradient(135deg, #ffb547, #ff7b3a);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-warm);
}
.brand-name {
  font-size: 17px;
  font-weight: 700;
}
.brand-sub {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--green);
  margin-top: 2px;
}
.brand-sub.off {
  color: var(--danger);
}
.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 42px;
  padding: 0 12px;
  border-radius: 12px;
  font-size: 15px;
  color: var(--text-2);
  text-align: left;
  transition: background 0.15s, color 0.15s;
}
.nav-item:hover {
  background: var(--surface-2);
}
.nav-item.selected {
  background: var(--accent-soft);
  color: var(--accent-text);
  font-weight: 600;
}
.rooms-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-3);
  padding: 24px 12px 8px;
}
.nav-item.room {
  height: 38px;
  font-size: 14px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--surface-3);
  margin: 0 5px;
}
.dot.on {
  background: var(--warm);
  box-shadow: 0 0 0 3px var(--warm-soft);
}
</style>
