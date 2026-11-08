<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { showToast } from 'vant'
import { api, type Device } from '../api'
import { deviceList, devices, loadDevices, loadRules, onHubEvent, rooms, rules } from '../store'
import BindingEditor from '../components/BindingEditor.vue'
import DeviceIcon from '../components/DeviceIcon.vue'
import { fullName, miHomeLabel } from '../naming'

const MORE_EVENTS: [string, string][] = [['double_click', '双击'], ['long_click_press', '长按']]
const ACTION_NAMES: Record<string, string> = { toggle: '切换', turn_on: '打开', turn_off: '关闭', open: '打开', close: '关闭', stop: '暂停', ring: '响' }

const switches = computed(() => deviceList.value.filter((d) => d.kind === 'switch'))
const roomIndex = (room: string) => (rooms.value.indexOf(room) + 1 || 999)
const byRoom = (a: Device, b: Device) => roomIndex(a.room) - roomIndex(b.room) || a.name.localeCompare(b.name)
const active = computed(() => switches.value.filter((d) => d.state.online).sort(byRoom))
const pending = computed(() => switches.value.filter((d) => !d.state.online).sort(byRoom))
const showPending = ref(false)

function binding(id: string, event: string) {
  const rule = rules.value.find((r) => r.trigger.device === id && r.trigger.event === event)
  if (!rule) return null
  const names = rule.actions.map((a) => (devices[a.device] ? fullName(devices[a.device]) : '?'))
  const kinds = new Set(rule.actions.map((a) => a.action))
  const verb = kinds.size === 1 ? ACTION_NAMES[[...kinds][0]] ?? '' : ''
  return { text: names.join('、'), verb }
}

function targets(id: string) {
  const rule = rules.value.find((r) => r.trigger.device === id && r.trigger.event === 'click')
  return (rule?.actions ?? []).map((a) => devices[a.device]).filter(Boolean)
}
const expanded = ref<Set<string>>(new Set())
function toggleMore(id: string) {
  if (expanded.value.has(id)) expanded.value.delete(id)
  else expanded.value.add(id)
}

const editSwitch = ref<string | null>(null)
const editEvent = ref('click')
function editBinding(id: string, event: string) {
  editSwitch.value = id
  editEvent.value = event
}

