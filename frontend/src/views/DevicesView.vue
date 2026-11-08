<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { showToast } from 'vant'
import { api, type Device } from '../api'
import { EVENT_NAMES, cloud, deviceList, devices, events, loadDevices, loadEvents, rooms } from '../store'
import CloudCard from '../components/CloudCard.vue'
import DeviceIcon from '../components/DeviceIcon.vue'
import PairingCard from '../components/PairingCard.vue'

const synced = computed(() => !!cloud.value?.logged_in)

const tab = ref('devices')
const editing = ref<Device | null>(null)
const form = ref({ name: '', room: '', hidden: false })
const showRoomPicker = ref(false)
const newRoom = ref('')

onMounted(loadEvents)

const GROUPS: [string, string][] = [['light', '灯'], ['switch', '无线开关'], ['curtain', '窗帘'], ['plug', '插座'], ['other', '其他设备']]
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

const timeFmt = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
</script>

<template>
  <div class="devices">
    <header class="hero"><div class="title">设备</div></header>
    <CloudCard />
    <PairingCard />
    <van-tabs v-model:active="tab" background="#f6f7f9" color="#3e7bfa" line-width="16px">
      <van-tab title="设备管理" name="devices">
        <van-cell-group v-for="g in grouped" :key="g.kind" inset :title="`${g.label}（${g.items.length}）`">
          <van-cell v-for="d in g.items" :key="d.id" :title="d.name" :label="`${d.room} · ${statusText(d)}`" is-link center @click="edit(d)">
            <template #icon><DeviceIcon :kind="d.kind" :active="!!d.state.online" class="cell-icon" /></template>
          </van-cell>
        </van-cell-group>
      </van-tab>
      <van-tab title="事件日志" name="events">
        <div class="tip">按下任意无线开关，这里会实时显示是哪个开关。</div>
        <van-cell-group inset>
          <van-cell v-for="(e, i) in events" :key="i" :title="devices[e.device]?.name ?? e.device" :value="EVENT_NAMES[e.event] ?? e.event"
            :label="timeFmt.format(new Date(e.ts * 1000))" @click="devices[e.device] && edit(devices[e.device])" is-link />
          <van-cell v-if="!events.length" title="暂无事件" />
        </van-cell-group>
      </van-tab>
    </van-tabs>

    <van-popup :show="!!editing" position="bottom" round @update:show="(v: boolean) => !v && (editing = null)">
      <div class="edit" v-if="editing">
        <div class="edit-title">设备设置</div>
        <van-cell-group inset>
          <van-field v-model="form.name" label="名称" :placeholder="editing.cloud_name" clearable />
          <van-cell title="房间" :value="form.room" is-link @click="showRoomPicker = true" />
          <van-cell title="在首页隐藏">
            <template #right-icon><van-switch v-model="form.hidden" size="22px" /></template>
          </van-cell>
          <van-cell title="型号" :value="editing.model" />
        </van-cell-group>
        <div class="sync-tip" v-if="synced">
          米家里叫「{{ editing.cloud_name }}」，在「{{ editing.cloud_room }}」。这里修改只在本应用显示，名称清空则恢复米家的名字。
        </div>
        <div class="edit-actions"><van-button block round type="primary" @click="save">保存</van-button></div>
      </div>
    </van-popup>

    <van-action-sheet v-model:show="showRoomPicker" title="选择房间">
      <van-cell v-for="r in rooms" :key="r" :title="r" clickable @click="pickRoom(r)">
        <template #right-icon><van-icon v-if="form.room === r" name="success" color="#3e7bfa" /></template>
      </van-cell>
      <van-field v-model="newRoom" placeholder="新建房间" center>
        <template #button><van-button size="small" type="primary" round @click="addRoom">添加</van-button></template>
      </van-field>
      <div style="height: 24px" />
    </van-action-sheet>
  </div>
</template>

<style scoped>
.hero {
  padding: calc(20px + env(safe-area-inset-top)) 20px 4px;
}
.title {
  font-size: 26px;
  font-weight: 700;
}
.cell-icon {
  margin-right: 12px;
  transform: scale(0.85);
}
.tip {
  font-size: 12px;
  color: #8f959e;
  padding: 12px 20px 0;
}
.edit {
  padding: 20px 0 calc(24px + env(safe-area-inset-bottom));
}
.edit-title {
  text-align: center;
  font-weight: 600;
  margin-bottom: 16px;
}
.sync-tip {
  font-size: 12px;
  color: #8f959e;
  padding: 10px 32px 0;
}
.edit-actions {
  padding: 20px 16px 0;
}
</style>
