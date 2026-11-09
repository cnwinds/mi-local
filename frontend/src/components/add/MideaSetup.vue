<script setup lang="ts">
import { ref } from 'vue'
import { showFailToast } from 'vant'
import { api, type Device } from '../../api'

const emit = defineEmits<{ done: [devices: Device[]] }>()

const account = ref('')
const password = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  try {
    const added = await api.setupMidea(account.value.trim(), password.value)
    password.value = ''
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
    <p class="lead">
      用美的美居 App 的账号登录一次，取得空调的局域网密钥。之后程序在局域网里直接控制空调，不经过美的云端，还能用小爱音箱语音控制。
    </p>
    <van-cell-group inset class="form">
      <van-field v-model="account" label="手机号" placeholder="美的美居登录手机号" autocomplete="username" />
      <van-field v-model="password" type="password" label="密码" placeholder="美的美居密码" autocomplete="current-password" />
    </van-cell-group>
    <p class="note">密码只用这一次，不会保存。空调需要已在美的美居里绑定，并和本机在同一个局域网。</p>
    <van-button round block type="primary" :loading="busy" loading-text="正在查找空调…" :disabled="!account || !password" @click="submit">
      开始接入
    </van-button>
  </div>
</template>

<style scoped>
.setup {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.lead {
  margin: 0;
  font-size: 14px;
  color: var(--text-2);
  line-height: 1.7;
}
.form {
  margin: 0;
}
.note {
  margin: 0;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.6;
}
</style>
