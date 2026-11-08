<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { api, type Rule, type RuleAction } from '../api'
import { CONTROLLABLE, EVENT_NAMES, deviceList, devices, loadRules, onHubEvent } from '../store'

const props = defineProps<{ rule: Rule | null }>()
const emit = defineEmits<{ close: [] }>()

const show = computed({
  get: () => !!props.rule,
  set: (v) => !v && emit('close'),
})

const name = ref('')
const triggerDevice = ref('')
const triggerEvent = ref('click')
const actions = ref<RuleAction[]>([])

watch(
  () => props.rule,
  (r) => {
    if (!r) return
    name.value = r.name
    triggerDevice.value = r.trigger.device
    triggerEvent.value = r.trigger.event
    actions.value = r.actions.map((a) => ({ ...a }))
  },
)

const switches = computed(() => deviceList.value.filter((d) => d.kind === 'switch'))
const targets = computed(() =>
  deviceList.value
    .filter((d) => CONTROLLABLE.has(d.kind) && d.kind !== 'other' && !d.hidden)
    .sort((a, b) => a.room.localeCompare(b.room)),
)

const ACTIONS: Record<string, [string, string][]> = {
  light: [['toggle', '切换开关'], ['turn_on', '打开'], ['turn_off', '关闭']],
  plug: [['toggle', '切换开关'], ['turn_on', '打开'], ['turn_off', '关闭']],
  curtain: [['open', '打开'], ['close', '关闭'], ['stop', '暂停']],
}

// "Press the switch to identify it"
const listening = ref(false)
let unlisten: (() => void) | null = null
function listen() {
  listening.value = true
  unlisten?.()
  unlisten = onHubEvent((e) => {
    if (devices[e.device]?.kind !== 'switch') return
    triggerDevice.value = e.device
    if (e.event === 'click' || e.event === 'double_click' || e.event === 'long_click_press') triggerEvent.value = e.event
    stopListening()
    showToast(`已识别：${devices[e.device].name}`)
  })
}
function stopListening() {
  listening.value = false
  unlisten?.()
  unlisten = null
}
onUnmounted(stopListening)

const showTargetPicker = ref(false)
const selectedTargets = ref<string[]>([])
function openTargetPicker() {
  selectedTargets.value = actions.value.map((a) => a.device)
  showTargetPicker.value = true
}
function confirmTargets() {
  const existing = new Map(actions.value.map((a) => [a.device, a]))
  actions.value = selectedTargets.value.map(
    (id) => existing.get(id) ?? { device: id, action: devices[id].kind === 'curtain' ? 'open' : 'toggle' },
  )
  showTargetPicker.value = false
}

async function save() {
  if (!triggerDevice.value) return showToast('请选择开关')
  if (!actions.value.length) return showToast('请添加要控制的设备')
  const rule: Rule = {
    name: name.value || `${devices[triggerDevice.value]?.name} ${EVENT_NAMES[triggerEvent.value]}`,
    enabled: props.rule?.enabled ?? true,
    trigger: { type: 'device_event', device: triggerDevice.value, event: triggerEvent.value },
    actions: actions.value,
  }
  if (props.rule?.id) await api.updateRule(props.rule.id, rule)
  else await api.createRule(rule)
  await loadRules()
  showToast('已保存')
  emit('close')
}

async function remove() {
  if (!props.rule?.id) return
  await showConfirmDialog({ title: '删除自动化', message: `确定删除「${props.rule.name}」？` })
  await api.deleteRule(props.rule.id)
  await loadRules()
  emit('close')
}
</script>

