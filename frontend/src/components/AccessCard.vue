<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, type Component } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'
import { CircleCheck, Plus, ShieldCheck, Tablet, UserRound } from 'lucide-vue-next'
import { api, type AuthDevice, type Role } from '../api'
import { sinceText } from '../rooms'

const ROLES: { role: Role; name: string; desc: string; icon: Component }[] = [
  { role: 'family', name: '家人', desc: '控制设备、看摄像头和记录，不能改设置', icon: UserRound },
  { role: 'panel', name: '墙面面板', desc: '只能控制设备，适合固定在墙上的平板', icon: Tablet },
  { role: 'admin', name: '管理员', desc: '全部功能，包括设置和配对新设备', icon: ShieldCheck },
]
const roleOf = (r: Role) => ROLES.find((x) => x.role === r)!

const list = ref<AuthDevice[]>([])
const load = async () => (list.value = await api.authDevices())
onMounted(load)
const counts = computed(() =>
  ROLES.map((r) => ({ ...r, n: list.value.filter((d) => d.role === r.role).length })).filter((r) => r.n),
)

// Pairing: pick a role, show the code and its QR, and watch for the new device to turn up.
const pairing = ref(false)
const role = ref<Role>('family')
const code = ref<{ code: string; expires: number } | null>(null)
const paired = ref<AuthDevice | null>(null)
const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | undefined
let known = new Set<string>()

const left = computed(() => (code.value ? Math.max(0, Math.round((code.value.expires - now.value) / 1000)) : 0))
const leftText = computed(() => `${Math.floor(left.value / 60)}:${String(left.value % 60).padStart(2, '0')}`)
const host = location.host
const pairUrl = computed(() => (code.value ? `${location.origin}${location.pathname}#/pair?code=${code.value.code}` : ''))
const qrSrc = computed(() => `/api/qr.svg?text=${encodeURIComponent(pairUrl.value)}`)

function openPairing() {
  role.value = 'family'
  code.value = null
  paired.value = null
  pairing.value = true
}
async function generate() {
  try {
    await load()
    known = new Set(list.value.map((d) => d.id))
    const c = await api.createPairCode(role.value)
    now.value = Date.now()
    code.value = { code: c.code, expires: now.value + c.expires_in * 1000 }
    clearInterval(ticker)
    let polls = 0
    ticker = setInterval(async () => {
      now.value = Date.now()
      if (!left.value || paired.value) return clearInterval(ticker)
      if (++polls % 2) return
      await load()
      paired.value = list.value.find((d) => !known.has(d.id)) ?? null
    }, 1000)
  } catch (e) {
    showFailToast((e as Error).message)
  }
}
function closePairing() {
  clearInterval(ticker)
  pairing.value = false
}
onBeforeUnmount(() => clearInterval(ticker))

// Managing a paired device: change its role or revoke it.
const managing = ref<AuthDevice | null>(null)
const showList = ref(false)
function openList() {
  showList.value = true
  load()
}
const actions = computed(() => [
  ...ROLES.filter((r) => r.role !== managing.value?.role).map((r) => ({ name: `改为${r.name}`, role: r.role })),
  { name: '撤销授权', color: 'var(--danger)', role: null },
])
async function act(a: { role: Role | null }) {
  const d = managing.value!
  managing.value = null
  try {
    if (a.role) {
      await api.updateAuthDevice(d.id, { role: a.role })
      showSuccessToast(`已改为${roleOf(a.role).name}`)
    } else {
      await showConfirmDialog({
        title: `撤销「${d.name}」`,
        message: d.current ? '这就是你正在用的设备，撤销后需要重新配对。' : '撤销后这台设备需要重新配对才能使用。',
      })
      await api.revokeAuthDevice(d.id)
      if (d.current) return location.reload()
    }
  } catch (e) {
    if (e instanceof Error) showFailToast(e.message)
  }
  load()
}
</script>

