<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Device } from '../api'
import { EVENT_NAMES, deviceList, devices, events, loadEvents } from '../store'
import { deviceStatus } from '../rooms'
import CloudCard from '../components/CloudCard.vue'
import DeviceIcon from '../components/DeviceIcon.vue'
import DeviceSheet from '../components/DeviceSheet.vue'
import GatewayCard from '../components/gateway/GatewayCard.vue'
import PageHeader from '../components/PageHeader.vue'
import VoiceCard from '../components/VoiceCard.vue'
import { ChevronRight, EyeOff } from 'lucide-vue-next'

const tab = ref('devices')
const detailId = ref<string | null>(null)

onMounted(loadEvents)

const GROUPS: [string, string][] = [['light', '灯'], ['switch', '无线开关'], ['curtain', '窗帘'], ['plug', '插座'], ['ac', '空调'], ['bath_heater', '浴霸'], ['airer', '晾衣架'], ['doorbell', '门铃'], ['other', '其他设备']]
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
</script>

<template>
  <div class="devices">
    <PageHeader title="设备" :subtitle="`共 ${deviceList.length} 台 · ${onlineCount} 台在线`" />
    <div class="top-cards">
      <GatewayCard @edit="edit" />
      <CloudCard />
      <VoiceCard @edit="edit" />
    </div>
    <van-tabs v-model:active="tab" line-width="18px" class="tabs">
      <van-tab title="设备管理" name="devices">
        <div class="groups">
          <section v-for="g in grouped" :key="g.kind" class="group">
            <div class="section-label">{{ g.label }} · {{ g.items.length }}</div>
            <div class="group-list card">
              <div v-for="d in g.items" :key="d.id" class="item" @click="edit(d)">
                <DeviceIcon :kind="d.kind" :model="d.model" :size="38" :class="{ dim: !d.state.online }" />
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
        <div class="tip">按下任意无线开关，这里会实时显示是哪个开关。</div>
        <van-cell-group inset class="events">
          <van-cell v-for="(e, i) in events" :key="i" :title="devices[e.device]?.name ?? e.device" :value="EVENT_NAMES[e.event] ?? e.event"
            :label="timeFmt.format(new Date(e.ts * 1000))" @click="devices[e.device] && edit(devices[e.device])" is-link />
          <van-cell v-if="!events.length" title="暂无事件" />
        </van-cell-group>
      </van-tab>
    </van-tabs>

    <DeviceSheet :device-id="detailId" @close="detailId = null" />
  </div>
</template>

<style scoped>
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
.tip {
  font-size: 12px;
  color: var(--text-3);
  padding: 12px 20px 8px;
}
@media (min-width: 900px) {
  .top-cards {
    padding: 8px 0 4px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
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

