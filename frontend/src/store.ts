import { computed, reactive, ref } from 'vue'
import { showFailToast } from 'vant'
import {
  api,
  type CloudStatus,
  type Device,
  type DeviceField,
  type DeviceState,
  type GatewayStatus,
  type HubEvent,
  type PairingStatus,
  type PanelItem,
  type Rule,
  type Scene,
  type VoiceStatus,
} from './api'

export const devices = reactive<Record<string, Device>>({})
export const rooms = ref<string[]>([])
export const rules = ref<Rule[]>([])
/** Newest first; older pages are fetched on demand. */
export const events = ref<HubEvent[]>([])
export const eventsTotal = ref(0)
export const connected = ref(false)
export const cloud = ref<CloudStatus | null>(null)
export const pairing = ref<PairingStatus | null>(null)
export const gateway = ref<GatewayStatus | null>(null)
export const gatewayName = computed(() => gateway.value?.name || '网关')
export const panels = ref<Record<string, PanelItem[]>>({})
export const scenes = ref<Scene[]>([])
export const voice = ref<VoiceStatus | null>(null)

type EventListener = (e: HubEvent) => void
const eventListeners = new Set<EventListener>()

export const deviceList = computed(() => Object.values(devices))

export const EVENT_NAMES: Record<string, string> = {
  click: '单击',
  double_click: '双击',
  long_click_press: '长按',
  long_click_release: '长按松开',
  unlock: '开锁',
  door_open: '开门',
  door_close: '关门',
}

export async function loadDevices() {
  const list = await api.devices()
  for (const id of Object.keys(devices)) delete devices[id]
  for (const d of list) devices[d.id] = d
  rooms.value = await api.rooms()
}

export async function loadRules() {
  rules.value = await api.rules()
}

export async function loadCloud() {
  cloud.value = await api.cloud()
}

export async function loadVoice() {
  voice.value = await api.voice()
}

export async function loadPairing() {
  pairing.value = await api.pairing()
}

export async function loadGateway() {
  gateway.value = await api.gateway()
}

export async function loadPanels() {
  panels.value = await api.panels()
}

export async function loadScenes() {
  scenes.value = await api.scenes()
}

export const deviceFields = reactive<Record<string, DeviceField[]>>({})
const fieldRequests = new Map<string, Promise<void>>()

export function ensureFields(id: string) {
  if (deviceFields[id]?.length || fieldRequests.has(id)) return
  const req = api
    .deviceFields(id)
    .then((f) => {
      deviceFields[id] = f
    })
    .catch(() => {})
    .finally(() => fieldRequests.delete(id))
  fieldRequests.set(id, req)
}

export async function loadEvents() {
  const page = await api.events()
  events.value = page.items
  eventsTotal.value = page.total
}

export async function loadOlderEvents() {
  const last = events.value[events.value.length - 1]
  if (!last) return
  events.value = [...events.value, ...(await api.events(last.ts)).items]
}

export function onHubEvent(listener: EventListener) {
  eventListeners.add(listener)
  return () => eventListeners.delete(listener)
}

export async function sendCommand(id: string, action: string, value?: unknown, optimistic?: DeviceState) {
  const device = devices[id]
  const previous = { ...device.state }
  if (optimistic) device.state = { ...device.state, ...optimistic }
  try {
    device.state = { ...device.state, ...(await api.command(id, action, value)) }
  } catch (e) {
    device.state = previous
    showFailToast(`${device.name}：操作失败`)
  }
}

export function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/api/ws`)
  ws.onopen = () => {
    connected.value = true
    loadDevices()
    loadCloud()
    loadVoice()
    loadGateway()
    loadPanels()
    loadScenes()
  }
  ws.onclose = () => {
    connected.value = false
    setTimeout(connect, 2000)
  }
  ws.onmessage = (msg) => {
    const data = JSON.parse(msg.data)
    if (data.type === 'state' && devices[data.id]) {
      devices[data.id].state = data.state
    } else if (data.type === 'fields') {
      delete deviceFields[data.id]
      ensureFields(data.id)
    } else if (data.type === 'devices') {
      loadDevices()
      loadVoice()
    } else if (data.type === 'cloud') {
      loadCloud()
    } else if (data.type === 'voice') {
      loadVoice()
    } else if (data.type === 'gateway') {
      loadGateway()
    } else if (data.type === 'pairing') {
      loadPairing()
    } else if (data.type === 'panels') {
      loadPanels()
    } else if (data.type === 'scenes') {
      loadScenes()
    } else if (data.type === 'event') {
      const e: HubEvent = { ts: data.ts, device: data.device, event: data.event }
      events.value = [e, ...events.value]
      eventsTotal.value += 1
      eventListeners.forEach((l) => l(e))
    }
  }
}
