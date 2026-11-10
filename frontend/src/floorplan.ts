import type { FloorRoom, Floorplan, PlanPoint } from './api'

export function bbox(points: PlanPoint[]) {
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  const x = Math.min(...xs)
  const y = Math.min(...ys)
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y }
}

export const svgPoints = (r: FloorRoom) => r.points.map((p) => p.join(',')).join(' ')

/** Default label spot: just inside the room's top left corner. */
export const labelAt = (r: FloorRoom): PlanPoint => r.label ?? ((b) => [b.x + 8, b.y + 8] as PlanPoint)(bbox(r.points))

const AUTO_HEIGHT = 200
const AUTO_GAP = 10
/** Width : height the packed rooms aim for, so the result reads as a flat rather than a strip. */
const AUTO_ASPECT = 1.4

/** A first plan for a home without one: a box per room, wider for busier rooms, packed into equal-width rows. */
export function autoLayout(rooms: { name: string; devices: number }[]): FloorRoom[] {
  const sized = rooms.map((r) => ({ name: r.name, w: Math.min(420, 180 + 40 * Math.max(0, r.devices - 2)) }))
  const total = sized.reduce((a, r) => a + r.w, 0)
  // rows × (aspect × rows × height) ≈ total width of all rooms
  const count = Math.min(sized.length, Math.max(1, Math.round(Math.sqrt(total / (AUTO_ASPECT * AUTO_HEIGHT)))))
  const rows: { name: string; w: number }[][] = [[]]
  let acc = 0
  for (const r of sized) {
    const row = rows.length
    if (rows[row - 1].length && row < count && acc + r.w / 2 > (total / count) * row) rows.push([])
    rows[rows.length - 1].push(r)
    acc += r.w
  }
  const out: FloorRoom[] = []
  const rowWidth = Math.round(Math.max(...rows.map((row) => row.reduce((a, r) => a + r.w, 0))))
  rows.forEach((row, i) => {
    const sum = row.reduce((a, r) => a + r.w, 0)
    const scale = (rowWidth - AUTO_GAP * (row.length - 1)) / sum
    const y = i * (AUTO_HEIGHT + AUTO_GAP)
    let x = 0
    for (const r of row) {
      const w = Math.round(r.w * scale)
      out.push({ name: r.name, points: [[x, y], [x + w, y], [x + w, y + AUTO_HEIGHT], [x, y + AUTO_HEIGHT]] })
      x += w + AUTO_GAP
    }
  })
  return out
}

/** The viewBox that shows every room and placed device, with a little air around it. */
export function fitView(plan: Pick<Floorplan, 'rooms' | 'devices' | 'cameras'>): Floorplan['view'] {
  const points = [...plan.rooms.flatMap((r) => r.points), ...Object.values(plan.devices), ...Object.values(plan.cameras)]
  if (!points.length) return [0, 0, 1000, 700]
  const b = bbox(points)
  const pad = Math.max(12, Math.max(b.w, b.h) * 0.02)
  return [Math.round(b.x - pad), Math.round(b.y - pad), Math.round(b.w + 2 * pad), Math.round(b.h + 2 * pad)]
}
