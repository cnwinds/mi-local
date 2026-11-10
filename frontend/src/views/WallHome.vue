<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Minimize2 } from 'lucide-vue-next'
import { floorplan } from '../store'
import { headline } from '../home'
import { exitWall } from '../router'
import FloorPlan from '../components/home/FloorPlan.vue'
import HomeStats from '../components/home/HomeStats.vue'

const now = ref(new Date())
const timer = setInterval(() => (now.value = new Date()), 10_000)
const clock = computed(() => now.value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))
const dateText = computed(() => now.value.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }))

// Landscape puts the clock and cards beside the plan; portrait stacks them above it.
const portraitQuery = matchMedia('(orientation: portrait)')
const portrait = ref(portraitQuery.matches)
const onOrientation = (e: MediaQueryListEvent) => (portrait.value = e.matches)
portraitQuery.addEventListener('change', onOrientation)

// Keep the screen awake where the browser allows it; the lock drops whenever the page is hidden.
let wakeLock: WakeLockSentinel | null = null
async function keepAwake() {
  wakeLock = (await navigator.wakeLock?.request('screen').catch(() => null)) ?? null
}
const onVisible = () => document.visibilityState === 'visible' && keepAwake()
onMounted(() => {
  keepAwake()
  document.addEventListener('visibilitychange', onVisible)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  portraitQuery.removeEventListener('change', onOrientation)
  document.removeEventListener('visibilitychange', onVisible)
  wakeLock?.release().catch(() => {})
})

// Browsers only grant full screen from a user gesture, so the first tap anywhere asks for it.
function enterFullscreen(e: MouseEvent) {
  if (document.fullscreenElement || (e.target as Element).closest('.exit')) return
  document.documentElement.requestFullscreen?.().catch(() => {})
}
function exit() {
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
  exitWall()
}
</script>

<template>
  <div class="wall-home" :class="{ portrait }" @click.capture="enterFullscreen">
    <aside class="side">
      <div class="time">
        <div class="clock num">{{ clock }}</div>
        <div class="date">{{ dateText }}</div>
        <div class="headline">{{ headline }}</div>
      </div>
      <HomeStats :column="!portrait" class="stats" />
    </aside>
    <main class="plan-area">
      <FloorPlan v-if="floorplan" wall />
      <van-empty v-else description="还没有户型图" />
    </main>
    <button class="exit" title="退出墙面模式" @click.stop="exit"><Minimize2 :size="18" /></button>
  </div>
</template>

<style scoped>
.wall-home {
  height: 100vh;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 32px;
  padding: 32px;
  overflow: hidden;
}
.side {
  display: flex;
  flex-direction: column;
  gap: 28px;
  min-width: 0;
}
.clock {
  font-size: 76px;
  font-weight: 250;
  line-height: 1;
  letter-spacing: -0.04em;
}
.date {
  margin-top: 10px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-2);
}
.headline {
  margin-top: 6px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-3);
}
.plan-area {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
}
.plan-area > * {
  flex: 1;
}

/* Portrait tablets: clock and cards on top, the plan below */
.wall-home.portrait {
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
  gap: 24px;
  padding: 28px 24px;
}
.portrait .side {
  gap: 20px;
}
.portrait .clock {
  font-size: 64px;
}

.exit {
  position: fixed;
  top: 16px;
  right: 16px;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
  background: var(--surface-glass);
  box-shadow: var(--shadow-1);
  opacity: 0.6;
  transition: opacity 0.2s;
}
.exit:hover {
  opacity: 1;
}
</style>
