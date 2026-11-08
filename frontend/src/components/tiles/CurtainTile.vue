<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Device } from '../../api'
import { sendCommand } from '../../store'
import TileHeader from './TileHeader.vue'

const props = defineProps<{ device: Device }>()

const s = computed(() => props.device.state)
const online = computed(() => !!s.value.online)
const position = ref(s.value.position ?? 0)
watch(() => s.value.position, (v) => (position.value = v ?? 0))

const status = computed(() => {
  if (!online.value) return '离线'
  const p = s.value.position ?? 0
  return p <= 2 ? '已关闭' : p >= 98 ? '已打开' : `开合 ${p}%`
})
const cmd = (action: string, value?: number) =>
  sendCommand(props.device.id, action, value, value !== undefined ? { position: value } : undefined)
</script>

<template>
  <div class="curtain-tile" :class="{ offline: !online }">
    <TileHeader kind="curtain" :name="device.name" :status="status" :active="online && (s.position ?? 0) > 2" />
    <template v-if="online">
      <div class="buttons">
        <button @click="cmd('open')">打开</button>
        <button @click="cmd('stop')">暂停</button>
        <button @click="cmd('close')">关闭</button>
      </div>
      <van-slider v-model="position" :min="0" :max="100" bar-height="6px" button-size="22px" class="slider"
        @change="(v: number) => cmd('set_position', v)" />
    </template>
  </div>
</template>

<style scoped>
.curtain-tile {
  background: #fff;
  border-radius: 18px;
  padding: 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.offline {
  opacity: 0.5;
}
.buttons {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.buttons button {
  flex: 1;
  border: none;
  font: inherit;
  font-size: 14px;
  padding: 10px 0;
  border-radius: 12px;
  background: #f0f1f4;
  color: #1f2329;
  -webkit-tap-highlight-color: transparent;
}
.buttons button:active {
  background: #e3e6ea;
}
.slider {
  margin: 18px 6px 6px;
  width: auto;
}
</style>
