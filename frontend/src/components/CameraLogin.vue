<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showSuccessToast } from 'vant'
import { CircleAlert, Cctv } from 'lucide-vue-next'
import { api } from '../api'

// The camera service (go2rtc) keeps its own Xiaomi login. This walks the admin through it from here,
// instead of an SSH tunnel to go2rtc's own page.
const props = defineProps<{ cameras: string[] }>()
const emit = defineEmits<{ done: []; ready: [ready: boolean] }>()

const status = ref<{ running: boolean; logged_in: boolean; other_account: boolean } | null>(null)
const step = ref<'account' | 'captcha' | 'verify'>('account')
const username = ref('')
const password = ref('')
const code = ref('')
const captcha = ref('')
const verifyTo = ref('')
const busy = ref(false)
const error = ref('')

async function load() {
  status.value = await api.go2rtc().catch(() => null)
  // Until go2rtc runs and is logged in, the players would only spin on errors.
  emit('ready', !status.value || status.value.logged_in)
}
onMounted(load)

async function submit() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const fields =
      step.value === 'account'
        ? { username: username.value, password: password.value }
        : step.value === 'captcha'
          ? { captcha: code.value }
          : { verify: code.value }
    const result = await api.go2rtcLogin(fields)
    password.value = ''
    code.value = ''
    if (result.captcha) {
      captcha.value = result.captcha
      step.value = 'captcha'
    } else if (result.verify) {
      verifyTo.value = result.verify
      step.value = 'verify'
    } else {
      showSuccessToast('摄像头服务已登录，正在同步摄像头')
      step.value = 'account'
      await load()
      setTimeout(() => emit('done'), 4000)
    }
  } catch (e) {
    error.value = (e as Error).message
    // A wrong captcha or code sends go2rtc back to the start.
    if (step.value !== 'account') step.value = 'account'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="status && !status.logged_in" class="camera-login card">
    <div class="head">
      <div class="badge"><Cctv :size="18" /></div>
      <div>
        <div class="title">连接摄像头</div>
        <div class="sub">
          <template v-if="!status.running">没有检测到监控服务 go2rtc。按 README 部署后刷新本页。</template>
          <template v-else-if="status.other_account">监控服务登录的是另一个小米账号，请用米家同步的同一个账号重新登录。</template>
          <template v-else>监控服务需要用小米账号登录一次才能取到画面，请用和米家同步相同的账号。</template>
        </div>
      </div>
    </div>
    <div v-if="props.cameras.length" class="found">
      已发现 {{ props.cameras.length }} 个摄像头：{{ props.cameras.join('、') }}
    </div>

    <form v-if="status.running" class="form" @submit.prevent="submit">
      <template v-if="step === 'account'">
        <input v-model="username" autocomplete="username" placeholder="手机号、邮箱或小米 ID" />
        <input v-model="password" type="password" autocomplete="current-password" placeholder="密码" />
      </template>
      <template v-else-if="step === 'captcha'">
        <img :src="`data:image/jpeg;base64,${captcha}`" alt="图形验证码" class="captcha" />
        <input v-model="code" autocomplete="off" placeholder="输入图中的字符" />
      </template>
      <template v-else>
        <div class="hint">验证码已发送到 {{ verifyTo }}</div>
        <input v-model="code" inputmode="numeric" autocomplete="one-time-code" placeholder="收到的验证码" />
      </template>
      <div v-if="error" class="error"><CircleAlert :size="14" />{{ error }}</div>
      <div class="actions">
        <span class="note">密码只用于这一次登录，mi-local 不保存</span>
        <button class="submit" type="submit" :disabled="busy || (step === 'account' ? !username || !password : !code)">
          {{ busy ? '登录中…' : step === 'account' ? '登录' : '继续' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.camera-login {
  margin: 8px 16px 0;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.head {
  display: flex;
  gap: 12px;
}
.badge {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-soft);
  color: var(--accent);
}
.title {
  font-size: 15px;
  font-weight: 650;
}
.sub {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-3);
}
.found {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-2);
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}
.form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.form input {
  height: 42px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text);
  font: inherit;
  font-size: 15px;
  outline: none;
}
.form input:focus {
  border-color: var(--accent);
  background: var(--surface);
}
.captcha {
  align-self: flex-start;
  height: 48px;
  border-radius: 8px;
  background: #fff;
}
.hint {
  font-size: 13px;
  color: var(--text-2);
}
.error {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--danger);
}
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.note {
  font-size: 12px;
  color: var(--text-3);
}
.submit {
  height: 38px;
  padding: 0 20px;
  border-radius: var(--radius-sm);
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}
.submit:disabled {
  opacity: 0.45;
}
@media (min-width: 900px) {
  .camera-login {
    margin: 8px 0 0;
    max-width: 560px;
  }
}
</style>
