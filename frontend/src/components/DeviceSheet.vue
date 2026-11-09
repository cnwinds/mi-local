<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { BellRing, Power } from 'lucide-vue-next'
import type { Device } from '../api'
import { devices, sendCommand } from '../store'
import DeviceIcon from './DeviceIcon.vue'
import AcTile from './tiles/AcTile.vue'
import CurtainTile from './tiles/CurtainTile.vue'
import BathHeaterTile from './tiles/BathHeaterTile.vue'
import AirerTile from './tiles/AirerTile.vue'
import MiotPanel from './MiotPanel.vue'
import DeviceSettings from './DeviceSettings.vue'

const props = defineProps<{ deviceId: string | null }>()
const emit = defineEmits<{ close: [] }>()

const show = computed({
  get: () => !!props.deviceId,
  set: (v) => !v && emit('close'),
})
const device = computed<Device | undefined>(() => (props.deviceId ? devices[props.deviceId] : undefined))
const s = computed(() => device.value?.state ?? {})
const TILES = { ac: AcTile, curtain: CurtainTile, bath_heater: BathHeaterTile, airer: AirerTile } as Record<string, unknown>
const tile = computed(() => (device.value ? TILES[device.value.kind] : undefined))

const controllable = computed(() => !!device.value && !['switch', 'gateway'].includes(device.value.kind))
const view = ref<'control' | 'settings'>('control')
watch(
  () => props.deviceId,
  () => (view.value = 'control'),
)

const brightness = ref(50)
const colorTemp = ref(50)
watch(
  s,
  (v) => {
    brightness.value = v.brightness ?? 50
    colorTemp.value = v.color_temp ?? 50
  },
  { immediate: true },
)

function cmd(action: string, value?: unknown, optimistic?: Record<string, unknown>) {
  if (device.value) sendCommand(device.value.id, action, value, optimistic)
}
</script>

<template>
  <van-popup v-model:show="show" position="bottom" round closeable class="device-sheet">
    <div v-if="device" class="body">
      <div v-if="controllable" class="tabs">
        <button :class="{ on: view === 'control' }" @click="view = 'control'">控制</button>
        <button :class="{ on: view === 'settings' }" @click="view = 'settings'">设置</button>
      </div>
      <template v-if="view === 'settings' || !controllable">
        <div class="head">
          <DeviceIcon :kind="device.kind" :model="device.model" :size="48" />
          <div>
            <div class="title">{{ device.name }}</div>
            <div class="sub">{{ device.room }} · {{ s.online ? '在线' : '离线' }}<template v-if="s.battery !== undefined"> · 电量 {{ s.battery }}%</template></div>
          </div>
        </div>
        <DeviceSettings :device="device" @saved="controllable ? (view = 'control') : emit('close')" />
      </template>
      <component :is="tile" v-else-if="tile && s.online" :device="device" class="embedded" />
      <template v-else>
        <div class="head">
          <DeviceIcon :kind="device.kind" :model="device.model" :active="!!s.power" :size="48" />
          <div>
            <div class="title">{{ device.name }}</div>
            <div class="sub">{{ device.room }} · {{ s.online ? '在线' : '离线' }}</div>
          </div>
        </div>

        <button v-if="s.online && device.kind === 'doorbell'" class="power on" @click="cmd('ring')">
          <BellRing :size="40" :stroke-width="2" />
          <span>点按响铃</span>
        </button>

        <button v-if="s.online && (device.kind === 'light' || device.kind === 'plug')" class="power" :class="{ on: s.power }"
          @click="cmd(s.power ? 'turn_off' : 'turn_on', undefined, { power: !s.power })">
          <Power :size="40" :stroke-width="2" />
          <span>{{ s.power ? '已开启' : '已关闭' }}</span>
        </button>

        <template v-if="s.online && device.kind === 'light'">
          <div class="row-label">亮度 <span class="num">{{ brightness }}%</span></div>
          <van-slider v-model="brightness" :min="1" :max="100" bar-height="32px" active-color="var(--warm)"
            @change="(v: number) => cmd('set_brightness', v, { power: true, brightness: v })">
            <template #button><span /></template>
          </van-slider>
          <div class="row-label">色温 <span>{{ colorTemp < 40 ? '暖光' : colorTemp > 70 ? '冷光' : '自然光' }}</span></div>
          <van-slider v-model="colorTemp" :min="0" :max="100" bar-height="32px" class="ct"
            @change="(v: number) => cmd('set_color_temp', v, { power: true, color_temp: v })">
            <template #button><span class="ct-knob" /></template>
          </van-slider>
        </template>

        <div v-if="s.online && device.kind === 'plug'" class="row-label">当前功率 <span class="num">{{ s.load_power ?? 0 }} W</span></div>
        <div v-if="!s.online" class="tip">设备离线，暂时连不上</div>
        <MiotPanel v-else-if="s.props" :device="device" />
        <div v-else-if="device.kind === 'other'" class="tip">这台设备没有公开的功能说明，暂时只能查看在线状态</div>
      </template>
    </div>
  </van-popup>
</template>

<style scoped>
.body {
  padding: 24px 20px calc(24px + env(safe-area-inset-bottom));
  max-height: 86vh;
  overflow-y: auto;
}
.embedded {
  box-shadow: none;
  padding: 4px 0 0;
  background: transparent !important;
}
.tabs {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  margin: -8px 0 18px;
  border-radius: 12px;
  background: var(--surface-3);
}
.tabs button {
  height: 30px;
  padding: 0 16px;
  border-radius: 10px;
  font-size: 13px;
  color: var(--text-2);
  transition: all 0.2s;
}
.tabs button.on {
  background: var(--surface);
  color: var(--text);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}
@media (min-width: 640px) {
  .device-sheet {
    width: 560px;
    right: 0;
    margin: 0 auto;
  }
}
.head {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 24px;
}
.title {
  font-size: 19px;
  font-weight: 650;
}
.sub {
  font-size: 13px;
  color: var(--text-3);
  margin-top: 2px;
}
.power {
  margin: 4px auto 20px;
  width: 128px;
  height: 128px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-3);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  transition: all 0.25s;
}
.power.on {
  background: var(--warm-glow);
  color: #fff;
  box-shadow: 0 0 0 10px var(--warm-soft), var(--shadow-warm);
}
.row-label {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 500;
  margin: 20px 0 10px;
}
.row-label span {
  color: var(--text-3);
  font-weight: 400;
}
.van-slider {
  border-radius: 14px;
  overflow: hidden;
}
.ct {
  --van-slider-inactive-background: transparent;
  --van-slider-active-background: transparent;
  background: linear-gradient(90deg, #ffb35c, #fff3e0, #cfe3ff);
  overflow: visible;
}
.ct-knob {
  display: block;
  width: 6px;
  height: 26px;
  border-radius: 3px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
}
.tip {
  text-align: center;
  color: var(--text-3);
  padding: 16px 0;
}
.mi {
  margin-top: 18px;
  font-size: 12px;
  color: var(--text-3);
  text-align: center;
}
</style>
