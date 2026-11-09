<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import type { Device } from '../api'
import { deviceList, devices, gatewayName, loadRules, onHubEvent, rooms, rules } from '../store'
import BindingEditor from '../components/BindingEditor.vue'
import DeviceSheet from '../components/DeviceSheet.vue'
import { BatteryLow, BatteryMedium, ChevronDown, ChevronRight, ChevronUp, Hand, Plus, Settings2 } from 'lucide-vue-next'
import DeviceIcon from '../components/DeviceIcon.vue'
import PageHeader from '../components/PageHeader.vue'
import { fullName } from '../naming'

const GESTURES: [string, string][] = [['click', '单击'], ['double_click', '双击'], ['long_click_press', '长按']]
const ACTION_NAMES: Record<string, string> = { toggle: '切换', turn_on: '打开', turn_off: '关闭', open: '打开', close: '关闭', stop: '暂停', ring: '响', up: '升起', down: '降下' }

const switches = computed(() => deviceList.value.filter((d) => d.kind === 'switch'))
const roomIndex = (room: string) => (rooms.value.indexOf(room) + 1 || 999)
const byRoom = (a: Device, b: Device) => roomIndex(a.room) - roomIndex(b.room) || a.name.localeCompare(b.name)
const active = computed(() => switches.value.filter((d) => d.state.online).sort(byRoom))
const pending = computed(() => switches.value.filter((d) => !d.state.online).sort(byRoom))
const showPending = ref(false)

const groups = computed(() => {
  const out: { room: string; items: Device[] }[] = []
  for (const d of active.value) {
    const g = out.find((x) => x.room === d.room) ?? out[out.push({ room: d.room, items: [] }) - 1]
    g.items.push(d)
  }
  return out
})

/** The room is already the section title, so "儿童房吸顶灯开关" reads as "吸顶灯开关" inside it. */
const shortName = (d: Device) => (d.name.startsWith(d.room) && d.name.length > d.room.length ? d.name.slice(d.room.length) : d.name)

function binding(id: string, event: string) {
  const rule = rules.value.find((r) => r.trigger.device === id && r.trigger.event === event)
  if (!rule?.actions.length) return null
  const targets = rule.actions.map((a) => devices[a.device]).filter(Boolean)
  const kinds = new Set(rule.actions.map((a) => a.action))
  const verb = kinds.size === 1 ? ACTION_NAMES[[...kinds][0]] ?? '' : ''
  return { targets, verb }
}

const editSwitch = ref<string | null>(null)
const editEvent = ref('click')
function editBinding(id: string, event: string) {
  editSwitch.value = id
  editEvent.value = event
}
const settingsId = ref<string | null>(null)

// Pressing a physical switch brings its card into view and lights its key.
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
</script>

<template>
  <div class="switches">
    <PageHeader title="开关" :subtitle="`${active.length} 个无线开关 · 联动全部在本地运行，断网也能用`" />
    <div class="note"><Hand :size="14" />按一下任意无线开关，它的卡片会亮起并滚到眼前</div>

    <section v-for="g in groups" :key="g.room" class="room">
      <div class="section-label">{{ g.room }} · {{ g.items.length }}</div>
      <div class="list">
        <div v-for="d in g.items" :id="`sw-${d.id}`" :key="d.id" class="sw card" :class="{ flash: flashing === d.id }">
          <div class="head">
            <div class="key"><span /></div>
            <div class="head-text">
              <div class="name">{{ shortName(d) }}</div>
              <div class="meta">
                <span v-if="d.state.battery !== undefined" class="battery" :class="{ low: d.state.battery < 20 }">
                  <component :is="d.state.battery < 20 ? BatteryLow : BatteryMedium" :size="14" />{{ d.state.battery }}%
                </span>
                <span v-if="flashing === d.id" class="live">刚刚按下</span>
              </div>
            </div>
            <button class="settings" title="名称和房间" @click="settingsId = d.id"><Settings2 :size="17" /></button>
          </div>

          <div class="gestures">
            <button v-for="[event, label] in GESTURES" :key="event" class="gesture" :class="{ primary: event === 'click' }"
              @click="editBinding(d.id, event)">
              <span class="g-label">{{ label }}</span>
              <template v-if="binding(d.id, event)">
                <span class="targets">
                  <span v-for="t in binding(d.id, event)!.targets" :key="t.id" class="target" :class="{ lit: t.state.power }">
                    <DeviceIcon :kind="t.kind" :model="t.model" :active="!!t.state.power" :size="22" />{{ fullName(t) }}
                  </span>
                </span>
                <span v-if="event !== 'click' && binding(d.id, event)!.verb" class="verb">{{ binding(d.id, event)!.verb }}</span>
              </template>
              <span v-else class="empty"><Plus v-if="event === 'click'" :size="14" />{{ event === 'click' ? '选择要控制的设备' : '未设置' }}</span>
              <ChevronRight :size="16" class="arrow" />
            </button>
          </div>
        </div>
      </div>
    </section>

    <van-empty v-if="!active.length" :description="`还没有接入「${gatewayName}」的开关，到「设备」页添加`" />

    <div v-if="pending.length" class="pending">
      <button class="section-label pending-head" @click="showPending = !showPending">
        <span>还没迁移到{{ gatewayName }} · {{ pending.length }}</span>
        <component :is="showPending ? ChevronUp : ChevronDown" :size="15" />
      </button>
      <template v-if="showPending">
        <div class="pending-tip">这些开关还接在多模网关上，由米家控制。重新配对到「{{ gatewayName }}」后才能在这里设置。</div>
        <div class="pending-list card">
          <div v-for="d in pending" :id="`sw-${d.id}`" :key="d.id" class="pending-item" :class="{ flash: flashing === d.id }">
            <span>{{ d.name }}</span><span class="meta">{{ d.room }}</span>
          </div>
        </div>
      </template>
    </div>

    <BindingEditor :switch-id="editSwitch" :event="editEvent" :simple="editEvent === 'click'" @close="editSwitch = null" />
    <DeviceSheet :device-id="settingsId" @close="settingsId = null" />
  </div>
