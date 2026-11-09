<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { showFailToast } from 'vant'
import { api, type Device, type LockinCapture } from '../../api'
import { deviceList, loadDevices } from '../../store'
import { Check, ChevronDown, ChevronUp } from 'lucide-vue-next'

const emit = defineEmits<{ done: [devices: Device[]] }>()

const caUrl = `${location.origin}/api/lockin/ca.crt`
const qrSrc = `/api/qr.svg?text=${encodeURIComponent(caUrl)}`
const proxyHost = location.hostname

const os = ref<'ios' | 'android'>(/android/i.test(navigator.userAgent) ? 'android' : 'ios')
const capture = ref<LockinCapture | null>(null)
const starting = ref(false)
let timer: number | undefined

async function poll() {
  const status = await api.lockin().catch(() => null)
  if (!status) return
  capture.value = status.capture
  if (status.capture.done) {
    stopPolling()
    await loadDevices()
    emit('done', deviceList.value.filter((d) => d.id.startsWith('lockin.')))
  } else if (!status.capture.active) {
    stopPolling()
  }
}
function stopPolling() {
  clearInterval(timer)
  timer = undefined
}
async function start() {
  starting.value = true
  try {
    capture.value = await api.captureLockin(true)
    stopPolling()
    timer = window.setInterval(poll, 2000)
  } catch (e) {
    showFailToast((e as Error).message)
  } finally {
    starting.value = false
  }
}
async function cancel() {
  stopPolling()
  capture.value = await api.captureLockin(false)
}
onBeforeUnmount(stopPolling)

const remaining = computed(() => {
  const s = capture.value?.remaining ?? 0
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
})
const phase = computed(() => {
  const c = capture.value
  if (!c?.active) return 'idle'
  if (c.error) return 'error'
  if (c.seen_lockin) return 'verifying'
  return c.seen_any ? 'connected' : 'waiting'
})

