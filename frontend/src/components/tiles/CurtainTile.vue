<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronsLeftRight, ChevronsRightLeft, Pause } from 'lucide-vue-next'
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
  return p <= 2 ? '已关闭' : p >= 98 ? '已打开' : `打开了 ${p}%`
})
const cmd = (action: string, value?: number) =>
  sendCommand(props.device.id, action, value, value !== undefined ? { position: value } : undefined)
</script>

<template>
  <div class="curtain-tile card" :class="{ offline: !online }">
    <TileHeader kind="curtain" :name="device.name" :status="status" :active="online && (s.position ?? 0) > 2" />
    <template v-if="online">
      <div class="visual">
        <div class="panel left" :style="{ width: `${50 - position / 2.2}%` }" />
        <div class="panel right" :style="{ width: `${50 - position / 2.2}%` }" />
      </div>
      <van-slider v-model="position" :min="0" :max="100" bar-height="6px" button-size="22px" class="slider"
        @change="(v: number) => cmd('set_position', v)" />
      <div class="buttons">
        <button @click="cmd('open')"><ChevronsLeftRight :size="18" />打开</button>
        <button @click="cmd('stop')"><Pause :size="18" />暂停</button>
        <button @click="cmd('close')"><ChevronsRightLeft :size="18" />关闭</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.curtain-tile {
  padding: 16px;
}
.offline {
  opacity: 0.5;
}
.visual {
  position: relative;
  height: 44px;
  margin: 16px 0 4px;
  border-radius: 12px;
  background: linear-gradient(180deg, #cfe6ff, #eef6ff);
  overflow: hidden;
}
.panel {
  position: absolute;
  top: 0;
  bottom: 0;
  background: repeating-linear-gradient(90deg, #c9d2fb 0 7px, #b3bff7 7px 9px, #c9d2fb 9px 14px);
  transition: width 0.4s ease;
}
.panel.left {
  left: 0;
  border-radius: 0 6px 6px 0;
}
.panel.right {
  right: 0;
  border-radius: 6px 0 0 6px;
}
.slider {
  margin: 16px 6px 4px;
  width: auto;
}
.buttons {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
.buttons button {
  flex: 1;
  height: 42px;
  border-radius: 12px;
  background: var(--surface-2);
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: background 0.15s;
}
.buttons button:active {
  background: var(--surface-3);
}
@media (prefers-color-scheme: dark) {
  .visual {
    background: linear-gradient(180deg, #1d2a3d, #202838);
  }
  .panel {
    background: repeating-linear-gradient(90deg, #39437a 0 7px, #2f386a 7px 9px, #39437a 9px 14px);
  }
}
</style>
