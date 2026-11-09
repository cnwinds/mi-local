<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { showFailToast } from 'vant'
import { api, type Device } from '../api'
import { deviceList } from '../store'
import { Lock } from 'lucide-vue-next'

const emit = defineEmits<{ edit: [device: Device] }>()

const configured = ref(false)
const showSetup = ref(false)
const token = ref('')
const busy = ref(false)
const added = ref<Device[]>([])

const locks = computed(() => deviceList.value.filter((d) => d.id.startsWith('lockin.')))
const offline = computed(() => locks.value.filter((d) => !d.state.online).length)

const subtitle = computed(() => {
  if (!configured.value || !locks.value.length) return '鹿客门锁不支持米家，可以用鹿客 App 的访问令牌只读接入'
  if (offline.value) return `${offline.value} 把锁连不上鹿客云，令牌可能过期了`
  return `已接入 ${locks.value.map((d) => d.name).join('、')} · 只读`
})

onMounted(async () => {
  configured.value = (await api.lockin()).configured
})

function openSetup() {
  added.value = []
  token.value = ''
  showSetup.value = true
}

async function submit() {
  busy.value = true
  try {
    added.value = await api.setupLockin(token.value.trim())
    token.value = ''
    configured.value = true
  } catch (e) {
    showFailToast({ message: (e as Error).message, duration: 4000 })
  } finally {
    busy.value = false
  }
}

function editDevice(d: Device) {
  showSetup.value = false
  emit('edit', d)
}
</script>

<template>
  <div class="lockin card">
    <div class="row">
      <div class="badge" :class="{ on: locks.length && !offline }"><Lock :size="20" /></div>
      <div class="text">
        <div class="title">鹿客门锁</div>
        <div class="sub">{{ subtitle }}</div>
      </div>
    </div>
    <div class="links"><span @click="openSetup">{{ locks.length ? '更新令牌' : '接入门锁' }}</span></div>

    <van-popup v-model:show="showSetup" round closeable :style="{ width: 'min(92%, 460px)' }">
      <div class="setup">
        <div class="setup-title">接入鹿客门锁（只读）</div>
        <template v-if="!added.length">
          <ol class="steps">
            <li>手机装一个 HTTPS 抓包工具（iPhone 用 Stream，安卓用 HttpCanary），按它的提示安装并信任证书。</li>
            <li>开始抓包，打开鹿客 App 进入门锁页面，下拉刷新一次。</li>
            <li>在记录里找 <code>device-server-2c.dding.net</code> 的请求，复制网址里 <code>access_token=</code> 后面的完整内容（很长，中间有一个冒号）。</li>
          </ol>
          <div class="warn">这个令牌相当于家门钥匙的远程权限，只粘贴在这里，不要发给任何人。本程序只用它读取状态，从不发开锁指令。</div>
          <van-field v-model="token" type="textarea" rows="3" placeholder="粘贴 access_token" class="token" />
          <van-button round block type="primary" :loading="busy" loading-text="正在连接鹿客云…" :disabled="token.trim().length < 20"
            @click="submit">接入</van-button>
        </template>
        <template v-else>
          <div class="steps">接入成功！选好房间后，可以在门锁详情里设置「有人开锁时」自动开灯等联动。</div>
          <div v-for="d in added" :key="d.id" class="added" @click="editDevice(d)">
            <span>{{ d.name }}</span><span class="added-room">{{ d.room }} · 去设置 ›</span>
          </div>
        </template>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.lockin {
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
.steps {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.7;
}
.steps code {
  font-size: 12px;
  background: var(--surface-2);
  padding: 1px 4px;
  border-radius: 4px;
  word-break: break-all;
}
.warn {
  font-size: 12px;
  color: var(--heat);
  line-height: 1.6;
}
.token {
  border-radius: 12px;
  background: var(--surface-2);
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
