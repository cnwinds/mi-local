export type Kind = 'light' | 'plug' | 'curtain' | 'switch' | 'other' | 'gateway'

export interface DeviceState {
  online?: boolean
  power?: boolean
  brightness?: number
  color_temp?: number
  position?: number
  battery?: number
  load_power?: number
}

export interface Device {
  id: string
  name: string
  room: string
  kind: Kind
  model: string
  hidden: boolean
  state: DeviceState
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
  patchDevice: (id: string, patch: Partial<Pick<Device, 'name' | 'room' | 'hidden'>>) =>
    request<Device>('PATCH', `/devices/${encodeURIComponent(id)}`, patch),
  command: (id: string, action: string, value?: unknown) =>
    request<DeviceState>('POST', `/devices/${encodeURIComponent(id)}/command`, { action, value }),
  rooms: () => request<string[]>('GET', '/rooms'),
  setRooms: (rooms: string[]) => request<string[]>('PUT', '/rooms', rooms),
  rules: () => request<Rule[]>('GET', '/rules'),
  createRule: (rule: Rule) => request<Rule>('POST', '/rules', rule),
  updateRule: (id: string, rule: Rule) => request<Rule>('PUT', `/rules/${id}`, rule),
  deleteRule: (id: string) => request<unknown>('DELETE', `/rules/${id}`),
  runRule: (id: string) => request<unknown>('POST', `/rules/${id}/run`),
  events: () => request<HubEvent[]>('GET', '/events'),
  cloud: () => request<CloudStatus>('GET', '/cloud'),
  cloudLogin: () => request<CloudLogin>('POST', '/cloud/login'),
  cloudSync: () => request<SyncSummary>('POST', '/cloud/sync'),
  cloudLogout: () => request<unknown>('POST', '/cloud/logout'),
}
