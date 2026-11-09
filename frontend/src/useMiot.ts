import { computed, onBeforeUnmount, reactive, watchEffect, type Ref } from 'vue'
import type { Device, DeviceField, PropValue } from './api'
import { deviceFields, ensureFields, sendCommand } from './store'
import { isNumeric, mainPowerKey } from './miot'

export type Control = 'switch' | 'chips' | 'stepper' | 'slider' | 'text'

export function controlOf(f: DeviceField): Control {
  if (!f.writable) return 'text'
  if (f.format === 'bool') return 'switch'
  if (f.values.length) return 'chips'
  if (f.range && isNumeric(f)) return (f.range[1] - f.range[0]) / f.range[2] <= 60 ? 'stepper' : 'slider'
  return 'text'
}

/** Reading and writing the spec properties of one device; stepper taps are batched into one write. */
export function useMiot(device: Ref<Device>) {
  watchEffect(() => {
    if (device.value.state.props) ensureFields(device.value.id)
  })

  const fields = computed(() => deviceFields[device.value.id] ?? [])
  const values = computed(() => device.value.state.props ?? {})
  const powerKey = computed(() => mainPowerKey(fields.value))
  const on = computed(() => (powerKey.value ? values.value[powerKey.value] === true : true))
  const pending = reactive<Record<string, number>>({})
  const timers: Record<string, ReturnType<typeof setTimeout>> = {}
  onBeforeUnmount(() => Object.values(timers).forEach(clearTimeout))

  function set(f: DeviceField, value: PropValue) {
    sendCommand(device.value.id, 'set_prop', { key: f.key, value }, { props: { ...values.value, [f.key]: value } })
  }

  const num = (f: DeviceField) => pending[f.key] ?? Number(values.value[f.key])

  function step(f: DeviceField, dir: number) {
    const [lo, hi, st] = f.range!
    const next = Math.min(hi, Math.max(lo, Math.round((num(f) + dir * st) * 100) / 100))
    pending[f.key] = next
    clearTimeout(timers[f.key])
    timers[f.key] = setTimeout(() => {
      set(f, next)
      delete pending[f.key]
    }, 700)
  }

  function togglePower() {
    const f = fields.value.find((x) => x.key === powerKey.value)
    if (f) set(f, !on.value)
  }

  return { fields, values, powerKey, on, set, num, step, togglePower }
}
