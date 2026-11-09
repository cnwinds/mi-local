<script setup lang="ts">
import { ref } from 'vue'
import { showFailToast } from 'vant'
import { api, type Device } from '../../api'

const emit = defineEmits<{ done: [devices: Device[]] }>()

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
    <p class="lead">鹿客门锁不支持米家，可以通过鹿客云只读接入：查看门状态、电量和开锁记录，并用开锁触发联动。不能远程开锁。</p>
    <ol class="steps">
      <li>手机装一个 HTTPS 抓包工具（iPhone 用 Stream，安卓用 HttpCanary），按提示安装并信任证书。</li>
      <li>开始抓包，打开鹿客 App 进入门锁页面，下拉刷新一次。</li>
      <li>找到 <code>device-server-2c.dding.net</code> 的请求，复制网址里 <code>access_token=</code> 后面的完整内容（很长，中间有一个冒号）。</li>
    </ol>
    <van-field v-model="token" type="textarea" rows="3" placeholder="粘贴 access_token" class="token" />
    <p class="note warn">令牌相当于家门的远程权限，只粘贴在这里，不要发给任何人。</p>
    <van-button round block type="primary" :loading="busy" loading-text="正在连接鹿客云…" :disabled="token.trim().length < 20"
      @click="submit">接入</van-button>
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
.steps {
  margin: 0;
  padding: 12px 14px 12px 32px;
  border-radius: 14px;
  background: var(--surface-2);
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.75;
}
.steps code {
  font-size: 12px;
  background: var(--surface);
  padding: 1px 4px;
  border-radius: 4px;
  word-break: break-all;
}
.token {
  border-radius: 12px;
  background: var(--surface-2);
}
.note {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
}
.warn {
  color: var(--heat);
}
</style>
