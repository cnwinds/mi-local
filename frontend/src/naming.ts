import type { Device } from './api'

/** "筒灯" in 卧室 → "卧室筒灯"; names that already start with the room are kept. */
export function fullName(d: Device) {
  return d.name.startsWith(d.room) || d.room === '未分配' ? d.name : `${d.room}${d.name}`
}

/** Name a wireless switch after what its single click controls, plus the room it belongs in. */
export function suggestSwitchName(targets: Device[]): { name: string; room: string } | null {
  if (!targets.length) return null
  const rooms = [...new Set(targets.map((d) => d.room))]
  const room = rooms.length === 1 ? rooms[0] : ''
  let label: string
  if (targets.length === 1) label = fullName(targets[0])
  else if (room && targets.length > 2) label = `${room}的灯`
  else label = targets.slice(0, 2).map(fullName).join('和') + (targets.length > 2 ? '等' : '')
  return { name: `${label}开关`, room }
}
