<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { api, type Device, type RuleAction, type Scene } from '../api'
import { deviceList, devices, loadScenes } from '../store'
import { roomDevices } from '../rooms'

// scene: null = closed, {} without id = new scene for `room`.
const props = defineProps<{ room: string; scene: Scene | null }>()
const emit = defineEmits<{ close: [] }>()

const show = computed({ get: () => !!props.scene, set: (v) => !v && emit('close') })

const ICONS = ['⭐', '🌙', '☀️', '🛏️', '🎬', '🍽️', '📖', '🏠', '🚪', '❄️', '🔥', '🛁']

interface Choice {
  key: string
  label: string
  value?: { min: number; max: number; default: number; unit: string }
  actions: (value?: number) => Omit<RuleAction, 'device'>[]
}

const CHOICES: Record<string, Choice[]> = {
  light: [
    { key: 'on', label: '打开', actions: () => [{ action: 'turn_on' }] },
    { key: 'off', label: '关闭', actions: () => [{ action: 'turn_off' }] },
    {
      key: 'dim', label: '亮度', value: { min: 1, max: 100, default: 30, unit: '%' },
      actions: (v) => [{ action: 'set_brightness', value: v }],
    },
  ],
  plug: [
    { key: 'on', label: '打开', actions: () => [{ action: 'turn_on' }] },
    { key: 'off', label: '关闭', actions: () => [{ action: 'turn_off' }] },
  ],
  curtain: [
    { key: 'open', label: '打开', actions: () => [{ action: 'open' }] },
    { key: 'close', label: '关闭', actions: () => [{ action: 'close' }] },
  ],
  ac: [
    { key: 'off', label: '关闭', actions: () => [{ action: 'turn_off' }] },
    {
      key: 'cool', label: '制冷', value: { min: 16, max: 30, default: 26, unit: '°' },
      actions: (v) => [{ action: 'set_mode', value: 'cool' }, { action: 'set_temp', value: v }, { action: 'turn_on' }],
    },
    {
      key: 'heat', label: '制热', value: { min: 16, max: 30, default: 24, unit: '°' },
      actions: (v) => [{ action: 'set_mode', value: 'heat' }, { action: 'set_temp', value: v }, { action: 'turn_on' }],
    },
  ],
  bath_heater: [
    { key: 'off', label: '全关', actions: () => [{ action: 'turn_off' }] },
    { key: 'light', label: '开照明', actions: () => [{ action: 'set_light', value: true }] },
    { key: 'heat', label: '开暖风', actions: () => [{ action: 'set_heating', value: true }] },
  ],
  airer: [
    { key: 'up', label: '升起', actions: () => [{ action: 'up' }] },
    { key: 'down', label: '降下', actions: () => [{ action: 'down' }] },
  ],
  doorbell: [{ key: 'ring', label: '响铃', actions: () => [{ action: 'ring' }] }],
}

const name = ref('')
const icon = ref(ICONS[0])
const picked = ref<Record<string, { key: string; value?: number }>>({})
const showAll = ref(false)

// Numbers are the user's setting, so a choice is recognised by its actions with numbers masked.
const shape = (list: Omit<RuleAction, 'device'>[]) =>
  list.map((a) => `${a.action}:${typeof a.value === 'number' ? '#' : String(a.value ?? '')}`).join()

/** Recognise which choice produced each device's saved actions. */
function parse(actions: RuleAction[]) {
  const byDevice: Record<string, RuleAction[]> = {}
  for (const a of actions) (byDevice[a.device] ??= []).push(a)
  const result: Record<string, { key: string; value?: number }> = {}
  for (const [id, list] of Object.entries(byDevice)) {
    const choice = (CHOICES[devices[id]?.kind] ?? []).find((c) => shape(c.actions(0)) === shape(list))
    const value = list.find((a) => typeof a.value === 'number')?.value as number | undefined
    if (choice) result[id] = { key: choice.key, value }
  }
  return result
}

watch(
  () => props.scene,
  (scene) => {
    if (!scene) return
    name.value = scene.name
    icon.value = scene.icon || ICONS[0]
    picked.value = parse(scene.actions)
    showAll.value = scene.actions.some((a) => devices[a.device] && devices[a.device].room !== props.room)
  },
  { immediate: true },
)

const groups = computed(() => {
  const inRoom = roomDevices(props.room).filter((d) => CHOICES[d.kind])
  const result = [{ room: props.room, items: inRoom }]
  if (showAll.value) {
    const others = deviceList.value.filter((d) => d.room !== props.room && CHOICES[d.kind] && !d.hidden)
    for (const room of [...new Set(others.map((d) => d.room))]) result.push({ room, items: others.filter((d) => d.room === room) })
  }
  return result.filter((g) => g.items.length)
})

