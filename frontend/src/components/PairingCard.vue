<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { showFailToast } from 'vant'
import { api } from '../api'
import { devices, loadPairing, loadRules, pairing } from '../store'
import BindingEditor from './BindingEditor.vue'

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
  <div class="pair">
    <div class="row">
      <div>
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
          <li>用卡针长按设备上的配对孔约 5 秒，指示灯闪烁后松开。</li>
          <li>配对成功后<b>按一下开关</b>，它就会出现在下面的列表里。</li>
          <li>点「设置控制的灯」选好要控制的灯，开关会按灯自动命名。</li>
        </ol>

        <div class="status" v-if="active">
          <van-loading size="18" color="#3e7bfa" />
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

    <BindingEditor :switch-id="configure" event="click" @close="configure = null" />
  </div>
</template>

<style scoped>
.pair {
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
.sheet {
  padding: 20px 0 calc(24px + env(safe-area-inset-bottom));
}
.sheet-title {
  text-align: center;
  font-weight: 600;
  margin-bottom: 8px;
}
.steps {
  margin: 0;
  padding: 8px 24px 4px 40px;
  font-size: 13px;
  color: #646a73;
  line-height: 1.7;
}
.status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 12px 0;
  font-size: 14px;
  color: #3e7bfa;
}
.actions {
  padding: 16px 16px 0;
}
</style>
