<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'
import { ChevronDown, ChevronUp, CircleAlert, KeyRound, Wand2 } from 'lucide-vue-next'
import { api, type GatewayCandidate } from '../../api'
import { gateway } from '../../store'

// Settings for one gateway: its address and LAN key. Which gateway is fixed by the row that opened it.
const props = defineProps<{ show: boolean; gw: GatewayCandidate }>()
const emit = defineEmits<{ close: [] }>()
const visible = computed({ get: () => props.show, set: (v) => !v && emit('close') })

const ip = ref('')
const lanKey = ref('')
const saving = ref(false)
const showHelp = ref(false)

const isCurrent = computed(() => !!gateway.value?.configured && gateway.value.id === props.gw.id)
const keyRequired = computed(() => !isCurrent.value || !gateway.value?.has_key)

watch(
  () => props.show,
  (show) => {
    if (!show) return
    ip.value = isCurrent.value ? gateway.value?.ip ?? '' : props.gw.ip ?? ''
    lanKey.value = ''
  },
)

// Newer Mi Home apps hide the key; the hub reads it from the gateway with the token the cloud sync provides.
const fetching = ref(false)
async function fetchKey() {
  fetching.value = true
  try {
    const target = { id: props.gw.id, ip: ip.value.trim() }
    let status = await api.gatewayKey(target)
    if (!status.gateway_has_key) {
      await showConfirmDialog({
        title: '网关还没有局域网密钥',
        message: '要生成一个新密钥写入网关吗？写入后网关会开启局域网协议，mi-local 就能控制窗帘、插座和门铃。',
      })
      status = await api.gatewayKey({ ...target, create: true })
    }
    gateway.value = status
    showSuccessToast('已从网关取得密钥')
    emit('close')
  } catch (e) {
    if (e instanceof Error) showFailToast(e.message)
  } finally {
    fetching.value = false
  }
}

async function save() {
  saving.value = true
  try {
    gateway.value = await api.configureGateway({ id: props.gw.id, ip: ip.value.trim(), lan_key: lanKey.value.trim() })
    showSuccessToast('已保存')
    emit('close')
  } catch (e) {
    showFailToast((e as Error).message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <van-popup v-model:show="visible" round closeable position="bottom">
    <div class="sheet">
      <div class="sheet-title">{{ gw.name }}</div>
      <div class="sheet-sub">{{ [gw.room, gw.model, gw.online ? '' : '米家显示离线'].filter(Boolean).join(' · ') }}</div>
      <div v-if="!isCurrent && gateway?.configured" class="block">
        <div class="switch-note card">
          <CircleAlert :size="18" />
          <span>已经启用了「{{ gateway.name }}」。目前同时只能用一台网关 2，启用这台会停用那台。</span>
        </div>
      </div>

      <div class="block">
        <div class="label">IP 地址</div>
        <van-field v-model="ip" class="field card" :placeholder="gw.ip ?? '例如 192.168.1.120'" inputmode="decimal" clearable />
        <div class="hint">默认用米家里记录的地址。网关换了 IP 而米家还没更新时，可以在这里手动改。</div>
      </div>

      <div class="block">
        <div class="label">局域网密钥</div>
        <van-field v-model="lanKey" class="field card" type="password" maxlength="16" autocomplete="off"
          :placeholder="keyRequired ? '16 位字母或数字' : '已设置，留空则不修改'">
          <template #left-icon><KeyRound :size="18" color="var(--text-3)" /></template>
        </van-field>
        <div v-if="keyRequired" class="hint warn">没有密钥时只能看状态和收开关事件，控制窗帘、插座和门铃都需要它。</div>
        <van-button class="fetch" block round :loading="fetching" @click="fetchKey">
          <span class="fetch-text"><Wand2 :size="16" />自动从网关获取密钥（推荐）</span>
        </van-button>
        <button class="help-toggle" @click="showHelp = !showHelp">
          这是怎么做到的 <component :is="showHelp ? ChevronUp : ChevronDown" :size="14" />
        </button>
        <ol v-if="showHelp" class="help">
          <li>同步米家时，mi-local 拿到了网关的通信 token，用它在局域网里直接向网关读取密钥，填到这里。</li>
          <li>网关还没有密钥时，会先问你，确认后生成一个 16 位密钥写入网关，同时开启局域网协议。</li>
          <li>已经有密钥的网关不会被改写，正在用这个密钥的其他系统不受影响。</li>
          <li>也可以手动填写。旧版米家 App 在网关「关于」页连续点击版本号，可以在开发者选项的「局域网通信协议」里看到；新版 App 已经去掉了这个入口。</li>
        </ol>
      </div>

      <div class="sheet-actions">
        <van-button block round type="primary" :disabled="keyRequired && !isCurrent && !lanKey" :loading="saving" @click="save">
          {{ isCurrent ? '保存' : '启用这台网关' }}
        </van-button>
      </div>
    </div>
  </van-popup>
</template>

<style scoped>
.block {
  padding: 0 16px;
  margin-top: 18px;
}
.block:first-of-type {
  margin-top: 0;
}
.label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  margin: 0 4px 8px;
}
.sheet-sub {
  margin: -10px 0 18px;
  text-align: center;
  font-size: 12px;
  color: var(--text-3);
}
.switch-note {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--warm-strong);
}
.field {
  padding: 12px 14px;
  border-radius: var(--radius);
}
.field :deep(.van-field__left-icon) {
  display: flex;
  align-items: center;
  margin-right: 8px;
}
.hint {
  font-size: 12px;
  color: var(--text-3);
  margin: 8px 4px 0;
  line-height: 1.5;
}
.hint.warn {
  color: var(--warm-strong);
}
.fetch {
  margin-top: 10px;
}
.fetch-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.help-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--accent);
  margin: 10px 4px 0;
}
.help {
  margin: 8px 0 0;
  padding: 12px 16px 12px 32px;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.8;
}
</style>
