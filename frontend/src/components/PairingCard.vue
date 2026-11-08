<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { showFailToast } from 'vant'
import { api } from '../api'
import { devices, loadPairing, loadRules, pairing } from '../store'
import BindingEditor from './BindingEditor.vue'
import { Radio } from 'lucide-vue-next'

const show = ref(false)
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
  <div class="pair card" :class="{ active }">
    <div class="row">
      <div class="badge"><Radio :size="20" /></div>
      <div class="text">
        <div class="title">添加子设备</div>
        <div class="sub">{{ active ? `网关 2 配对中，剩余 ${remaining} 秒` : '把无线开关、窗帘等配对到网关 2' }}</div>
      </div>
      <van-button size="small" round type="primary" plain @click="show = true">添加</van-button>
    </div>

    <van-popup v-model:show="show" round closeable position="bottom">
      <div class="sheet">
        <div class="sheet-title">添加到网关 2</div>
        <ol class="steps">
          <li>如果设备之前接在其他网关上，先在米家 App 里把它删除，并删掉它相关的米家自动化。</li>
          <li>点下面的「开始配对」，网关 2 会进入配对模式 2 分钟。</li>
          <li>把设备拿到网关旁边，用卡针长按配对孔约 5 秒，指示灯闪烁后松开。</li>
          <li>无线开关松开后<b>每隔两三秒按一下</b>，让它保持唤醒，直到下面的列表里出现它。</li>
          <li>点「设置控制的灯」选好要控制的灯，开关会按灯自动命名。</li>
        </ol>

        <div class="status" v-if="active">
          <van-loading size="18" color="var(--accent)" />
          <span>配对中，剩余 {{ remaining }} 秒</span>
        </div>

        <van-cell-group inset v-if="found.length" title="本次已配对">
          <van-cell v-for="d in found" :key="d.id" :title="d.name" :label="d.room" icon="checked" center>
            <template #value>
              <van-button v-if="d.kind === 'switch'" size="small" round type="primary" @click="configure = d.id">设置控制的灯</van-button>
            </template>
          </van-cell>
        </van-cell-group>

        <div class="actions">
          <van-button block round type="primary" :loading="starting" @click="start">
            {{ active ? '重新开始 2 分钟' : found.length ? '继续添加下一个' : '开始配对' }}
          </van-button>
        </div>
      </div>
    </van-popup>

    <BindingEditor :switch-id="configure" event="click" simple @close="configure = null" />
  </div>
</template>

<style scoped>
.pair {
  padding: 16px;
  transition: box-shadow 0.3s;
}
.pair.active {
  box-shadow: 0 0 0 2px var(--accent), var(--shadow-1);
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
  background: var(--accent-soft);
  color: var(--accent);
}
.active .badge {
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  50% {
    box-shadow: 0 0 0 6px var(--accent-soft);
  }
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
  gap: 8px;
  margin: 12px 0;
  font-size: 14px;
  color: var(--accent);
}
.actions {
  padding: 16px 16px 0;
}
</style>
