<script setup lang="ts">
import { computed, ref, watch, type Component } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import { AirVent, ChevronLeft, ChevronRight, CircleCheck, Cloud, Lock, Router } from 'lucide-vue-next'
import { api, type Device } from '../../api'
import { cloud, deviceList, gateway, loadCloud } from '../../store'
import PairingSheet from '../gateway/PairingSheet.vue'
import MideaSetup from './MideaSetup.vue'
import LockinSetup from './LockinSetup.vue'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ close: []; edit: [device: Device] }>()

type Step = 'menu' | 'midea' | 'lockin' | 'done'
const step = ref<Step>('menu')
const added = ref<Device[]>([])
const syncing = ref(false)
const showPairing = ref(false)

const open = computed({
  get: () => props.show,
  set: (v) => !v && emit('close'),
})
watch(
  () => props.show,
  (v) => {
    if (v) {
      step.value = 'menu'
      added.value = []
    }
  },
)

const count = (prefix: string) => deviceList.value.filter((d) => d.id.startsWith(prefix)).length
const lockinBroken = computed(() => deviceList.value.some((d) => d.id.startsWith('lockin.') && !d.state.online))

interface Option {
  key: string
  icon: Component
  title: string
  desc: string
  badge?: string
  warn?: boolean
  disabled?: boolean
  run: () => void
}

const sections = computed<{ title: string; items: Option[] }[]>(() => [
  {
    title: '米家设备',
    items: [
      {
        key: 'mihome',
        icon: Cloud,
        title: '米家 App 里的设备',
        desc: cloud.value?.logged_in ? 'Wi-Fi 灯、空调、家电等，先在米家 App 添加好，再点这里同步过来' : '先在「设备」页登录米家账号',
        disabled: !cloud.value?.logged_in,
        run: sync,
      },
      {
        key: 'zigbee',
        icon: Router,
        title: '网关子设备',
        desc: gateway.value?.configured ? '无线开关、窗帘电机、插座、传感器，让网关进入配对模式后按设备上的配对键' : '先在设备列表的「网关」里完成配置',
        disabled: !gateway.value?.configured,
        run: () => (showPairing.value = true),
      },
    ],
  },
  {
    title: '其他品牌',
    items: [
      {
        key: 'midea',
        icon: AirVent,
        title: '美的 / 华凌 / 小天鹅空调',
        desc: '用美的美居账号取一次密钥，之后局域网直接控制，也能用小爱音箱语音控制',
        badge: count('midea.') ? `已接入 ${count('midea.')} 台` : undefined,
        run: () => (step.value = 'midea'),
      },
      {
        key: 'lockin',
        icon: Lock,
        title: '鹿客门锁',
        desc: '只读接入：门状态、电量、开锁记录和开锁联动',
        badge: count('lockin.') ? (lockinBroken.value ? '令牌失效，点此更新' : '已接入') : undefined,
        warn: lockinBroken.value,
        run: () => (step.value = 'lockin'),
      },
    ],
  },
])

const STEP_TITLES: Record<Step, string> = { menu: '添加设备', midea: '美的空调', lockin: '鹿客门锁', done: '接入成功' }

async function sync() {
  syncing.value = true
  try {
    const s = await api.cloudSync()
    const n = s.added.length
    showSuccessToast(n ? `新增 ${n} 台设备` : '没有新设备')
    if (n) emit('close')
  } catch (e) {
    showFailToast((e as Error).message)
  } finally {
    syncing.value = false
    loadCloud()
  }
}

function finished(devices: Device[]) {
  added.value = devices
  step.value = 'done'
}

function editDevice(d: Device) {
  emit('close')
  emit('edit', d)
}
</script>

<template>
  <van-popup v-model:show="open" position="bottom" round closeable class="add-sheet">
    <div class="body">
      <div class="bar">
        <button v-if="step === 'midea' || step === 'lockin'" class="back" @click="step = 'menu'"><ChevronLeft :size="22" /></button>
        <span class="heading">{{ STEP_TITLES[step] }}</span>
      </div>

      <template v-if="step === 'menu'">
        <p class="hint">选择设备从哪里来</p>
        <section v-for="sec in sections" :key="sec.title">
          <div class="section-label">{{ sec.title }}</div>
          <div class="options">
            <button v-for="o in sec.items" :key="o.key" class="option" :disabled="o.disabled || (o.key === 'mihome' && syncing)"
              @click="o.run()">
              <span class="icon"><component :is="o.icon" :size="22" /></span>
              <span class="text">
                <span class="title">{{ o.title }}<span v-if="o.badge" class="badge" :class="{ warn: o.warn }">{{ o.badge }}</span></span>
                <span class="desc">{{ o.key === 'mihome' && syncing ? '正在同步…' : o.desc }}</span>
              </span>
              <ChevronRight :size="18" class="chev" />
            </button>
          </div>
        </section>
      </template>

      <MideaSetup v-else-if="step === 'midea'" @done="finished" />
      <LockinSetup v-else-if="step === 'lockin'" @done="finished" />

      <div v-else class="done">
        <CircleCheck :size="52" color="var(--green)" />
        <p>接入成功！给设备选好房间、起个好认的名字就能用了。</p>
        <button v-for="d in added" :key="d.id" class="option" @click="editDevice(d)">
          <span class="text"><span class="title">{{ d.name }}</span><span class="desc">{{ d.room }} · 去设置</span></span>
          <ChevronRight :size="18" class="chev" />
        </button>
        <van-button round block @click="emit('close')">完成</van-button>
      </div>
    </div>
    <PairingSheet :show="showPairing" @close="showPairing = false" />
  </van-popup>
</template>

<style scoped>
.body {
  padding: 20px 20px calc(24px + env(safe-area-inset-bottom));
  max-height: 88vh;
  overflow-y: auto;
}
@media (min-width: 640px) {
  .add-sheet {
    width: 560px;
    right: 0;
    margin: 0 auto;
  }
}
.bar {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 32px;
  margin-bottom: 4px;
}
.back {
  margin-left: -8px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-2);
}
.heading {
  font-size: 19px;
  font-weight: 650;
}
.hint {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--text-3);
}
.section-label {
  margin: 18px 0 8px;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.option {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border-radius: 16px;
  background: var(--surface-2);
  text-align: left;
  transition: background 0.15s;
}
.option:not(:disabled):active {
  background: var(--surface-3);
}
@media (hover: hover) {
  .option:not(:disabled):hover {
    background: var(--surface-3);
  }
}
.option:disabled {
  opacity: 0.5;
  cursor: default;
}
.icon {
  flex: none;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  color: var(--accent);
}
.text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.badge {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 8px;
  background: var(--accent-soft);
  color: var(--accent-text);
}
.badge.warn {
  background: var(--warm-soft);
  color: var(--warm-strong);
}
.desc {
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.5;
}
.chev {
  flex: none;
  color: var(--text-3);
}
.done {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding-top: 8px;
}
.done p {
  margin: 0 0 4px;
  font-size: 14px;
  color: var(--text-2);
  text-align: center;
}
</style>
