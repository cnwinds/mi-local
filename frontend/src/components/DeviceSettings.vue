<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'
import { Check } from 'lucide-vue-next'
import { api, type Device } from '../api'
import { cloud, loadDevices, rooms } from '../store'

const props = defineProps<{ device: Device }>()
const emit = defineEmits<{ saved: [] }>()

const synced = computed(() => !!cloud.value?.logged_in)
const form = ref({ name: '', room: '', hidden: false })
watch(
  () => props.device.id,
  () => (form.value = { name: props.device.name, room: props.device.room, hidden: props.device.hidden }),
  { immediate: true },
)

const showRoomPicker = ref(false)
const newRoom = ref('')
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
  const d = props.device
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
  showToast('已保存')
  emit('saved')
}
</script>

<template>
  <div class="settings">
    <van-cell-group class="rows" :border="false">
      <van-field v-model="form.name" label="名称" :placeholder="device.cloud_name" clearable />
      <van-cell title="房间" :value="form.room" is-link @click="showRoomPicker = true" />
      <van-cell v-if="device.kind !== 'switch'" title="在首页隐藏">
        <template #right-icon><van-switch v-model="form.hidden" size="22px" /></template>
      </van-cell>
    </van-cell-group>
    <van-cell-group class="rows" :border="false">
      <van-cell title="型号" :value="device.model" />
      <van-cell v-if="synced" title="米家名称" :value="`${device.cloud_name} · ${device.cloud_room}`" />
    </van-cell-group>
    <div v-if="synced" class="tip">这里修改只在本应用显示，不会改动米家。名称清空即恢复米家的名字。</div>
    <van-button block round type="primary" class="save" @click="save">保存</van-button>

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
.rows {
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.rows + .rows {
  margin-top: 12px;
}
.tip {
  font-size: 12px;
  color: var(--text-3);
  padding: 10px 6px 0;
  line-height: 1.6;
}
.save {
  margin-top: 20px;
}
</style>
