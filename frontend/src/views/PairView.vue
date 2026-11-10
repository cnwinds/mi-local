<script setup lang="ts">
import { ref } from 'vue'
import { House, KeyRound } from 'lucide-vue-next'
import { api } from '../api'

// A pairing QR code opens …/#/pair?code=123456
const code = ref(location.hash.match(/[?&]code=([0-9A-Za-z-]+)/)?.[1] ?? '')
const name = ref(guessName())
const busy = ref(false)
const error = ref('')

function guessName() {
  const ua = navigator.userAgent
  if (/iPad/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return 'iPad'
  if (/iPhone/.test(ua)) return 'iPhone'
  if (/Android/.test(ua)) return /Mobile/.test(ua) ? '安卓手机' : '安卓平板'
  if (/Windows/.test(ua)) return 'Windows 电脑'
  if (/Macintosh/.test(ua)) return 'Mac'
  return ''
}

async function pair() {
  if (busy.value || !code.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    await api.pair(code.value, name.value)
    location.replace(location.pathname)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="pair">
    <form class="card panel" @submit.prevent="pair">
      <div class="logo"><House :size="22" :stroke-width="2.2" /></div>
      <h1>配对这台设备</h1>
      <p class="lead">为了安全，只有配对过的设备才能查看和控制家里。每台设备只需配对一次。</p>

      <label class="field">
        <span>配对码</span>
        <input v-model="code" class="code num" inputmode="text" autocomplete="one-time-code" placeholder="输入配对码"
          autofocus />
      </label>
      <label class="field">
        <span>这台设备叫</span>
        <input v-model="name" maxlength="24" placeholder="比如：客厅平板" />
      </label>
      <div v-if="error" class="error">{{ error }}</div>
      <button class="submit" type="submit" :disabled="busy || !code.trim()">{{ busy ? '配对中…' : '配对' }}</button>

      <div class="help">
        <KeyRound :size="14" />
        <div>
          6 位配对码在已配对的管理员设备上获取：「设备」页 →「已授权设备」→「配对新设备」。<br />
          第一台设备用盒子运行日志里的 8 位一次性码。
        </div>
      </div>
    </form>
  </div>
</template>

<style scoped>
.pair {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  box-sizing: border-box;
}
.panel {
  width: 100%;
  max-width: 380px;
  padding: 32px 24px 24px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.logo {
  width: 48px;
  height: 48px;
  border-radius: 15px;
  background: linear-gradient(135deg, #ffb547, #ff7b3a);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-warm);
}
h1 {
  margin: 4px 0 0;
  font-size: 24px;
  font-weight: 750;
}
.lead {
  margin: -8px 0 4px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-2);
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}
.field input {
  height: 46px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text);
  font: inherit;
  font-size: 16px;
  font-weight: 500;
  outline: none;
  transition: border-color 0.15s, background 0.15s;
}
.field input:focus {
  border-color: var(--accent);
  background: var(--surface);
}
.field input.code {
  height: 56px;
  font-size: 26px;
  letter-spacing: 0.2em;
  text-align: center;
  text-transform: uppercase;
}
.error {
  font-size: 13px;
  color: var(--danger);
}
.submit {
  height: 48px;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  transition: opacity 0.15s;
}
.submit:disabled {
  opacity: 0.45;
  cursor: default;
}
.help {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-3);
}
.help svg {
  flex: none;
  margin-top: 3px;
}
</style>