<template>
  <van-popup v-model:show="show" position="bottom" round :style="{ height: '92%' }" @closed="stopListening">
    <div class="editor">
      <div class="bar">
        <span class="cancel" @click="emit('close')">取消</span>
        <span class="heading">{{ rule?.id ? '编辑自动化' : '新建自动化' }}</span>
        <span class="save" @click="save">保存</span>
      </div>

      <div class="scroll">
        <van-cell-group inset title="名称">
          <van-field v-model="name" placeholder="留空则自动命名" />
        </van-cell-group>

        <van-cell-group inset title="如果">
          <van-cell title="开关" :value="devices[triggerDevice]?.name ?? '请选择'" />
          <div class="listen">
            <van-button v-if="!listening" size="small" round type="primary" plain icon="aim" @click="listen">按一下开关来识别</van-button>
            <van-button v-else size="small" round type="primary" loading loading-text="请按下要使用的开关…" @click="stopListening" />
          </div>
          <van-radio-group v-model="triggerDevice">
            <van-cell v-for="d in switches" :key="d.id" :title="d.name" :label="d.state.online ? d.room : '离线 · 尚未迁移到网关 2'" clickable @click="triggerDevice = d.id">
              <template #right-icon><van-radio :name="d.id" /></template>
            </van-cell>
          </van-radio-group>
          <van-cell title="按键方式">
            <template #value>
              <van-radio-group v-model="triggerEvent" direction="horizontal" class="events">
                <van-radio name="click">单击</van-radio>
                <van-radio name="double_click">双击</van-radio>
                <van-radio name="long_click_press">长按</van-radio>
              </van-radio-group>
            </template>
          </van-cell>
        </van-cell-group>

        <van-cell-group inset title="就执行">
          <van-cell v-for="(a, i) in actions" :key="a.device" :title="devices[a.device]?.name" :label="devices[a.device]?.room">
            <template #value>
              <select v-model="a.action" class="action-select">
                <option v-for="[value, label] in ACTIONS[devices[a.device]?.kind] ?? []" :key="value" :value="value">{{ label }}</option>
              </select>
              <van-icon name="cross" class="remove" @click="actions.splice(i, 1)" />
            </template>
          </van-cell>
          <van-cell title="添加设备" icon="plus" is-link @click="openTargetPicker" />
        </van-cell-group>
        <div class="hint" v-if="actions.filter((a) => a.action === 'toggle').length > 1">
          多个设备都选「切换开关」时，只要有一个亮着就全部关闭，否则全部打开。
        </div>

        <div class="danger" v-if="rule?.id">
          <van-button block round type="danger" plain @click="remove">删除自动化</van-button>
        </div>
      </div>
    </div>

    <van-popup v-model:show="showTargetPicker" position="bottom" round :style="{ height: '75%' }">
      <div class="bar">
        <span class="cancel" @click="showTargetPicker = false">取消</span>
        <span class="heading">选择设备</span>
        <span class="save" @click="confirmTargets">确定</span>
      </div>
      <div class="scroll">
        <van-checkbox-group v-model="selectedTargets">
          <van-cell-group inset>
            <van-cell v-for="d in targets" :key="d.id" :title="d.name" :label="d.room" clickable
              @click="selectedTargets.includes(d.id) ? selectedTargets.splice(selectedTargets.indexOf(d.id), 1) : selectedTargets.push(d.id)">
              <template #right-icon><van-checkbox :name="d.id" @click.stop /></template>
            </van-cell>
          </van-cell-group>
        </van-checkbox-group>
      </div>
    </van-popup>
  </van-popup>
</template>

<style scoped>
.editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f6f7f9;
}
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #fff;
}
.heading {
  font-weight: 600;
}
.cancel {
  color: #646a73;
}
.save {
  color: #3e7bfa;
  font-weight: 600;
}
.scroll {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 32px;
}
.listen {
  padding: 8px 16px;
}
.events {
  justify-content: flex-end;
}
.action-select {
  border: none;
  background: #f0f1f4;
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 14px;
  color: #1f2329;
}
.remove {
  margin-left: 10px;
  color: #c4c7cc;
  vertical-align: middle;
}
.hint {
  font-size: 12px;
  color: #8f959e;
  padding: 8px 32px;
}
.danger {
  padding: 24px 16px;
}
</style>
