<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight, Router } from 'lucide-vue-next'
import type { Device } from '../../api'
import { gateway, pairing } from '../../store'
import GatewayDetail from './GatewayDetail.vue'
import GatewaySettings from './GatewaySettings.vue'
import PairingSheet from './PairingSheet.vue'

// The gateway as one row of the device list; its detail sheet holds children, pairing and settings.
const emit = defineEmits<{ edit: [device: Device] }>()

const g = computed(() => gateway.value)
const showDetail = ref(false)
const showSettings = ref(false)
const showPairing = ref(false)

const state = computed(() => {
  if (!g.value?.configured) return 'none'
  if (pairing.value?.active) return 'pairing'
  return g.value.connected ? 'online' : 'offline'
})
const status = computed(() => {
  const v = g.value
  if (!v?.configured) return { text: '还没有配置，无线开关、窗帘、插座都要通过网关连接', warn: true }
  if (state.value === 'offline') return { text: `连不上 · ${v.ip}`, warn: true }
  if (!v.has_key) return { text: '还没设置局域网密钥，暂时不能控制窗帘、插座和门铃', warn: true }
  const children = `${v.children_online}/${v.children} 子设备在线`
  return { text: state.value === 'pairing' ? `配对中 · ${children}` : `${v.room} · ${children}`, warn: false }
})

function open() {
  if (!g.value?.configured || !g.value.has_key) showSettings.value = true
  else showDetail.value = true
}
const openSettings = () => {
  showDetail.value = false
  showSettings.value = true
}
const openPairing = () => {
  showDetail.value = false
  showPairing.value = true
}
</script>

<template>
  <div v-if="g" class="item" :class="state" @click="open">
    <div class="icon"><Router :size="19" /><span class="dot" /></div>
    <div class="item-text">
      <div class="item-name">{{ g.configured ? g.name : '网关' }}</div>
      <div class="item-meta" :class="{ warn: status.warn }">{{ status.text }}</div>
    </div>
    <ChevronRight :size="18" class="arrow" />
  </div>
  <GatewayDetail :show="showDetail" @close="showDetail = false" @settings="openSettings" @pair="openPairing"
    @edit="(d) => { showDetail = false; emit('edit', d) }" />
  <GatewaySettings :show="showSettings" @close="showSettings = false" />
  <PairingSheet :show="showPairing" @close="showPairing = false" />
</template>

<style scoped>
.item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.15s;
}
.item:active {
  background: var(--surface-2);
}
@media (hover: hover) {
  .item:hover {
    background: var(--surface-2);
  }
}
.icon {
  position: relative;
  width: 38px;
  height: 38px;
  border-radius: 34%;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  color: var(--text-3);
}
.online .icon,
.pairing .icon {
  background: var(--accent-soft);
  color: var(--accent);
}
.dot {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid var(--surface);
  background: var(--text-3);
}
.online .dot {
  background: var(--green);
}
.offline .dot {
  background: var(--danger);
}
.pairing .dot {
  background: var(--accent);
  animation: blink 1s ease-in-out infinite;
}
@keyframes blink {
  50% {
    opacity: 0.3;
  }
}
.item-text {
  flex: 1;
  min-width: 0;
}
.item-name {
  font-size: 15px;
  font-weight: 500;
}
.item-meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-3);
}
.item-meta.warn {
  color: var(--warm-strong);
}
.offline .item-meta.warn {
  color: var(--danger);
}
.arrow {
  color: var(--text-3);
  flex: none;
}
</style>
