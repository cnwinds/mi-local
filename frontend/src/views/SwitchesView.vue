<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { showToast } from 'vant'
import { api, type Device } from '../api'
import { deviceList, devices, gatewayName, loadDevices, loadRules, onHubEvent, rooms, rules } from '../store'
import BindingEditor from '../components/BindingEditor.vue'
import { BatteryMedium, ChevronDown, ChevronRight, ChevronUp, Hand, Pencil, Plus, ToggleRight } from 'lucide-vue-next'
import DeviceIcon from '../components/DeviceIcon.vue'
import PageHeader from '../components/PageHeader.vue'
import { fullName, miHomeLabel } from '../naming'

const MORE_EVENTS: [string, string][] = [['double_click', '双击'], ['long_click_press', '长按']]
const ACTION_NAMES: Record<string, string> = { toggle: '切换', turn_on: '打开', turn_off: '关闭', open: '打开', close: '关闭', stop: '暂停', ring: '响', up: '升起', down: '降下' }

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
    <PageHeader title="开关" :subtitle="`${active.length} 个无线开关 · 联动全部在本地运行，断网也能用`" />
    <div class="note"><Hand :size="14" />按一下任意无线开关，它的卡片会自动出现在眼前</div>

    <div class="list">
      <div v-for="d in active" :id="`sw-${d.id}`" :key="d.id" class="sw card" :class="{ flash: flashing === d.id }">
        <div class="head" @click="rename(d)">
          <div class="sw-icon"><ToggleRight :size="20" /></div>
          <div class="head-text">
            <div class="name">{{ d.name }}</div>
            <div class="meta">
              {{ d.room }}
              <span v-if="d.state.battery !== undefined" class="battery" :class="{ low: d.state.battery < 20 }">
                <BatteryMedium :size="13" />{{ d.state.battery }}%
              </span>
            </div>
            <div v-if="miHomeLabel(d)" class="meta mi">{{ miHomeLabel(d) }}</div>
          </div>
          <Pencil :size="15" class="edit" />
        </div>
        <div class="control" @click="editBinding(d.id, 'click')">
          <div class="press-label">按一下</div>
          <template v-if="targets(d.id).length">
            <div class="chips">
              <span v-for="t in targets(d.id)" :key="t.id" class="chip" :class="{ lit: t.state.power }">
                <DeviceIcon :kind="t.kind" :model="t.model" :active="!!t.state.power" :size="24" />{{ fullName(t) }}
              </span>
            </div>
            <ChevronRight :size="18" class="arrow" />
          </template>
          <button v-else class="choose"><Plus :size="16" />选择要控制的设备</button>
        </div>
        <button class="more-toggle" @click="toggleMore(d.id)">
          <span>双击 / 长按{{ MORE_EVENTS.some(([e]) => binding(d.id, e)) ? ' · 已设置' : '' }}</span>
          <component :is="expanded.has(d.id) ? ChevronUp : ChevronDown" :size="16" />
        </button>
        <template v-if="expanded.has(d.id)">
          <div v-for="[event, label] in MORE_EVENTS" :key="event" class="row" @click="editBinding(d.id, event)">
            <span class="event">{{ label }}</span>
            <template v-if="binding(d.id, event)">
              <span class="target">{{ binding(d.id, event)!.text }}</span>
              <span class="verb">{{ binding(d.id, event)!.verb }}</span>
            </template>
            <span v-else class="target empty">未设置</span>
            <ChevronRight :size="16" class="arrow" />
          </div>
        </template>
      </div>
    </div>

    <van-empty v-if="!active.length" :description="`还没有接入「${gatewayName}」的开关，到「设备」页添加`" />

    <div v-if="pending.length" class="pending">
      <button class="section-label pending-head" @click="showPending = !showPending">
        <span>还没迁移到{{ gatewayName }} · {{ pending.length }}</span>
        <component :is="showPending ? ChevronUp : ChevronDown" :size="15" />
      </button>
      <template v-if="showPending">
        <div class="pending-tip">这些开关还接在多模网关上，由米家控制。重新配对到「{{ gatewayName }}」后才能在这里设置。</div>
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
        <div class="room-chips">
          <span v-for="r in rooms" :key="r" class="room-chip" :class="{ on: form.room === r }" @click="form.room = r">{{ r }}</span>
        </div>
        <div class="rename-tip">米家里叫「{{ renaming.cloud_name }}」。这里的名字只在本应用显示，清空则恢复米家的名字。</div>
        <div class="rename-actions"><van-button block round type="primary" @click="saveName">保存</van-button></div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.note {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-3);
  padding: 0 20px 14px;
}
.list {
  display: grid;
  gap: 12px;
  padding: 0 16px;
}
.sw {
  padding: 4px 16px;
  transition: box-shadow 0.3s, background 0.3s;
}
.flash {
  background: var(--accent-soft);
  box-shadow: 0 0 0 2px var(--accent), var(--shadow-2);
}
.head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  cursor: pointer;
}
.sw-icon {
  width: 40px;
  height: 40px;
  border-radius: 13px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-soft);
  color: var(--accent);
}
.head-text {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 16px;
  font-weight: 600;
}
.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-3);
}
.meta.mi {
  display: block;
}
.battery {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.battery.low {
  color: var(--danger);
}
.edit {
  color: var(--text-3);
  flex: none;
}
.control {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  margin-bottom: 4px;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  cursor: pointer;
}
.press-label {
  flex: none;
  font-size: 12px;
  color: var(--text-3);
  writing-mode: horizontal-tb;
}
.chips {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  background: var(--surface);
  border-radius: 10px;
  padding: 3px 10px 3px 3px;
}
.chip.lit {
  background: var(--warm-soft);
}
.choose {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 34px;
  border-radius: 10px;
  color: var(--accent);
  font-size: 14px;
  font-weight: 500;
  box-shadow: inset 0 0 0 1.5px var(--accent);
}
.arrow {
  color: var(--text-3);
  flex: none;
}
.more-toggle {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-3);
  padding: 10px 0;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
  font-size: 14px;
  border-top: 1px solid var(--line);
  cursor: pointer;
}
.event {
  color: var(--text-3);
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
  color: var(--text-3);
}
.verb {
  font-size: 12px;
  color: var(--accent-text);
  background: var(--accent-soft);
  border-radius: 6px;
  padding: 1px 6px;
}
.verb:empty {
  display: none;
}
.pending {
  margin: 8px 16px 16px;
}
.pending-head {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pending-tip {
  font-size: 12px;
  color: var(--text-3);
  padding: 0 4px 8px;
}
.pending-item {
  display: flex;
  justify-content: space-between;
  background: var(--surface);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--text-2);
  transition: box-shadow 0.3s;
}
.rename {
  padding: 20px 0 calc(24px + env(safe-area-inset-bottom));
}
.rename-title {
  text-align: center;
  font-weight: 600;
  font-size: 16px;
  margin-bottom: 16px;
}
.room-chips {
  padding: 16px 16px 0;
}
.rename-tip {
  font-size: 12px;
  color: var(--text-3);
  padding: 12px 32px 0;
}
.rename-actions {
  padding: 20px 16px 0;
}
@media (min-width: 900px) {
  .note {
    padding: 0 0 18px;
  }
  .list {
    padding: 0;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
    gap: 16px;
  }
  .pending {
    margin: 16px 0;
  }
}
@media (min-width: 1400px) {
  .list {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>

