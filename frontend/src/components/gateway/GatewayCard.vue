<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight, KeyRound, Plus, Router, Settings2 } from 'lucide-vue-next'
import type { Device } from '../../api'
import { gateway, pairing } from '../../store'
import GatewayDetail from './GatewayDetail.vue'
import GatewaySettings from './GatewaySettings.vue'
import PairingSheet from './PairingSheet.vue'

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
const statusText = computed(() => {
  const ip = g.value?.ip ?? ''
  return { none: '', pairing: `配对中 · ${ip}`, online: `在线 · ${ip}`, offline: `连不上 · ${ip}` }[state.value]
})
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
  <div v-if="g" class="gateway card" :class="state">
    <template v-if="g.configured">
      <div class="head" @click="showDetail = true">
        <div class="icon"><Router :size="22" /><span class="dot" /></div>
        <div class="text">
          <div class="title">{{ g.name }}</div>
          <div class="status">{{ statusText }}</div>
        </div>
        <button class="icon-btn" title="网关设置" @click.stop="openSettings"><Settings2 :size="18" /></button>
      </div>
      <button v-if="!g.has_key" class="warn" @click="openSettings">
        <KeyRound :size="15" />还没设置局域网密钥，暂时不能控制窗帘、插座和门铃<ChevronRight :size="15" />
      </button>
      <div class="actions">
        <button class="stat" @click="showDetail = true">
          <b class="num">{{ g.children_online }}</b><span class="of num">/ {{ g.children }}</span>
          <span class="stat-label">子设备在线</span>
          <ChevronRight :size="16" class="chev" />
        </button>
        <button class="add" @click="openPairing"><Plus :size="17" />添加子设备</button>
      </div>
    </template>

    <div v-else class="empty">
      <div class="icon"><Router :size="22" /></div>
      <div class="text">
        <div class="title">还没有配置网关</div>
        <div class="status">无线开关、窗帘电机、插座等 Zigbee 设备都通过网关连接</div>
      </div>
      <van-button size="small" round type="primary" @click="showSettings = true">配置网关</van-button>
    </div>

    <GatewayDetail :show="showDetail" @close="showDetail = false" @settings="openSettings" @pair="openPairing"
      @edit="(d) => { showDetail = false; emit('edit', d) }" />
    <GatewaySettings :show="showSettings" @close="showSettings = false" />
    <PairingSheet :show="showPairing" @close="showPairing = false" />
  </div>
</template>

<style scoped>
.gateway {
  padding: 16px;
}
.head,
.empty {
  display: flex;
  align-items: center;
  gap: 12px;
}
.head {
  cursor: pointer;
}
.icon {
  position: relative;
  width: 42px;
  height: 42px;
  border-radius: 14px;
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
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2.5px solid var(--surface);
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
.text {
  flex: 1;
  min-width: 0;
}
.title {
  font-size: 15px;
  font-weight: 600;
}
.status {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 3px;
}
.offline .status {
  color: var(--danger);
}
.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-2);
  background: var(--surface-2);
}
.warn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 10px;
  background: var(--warm-soft);
  color: var(--warm-strong);
  font-size: 12px;
  text-align: left;
}
.warn svg:last-child {
  margin-left: auto;
  flex: none;
}
.actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.stat,
.add {
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  font-size: 13px;
}
.stat {
  flex: 1;
  gap: 4px;
  padding: 0 10px 0 12px;
  background: var(--surface-2);
}
.stat b {
  font-size: 17px;
  font-weight: 650;
}
.of {
  color: var(--text-3);
}
.stat-label {
  margin-left: 4px;
  color: var(--text-2);
}
.chev {
  margin-left: auto;
  color: var(--text-3);
}
.add {
  gap: 4px;
  padding: 0 14px;
  color: var(--accent);
  font-weight: 600;
  background: var(--accent-soft);
}
</style>
