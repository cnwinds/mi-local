import { computed } from 'vue'
import type { AcMode, Device, PanelItem, PanelSize, RuleAction } from './api'
import { deviceFields, deviceList, ensureFields, panels, rooms, sendCommand } from './store'
import { summarize } from './miot'

/** Wireless switches and the gateway are inputs, not things to operate from a panel. */
const PANEL_KINDS = new Set(['light', 'ac', 'curtain', 'bath_heater', 'airer', 'lock', 'plug', 'doorbell', 'remote', 'other'])
const LARGE_KINDS = new Set(['light', 'ac', 'curtain', 'bath_heater', 'airer', 'lock'])
const KIND_ORDER = ['lock', 'light', 'ac', 'bath_heater', 'curtain', 'airer', 'plug', 'doorbell', 'remote', 'other']

/** Appliances get a full card once they report something worth showing; offline ones stay compact. */
const isLarge = (d: Device) =>
  LARGE_KINDS.has(d.kind) || (!!d.state.online && (d.kind === 'plug' || (d.kind === 'other' && !!d.state.props)))

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
    .map((d) => ({ id: d.id, size: (isLarge(d) ? 'large' : 'small') as PanelSize }))
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
  for (const lock of list.filter((d) => d.kind === 'lock' && online(d) && d.state.door === 'open')) parts.push(`${lock.name}开着`)
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
  for (const d of list.filter((d) => d.kind === 'other' && online(d) && d.state.power)) parts.push(`${d.name}运行中`)
  if (!parts.length && list.length) parts.push(`${list.filter(online).length}/${list.length} 台设备在线`)
  return parts
}

export const roomActive = (room: string) => roomDevices(room).some(isRunning)

/** "3分钟前 " style prefix for event times, empty when unknown. */
export function sinceText(ts?: number): string {
  if (!ts) return ''
  const minutes = Math.max(0, Math.round((Date.now() / 1000 - ts) / 60))
  if (minutes < 1) return '刚刚 '
  if (minutes < 60) return `${minutes}分钟前 `
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)}小时前 `
  return `${Math.round(minutes / 1440)}天前 `
}

/** One line of status for lists and compact tiles. */
export function deviceStatus(d: Device): string {
  const s = d.state
  if (!s.online) return '离线'
  switch (d.kind) {
    case 'light':
      return s.power ? `亮度 ${s.brightness}%` : '关闭'
    case 'plug':
      return s.power ? `开启 · ${s.load_power ?? 0} W` : '关闭'
    case 'curtain':
      return `打开 ${s.position ?? 0}%`
    case 'ac':
      return s.power ? `${AC_MODE_NAMES[s.mode ?? 'auto']} ${s.target_temp}°` : '关闭'
    case 'switch':
      return s.battery !== undefined ? `电量 ${s.battery}%` : '在线'
    case 'doorbell':
      return '点按响铃'
    case 'lock': {
      const door = s.door === 'open' ? '门开着' : s.door === 'closed' ? '门已关' : '在线'
      return s.battery !== undefined && s.battery !== null ? `${door} · 电量 ${s.battery}%` : door
    }
    case 'airer':
      return s.light ? '照明开' : '在线'
    case 'remote':
      return '红外遥控'
  }
  if (s.props) ensureFields(d.id)
  return summarize(deviceFields[d.id] ?? [], s.props) || (s.power === undefined ? '在线' : s.power ? '开启' : '关闭')
}

export type RoomSize = 's' | 'm' | 'l'

/** Home tile size from how much the room has to show: an AC and several devices earn the big tile. */
export function roomSize(list: Device[]): RoomSize {
  const count = list.filter((d) => d.kind !== 'doorbell').length
  const hasAc = list.some((d) => d.kind === 'ac')
  if ((hasAc && count >= 4) || count >= 9) return 'l'
  if (hasAc || count >= 4) return 'm'
  return 's'
}

const KIND_LABELS: Partial<Record<Device['kind'], string>> = {
  light: '灯', ac: '空调', curtain: '窗帘', plug: '插座', bath_heater: '浴霸', airer: '晾衣架', lock: '门锁',
  remote: '遥控',
}

/** "卧室筒灯" in 卧室 → "筒灯"; falls back to the kind when nothing is left. */
export function shortName(d: Device): string {
  const rest = d.name.startsWith(d.room) ? d.name.slice(d.room.length).replace(/^[的\s]+/, '') : d.name
  return rest || KIND_LABELS[d.kind] || d.name
}

/** Whether a device is "on" in the sense its tile should light up. */
export function isActive(d: Device): boolean {
  const s = d.state
  if (!s.online) return false
  if (d.kind === 'curtain') return (s.position ?? 0) > 5
  if (d.kind === 'lock') return s.door === 'open'
  if (d.kind === 'airer') return !!s.light
  return !!s.power
}

/** One-tap action for a device chip, or null when the chip only opens details. */
export function quickToggle(d: Device): (() => void) | null {
  const s = d.state
  if (!s.online) return null
  switch (d.kind) {
    case 'curtain': {
      const open = (s.position ?? 0) <= 50
      return () => sendCommand(d.id, open ? 'open' : 'close', undefined, { position: open ? 100 : 0 })
    }
    case 'light':
    case 'plug':
    case 'ac':
    case 'bath_heater':
      return () => sendCommand(d.id, s.power ? 'turn_off' : 'turn_on', undefined, { power: !s.power })
    case 'other':
      return s.power === undefined ? null : () => sendCommand(d.id, 'toggle', undefined, { power: !s.power })
  }
  return null
}

/** Set every light in the room to one brightness, turning on the ones that are off. */
export function setRoomBrightness(list: Device[], brightness: number) {
  for (const d of lightsOf(list)) sendCommand(d.id, 'set_brightness', brightness, { power: true, brightness })
}

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