<template>
  <div class="access card">
    <div class="badge"><ShieldCheck :size="18" /></div>
    <button class="text" @click="openList">
      <div class="title">已授权设备</div>
      <div class="sub">
        <template v-if="list.length">{{ counts.map((c) => `${c.name} ${c.n}`).join(' · ') }}</template>
        <template v-else>只有配对过的设备能查看和控制家里</template>
      </div>
    </button>
    <van-button size="small" round type="primary" @click="openPairing"><Plus :size="14" />配对新设备</van-button>

    <van-popup v-model:show="showList" position="bottom" round closeable>
      <div class="sheet">
        <div class="sheet-title">已授权设备</div>
        <van-cell-group inset>
          <van-cell v-for="d in list" :key="d.id" is-link center @click="managing = d">
            <template #icon>
              <div class="role-icon" :class="d.role"><component :is="roleOf(d.role).icon" :size="17" /></div>
            </template>
            <template #title>
              {{ d.name }}<span v-if="d.current" class="me">本机</span>
            </template>
            <template #label>
              {{ roleOf(d.role).name }} · {{ d.last_seen ? `${sinceText(d.last_seen).trim()}使用` : '未使用' }}{{ d.ip ? ` · ${d.ip}` : '' }}
            </template>
          </van-cell>
        </van-cell-group>
        <div class="sheet-actions">
          <van-button round block type="primary" @click="openPairing">配对新设备</van-button>
        </div>
      </div>
    </van-popup>
    <van-action-sheet :show="!!managing" :title="managing?.name" :actions="actions" cancel-text="取消"
      @update:show="(v: boolean) => !v && (managing = null)" @select="act" />

    <van-popup :show="pairing" round closeable :style="{ width: 'min(92vw, 400px)' }" @update:show="(v: boolean) => !v && closePairing()">
      <div class="pairing">
        <template v-if="paired">
          <CircleCheck :size="52" color="var(--green)" />
          <div class="done-title">「{{ paired.name }}」已配对</div>
          <div class="done-sub">权限：{{ roleOf(paired.role).name }}</div>
          <van-button round block type="primary" @click="closePairing">完成</van-button>
        </template>
        <template v-else-if="code && left">
          <div class="pair-title">在新设备上输入配对码</div>
          <div class="code num">{{ code.code.slice(0, 3) }} {{ code.code.slice(3) }}</div>
          <img :src="qrSrc" alt="配对二维码" class="qr" />
          <div class="tip">
            手机可以直接扫码。平板或电脑打开 <b>{{ host }}</b>，输入上面的数字。<br />
            {{ leftText }} 后过期 · 权限：{{ roleOf(role).name }}
          </div>
        </template>
        <template v-else>
          <div class="pair-title">{{ code ? '配对码已过期' : '新设备的权限' }}</div>
          <div class="roles">
            <button v-for="r in ROLES" :key="r.role" class="role" :class="{ on: role === r.role }" @click="role = r.role">
              <div class="role-icon" :class="r.role"><component :is="r.icon" :size="18" /></div>
              <div>
                <div class="role-name">{{ r.name }}</div>
                <div class="role-desc">{{ r.desc }}</div>
              </div>
            </button>
          </div>
          <van-button round block type="primary" @click="generate">{{ code ? '重新生成配对码' : '生成配对码' }}</van-button>
        </template>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.access {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 12px 12px 14px;
}
.badge {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--green) 14%, transparent);
  color: var(--green);
}
.text {
  flex: 1;
  min-width: 0;
  text-align: left;
}
.title {
  font-size: 14px;
  font-weight: 600;
}
.sub {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.access :deep(.van-button__text) {
  display: flex;
  align-items: center;
  gap: 2px;
}
.role-icon {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  background: var(--accent-soft);
  color: var(--accent);
}
.role-icon.admin {
  background: var(--heat-soft);
  color: var(--heat);
}
.role-icon.panel {
  background: var(--cool-soft);
  color: var(--cool);
}
.me {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 11px;
  background: var(--accent-soft);
  color: var(--accent-text);
}
.pairing {
  padding: 28px 22px 22px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  text-align: center;
}
.pair-title {
  font-size: 17px;
  font-weight: 650;
}
.code {
  font-size: 42px;
  font-weight: 600;
  letter-spacing: 0.08em;
  line-height: 1;
}
.qr {
  width: 180px;
  height: 180px;
  border-radius: 12px;
}
.tip {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-3);
}
.tip b {
  color: var(--text-2);
}
.roles {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.role {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: var(--radius);
  background: var(--surface-2);
  text-align: left;
  box-shadow: inset 0 0 0 2px transparent;
  transition: box-shadow 0.15s, background 0.15s;
}
.role.on {
  background: var(--surface);
  box-shadow: inset 0 0 0 2px var(--accent);
}
.role-name {
  font-size: 14px;
  font-weight: 600;
}
.role-desc {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 2px;
}
.done-title {
  font-size: 18px;
  font-weight: 650;
}
.done-sub {
  font-size: 13px;
  color: var(--text-3);
  margin-top: -8px;
}
</style>
