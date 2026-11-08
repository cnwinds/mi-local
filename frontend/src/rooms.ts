import { computed } from 'vue'
import type { AcMode, Device, PanelItem, PanelSize, RuleAction } from './api'
import { deviceList, panels, rooms, sendCommand } from './store'

/** Wireless switches and the gateway are inputs, not things to operate from a panel. */
const PANEL_KINDS = new Set(['light', 'ac', 'curtain', 'bath_heater', 'airer', 'plug', 'doorbell', 'other'])
const LARGE_KINDS = new Set(['light', 'ac', 'curtain', 'bath_heater', 'airer'])
const KIND_ORDER = ['light', 'ac', 'bath_heater', 'curtain', 'airer', 'plug', 'doorbell', 'other']

export const AC_MODE_NAMES: Record<AcMode, string> = { cool: '制冷', heat: '制热', dry: '除湿', fan: '送风', auto: '自动' }

export function roomDevices(room: string): Device[] {
  return deviceList.value.filter((d) => d.room === room && PANEL_KINDS.has(d.kind) && !d.hidden)
}

/** Saved layout first, then devices added since, sorted by kind with online ones first. */
export function panelLayout(room: string): (PanelItem & { device: Device })[] {
  const list = roomDevices(room)
  const byId = new Map(list.map((d) => [d.id, d]))
  const saved = (panels.value[room] ?? []).filter((item) => byId.has(item.id))
  const savedIds = new Set(saved.map((i) => i.id))
  const added = list
    .filter((d) => !savedIds.has(d.id))
    .sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind) || Number(!!b.state.online) - Number(!!a.state.online))
    .map((d) => ({ id: d.id, size: (LARGE_KINDS.has(d.kind) ? 'large' : 'small') as PanelSize }))
  return [...saved, ...added].map((item) => ({ ...item, device: byId.get(item.id)! }))
}

export const panelRooms = computed(() => {
  const withDevices = rooms.value.filter((r) => roomDevices(r).length)
  for (const d of deviceList.value) if (!withDevices.includes(d.room) && roomDevices(d.room).length) withDevices.push(d.room)
  return withDevices
})

const online = (d: Device) => !!d.state.online
export const lightsOf = (list: Device[]) => list.filter((d) => d.kind === 'light' && online(d))
export const isRunning = (d: Device) =>
  online(d) && (d.kind === 'light' || d.kind === 'ac' || d.kind === 'bath_heater') && !!d.state.power

/** Short status phrases for a room, most important first. */
export function roomSummary(room: string): string[] {
  const list = roomDevices(room)
  const parts: string[] = []
  const lights = list.filter((d) => d.kind === 'light')
  if (lights.length) {
    const on = lights.filter((d) => online(d) && d.state.power).length
    parts.push(on ? `${on}/${lights.length} 灯亮` : '灯关')
  }
  for (const ac of list.filter((d) => d.kind === 'ac' && online(d))) {
    if (ac.state.power) parts.push(`空调${AC_MODE_NAMES[ac.state.mode ?? 'auto']} ${ac.state.target_temp}°`)
  }
  const temp = list.find((d) => online(d) && d.state.temperature !== undefined)?.state.temperature
  if (temp !== undefined) parts.push(`室温 ${temp}°`)
  for (const h of list.filter((d) => d.kind === 'bath_heater' && online(d) && d.state.power)) {
    const on = [h.state.heating && '暖风', h.state.blow && '吹风', h.state.ventilation && '换气', h.state.light && '照明']
    parts.push(`浴霸 ${on.filter(Boolean).join('、')}`)
  }
  const curtains = list.filter((d) => d.kind === 'curtain' && online(d))
  if (curtains.length) parts.push(curtains.some((c) => (c.state.position ?? 0) > 5) ? '窗帘开' : '窗帘关')
  return parts
}

export const roomActive = (room: string) => roomDevices(room).some(isRunning)

/** Lights act as one: any on turns all off, otherwise all on. */
export function toggleLights(list: Device[]) {
  const lights = lightsOf(list)
  const on = !lights.some((d) => d.state.power)
  lights.forEach((d) => sendCommand(d.id, on ? 'turn_on' : 'turn_off', undefined, { power: on }))
}

export interface BuiltinAction {
  key: string
  name: string
  icon: string
  run: (list: Device[]) => void
}

function setLights(list: Device[], brightness: number, color_temp: number) {
  for (const d of lightsOf(list)) {
    sendCommand(d.id, 'set_brightness', brightness, { power: true, brightness })
    sendCommand(d.id, 'set_color_temp', color_temp, { power: true, color_temp })
  }
}

export const BUILTIN_ACTIONS: BuiltinAction[] = [
  {
    key: 'all_off',
    name: '全关',
    icon: 'stop-circle-o',
    // Plugs are left alone: they often feed things like the fish tank that must stay on.
    run: (list) => list.filter(isRunning).forEach((d) => sendCommand(d.id, 'turn_off', undefined, { power: false })),
  },
  { key: 'bright', name: '明亮', icon: 'bulb-o', run: (list) => setLights(list, 100, 60) },
  { key: 'soft', name: '柔和', icon: 'fire-o', run: (list) => setLights(list, 35, 15) },
  { key: 'night', name: '夜灯', icon: 'eye-o', run: (list) => setLights(list, 1, 0) },
]

/** What a scene action does, in words, for chips and the editor. */
export function describeAction(a: RuleAction, d: Device | undefined): string {
  const name = d?.name ?? '已删除的设备'
  switch (a.action) {
    case 'turn_on':
      return `打开${name}`
    case 'turn_off':
      return `关闭${name}`
    case 'set_brightness':
      return `${name}亮度 ${a.value}%`
    case 'open':
      return `打开${name}`
    case 'close':
      return `关闭${name}`
    case 'set_temp':
      return `${name} ${a.value}°`
    case 'set_mode':
      return `${name}${AC_MODE_NAMES[a.value as AcMode] ?? ''}`
    case 'up':
      return `${name}升起`
    case 'down':
      return `${name}降下`
    case 'ring':
      return `${name}响铃`
    default:
      return `${name} ${a.action}`
  }
}
