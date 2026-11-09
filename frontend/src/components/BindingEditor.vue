<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'
import { api, type Device, type Rule, type RuleAction } from '../api'
import { EVENT_NAMES, deviceList, devices, loadDevices, loadRules, rooms, rules } from '../store'
import { suggestSwitchName } from '../naming'

const props = defineProps<{ switchId: string | null; event: string }>()
const emit = defineEmits<{ close: [] }>()

const show = computed({
  get: () => !!props.switchId,
  set: (v) => !v && emit('close'),
})

const ACTIONS: Record<string, [string, string][]> = {
  light: [['toggle', '切换'], ['turn_on', '打开'], ['turn_off', '关闭']],
  plug: [['toggle', '切换'], ['turn_on', '打开'], ['turn_off', '关闭']],
  curtain: [['open', '打开'], ['close', '关闭'], ['stop', '暂停']],
  doorbell: [['ring', '响铃']],
  ac: [['toggle', '切换'], ['turn_on', '打开'], ['turn_off', '关闭']],
  bath_heater: [['toggle', '切换'], ['turn_on', '开照明'], ['turn_off', '全关']],
  airer: [['up', '升起'], ['down', '降下'], ['stop', '暂停']],
}
const DEFAULT_ACTION: Record<string, string> = { curtain: 'open', doorbell: 'ring', airer: 'up' }
const defaultAction = (d: Device) => DEFAULT_ACTION[d.kind] ?? 'toggle'

const sw = computed(() => (props.switchId ? devices[props.switchId] : undefined))
const existing = computed<Rule | undefined>(() =>
  rules.value.find((r) => r.trigger.device === props.switchId && r.trigger.event === props.event),
)
const picked = ref<Record<string, string>>({})

watch(
  () => [props.switchId, props.event],
  () => {
    picked.value = Object.fromEntries((existing.value?.actions ?? []).map((a) => [a.device, a.action]))
  },
  { immediate: true },
)

// The switch's own room first, then rooms of devices already picked, then the rest in Mi Home order.
const groups = computed(() => {
  const kinds = ['light', 'plug', 'curtain', 'ac', 'bath_heater', 'airer', 'doorbell']
  const candidates = deviceList.value.filter((d) => kinds.includes(d.kind) && !d.hidden)
  const first = new Set([sw.value?.room, ...Object.keys(picked.value).map((id) => devices[id]?.room)].filter(Boolean))
  const order = [...first, ...rooms.value.filter((r) => !first.has(r))]
  for (const d of candidates) if (!order.includes(d.room)) order.push(d.room)
  return order
    .map((room) => ({ room, items: candidates.filter((d) => d.room === room) }))
    .filter((g) => g.items.length)
})

function toggle(d: Device) {
  if (picked.value[d.id]) delete picked.value[d.id]
  else picked.value[d.id] = defaultAction(d)
}

const pickedCount = computed(() => Object.keys(picked.value).length)
const multiToggle = computed(() => Object.values(picked.value).filter((a) => a === 'toggle').length > 1)

async function save() {
  if (!sw.value) return
  const actions: RuleAction[] = Object.entries(picked.value).map(([device, action]) => ({ device, action }))
  const id = existing.value?.id
  if (!actions.length) {
    if (id) await api.deleteRule(id)
  } else {
    let name = sw.value.name
    if (props.event === 'click' && (sw.value.name_auto || sw.value.name === sw.value.cloud_name)) {
      const suggestion = suggestSwitchName(actions.map((a) => devices[a.device]))
      if (suggestion) {
        name = suggestion.name
        await api.patchDevice(sw.value.id, {
          local_name: suggestion.name,
          ...(suggestion.room ? { local_room: suggestion.room } : {}),
          name_auto: true,
        })
      }
    }
    const rule: Rule = {
      name: `${name} ${EVENT_NAMES[props.event]}`,
      enabled: existing.value?.enabled ?? true,
      trigger: { type: 'device_event', device: sw.value.id, event: props.event },
      actions,
    }
    if (id) await api.updateRule(id, rule)
    else await api.createRule(rule)
  }
  await Promise.all([loadRules(), loadDevices()])
  showToast(actions.length ? '已保存' : '已清除')
  emit('close')
}
</script>

<template>
  <van-popup v-model:show="show" position="bottom" round :style="{ height: '88%' }">
    <div class="editor" v-if="sw">
      <div class="bar">
        <span class="cancel" @click="emit('close')">取消</span>
        <span class="heading">{{ `${EVENT_NAMES[event]}「${sw.name}」` }}</span>
        <span class="save" @click="save">保存</span>
      </div>
      <div class="sub">{{ pickedCount ? `已选 ${pickedCount} 个设备` : '选择要控制的设备，不选则清除这个按法' }}</div>

      <div class="scroll">
        <van-cell-group v-for="g in groups" :key="g.room" inset :title="g.room">
          <van-cell v-for="d in g.items" :key="d.id" :title="d.name" clickable center @click="toggle(d)">
            <template #icon>
              <van-checkbox :model-value="!!picked[d.id]" class="check" @click.stop="toggle(d)" />
            </template>
            <template #value>
              <span v-if="d.kind === 'doorbell'" class="try" @click.stop="api.command(d.id, 'ring')">试听</span>
              <select v-else-if="picked[d.id]" v-model="picked[d.id]" class="action-select" @click.stop>
                <option v-for="[value, label] in ACTIONS[d.kind] ?? []" :key="value" :value="value">{{ label }}</option>
              </select>
              <span v-else-if="!d.state.online" class="offline">离线</span>
              <span v-else-if="d.kind === 'light' && d.state.power" class="on">亮着</span>
            </template>
          </van-cell>
        </van-cell-group>
        <div class="hint" v-if="multiToggle">多个设备都选「切换」时：只要有一个亮着就全部关闭，否则全部打开。</div>
        <div class="hint" v-if="event === 'click' && (sw.name_auto || sw.name === sw.cloud_name)">
          保存后开关会按它控制的设备自动命名，例如「卧室筒灯开关」。
        </div>
      </div>
    </div>
  </van-popup>
</template>

<style scoped>
.editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 8px;
  background: var(--surface);
}
.heading {
  font-weight: 600;
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cancel {
  color: var(--text-2);
}
.save {
  color: var(--accent);
  font-weight: 600;
}
.sub {
  background: var(--surface);
  text-align: center;
  font-size: 12px;
  color: var(--text-3);
  padding-bottom: 12px;
}
.scroll {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 32px;
}
.check {
  margin-right: 12px;
}
.action-select {
  border: none;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 14px;
}
.try {
  font-size: 13px;
  color: var(--accent);
}
.offline {
  font-size: 12px;
  color: var(--text-3);
}
.on {
  font-size: 12px;
  color: var(--warm);
}
.hint {
  font-size: 12px;
  color: var(--text-3);
  padding: 8px 32px;
}
</style>
