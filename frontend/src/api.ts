export type Kind =
  | 'light' | 'plug' | 'curtain' | 'switch' | 'doorbell' | 'ac' | 'bath_heater' | 'airer' | 'lock' | 'other' | 'gateway'

export type AcMode = 'cool' | 'heat' | 'dry' | 'fan' | 'auto'

export interface AcCaps {
  modes: AcMode[]
  temp_min: number
  temp_max: number
  temp_step: number
  fan_levels: number
}

export interface DeviceState {
  online?: boolean
  power?: boolean
  brightness?: number
  color_temp?: number
  position?: number
  battery?: number
  load_power?: number
  // air conditioner
  mode?: AcMode
  target_temp?: number
  temperature?: number
  fan_level?: number
  swing?: boolean
  caps?: AcCaps
  // bath heater / airer
  light?: boolean
  heating?: boolean
  blow?: boolean
  ventilation?: boolean
  motor?: 'up' | 'down' | 'stop'
  // lock (read-only)
  door?: 'open' | 'closed' | null
  lock_online?: boolean
  last_event?: string
  last_event_ts?: number
  // any device with a MIoT spec, keyed by DeviceField.key
  props?: Record<string, PropValue>
}

export type PropValue = boolean | number | string

export interface DeviceField {
  key: string
  service: string
  name: string
  prop: string
  format: string
  unit: string | null
  range: [number, number, number] | null
  values: { value: PropValue; label: string }[]
  writable: boolean
  vendor: boolean
}

export type PanelSize = 'large' | 'small' | 'hidden'

export interface PanelItem {
  id: string
  size: PanelSize
}

export interface Scene {
  id?: string
  room: string
  name: string
  icon: string
  actions: RuleAction[]
}

export interface Device {
  id: string
  name: string
  room: string
  kind: Kind
  model: string
  hidden: boolean
  cloud_name: string
  cloud_room: string
  name_auto: boolean
  state: DeviceState
}

export interface DevicePatch {
  name?: string
  room?: string
  hidden?: boolean
  local_name?: string
  local_room?: string
  name_auto?: boolean
}

export interface RuleAction {
  device: string
  action: string
  value?: unknown
}

export interface Rule {
  id?: string
  name: string
  enabled: boolean
  trigger: { type: 'device_event'; device: string; event: string }
  actions: RuleAction[]
}

export interface HubEvent {
  ts: number
  device: string
  event: string
}

export interface Stats {
  since: number
  first: number | null
  days: number
  total_presses: number
  press_types: Record<string, number>
  total_turn_ons: number
  total_doors: number
  switches: { device: string; count: number }[]
  usage: { device: string; on_seconds: number; turn_ons: number; rate: number }[]
  /** [weekday 0 = Monday][hour] */
  heatmap: number[][]
  peak_hour: number | null
  /** day: local midnight as a unix timestamp */
  daily: { day: number; presses: number; turn_ons: number; doors: number }[]
}

export interface Camera {
  id: string
  name: string
  room: string
  model: string
  hidden: boolean
  /** go2rtc cannot speak this model's P2P protocol; it stays off the wall until re-checked. */
  unsupported: boolean
}

export interface LockinCapture {
  active: boolean
  port: number
  remaining: number
  seen_any: boolean
  seen_lockin: boolean
  done: boolean
  error: string
}

export interface SyncSummary {
  added: string[]
  renamed: string[]
  moved: string[]
  token_changed: string[]
  ip_changed: string[]
}

export interface CloudLogin {
  state: 'waiting' | 'success' | 'expired' | 'error'
  qr_url: string
  login_url: string
  error?: string
}

export interface CloudStatus {
  logged_in: boolean
  user_id: string | null
  last_sync: number | null
  last_error: string | null
  summary: SyncSummary | null
  login: CloudLogin | null
}

export interface GatewayChild {
  sid: string
  online: boolean
  device: Device | null
}

export interface GatewayCandidate {
  id: string
  name: string
  model: string
  ip: string | null
  room: string
  online: boolean
  supported: boolean
}

export interface GatewayStatus {
  configured: boolean
  connected: boolean
  last_seen_ago: number | null
  children: number
  children_online: number
  candidates: GatewayCandidate[]
  id?: string
  name?: string
  model?: string
  room?: string
  ip?: string
  cloud_ip?: string | null
  mac?: string
  has_key?: boolean
  has_token?: boolean
}

