<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { showFailToast } from 'vant'
import { CircleCheck } from 'lucide-vue-next'
import { api } from '../../api'
import { devices, gatewayName, loadPairing, loadRules, pairing } from '../../store'
import BindingEditor from '../BindingEditor.vue'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ close: [] }>()
const visible = computed({ get: () => props.show, set: (v) => !v && emit('close') })

const configure = ref<string | null>(null)
const starting = ref(false)
const remaining = ref(0)
let timer: number | undefined

const active = computed(() => remaining.value > 0)
const found = computed(() => (pairing.value?.found ?? []).map((id) => devices[id]).filter(Boolean))

watch(pairing, (p) => (remaining.value = p?.remaining ?? 0), { immediate: true })

onMounted(() => {
  loadPairing()
  loadRules()
  timer = window.setInterval(() => remaining.value > 0 && remaining.value--, 1000)
})
onUnmounted(() => clearInterval(timer))

async function start() {
  starting.value = true
  try {
    pairing.value = await api.startPairing(120)
  } catch (e) {
    showFailToast((e as Error).message)
  } finally {
    starting.value = false
  }
}
</script>

<template>
  <van-popup v-model:show="visible" round closeable position="bottom">
    <div class="sheet">
      <div class="sheet-title">添加子设备到「{{ gatewayName }}」</div>
      <ol class="steps">
        <li>如果设备之前接在其他网关上，先在米家 App 里把它删除，并删掉它相关的米家自动化。</li>
        <li>点下面的「开始配对」，网关会进入配对模式 2 分钟。</li>
        <li>把设备拿到网关旁边，用卡针长按配对孔约 5 秒，指示灯闪烁后松开。</li>
        <li>无线开关松开后<b>每隔两三秒按一下</b>，让它保持唤醒，直到下面的列表里出现它。</li>
        <li>点「设置控制的设备」选好要控制的灯，开关会按灯自动命名。</li>
      </ol>

      <div v-if="active" class="status">
        <span class="ring"><span /></span>
        <span>配对中，剩余 <b class="num">{{ remaining }}</b> 秒</span>
      </div>

      <div v-if="found.length" class="found card">
        <div class="found-title">本次已配对</div>
        <div v-for="d in found" :key="d.id" class="found-row">
          <CircleCheck :size="18" color="var(--green)" />
          <div class="found-name">{{ d.name }}<span>{{ d.room }}</span></div>
          <van-button v-if="d.kind === 'switch'" size="small" round type="primary" @click="configure = d.id">设置控制的设备</van-button>
        </div>
      </div>

      <div class="sheet-actions">
        <van-button block round type="primary" :loading="starting" @click="start">
          {{ active ? '重新开始 2 分钟' : found.length ? '继续添加下一个' : '开始配对' }}
        </van-button>
      </div>
    </div>
    <BindingEditor :switch-id="configure" event="click" simple @close="configure = null" />
  </van-popup>
</template>

<style scoped>
.steps {
  margin: 0;
  padding: 0 24px 4px 40px;
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.8;
}
.status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin: 16px 0 4px;
  font-size: 14px;
  color: var(--accent-text);
}
.ring {
  position: relative;
  width: 12px;
  height: 12px;
}
.ring span,
.ring::after {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: var(--accent);
}
.ring::after {
  content: '';
  animation: ping 1.4s ease-out infinite;
}
@keyframes ping {
  to {
    transform: scale(2.6);
    opacity: 0;
  }
}
.found {
  margin: 14px 16px 0;
  padding: 6px 14px;
}
.found-title {
  font-size: 12px;
  color: var(--text-3);
  padding: 8px 0 4px;
}
.found-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
}
.found-row + .found-row {
  border-top: 1px solid var(--line);
}
.found-name {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
}
.found-name span {
  margin-left: 6px;
  font-size: 12px;
  color: var(--text-3);
  font-weight: 400;
}
</style>
