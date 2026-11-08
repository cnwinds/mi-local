import type { Device } from './api'

/** "筒灯" in 卧室 → "卧室筒灯"; names that already start with the room are kept. */
export function fullName(d: Device) {
  return d.name.startsWith(d.room) || d.room === '未分配' ? d.name : `${d.room}${d.name}`
}

/** "米家：窗帘 2（客厅走道）" when the local name or room differs from Mi Home, otherwise "". */
export function miHomeLabel(d: Device) {
  if (!d.cloud_name || (d.name === d.cloud_name && d.room === d.cloud_room)) return ''
  return `米家：${d.cloud_name}${d.room !== d.cloud_room ? `（${d.cloud_room}）` : ''}`
}

/** Name a wireless switch after what its single click controls, plus the room it belongs in. */
export function suggestSwitchName(all: Device[]): { name: string; room: string } | null {
  // The doorbell lives wherever the gateway is, so it never decides the switch's room.
  const targets = all.filter((d) => d.kind !== 'doorbell')
  if (!targets.length) return all.length ? { name: '门铃开关', room: '' } : null
  const rooms = [...new Set(targets.map((d) => d.room))]
  const room = rooms.length === 1 ? rooms[0] : ''
  let label: string
  if (targets.length === 1) label = fullName(targets[0])
  else if (room && targets.length > 2) label = `${room}的灯`
  else label = targets.slice(0, 2).map(fullName).join('和') + (targets.length > 2 ? '等' : '')
  return { name: `${label}开关`, room }
}
