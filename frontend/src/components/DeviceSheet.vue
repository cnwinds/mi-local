<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Device } from '../api'
import { devices, sendCommand } from '../store'
import DeviceIcon from './DeviceIcon.vue'

const props = defineProps<{ deviceId: string | null }>()
const emit = defineEmits<{ close: [] }>()

const show = computed({
  get: () => !!props.deviceId,
  set: (v) => !v && emit('close'),
})
const device = computed<Device | undefined>(() => (props.deviceId ? devices[props.deviceId] : undefined))
const s = computed(() => device.value?.state ?? {})

const brightness = ref(50)
const colorTemp = ref(50)
const position = ref(0)
watch(
  s,
  (v) => {
    brightness.value = v.brightness ?? 50
    colorTemp.value = v.color_temp ?? 50
    position.value = v.position ?? 0
  },
  { immediate: true },
)

function cmd(action: string, value?: unknown, optimistic?: Record<string, unknown>) {
  if (device.value) sendCommand(device.value.id, action, value, optimistic)
}
</script>

<template>
  <van-popup v-model:show="show" position="bottom" round closeable class="sheet">
    <div v-if="device" class="body">
      <div class="head">
        <DeviceIcon :kind="device.kind" :active="!!s.power" />
        <div>
          <div class="title">{{ device.name }}</div>
          <div class="sub">{{ device.room }} · {{ s.online ? '在线' : '离线' }}</div>
        </div>
      </div>

      <template v-if="s.online && (device.kind === 'light' || device.kind === 'plug')">
        <div class="power" :class="{ on: s.power }" @click="cmd(s.power ? 'turn_off' : 'turn_on', undefined, { power: !s.power })">
          <van-icon name="bulb-o" v-if="device.kind === 'light'" />
          <van-icon name="fire-o" v-else />
          <span>{{ s.power ? '已开启' : '已关闭' }}</span>
        </div>
      </template>

      <template v-if="s.online && device.kind === 'light'">
        <div class="row-label">亮度 <span>{{ brightness }}%</span></div>
        <van-slider v-model="brightness" :min="1" :max="100" bar-height="28px" active-color="#f5a623"
          @change="(v: number) => cmd('set_brightness', v, { power: true, brightness: v })">
          <template #button><span /></template>
        </van-slider>
        <div class="row-label">色温 <span>{{ colorTemp < 40 ? '暖光' : colorTemp > 70 ? '冷光' : '自然光' }}</span></div>
        <van-slider v-model="colorTemp" :min="0" :max="100" bar-height="28px" class="ct"
          @change="(v: number) => cmd('set_color_temp', v, { power: true, color_temp: v })">
          <template #button><span /></template>
        </van-slider>
      </template>

      <template v-if="s.online && device.kind === 'plug'">
        <div class="row-label">当前功率 <span>{{ s.load_power ?? 0 }} W</span></div>
      </template>

      <template v-if="s.online && device.kind === 'curtain'">
        <div class="curtain-buttons">
          <van-button round @click="cmd('open')">打开</van-button>
          <van-button round @click="cmd('stop')">暂停</van-button>
          <van-button round @click="cmd('close')">关闭</van-button>
        </div>
        <div class="row-label">开合度 <span>{{ position }}%</span></div>
        <van-slider v-model="position" :min="0" :max="100" bar-height="28px"
          @change="(v: number) => cmd('set_position', v, { position: v })">
          <template #button><span /></template>
        </van-slider>
      </template>

      <div v-if="!s.online" class="offline-tip">设备离线，无法通过局域网连接</div>
      <div v-else-if="device.kind === 'other'" class="offline-tip">该设备暂只支持查看在线状态</div>
    </div>
  </van-popup>
</template>

<style scoped>
.body {
  padding: 24px 20px calc(28px + env(safe-area-inset-bottom));
}
.head {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 24px;
}
.title {
  font-size: 18px;
  font-weight: 600;
}
.sub {
  font-size: 12px;
  color: #8f959e;
  margin-top: 2px;
}
.power {
  margin: 0 auto 24px;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: #f0f1f4;
  color: #9aa0ab;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 14px;
  transition: all 0.2s;
}
.power .van-icon {
  font-size: 40px;
}
.power.on {
  background: #fff3d6;
  color: #f5a623;
  box-shadow: 0 0 0 8px #fff9ea;
}
.row-label {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #1f2329;
  margin: 18px 0 10px;
}
.row-label span {
  color: #8f959e;
}
.van-slider {
  border-radius: 14px;
  overflow: hidden;
}
.ct {
  --van-slider-inactive-background: transparent;
  --van-slider-active-background: transparent;
  background: linear-gradient(90deg, #ffb35c, #fff3e0, #cfe3ff);
}
.curtain-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
}
.curtain-buttons .van-button {
  flex: 1;
}
.offline-tip {
  text-align: center;
  color: #8f959e;
  padding: 16px 0;
}
</style>
