<script setup lang="ts">
import { computed, ref } from 'vue'
import { showDialog } from 'vant'
import { ChevronRight, Router } from 'lucide-vue-next'
import type { Device, GatewayCandidate } from '../../api'
import { gateway, pairing } from '../../store'
import GatewayDetail from './GatewayDetail.vue'
import GatewaySettings from './GatewaySettings.vue'
import PairingSheet from './PairingSheet.vue'

// One gateway of the Mi Home account as a row of the device list. The one the hub talks to opens its detail
// sheet (children, pairing, settings); other Gateway 2s open their own settings; the rest only explain.
const props = defineProps<{ gw: GatewayCandidate }>()
const emit = defineEmits<{ edit: [device: Device] }>()

const g = computed(() => gateway.value)
const active = computed(() => !!g.value?.configured && g.value.id === props.gw.id)
const showDetail = ref(false)
const showSettings = ref(false)
const showPairing = ref(false)

const state = computed(() => {
  if (!active.value) return 'none'
  if (pairing.value?.active) return 'pairing'
  return g.value!.connected ? 'online' : 'offline'
})
const name = computed(() => (active.value ? g.value!.name : props.gw.name) || '网关')
const status = computed(() => {
  const v = g.value
  if (!props.gw.supported) return { text: `${props.gw.model} · 不支持局域网协议，子设备通过云端控制`, warn: false }
  if (!active.value) {
    return v?.configured
      ? { text: '同时只能启用一台网关 2，点击可以改用这台', warn: false }
      : { text: '还没启用局域网控制，无线开关、窗帘、插座都要通过它连接', warn: true }
  }
  if (state.value === 'offline') return { text: `连不上 · ${v!.ip}`, warn: true }
  if (!v!.has_key) return { text: '还没设置局域网密钥，暂时不能控制窗帘、插座和门铃', warn: true }
  const children = `${v!.children_online}/${v!.children} 子设备在线`
  return { text: state.value === 'pairing' ? `配对中 · ${children}` : `${v!.room} · ${children}`, warn: false }
})

function open() {
  if (!props.gw.supported) {
    showDialog({
      title: name.value,
      message: `${props.gw.model} 不提供局域网协议，mi-local 不能直接和它通信。挂在它下面的子设备会通过米家云端控制，断网时不可用。`,
    })
  } else if (active.value && g.value!.has_key) {
    showDetail.value = true
  } else {
    showSettings.value = true
  }
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
  <div class="item" :class="[state, { unsupported: !gw.supported }]" @click="open">
    <div class="icon"><Router :size="19" /><span v-if="active" class="dot" /></div>
    <div class="item-text">
      <div class="item-name">{{ name }}</div>
      <div class="item-meta" :class="{ warn: status.warn }">{{ status.text }}</div>
    </div>
    <ChevronRight :size="18" class="arrow" />
  </div>
  <template v-if="gw.supported">
    <GatewayDetail v-if="active" :show="showDetail" @close="showDetail = false" @settings="openSettings" @pair="openPairing"
      @edit="(d) => { showDetail = false; emit('edit', d) }" />
    <GatewaySettings :show="showSettings" :gw="gw" @close="showSettings = false" />
    <PairingSheet v-if="active" :show="showPairing" @close="showPairing = false" />
  </template>
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
.item ~ .item {
  border-top: 1px solid var(--line);
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
.unsupported .icon {
  opacity: 0.5;
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
