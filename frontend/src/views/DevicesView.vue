<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { showToast } from 'vant'
import { api, type Device } from '../api'
import { EVENT_NAMES, cloud, deviceList, devices, events, loadDevices, loadEvents, rooms } from '../store'
import CloudCard from '../components/CloudCard.vue'
import DeviceIcon from '../components/DeviceIcon.vue'
import GatewayCard from '../components/gateway/GatewayCard.vue'
import PageHeader from '../components/PageHeader.vue'
import { Check, ChevronRight, EyeOff } from 'lucide-vue-next'
import { miHomeLabel } from '../naming'

const synced = computed(() => !!cloud.value?.logged_in)

const tab = ref('devices')
const editing = ref<Device | null>(null)
const form = ref({ name: '', room: '', hidden: false })
const showRoomPicker = ref(false)
const newRoom = ref('')

onMounted(loadEvents)

const GROUPS: [string, string][] = [['light', '灯'], ['switch', '无线开关'], ['curtain', '窗帘'], ['plug', '插座'], ['ac', '空调'], ['bath_heater', '浴霸'], ['airer', '晾衣架'], ['doorbell', '门铃'], ['other', '其他设备']]
const grouped = computed(() =>
  GROUPS.map(([kind, label]) => ({ kind, label, items: deviceList.value.filter((d) => d.kind === kind) })).filter((g) => g.items.length),
)

function edit(d: Device) {
  editing.value = d
  form.value = { name: d.name, room: d.room, hidden: d.hidden }
}

function pickRoom(room: string) {
  form.value.room = room
  showRoomPicker.value = false
}

function addRoom() {
  const room = newRoom.value.trim()
  if (!room) return
  if (!rooms.value.includes(room)) api.setRooms([...rooms.value, room]).then((r) => (rooms.value = r))
  pickRoom(room)
  newRoom.value = ''
}

async function save() {
  const d = editing.value
  if (!d) return
  const name = form.value.name.trim()
  await api.patchDevice(
    d.id,
    synced.value
      ? {
          hidden: form.value.hidden,
          local_name: name && name !== d.cloud_name ? name : '',
          local_room: form.value.room !== d.cloud_room ? form.value.room : '',
          name_auto: name === d.name ? d.name_auto : false,
        }
      : { ...form.value, name },
  )
  await loadDevices()
  editing.value = null
  showToast('已保存')
}

function statusText(d: Device) {
  if (!d.state.online) return '离线'
  if (d.kind === 'switch') return d.state.battery !== undefined ? `电量 ${d.state.battery}%` : '在线'
  return d.hidden ? '在线 · 已在首页隐藏' : '在线'
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
                  <div v-if="miHomeLabel(d)" class="item-meta">{{ miHomeLabel(d) }}</div>
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

    <van-popup :show="!!editing" position="bottom" round @update:show="(v: boolean) => !v && (editing = null)">
      <div class="sheet" v-if="editing">
        <div class="sheet-title">设备设置</div>
        <van-cell-group inset>
          <van-field v-model="form.name" label="名称" :placeholder="editing.cloud_name" clearable />
          <van-cell title="房间" :value="form.room" is-link @click="showRoomPicker = true" />
          <van-cell title="在首页隐藏">
            <template #right-icon><van-switch v-model="form.hidden" size="22px" /></template>
          </van-cell>
          <van-cell title="型号" :value="editing.model" />
        </van-cell-group>
        <div class="sheet-tip" v-if="synced">
          米家里叫「{{ editing.cloud_name }}」，在「{{ editing.cloud_room }}」。这里修改只在本应用显示，名称清空则恢复米家的名字。
        </div>
        <div class="sheet-actions"><van-button block round type="primary" @click="save">保存</van-button></div>
      </div>
    </van-popup>

    <van-action-sheet v-model:show="showRoomPicker" title="选择房间">
      <van-cell v-for="r in rooms" :key="r" :title="r" clickable @click="pickRoom(r)">
        <template #right-icon><Check v-if="form.room === r" :size="18" color="var(--accent)" /></template>
      </van-cell>
      <van-field v-model="newRoom" placeholder="新建房间" center>
        <template #button><van-button size="small" type="primary" round @click="addRoom">添加</van-button></template>
      </van-field>
      <div style="height: 24px" />
    </van-action-sheet>
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