function choose(d: Device, key: string) {
  if (picked.value[d.id]?.key === key) {
    delete picked.value[d.id]
    return
  }
  const choice = CHOICES[d.kind].find((c) => c.key === key)!
  picked.value[d.id] = { key, value: choice.value?.default }
}

const choiceOf = (d: Device) => CHOICES[d.kind].find((c) => c.key === picked.value[d.id]?.key)

async function save() {
  const actions: RuleAction[] = []
  for (const [id, p] of Object.entries(picked.value)) {
    const choice = CHOICES[devices[id]?.kind]?.find((c) => c.key === p.key)
    if (choice) actions.push(...choice.actions(p.value).map((a) => ({ device: id, ...a })))
  }
  if (!name.value.trim()) return showToast('起个名字，比如「睡觉」')
  if (!actions.length) return showToast('至少选一个设备')
  const scene: Scene = { room: props.room, name: name.value.trim(), icon: icon.value, actions }
  if (props.scene?.id) await api.updateScene(props.scene.id, scene)
  else await api.createScene(scene)
  await loadScenes()
  showToast('已保存')
  emit('close')
}

async function remove() {
  if (!props.scene?.id) return
  await showConfirmDialog({ title: `删除「${props.scene.name}」？` })
  await api.deleteScene(props.scene.id)
  await loadScenes()
  emit('close')
}
</script>

<template>
  <van-popup v-model:show="show" position="bottom" round :style="{ height: '88%' }">
    <div class="editor">
      <div class="bar">
        <span class="cancel" @click="emit('close')">取消</span>
        <span class="heading">{{ scene?.id ? '编辑快捷操作' : '新建快捷操作' }}</span>
        <span class="save" @click="save">保存</span>
      </div>
      <div class="scroll">
        <van-cell-group inset>
          <van-field v-model="name" label="名称" placeholder="比如：睡觉、看电影" maxlength="12" />
        </van-cell-group>
        <div class="icons">
          <span v-for="i in ICONS" :key="i" class="icon" :class="{ selected: icon === i }" @click="icon = i">{{ i }}</span>
        </div>

        <div v-for="g in groups" :key="g.room" class="group">
          <div class="group-title">{{ g.room }}</div>
          <div v-for="d in g.items" :key="d.id" class="device" :class="{ picked: picked[d.id] }">
            <div class="device-name">{{ d.name }}</div>
            <div class="choices">
              <button v-for="c in CHOICES[d.kind]" :key="c.key" :class="{ selected: picked[d.id]?.key === c.key }"
                @click="choose(d, c.key)">{{ c.label }}</button>
            </div>
            <div v-if="choiceOf(d)?.value" class="value">
              <van-stepper v-model="picked[d.id].value" :min="choiceOf(d)!.value!.min" :max="choiceOf(d)!.value!.max"
                :step="choiceOf(d)!.value!.unit === '%' ? 10 : 1" integer />
              <span>{{ choiceOf(d)!.value!.unit }}</span>
            </div>
          </div>
        </div>
        <div class="more" @click="showAll = !showAll">{{ showAll ? '只显示本房间设备' : '加入其他房间的设备' }}</div>
        <div v-if="scene?.id" class="delete" @click="remove">删除这个快捷操作</div>
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
  padding: 16px 20px 12px;
  background: var(--surface);
}
.heading {
  font-weight: 600;
}
.cancel {
  color: var(--text-2);
}
.save {
  color: var(--accent);
  font-weight: 600;
}
.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0 40px;
}
.icons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px 4px;
}
.icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}
.icon.selected {
  box-shadow: 0 0 0 2px var(--accent);
}
.group {
  margin: 12px 16px 0;
}
.group-title {
  font-size: 13px;
  color: var(--text-3);
  margin: 8px 4px;
}
.device {
  background: var(--surface);
  border-radius: 14px;
  padding: 12px;
  margin-bottom: 8px;
}
.device.picked {
  box-shadow: 0 0 0 1.5px var(--accent) inset;
}
.device-name {
  font-size: 14px;
  color: var(--text);
  margin-bottom: 8px;
}
.choices {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.choices button {
  border: none;
  font: inherit;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: 10px;
  background: var(--surface-2);
  color: var(--text-2);
}
.choices button.selected {
  background: var(--accent);
  color: #fff;
}
.value {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-2);
}
.more,
.delete {
  text-align: center;
  font-size: 14px;
  padding: 16px;
  color: var(--accent);
}
.delete {
  color: var(--danger);
}
</style>
