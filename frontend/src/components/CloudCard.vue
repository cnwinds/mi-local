<script setup lang="ts">
import { computed, ref } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'
import { api, type SyncSummary } from '../api'
import { cloud, loadCloud } from '../store'

const syncing = ref(false)
const showQr = ref(false)

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
    await api.cloudLogin()
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
  <div class="cloud" v-if="cloud">
    <div class="row">
      <div>
        <div class="title">米家同步</div>
        <div class="sub" v-if="cloud.logged_in">
          账号 {{ cloud.user_id }} · {{ cloud.last_sync ? `上次同步 ${timeFmt.format(new Date(cloud.last_sync * 1000))}` : '尚未同步' }}
        </div>
        <div class="sub" v-else>登录后自动同步设备名称、房间和密钥</div>
      </div>
      <van-button v-if="cloud.logged_in" size="small" round type="primary" :loading="syncing" @click="sync">立即同步</van-button>
      <van-button v-else size="small" round type="primary" @click="startLogin">扫码登录</van-button>
    </div>
    <div class="result" v-if="cloud.logged_in && cloud.last_error">同步失败：{{ cloud.last_error }}（断网时正常，本地功能不受影响）</div>
    <div class="result" v-else-if="cloud.logged_in && summaryText">{{ summaryText }}</div>
    <div class="links" v-if="cloud.logged_in"><span @click="logout">退出账号</span></div>

    <van-popup v-model:show="showQr" round closeable :style="{ width: '86%' }">
      <div class="qr" v-if="login">
        <div class="qr-title">用米家 App 扫码登录</div>
        <template v-if="login.state === 'waiting'">
          <img :src="login.qr_url" alt="登录二维码" />
          <div class="qr-tip">打开米家 App，点右上角「+」→「扫一扫」。<br />如果正在用这台手机看本页面，请在电脑浏览器打开本页面扫码。</div>
        </template>
        <div v-else-if="login.state === 'success'" class="qr-done">
          <van-icon name="checked" color="#07c160" size="48" />
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
  margin: 12px 16px 0;
  background: #fff;
  border-radius: 16px;
  padding: 16px;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.title {
  font-size: 15px;
  font-weight: 600;
}
.sub {
  font-size: 12px;
  color: #8f959e;
  margin-top: 4px;
}
.result {
  margin-top: 10px;
  font-size: 12px;
  color: #646a73;
  background: #f6f7f9;
  border-radius: 8px;
  padding: 8px 10px;
}
.links {
  margin-top: 10px;
  font-size: 12px;
  color: #8f959e;
  text-align: right;
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
  color: #8f959e;
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
