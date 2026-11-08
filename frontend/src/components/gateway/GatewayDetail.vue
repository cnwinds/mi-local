<script setup lang="ts">
import { computed } from 'vue'
import { Plus, Router, Settings2 } from 'lucide-vue-next'
import type { Device } from '../../api'
import { gateway } from '../../store'
import GatewayChildren from './GatewayChildren.vue'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ close: []; settings: []; pair: []; edit: [device: Device] }>()
const visible = computed({ get: () => props.show, set: (v) => !v && emit('close') })

const g = computed(() => gateway.value)
const lastSeen = computed(() => {
  const ts = g.value?.last_seen
  if (!ts) return '还没收到过网关的消息'
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts))
  return s < 60 ? `${s} 秒前` : s < 3600 ? `${Math.round(s / 60)} 分钟前` : `${Math.round(s / 3600)} 小时前`
})
const rows = computed(() => {
  const v = g.value
  if (!v?.configured) return []
  return [
    ['型号', v.model],
    ['所在房间', v.room],
    ['IP 地址', v.ip + (v.cloud_ip && v.cloud_ip !== v.ip ? '（手动）' : '')],
    ['MAC', v.mac],
    ['局域网密钥', v.has_key ? '已设置' : '未设置'],
    ['最后通信', lastSeen.value],
  ]
})
</script>

<template>
  <van-popup v-model:show="visible" round closeable position="bottom" :style="{ height: '86%' }">
    <div v-if="g?.configured" class="detail">
      <div class="hero">
        <div class="icon" :class="{ on: g.connected }"><Router :size="28" /></div>
        <div class="name">{{ g.name }}</div>
        <div class="state" :class="{ on: g.connected }">
          <span class="dot" />{{ g.connected ? '在线，局域网通信正常' : '连不上网关，检查网关电源和 IP' }}
        </div>
        <div class="buttons">
          <button @click="emit('pair')"><Plus :size="16" />添加子设备</button>
          <button @click="emit('settings')"><Settings2 :size="16" />设置</button>
        </div>
      </div>

      <div class="info card">
        <div v-for="[k, v] in rows" :key="k" class="row">
          <span>{{ k }}</span><b :class="{ warn: k === '局域网密钥' && !g.has_key }">{{ v }}</b>
        </div>
      </div>

      <div class="section-label">子设备</div>
      <GatewayChildren v-if="show" @edit="(d) => emit('edit', d)" />
    </div>
  </van-popup>
</template>

<style scoped>
.detail {
  height: 100%;
  overflow-y: auto;
  padding: 28px 16px calc(24px + env(safe-area-inset-bottom));
  box-sizing: border-box;
}
.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.icon {
  width: 64px;
  height: 64px;
  border-radius: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  color: var(--text-3);
}
.icon.on {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 10px 24px rgba(75, 103, 245, 0.3);
}
.name {
  margin-top: 12px;
  font-size: 20px;
  font-weight: 700;
}
.state {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  font-size: 13px;
  color: var(--danger);
}
.state.on {
  color: var(--text-2);
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}
.state.on .dot {
  background: var(--green);
}
.buttons {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
.buttons button {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 38px;
  padding: 0 16px;
  border-radius: 12px;
  background: var(--surface);
  box-shadow: var(--shadow-1);
  font-size: 14px;
  font-weight: 500;
}
.buttons button:first-child {
  background: var(--accent);
  color: #fff;
}
.info {
  margin-top: 20px;
  padding: 4px 16px;
}
.row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 0;
  font-size: 14px;
}
.row + .row {
  border-top: 1px solid var(--line);
}
.row span {
  color: var(--text-3);
}
.row b {
  font-weight: 500;
  text-align: right;
  word-break: break-all;
}
.row b.warn {
  color: var(--warm-strong);
}
</style>
