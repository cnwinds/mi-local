import { computed } from 'vue'
import { deviceList } from './store'
import { AC_MODE_NAMES, isRunning } from './rooms'

/** Whole-home status shared by the home page and the wall panel. */
const visible = computed(() => deviceList.value.filter((d) => !d.hidden && d.state.online))
export const lightsOn = computed(() => visible.value.filter((d) => d.kind === 'light' && isRunning(d)))
export const acsOn = computed(() => visible.value.filter((d) => d.kind === 'ac' && isRunning(d)))
export const curtainsOpen = computed(() => visible.value.filter((d) => d.kind === 'curtain' && (d.state.position ?? 0) > 5))
const temps = computed(() => visible.value.map((d) => d.state.temperature).filter((t): t is number => t !== undefined))
export const avgTemp = computed(() =>
  temps.value.length ? Math.round((temps.value.reduce((a, b) => a + b, 0) / temps.value.length) * 10) / 10 : null,
)

export const headline = computed(() => {
  if (!lightsOn.value.length && !acsOn.value.length) return '家里很安静，灯和空调都关着'
  const parts = []
  if (lightsOn.value.length) parts.push(`${lightsOn.value.length} 盏灯亮着`)
  for (const ac of acsOn.value) parts.push(`${ac.room}空调在${AC_MODE_NAMES[ac.state.mode ?? 'auto']}`)
  return parts.join('，')
})
