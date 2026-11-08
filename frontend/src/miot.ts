import type { DeviceField, PropValue } from './api'

const UNITS: Record<string, string> = {
  celsius: '℃',
  percentage: '%',
  minutes: '分钟',
  hours: '小时',
  days: '天',
  seconds: '秒',
  'μg/m3': 'μg/m³',
  kWh: 'kWh',
  watt: 'W',
  L: 'L',
  rpm: '转/分',
  ppm: 'ppm',
}

export function unitLabel(unit: string | null) {
  return unit ? (UNITS[unit] ?? unit) : ''
}

export function isNumeric(f: DeviceField) {
  return f.format !== 'bool' && f.format !== 'string'
}

export function formatValue(f: DeviceField, v: PropValue | undefined): string {
  if (v === undefined || v === null) return '—'
  const option = f.values.find((o) => o.value === v)
  if (option) return option.label
  if (f.format === 'bool') return v ? '开' : '关'
  if (typeof v === 'number') {
    if (f.unit === 'seconds' && v >= 60 && v % 60 === 0) return `${v / 60} 分钟`
    const n = Number.isInteger(v) ? v : Math.round(v * 10) / 10
    const unit = unitLabel(f.unit)
    return unit.length > 1 && !/[a-zA-Z³]/.test(unit) ? `${n} ${unit}` : `${n}${unit}`
  }
  return String(v)
}

export function mainPowerKey(fields: DeviceField[]) {
  return fields[0]?.prop === 'on' ? fields[0].key : undefined
}

const SUMMARY: [string, (s: string) => string][] = [
  ['status', (s) => s],
  ['mode', (s) => s],
  ['target-temperature', (s) => `设定 ${s}`],
  ['temperature', (s) => `当前 ${s}`],
  ['fan-level', (s) => `风量 ${s}`],
  ['left-time', (s) => `剩余 ${s}`],
  ['volume', (s) => `音量 ${s}`],
]

/** A short status line for tiles, e.g. "工作中 · 设定 47℃". */
export function summarize(fields: DeviceField[], props: Record<string, PropValue> | undefined): string {
  if (!props || !fields.length) return ''
  const power = mainPowerKey(fields)
  if (power && props[power] === false) return '已关闭'
  const parts: string[] = []
  for (const [prop, fmt] of SUMMARY) {
    const f = fields.find((x) => x.prop === prop && props[x.key] !== undefined)
    if (f) parts.push(fmt(formatValue(f, props[f.key])))
    if (parts.length === 2) break
  }
  return parts.join(' · ')
}