</template>

<style scoped>
.note {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-3);
  padding: 0 20px 6px;
}
.room {
  padding: 0 16px;
}
.list {
  display: grid;
  gap: 12px;
}
.sw {
  padding: 14px;
  transition: box-shadow 0.3s, background 0.3s;
}
.flash {
  box-shadow: 0 0 0 2px var(--accent), var(--shadow-2);
}
.head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 2px 12px;
}
/* A drawing of the physical wireless switch; it lights up when pressed. */
.key {
  flex: none;
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: linear-gradient(160deg, var(--surface) 0%, var(--surface-2) 100%);
  box-shadow: inset 0 0 0 1px var(--line), 0 3px 8px rgba(17, 24, 39, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.25s;
}
.key span {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--surface-2);
  box-shadow: inset 0 1px 2px rgba(17, 24, 39, 0.12);
  transition: all 0.25s;
}
.flash .key {
  background: var(--accent);
  transform: scale(0.94);
  box-shadow: 0 6px 18px rgba(75, 103, 245, 0.4);
}
.flash .key span {
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 0 0 10px rgba(255, 255, 255, 0.8);
}
.head-text {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
  font-size: 12px;
  color: var(--text-3);
}
.battery {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.battery.low {
  color: var(--danger);
}
.live {
  color: var(--accent-text);
  font-weight: 600;
}
.settings {
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
  background: var(--surface-2);
}
.gestures {
  border-radius: var(--radius);
  background: var(--surface-2);
  overflow: hidden;
}
.gesture {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 6px 12px;
  text-align: left;
  font-size: 13px;
  transition: background 0.15s;
}
.gesture + .gesture {
  border-top: 1px solid var(--line);
}
.gesture:active {
  background: var(--surface-3);
}
.gesture.primary {
  min-height: 52px;
}
.g-label {
  flex: none;
  width: 30px;
  font-size: 12px;
  color: var(--text-3);
}
.primary .g-label {
  color: var(--text-2);
  font-weight: 600;
}
.targets {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.target {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  padding: 3px 10px 3px 3px;
  border-radius: 10px;
  background: var(--surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gesture:not(.primary) .target {
  background: transparent;
  padding: 0;
}
.gesture:not(.primary) .target :deep(.device-icon) {
  display: none;
}
.target.lit {
  background: var(--warm-soft);
}
.gesture:not(.primary) .target.lit {
  background: transparent;
}
.empty {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-3);
}
.primary .empty {
  color: var(--accent-text);
  font-weight: 500;
}
.verb {
  flex: none;
  font-size: 11px;
  color: var(--accent-text);
  background: var(--accent-soft);
  border-radius: 6px;
  padding: 1px 6px;
}
.arrow {
  flex: none;
  color: var(--text-3);
}
.pending {
  margin: 16px;
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
.pending-list {
  padding: 2px 16px;
}
.pending-item {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  font-size: 14px;
  color: var(--text-2);
  transition: color 0.3s;
}
.pending-item + .pending-item {
  border-top: 1px solid var(--line);
}
.pending-item.flash {
  box-shadow: none;
  color: var(--accent-text);
  font-weight: 600;
}
@media (min-width: 640px) {
  .list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }
}
@media (min-width: 900px) {
  .note {
    padding: 0 0 6px;
  }
  .room {
    padding: 0;
  }
  .list {
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
