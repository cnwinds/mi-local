<script setup lang="ts">
import { computed, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'
import { api, type CloudRegion, type SyncSummary } from '../api'
import { cloud, loadCloud } from '../store'
import { CircleCheck, Cloud as CloudIcon, LogOut, RefreshCw } from 'lucide-vue-next'

const syncing = ref(false)
const showQr = ref(false)

// The account is global; the region is which Mi Home servers hold its devices (the Mi Home app's region setting).
const REGIONS: { id: CloudRegion; name: string }[] = [
  { id: 'cn', name: '中国大陆' }, { id: 'sg', name: '新加坡' }, { id: 'de', name: '欧洲' },
  { id: 'us', name: '美国' }, { id: 'ru', name: '俄罗斯' }, { id: 'i2', name: '印度' },
]
const region = ref<CloudRegion>('cn')
const regionName = computed(() => REGIONS.find((r) => r.id === cloud.value?.region)?.name)

const login = computed(() => cloud.value?.login)
const timeFmt = new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })

const summaryText = computed(() => describe(cloud.value?.summary))

function describe(s: SyncSummary | null | undefined) {
  if (!s) return ''
  const parts = [
    s.added.length && `新增 ${s.added.length}`,
    s.renamed.length && `改名 ${s.renamed.length}`,
    s.moved.length && `换房间 ${s.moved.length}`,
    s.token_changed.length && `更新密钥 ${s.token_changed.length}`,
    s.ip_changed.length && `IP 变化 ${s.ip_changed.length}`,
  ].filter(Boolean)
  return parts.length ? parts.join('，') : '没有变化'
}

async function startLogin() {
  try {
    await api.cloudLogin(region.value)
    await loadCloud()
    showQr.value = true
  } catch (e) {
    showFailToast((e as Error).message)
  }
}

async function sync() {
  syncing.value = true
  try {
    const summary = await api.cloudSync()
    showSuccessToast(`同步完成：${describe(summary)}`)
  } catch (e) {
    showFailToast((e as Error).message)
  } finally {
    syncing.value = false
    loadCloud()
  }
}

async function logout() {
  await showConfirmDialog({ title: '退出米家账号', message: '退出后不再自动同步，已同步的设备和规则保留。' })
  await api.cloudLogout()
  loadCloud()
}
</script>

<template>
  <div class="cloud card" v-if="cloud">
    <div class="badge" :class="{ on: cloud.logged_in, error: cloud.logged_in && cloud.last_error }">
      <CloudIcon :size="18" />
    </div>
    <div class="text" :title="cloud.logged_in ? `米家账号 ${cloud.user_id}` : ''">
      <div class="title">米家同步</div>
      <div v-if="!cloud.logged_in" class="sub">登录后自动同步设备名称、房间和密钥</div>
      <div v-else-if="cloud.last_error" class="sub error">同步失败：{{ cloud.last_error }}（断网时正常，本地功能不受影响）</div>
      <div v-else class="sub">
        <template v-if="cloud.region !== 'cn'">{{ regionName }} · </template>
        {{ cloud.last_sync ? timeFmt.format(new Date(cloud.last_sync * 1000)) : '尚未同步' }}<template v-if="summaryText"> · {{ summaryText }}</template>
      </div>
    </div>
    <select v-if="!cloud.logged_in" v-model="region" class="region" title="米家 App 里设置的服务器地区">
      <option v-for="r in REGIONS" :key="r.id" :value="r.id">{{ r.name }}</option>
    </select>
    <template v-if="cloud.logged_in">
      <button class="icon-btn primary" :class="{ spin: syncing }" :disabled="syncing" title="立即同步" @click="sync">
        <RefreshCw :size="17" :stroke-width="2.2" />
      </button>
      <button class="icon-btn" title="退出米家账号" @click="logout"><LogOut :size="16" /></button>
    </template>
    <van-button v-else size="small" round type="primary" @click="startLogin">扫码登录</van-button>

    <van-popup v-model:show="showQr" round closeable :style="{ width: '86%' }">
      <div class="qr" v-if="login">
        <div class="qr-title">用米家 App 扫码登录</div>
        <template v-if="login.state === 'waiting'">
          <img :src="login.qr_url" alt="登录二维码" />
          <div class="qr-tip">打开米家 App，点右上角「+」→「扫一扫」。<br />如果正在用这台手机看本页面，请在电脑浏览器打开本页面扫码。</div>
        </template>
        <div v-else-if="login.state === 'success'" class="qr-done">
          <CircleCheck :size="48" color="var(--green)" />
          <div>登录成功，正在同步…</div>
          <van-button round block type="primary" @click="showQr = false">完成</van-button>
        </div>
        <div v-else class="qr-done">
          <div>{{ login.state === 'expired' ? '二维码已过期' : `登录失败：${login.error}` }}</div>
          <van-button round block type="primary" @click="startLogin">重新获取二维码</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.cloud {
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
  background: var(--surface-2);
  color: var(--text-3);
}
.badge.on {
  background: var(--cool-soft);
  color: var(--cool);
}
.text {
  flex: 1;
  min-width: 0;
}
.badge.error {
  background: var(--heat-soft);
  color: var(--heat);
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
.sub.error {
  color: var(--heat);
}
.region {
  flex: none;
  height: 30px;
  padding: 0 6px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--surface-2);
  color: var(--text-2);
  font: inherit;
  font-size: 12px;
}
.icon-btn {
  flex: none;
  width: 34px;
  height: 34px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
  transition: background 0.15s, color 0.15s;
}
.icon-btn:hover {
  background: var(--surface-2);
  color: var(--text-2);
}
.icon-btn.primary {
  background: var(--accent-soft);
  color: var(--accent-text);
}
.icon-btn.spin svg {
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.qr {
  padding: 24px 20px;
  text-align: center;
}
.qr-title {
  font-weight: 600;
  margin-bottom: 12px;
}
.qr img {
  width: 220px;
  height: 220px;
}
.qr-tip {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 8px;
  line-height: 1.6;
}
.qr-done {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
}
</style>