// Pressing a physical switch brings its card into view.
const flashing = ref<string | null>(null)
let flashTimer: number | undefined
const stop = onHubEvent(async (e) => {
  if (devices[e.device]?.kind !== 'switch') return
  if (!devices[e.device].state.online) showPending.value = true
  flashing.value = e.device
  await nextTick()
  document.getElementById(`sw-${e.device}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  clearTimeout(flashTimer)
  flashTimer = window.setTimeout(() => (flashing.value = null), 2500)
})
onUnmounted(() => {
  stop()
  clearTimeout(flashTimer)
})
onMounted(loadRules)

// Local rename: Mi Home cannot be written back to.
const renaming = ref<Device | null>(null)
const form = ref({ name: '', room: '' })
function rename(d: Device) {
  renaming.value = d
  form.value = { name: d.name, room: d.room }
}
async function saveName() {
  const d = renaming.value
  if (!d) return
  const name = form.value.name.trim()
  await api.patchDevice(d.id, {
    local_name: name && name !== d.cloud_name ? name : '',
    local_room: form.value.room !== d.cloud_room ? form.value.room : '',
    name_auto: false,
  })
  await loadDevices()
  renaming.value = null
  showToast('已保存')
}
</script>

<template>
  <div class="switches">
    <header class="hero"><div class="title">开关</div></header>
    <div class="note">按一下任意无线开关，它的卡片会自动出现在眼前。所有联动都在本地运行，断网也能用。</div>

    <div v-for="d in active" :id="`sw-${d.id}`" :key="d.id" class="card" :class="{ flash: flashing === d.id }">
      <div class="head" @click="rename(d)">
        <div class="name">{{ d.name }}</div>
        <div class="meta">{{ d.room }}<template v-if="d.state.battery !== undefined"> · 电量 {{ d.state.battery }}%</template></div>
        <div class="meta" v-if="miHomeLabel(d)">{{ miHomeLabel(d) }}</div>
        <van-icon name="edit" class="edit" />
      </div>
      <div class="control" @click="editBinding(d.id, 'click')">
        <template v-if="targets(d.id).length">
          <div class="chips">
            <span v-for="t in targets(d.id)" :key="t.id" class="chip" :class="{ lit: t.state.power }">
              <DeviceIcon :kind="t.kind" :active="!!t.state.power" class="chip-icon" />{{ fullName(t) }}
            </span>
          </div>
          <span class="change">更换</span>
        </template>
        <van-button v-else block round type="primary" plain icon="plus" size="small">选择要控制的灯</van-button>
      </div>
      <div class="more-toggle" @click="toggleMore(d.id)">
        <span>双击 / 长按{{ MORE_EVENTS.some(([e]) => binding(d.id, e)) ? '（已设置）' : '' }}</span>
        <van-icon :name="expanded.has(d.id) ? 'arrow-up' : 'arrow-down'" />
      </div>
      <template v-if="expanded.has(d.id)">
        <div v-for="[event, label] in MORE_EVENTS" :key="event" class="row" @click="editBinding(d.id, event)">
          <span class="event">{{ label }}</span>
          <template v-if="binding(d.id, event)">
            <span class="target">{{ binding(d.id, event)!.text }}</span>
            <span class="verb">{{ binding(d.id, event)!.verb }}</span>
          </template>
          <span v-else class="target empty">未设置</span>
          <van-icon name="arrow" class="arrow" />
        </div>
      </template>
    </div>

    <van-empty v-if="!active.length" description="还没有接入网关 2 的开关，到「设备」页添加" />

    <div v-if="pending.length" class="pending">
      <div class="pending-head" @click="showPending = !showPending">
        <span>还没迁移到网关 2（{{ pending.length }}）</span>
        <van-icon :name="showPending ? 'arrow-up' : 'arrow-down'" />
      </div>
      <template v-if="showPending">
        <div class="pending-tip">这些开关还接在多模网关上，由米家控制。迁移到网关 2 后才能在这里设置。</div>
        <div v-for="d in pending" :id="`sw-${d.id}`" :key="d.id" class="pending-item" :class="{ flash: flashing === d.id }">
          <span>{{ d.name }}</span><span class="meta">{{ d.room }}</span>
        </div>
      </template>
    </div>

    <BindingEditor :switch-id="editSwitch" :event="editEvent" :simple="editEvent === 'click'" @close="editSwitch = null" />

    <van-popup :show="!!renaming" position="bottom" round @update:show="(v: boolean) => !v && (renaming = null)">
      <div class="rename" v-if="renaming">
        <div class="rename-title">开关名称</div>
        <van-cell-group inset>
          <van-field v-model="form.name" label="名称" :placeholder="renaming.cloud_name" clearable />
        </van-cell-group>
        <div class="rooms">
          <span v-for="r in rooms" :key="r" class="room" :class="{ on: form.room === r }" @click="form.room = r">{{ r }}</span>
        </div>
        <div class="rename-tip">米家里叫「{{ renaming.cloud_name }}」。这里的名字只在本应用显示，清空则恢复米家的名字。</div>
        <div class="rename-actions"><van-button block round type="primary" @click="saveName">保存</van-button></div>
      </div>
    </van-popup>
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
.note {
  font-size: 12px;
  color: #8f959e;
  padding: 0 20px 12px;
}
.card {
  margin: 0 16px 12px;
  background: #fff;
  border-radius: 16px;
  padding: 6px 16px;
  transition: box-shadow 0.3s, background 0.3s;
}
.flash {
  background: #eaf2ff;
  box-shadow: 0 0 0 2px #3e7bfa;
}
.head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 0 8px;
  border-bottom: 1px solid #f0f1f4;
}
.name {
  font-size: 16px;
  font-weight: 600;
}
.meta {
  font-size: 12px;
  color: #8f959e;
}
.edit {
  margin-left: auto;
  color: #c4c7cc;
}
.control {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
}
.chips {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  background: #f6f7f9;
  border-radius: 10px;
  padding: 4px 10px 4px 4px;
}
.chip.lit {
  background: #fff6e5;
}
.chip-icon {
  transform: scale(0.6);
  margin: -8px -6px;
}
.change {
  font-size: 13px;
  color: #3e7bfa;
  flex: none;
}
.more-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #8f959e;
  padding: 8px 0 10px;
  border-top: 1px solid #f6f7f9;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
  font-size: 14px;
}
.row + .row {
  border-top: 1px solid #f6f7f9;
}
.event {
  color: #8f959e;
  width: 32px;
  flex: none;
}
.target {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.target.empty {
  color: #c4c7cc;
}
.verb {
  font-size: 12px;
  color: #3e7bfa;
  background: #e8f0ff;
  border-radius: 6px;
  padding: 1px 6px;
}
.verb:empty {
  display: none;
}
.arrow {
  color: #c4c7cc;
}
.pending {
  margin: 4px 16px 16px;
}
.pending-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #646a73;
  padding: 8px 4px;
}
.pending-tip {
  font-size: 12px;
  color: #8f959e;
  padding: 0 4px 8px;
}
.pending-item {
  display: flex;
  justify-content: space-between;
  background: #fff;
  border-radius: 12px;
  padding: 12px 16px;
  margin-bottom: 8px;
  font-size: 14px;
  color: #8f959e;
  transition: box-shadow 0.3s;
}
.rename {
  padding: 20px 0 calc(24px + env(safe-area-inset-bottom));
}
.rename-title {
  text-align: center;
  font-weight: 600;
  margin-bottom: 16px;
}
.rooms {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 16px 16px 0;
}
.room {
  font-size: 13px;
  padding: 6px 12px;
  border-radius: 16px;
  background: #f0f1f4;
  color: #646a73;
}
.room.on {
  background: #3e7bfa;
  color: #fff;
}
.rename-tip {
  font-size: 12px;
  color: #8f959e;
  padding: 12px 32px 0;
}
.rename-actions {
  padding: 20px 16px 0;
}
</style>
