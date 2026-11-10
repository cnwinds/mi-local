<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { showToast } from 'vant'
import { LayoutGrid, Map as MapIcon, TabletSmartphone } from 'lucide-vue-next'
import { can, floorplan } from '../store'
import { panelRooms } from '../rooms'
import { headline } from '../home'
import { openWall } from '../router'
import PageHeader from '../components/PageHeader.vue'
import RoomTile from '../components/home/RoomTile.vue'
import FloorPlan from '../components/home/FloorPlan.vue'
import HomeStats from '../components/home/HomeStats.vue'
import FloorPlanEditor from '../components/home/FloorPlanEditor.vue'

const now = ref(new Date())
const timer = setInterval(() => (now.value = new Date()), 60_000)
onBeforeUnmount(() => clearInterval(timer))

// Wide screens control devices on the plan; phones get a compact plan above the room tiles.
const wideQuery = matchMedia('(min-width: 900px)')
const wide = ref(wideQuery.matches)
const onWide = (e: MediaQueryListEvent) => (wide.value = e.matches)
wideQuery.addEventListener('change', onWide)
onBeforeUnmount(() => wideQuery.removeEventListener('change', onWide))
const mode = ref(localStorage.getItem('home-view') === 'tiles' ? 'tiles' : 'plan')
function setMode(m: 'plan' | 'tiles') {
  mode.value = m
  localStorage.setItem('home-view', m)
}
const canPlan = computed(() => !!floorplan.value)
const showPlan = computed(() => canPlan.value && mode.value === 'plan')
const showTiles = computed(() => !showPlan.value || !wide.value)
const greeting = computed(() => {
  const h = now.value.getHours()
  return h < 5 ? '夜深了' : h < 11 ? '早上好' : h < 13 ? '中午好' : h < 18 ? '下午好' : '晚上好'
})
const dateText = computed(() => now.value.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }))

const creating = ref(false)

function toWall() {
  openWall()
  showToast({ message: '点一下屏幕进入全屏。\n点右上角按钮可以退出', duration: 3000 })
}
</script>

<template>
  <div class="home">
    <PageHeader :eyebrow="dateText" :title="greeting" :subtitle="headline">
      <button v-if="!canPlan && wide && can('admin')" class="create-plan" @click="creating = true">
        <MapIcon :size="16" />创建户型图
      </button>
      <button v-if="canPlan && wide" class="wall-button" title="用作墙面面板：全屏常亮显示户型图" @click="toWall">
        <TabletSmartphone :size="16" />
      </button>
      <div v-if="canPlan" class="view-switch">
        <button :class="{ on: mode === 'plan' }" title="户型图" @click="setMode('plan')"><MapIcon :size="16" /></button>
        <button :class="{ on: mode === 'tiles' }" title="房间卡片" @click="setMode('tiles')"><LayoutGrid :size="16" /></button>
      </div>
    </PageHeader>

    <div :class="{ dash: showPlan && wide }">
      <HomeStats class="home-stats" :column="showPlan && wide" />

      <FloorPlan v-if="showPlan" :compact="!wide" class="plan" />
      <template v-if="showTiles">
        <div class="section-label rooms-label">房间</div>
        <div class="rooms">
          <RoomTile v-for="room in panelRooms" :key="room" :room="room" />
        </div>
        <van-empty v-if="!panelRooms.length" description="还没有设备，去「设备」页同步米家" />
      </template>
    </div>
    <FloorPlanEditor v-if="creating" @close="creating = false" />
  </div>
</template>

<style scoped>
.home {
  padding-bottom: 8px;
}
.home-stats {
  padding: 14px 16px 0;
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
  .rooms {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
@media (min-width: 900px) {
  .home-stats,
  .rooms,
  .rooms-label {
    padding-left: 0;
    padding-right: 0;
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

.view-switch {
  display: flex;
  gap: 2px;
  padding: 3px;
  border-radius: 12px;
  background: var(--surface-2);
}
.view-switch button,
.wall-button {
  width: 34px;
  height: 30px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
  transition: background 0.15s, color 0.15s;
}
.view-switch button.on {
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-1);
}
.wall-button {
  height: 36px;
  border-radius: 12px;
  background: var(--surface-2);
}
.wall-button:hover {
  color: var(--text);
}
.create-plan {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  background: var(--accent-soft);
  color: var(--accent-text);
}

.plan {
  padding: 18px 16px 0;
}
.dash .plan {
  padding: 0;
}

/* Floor plan on the left, the summary cards stacked beside it */
.dash {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 210px;
  gap: 24px;
  align-items: start;
  padding-top: 18px;
}
.dash .home-stats {
  order: 2;
  padding: 0;
}
</style>
