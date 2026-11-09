<script setup lang="ts">
import { computed, ref } from 'vue'
import { showFailToast } from 'vant'
import { api, type Device } from '../api'
import { cloud, voice } from '../store'
import { Mic } from 'lucide-vue-next'

const emit = defineEmits<{ edit: [device: Device] }>()

const showSetup = ref(false)
const account = ref('')
const password = ref('')
const busy = ref(false)
const added = ref<Device[]>([])

const onlineSpeakers = computed(() => voice.value?.speakers.filter((s) => s.online) ?? [])
const timeFmt = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' })

const subtitle = computed(() => {
  const v = voice.value
  if (!v) return ''
  if (!cloud.value?.logged_in) return '需要先登录米家账号'
  if (!v.devices.length) return '接入美的空调后，就能对小爱音箱说「打开××空调」'
  if (!v.enabled) return '已关闭'
  if (v.error) return `暂时连不上小爱服务：${v.error}`
  return `正在听 ${onlineSpeakers.value.length} 台音箱 · 可控制 ${v.devices.join('、')}`
})

function openSetup() {
  added.value = []
  showSetup.value = true
}

async function submit() {
  busy.value = true
  try {
    added.value = await api.setupMidea(account.value.trim(), password.value)
    password.value = ''
  } catch (e) {
    showFailToast({ message: (e as Error).message, duration: 4000 })
  } finally {
    busy.value = false
  }
}

async function toggle(enabled: boolean) {
  voice.value = await api.setVoice(enabled)
}

function editDevice(d: Device) {
  showSetup.value = false
  emit('edit', d)
}
</script>

<template>
  <div class="voice card" v-if="voice">
    <div class="row">
      <div class="badge" :class="{ on: voice.active }"><Mic :size="20" /></div>
      <div class="text">
        <div class="title">小爱语音 · 非米家设备</div>
        <div class="sub">{{ subtitle }}</div>
      </div>
      <van-switch v-if="voice.devices.length" :model-value="voice.enabled" size="20px" @update:model-value="toggle" />
    </div>
    <div class="result" v-if="voice.last">
      {{ timeFmt.format(new Date(voice.last.ts * 1000)) }} {{ voice.last.speaker }}听到「{{ voice.last.query }}」→ {{ voice.last.reply }}
    </div>
    <div class="links"><span @click="openSetup">{{ voice.devices.length ? '重新接入美的设备' : '接入美的空调' }}</span></div>

    <van-popup v-model:show="showSetup" round closeable :style="{ width: 'min(92%, 420px)' }">
      <div class="setup">
        <div class="setup-title">接入美的 / 华凌 / 小天鹅空调</div>
        <template v-if="!added.length">
          <div class="setup-tip">
            用美的美居 App 的账号登录一次，取得空调的局域网密钥。之后直接在局域网里控制空调，不经过美的云端。<b>密码只用这一次，不会保存。</b>
          </div>
          <van-cell-group inset class="form">
            <van-field v-model="account" label="手机号" placeholder="美的美居登录手机号" autocomplete="username" />
            <van-field v-model="password" type="password" label="密码" placeholder="美的美居密码" autocomplete="current-password" />
          </van-cell-group>
          <van-button round block type="primary" :loading="busy" loading-text="正在查找空调…" :disabled="!account || !password" @click="submit">
            开始接入
          </van-button>
        </template>
        <template v-else>
          <div class="setup-tip">接入成功！给它起一个和米家设备不重名的名字（例如「书房空调」），再选好房间，就可以对小爱说「打开书房空调」「书房空调调到 26 度」。</div>
          <div v-for="d in added" :key="d.id" class="added" @click="editDevice(d)">
            <span>{{ d.name }}</span><span class="added-room">{{ d.room }} · 去设置 ›</span>
          </div>
        </template>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.voice {
  padding: 16px;
}
.row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.badge {
  width: 42px;
  height: 42px;
  border-radius: 14px;
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
.title {
  font-size: 15px;
  font-weight: 600;
}
.sub {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 3px;
}
.result {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-2);
  background: var(--surface-2);
  border-radius: 10px;
  padding: 8px 12px;
}
.links {
  margin-top: 10px;
  font-size: 12px;
  color: var(--accent);
  text-align: right;
  cursor: pointer;
}
.setup {
  padding: 24px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.setup-title {
  font-weight: 600;
  text-align: center;
}
.setup-tip {
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.6;
}
.form {
  margin: 0;
}
.added {
  display: flex;
  justify-content: space-between;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--surface-2);
  cursor: pointer;
}
.added-room {
  font-size: 13px;
  color: var(--accent);
}
</style>