// Manual fallback: paste a token captured some other way.
const showManual = ref(false)
const token = ref('')
const busy = ref(false)
async function submit() {
  busy.value = true
  try {
    const added = await api.setupLockin(token.value.trim())
    token.value = ''
    emit('done', added)
  } catch (e) {
    showFailToast({ message: (e as Error).message, duration: 4000 })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="setup">
    <p class="lead">鹿客门锁不支持米家，这里通过鹿客云只读接入：门状态、电量和开锁记录，并能用开锁触发联动。不能远程开锁。</p>
    <p class="lead small">接入只需做一次：让手机临时经过本机上网，打开鹿客 App 时本机会自动拿到登录凭证。只会解开发往鹿客服务器的连接，其他 App 的流量原样通过。</p>

    <div class="os">
      <button :class="{ on: os === 'ios' }" @click="os = 'ios'">iPhone</button>
      <button :class="{ on: os === 'android' }" @click="os = 'android'">安卓</button>
    </div>

    <section class="step">
      <div class="num">1</div>
      <div class="body">
        <div class="title">在手机上安装本机证书</div>
        <div class="cert">
          <img :src="qrSrc" alt="证书下载二维码" class="qr" />
          <div class="cert-text">
            <p>用手机相机扫码下载，或在手机上直接点：</p>
            <a :href="caUrl" class="link">下载证书</a>
          </div>
        </div>
        <p v-if="os === 'ios'" class="how">
          下载后打开「设置」→ 顶部「已下载描述文件」→ 安装。<br />
          再到「设置 → 通用 → 关于本机 → 证书信任设置」，打开「mi-local 门锁接入证书」。
        </p>
        <p v-else class="how">
          打开「设置」，搜索「CA 证书」或「安装证书」→ 选择 CA 证书 → 选刚下载的 mi-local-ca.crt。
          部分安卓手机的 App 不信任用户安装的证书，如果后面一直显示「等待鹿客 App」，请改用 iPhone 接入。
        </p>
      </div>
    </section>

    <section class="step">
      <div class="num">2</div>
      <div class="body">
        <div class="title">把手机 Wi-Fi 代理指向本机</div>
        <p class="how">
          {{ os === 'ios' ? '设置 → 无线局域网 → 当前 Wi-Fi 右边的 ⓘ → 配置代理 → 手动' : '设置 → WLAN → 长按当前 Wi-Fi → 修改网络 → 高级选项 → 代理 → 手动' }}
        </p>
        <div class="proxy">
          <div><span>服务器</span><b class="num-text">{{ proxyHost }}</b></div>
          <div><span>端口</span><b class="num-text">{{ capture?.port ?? 8899 }}</b></div>
        </div>
      </div>
    </section>

    <section class="step">
      <div class="num">3</div>
      <div class="body">
        <div class="title">开始接入，然后打开鹿客 App 下拉刷新</div>
        <van-button v-if="phase === 'idle'" round block type="primary" :loading="starting" @click="start">开始接入</van-button>
        <div v-else class="live">
          <div class="live-row">
            <van-loading v-if="phase !== 'error'" size="16px" />
            <span class="live-text" :class="{ warn: phase === 'error' }">
              <template v-if="phase === 'waiting'">等待手机连上代理…</template>
              <template v-else-if="phase === 'connected'"><Check :size="14" class="ok" />手机已连上，现在打开鹿客 App 进入门锁页，下拉刷新</template>
              <template v-else-if="phase === 'verifying'"><Check :size="14" class="ok" />已收到鹿客 App 的连接，正在验证…</template>
              <template v-else>{{ capture?.error }}</template>
            </span>
            <span class="countdown num-text">{{ remaining }}</span>
          </div>
          <button class="cancel" @click="cancel">取消</button>
        </div>
      </div>
    </section>

    <p class="note">接入成功后，记得把手机 Wi-Fi 代理改回「关闭」。证书可以保留，也可以在设置里删除，不影响门锁使用。</p>

    <button class="manual-toggle" @click="showManual = !showManual">
      已经有 access_token？手动粘贴<component :is="showManual ? ChevronUp : ChevronDown" :size="14" />
    </button>
    <template v-if="showManual">
      <van-field v-model="token" type="textarea" rows="3" placeholder="粘贴 access_token" class="token" />
      <p class="note warn">令牌相当于家门的远程权限，只粘贴在这里，不要发给任何人。</p>
      <van-button round block plain type="primary" :loading="busy" loading-text="正在连接鹿客云…"
        :disabled="token.trim().length < 20" @click="submit">接入</van-button>
    </template>
  </div>
</template>

<style scoped>
.setup {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.lead {
  margin: 0;
  font-size: 14px;
  color: var(--text-2);
  line-height: 1.7;
}
.lead.small {
  font-size: 12px;
  color: var(--text-3);
}
.os {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 12px;
  background: var(--surface-2);
  align-self: flex-start;
}
.os button {
  padding: 6px 16px;
  border-radius: 9px;
  font-size: 13px;
  color: var(--text-3);
}
.os button.on {
  background: var(--surface);
  color: var(--text);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}
.step {
  display: flex;
  gap: 12px;
  padding: 14px;
  border-radius: 16px;
  background: var(--surface-2);
}
.num {
  flex: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.title {
  font-size: 15px;
  font-weight: 600;
  line-height: 24px;
}
.how {
  margin: 0;
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.7;
}
.cert {
  display: flex;
  align-items: center;
  gap: 14px;
}
.qr {
  width: 108px;
  height: 108px;
  border-radius: 10px;
  background: #fff;
  flex: none;
}
.cert-text p {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--text-3);
}
.link {
  display: inline-block;
  padding: 7px 14px;
  border-radius: 10px;
  background: var(--accent-soft);
  color: var(--accent-text);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}
.proxy {
  display: flex;
  gap: 10px;
}
.proxy > div {
  flex: 1;
  padding: 8px 12px;
  border-radius: 10px;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.proxy span {
  font-size: 11px;
  color: var(--text-3);
}
.num-text {
  font-family: var(--font-num);
  font-variant-numeric: tabular-nums;
}
.proxy b {
  font-size: 17px;
  user-select: all;
}
.live {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.live-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--surface);
}
.live-text {
  flex: 1;
  font-size: 13px;
  line-height: 1.5;
}
.live-text.warn {
  color: var(--heat);
}
.ok {
  color: var(--green);
  vertical-align: -2px;
  margin-right: 4px;
}
.countdown {
  font-size: 12px;
  color: var(--text-3);
}
.cancel {
  align-self: flex-end;
  font-size: 12px;
  color: var(--text-3);
}
.note {
  margin: 0;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.6;
}
.warn {
  color: var(--heat);
}
.manual-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-3);
  align-self: flex-start;
}
.token {
  border-radius: 12px;
  background: var(--surface-2);
}
</style>
