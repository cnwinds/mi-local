<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Device } from '../api'
import { EVENT_NAMES, deviceList, devices, events, gateway, loadEvents } from '../store'
import { deviceStatus } from '../rooms'
import CloudCard from '../components/CloudCard.vue'
import DeviceIcon from '../components/DeviceIcon.vue'
import DeviceSheet from '../components/DeviceSheet.vue'
import GatewayRow from '../components/gateway/GatewayRow.vue'
import PageHeader from '../components/PageHeader.vue'
import VoiceCard from '../components/VoiceCard.vue'
import AddDeviceSheet from '../components/add/AddDeviceSheet.vue'
import { ChevronRight, EyeOff, Plus } from 'lucide-vue-next'

const tab = ref('devices')
const detailId = ref<string | null>(null)
const showAdd = ref(false)
const eventLimit = ref(100)

onMounted(loadEvents)

const GROUPS: [string, string][] = [['light', '灯'], ['switch', '无线开关'], ['curtain', '窗帘'], ['plug', '插座'], ['ac', '空调'], ['bath_heater', '浴霸'], ['airer', '晾衣架'], ['lock', '门锁'], ['doorbell', '门铃'], ['other', '其他设备']]
const grouped = computed(() =>
  GROUPS.map(([kind, label]) => ({ kind, label, items: deviceList.value.filter((d) => d.kind === kind) })).filter((g) => g.items.length),
)

const edit = (d: Device) => (detailId.value = d.id)

function statusText(d: Device) {
  const text = deviceStatus(d)
  return d.hidden && d.state.online ? `${text} · 首页已隐藏` : text
}

const onlineCount = computed(() => deviceList.value.filter((d) => d.state.online).length)

const timeFmt = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const dateFmt = new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' })
function eventTime(ts: number) {
  const d = new Date(ts * 1000)
  const today = new Date().toDateString() === d.toDateString()
  return today ? timeFmt.format(d) : `${dateFmt.format(d)} ${timeFmt.format(d)}`
}
</script>

<template>
  <div class="devices">
    <PageHeader title="设备" :subtitle="`共 ${deviceList.length} 台 · ${onlineCount} 台在线`">
      <button class="add-btn" @click="showAdd = true"><Plus :size="18" :stroke-width="2.4" />添加设备</button>
    </PageHeader>
    <div class="top-cards">
      <CloudCard />
      <VoiceCard />
    </div>
    <van-tabs v-model:active="tab" line-width="18px" class="tabs">
      <van-tab title="设备管理" name="devices">
        <div class="groups">
          <section v-if="gateway" class="group">
            <div class="section-label">网关</div>
            <div class="group-list card"><GatewayRow @edit="edit" /></div>
          </section>
          <section v-for="g in grouped" :key="g.kind" class="group">
            <div class="section-label">{{ g.label }} · {{ g.items.length }}</div>
            <div class="group-list card">
              <div v-for="d in g.items" :key="d.id" class="item" @click="edit(d)">
                <DeviceIcon :kind="d.kind" :model="d.model" :name="d.name" :size="38" :class="{ dim: !d.state.online }" />
                <div class="item-text">
                  <div class="item-name">{{ d.name }}<EyeOff v-if="d.hidden" :size="13" class="hidden-mark" /></div>
                  <div class="item-meta">
                    <span class="dot" :class="{ on: d.state.online }" />{{ d.room }} · {{ statusText(d) }}
                  </div>
                </div>
                <ChevronRight :size="18" class="arrow" />
              </div>
            </div>
          </section>
        </div>
      </van-tab>
      <van-tab title="事件日志" name="events">
        <div class="tip">记录无线开关按键和门锁开关门，保留最近 2000 条，重启也不会丢。</div>
        <van-cell-group inset class="events">
          <van-cell v-for="(e, i) in events.slice(0, eventLimit)" :key="i" :title="devices[e.device]?.name ?? e.device" :value="EVENT_NAMES[e.event] ?? e.event"
            :label="eventTime(e.ts)" @click="devices[e.device] && edit(devices[e.device])" is-link />
          <van-cell v-if="!events.length" title="暂无事件" />
          <van-cell v-if="events.length > eventLimit" :title="`再显示 100 条（还有 ${events.length - eventLimit} 条）`" class="more"
            @click="eventLimit += 100" />
        </van-cell-group>
      </van-tab>
    </van-tabs>

    <DeviceSheet :device-id="detailId" @close="detailId = null" />
    <AddDeviceSheet :show="showAdd" @close="showAdd = false" @edit="edit" />
  </div>
</template>

<style scoped>
.add-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 40px;
  padding: 0 16px 0 12px;
  border-radius: 20px;
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 6px 18px rgba(75, 103, 245, 0.3);
}
.add-btn:active {
  transform: scale(0.96);
}
.top-cards {
  display: grid;
  gap: 12px;
  padding: 8px 16px 4px;
}
.top-cards:empty {
  display: none;
}
.tabs {
  margin-top: 8px;
}
.groups {
  padding: 0 16px;
}
.group-list {
  padding: 2px 0;
  overflow: hidden;
}
.item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.15s;
}
.item + .item {
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
.dim {
  opacity: 0.4;
  filter: grayscale(1);
}
.item-text {
  flex: 1;
  min-width: 0;
}
.item-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 500;
}
.hidden-mark {
  color: var(--text-3);
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-3);
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-3);
  opacity: 0.5;
}
.dot.on {
  background: var(--green);
  opacity: 1;
}
.arrow {
  color: var(--text-3);
  flex: none;
}
.more {
  color: var(--accent);
  text-align: center;
  cursor: pointer;
}
.tip {
  font-size: 12px;
  color: var(--text-3);
  padding: 12px 20px 8px;
}
@media (min-width: 900px) {
  .top-cards {
    padding: 8px 0 4px;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    align-items: stretch;
  }
  .groups {
    padding: 0;
    columns: 2;
    column-gap: 20px;
  }
  .group {
    break-inside: avoid;
    padding-top: 1px;
  }
  .events {
    margin: 0;
  }
}
</style>