export interface PairingStatus {
  active: boolean
  remaining: number
  found: string[]
}

export interface VoiceStatus {
  enabled: boolean
  active: boolean
  error: string | null
  devices: string[]
  speakers: { name: string; online: boolean }[]
  last: { ts: number; speaker: string; query: string; reply: string } | null
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail ?? res.statusText)
  }
  return res.json()
}

export const api = {
  devices: () => request<Device[]>('GET', '/devices'),
  patchDevice: (id: string, patch: DevicePatch) =>
    request<Device>('PATCH', `/devices/${encodeURIComponent(id)}`, patch),
  command: (id: string, action: string, value?: unknown) =>
    request<DeviceState>('POST', `/devices/${encodeURIComponent(id)}/command`, { action, value }),
  deviceFields: (id: string) => request<DeviceField[]>('GET', `/devices/${encodeURIComponent(id)}/fields`),
  rooms: () => request<string[]>('GET', '/rooms'),
  setRooms: (rooms: string[]) => request<string[]>('PUT', '/rooms', rooms),
  rules: () => request<Rule[]>('GET', '/rules'),
  createRule: (rule: Rule) => request<Rule>('POST', '/rules', rule),
  updateRule: (id: string, rule: Rule) => request<Rule>('PUT', `/rules/${id}`, rule),
  deleteRule: (id: string) => request<unknown>('DELETE', `/rules/${id}`),
  runRule: (id: string) => request<unknown>('POST', `/rules/${id}/run`),
  events: (before?: number, limit = 100) =>
    request<{ total: number; items: HubEvent[] }>('GET', `/events?limit=${limit}${before ? `&before=${before}` : ''}`),
  stats: (days: number | null) =>
    request<Stats>('GET', `/stats?tz=${new Date().getTimezoneOffset()}${days ? `&days=${days}` : ''}`),
  cloud: () => request<CloudStatus>('GET', '/cloud'),
  cloudLogin: () => request<CloudLogin>('POST', '/cloud/login'),
  cloudSync: () => request<SyncSummary>('POST', '/cloud/sync'),
  cloudLogout: () => request<unknown>('POST', '/cloud/logout'),
  pairing: () => request<PairingStatus>('GET', '/gateway/pairing'),
  startPairing: (seconds = 120) => request<PairingStatus>('POST', '/gateway/pairing', { seconds }),
  gateway: () => request<GatewayStatus>('GET', '/gateway'),
  configureGateway: (config: { id: string; ip?: string; lan_key?: string }) =>
    request<GatewayStatus>('PUT', '/gateway', config),
  gatewayChildren: () => request<GatewayChild[]>('GET', '/gateway/children'),
  panels: () => request<Record<string, PanelItem[]>>('GET', '/panels'),
  setPanel: (room: string, layout: PanelItem[]) =>
    request<PanelItem[]>('PUT', `/panels/${encodeURIComponent(room)}`, layout),
  scenes: () => request<Scene[]>('GET', '/scenes'),
  createScene: (scene: Scene) => request<Scene>('POST', '/scenes', scene),
  updateScene: (id: string, scene: Scene) => request<Scene>('PUT', `/scenes/${id}`, scene),
  deleteScene: (id: string) => request<unknown>('DELETE', `/scenes/${id}`),
  runScene: (id: string) => request<unknown>('POST', `/scenes/${id}/run`),
  setupMidea: (account: string, password: string) => request<Device[]>('POST', '/midea/setup', { account, password }),
  lockin: () => request<{ configured: boolean; capture: LockinCapture }>('GET', '/lockin'),
  captureLockin: (active: boolean) => request<LockinCapture>('POST', '/lockin/capture', { active }),
  setupLockin: (access_token: string) => request<Device[]>('POST', '/lockin/setup', { access_token }),
  cameras: () => request<Camera[]>('GET', '/cameras'),
  updateCamera: (id: string, patch: { hidden?: boolean; unsupported?: boolean }) =>
    request<Camera[]>('PATCH', `/cameras/${id}`, patch),
  voice: () => request<VoiceStatus>('GET', '/voice'),
  setVoice: (enabled: boolean) => request<VoiceStatus>('PUT', '/voice', { enabled }),
}
