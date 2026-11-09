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

const METRIC_PROPS = [
  'run-status', 'left-time', 'status', 'temperature', 'relative-humidity', 'pm2.5-density', 'tds-out',
  'filter-life-level', 'mode', 'target-temperature', 'fault', 'heat-level',
]
const CONTROL_PROPS = ['target-temperature', 'target-humidity', 'fan-level', 'volume', 'mode', 'brightness']
const NO_FAULT = /^(无故障|正常)$/

export interface Metric {
  field: DeviceField
  text: string
}

/** What a wall-panel card shows: a few readings in big type and the controls people reach for most. */
export function cardModel(fields: DeviceField[], props: Record<string, PropValue>, powerKey?: string) {
  const std = fields.filter((f) => !f.vendor && f.key !== powerKey)
  const controls: DeviceField[] = []
  for (const prop of CONTROL_PROPS) {
    const f = std.find((x) => x.prop === prop && x.writable && !controls.includes(x))
    if (!f || controls.length >= 2) continue
    const fits = f.values.length ? f.values.length <= 4 : !!f.range && props[f.key] !== undefined
    if (fits) controls.push(f)
  }
  const toggles = std
    .filter((f) => f.format === 'bool' && f.writable && props[f.key] !== undefined)
    .sort((a, b) => Number(b.prop === 'on') - Number(a.prop === 'on'))
    .slice(0, 3)

  const metrics: Metric[] = []
  for (const prop of METRIC_PROPS) {
    if (metrics.length >= 3) break
    const f = std.find((x) => x.prop === prop && props[x.key] !== undefined && !controls.includes(x))
    if (!f) continue
    const text = formatValue(f, props[f.key])
    if (prop === 'fault' && NO_FAULT.test(text)) continue
    metrics.push({ field: f, text })
  }
  return { metrics, controls, toggles }
}

/** A label that stands on its own on a card: 灯 for a light's switch, 麦克风静音 next to the speaker's 静音. */
export function cardLabel(f: DeviceField, fields: DeviceField[]) {
  const base = f.prop === 'on' ? f.service : f.name
  return f.service !== fields[0]?.service && !base.includes(f.service) ? f.service + base : base
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
