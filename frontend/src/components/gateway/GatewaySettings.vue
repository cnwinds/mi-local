<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import { ChevronDown, ChevronUp, CircleAlert, KeyRound, Router } from 'lucide-vue-next'
import { api, type GatewayCandidate } from '../../api'
import { cloud, gateway } from '../../store'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ close: [] }>()
const visible = computed({ get: () => props.show, set: (v) => !v && emit('close') })

const selected = ref('')
const ip = ref('')
const lanKey = ref('')
const saving = ref(false)
const showHelp = ref(false)

// The saved gateway stays pickable even before the first cloud sync after a restart.
const options = computed<GatewayCandidate[]>(() => {
  const g = gateway.value
  const list = [...(g?.candidates ?? [])]
  if (g?.configured && g.id && !list.some((c) => c.id === g.id)) {
    list.unshift({ id: g.id, name: g.name ?? '网关', model: g.model ?? '', ip: g.cloud_ip ?? g.ip ?? null, room: g.room ?? '', online: true, supported: true })
  }
  return list.sort((a, b) => Number(b.supported) - Number(a.supported))
})
const choice = computed(() => options.value.find((c) => c.id === selected.value))
const isCurrent = computed(() => !!gateway.value?.configured && gateway.value.id === selected.value)
const keyRequired = computed(() => !isCurrent.value || !gateway.value?.has_key)

watch(
  () => props.show,
  (show) => {
    if (!show) return
    const g = gateway.value
    selected.value = g?.configured ? g.id! : options.value.find((c) => c.supported)?.id ?? ''
    ip.value = g?.configured ? g.ip ?? '' : ''
    lanKey.value = ''
  },
)
watch(selected, (id) => {
  if (!props.show) return
  if (gateway.value?.configured && gateway.value.id === id) ip.value = gateway.value.ip ?? ''
  else ip.value = options.value.find((c) => c.id === id)?.ip ?? ''
})

async function save() {
  if (!choice.value) return
  saving.value = true
  try {
    gateway.value = await api.configureGateway({ id: selected.value, ip: ip.value.trim(), lan_key: lanKey.value.trim() })
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
      <div class="sheet-title">网关设置</div>

      <div class="block">
        <div class="label">选择网关</div>
        <div v-if="!options.length" class="empty card">
          <CircleAlert :size="18" />
          <span>{{ cloud?.logged_in ? '米家账号里没有找到网关，同步一次米家后再试' : '先在上方登录米家账号并同步，这里会列出账号里的网关' }}</span>
        </div>
        <div class="options">
          <button v-for="c in options" :key="c.id" class="option card" :class="{ selected: selected === c.id, disabled: !c.supported }"
            :disabled="!c.supported" @click="selected = c.id">
            <span class="option-icon"><Router :size="20" /></span>
            <span class="option-text">
              <span class="option-name">{{ c.name }}</span>
              <span class="option-meta">{{ c.supported ? [c.room, c.ip, c.online ? '' : '米家显示离线'].filter(Boolean).join(' · ') : `${c.model} · 不支持局域网协议` }}</span>
            </span>
            <span class="radio" />
          </button>
        </div>
      </div>

      <template v-if="choice">
        <div class="block">
          <div class="label">IP 地址</div>
          <van-field v-model="ip" class="field card" :placeholder="choice.ip ?? '例如 192.168.1.120'" inputmode="decimal" clearable />
          <div class="hint">默认用米家里记录的地址。网关换了 IP 而米家还没更新时，可以在这里手动改。</div>
        </div>

        <div class="block">
          <div class="label">局域网密钥</div>
          <van-field v-model="lanKey" class="field card" type="password" maxlength="16" autocomplete="off"
            :placeholder="keyRequired ? '16 位字母或数字' : '已设置，留空则不修改'">
            <template #left-icon><KeyRound :size="18" color="var(--text-3)" /></template>
          </van-field>
          <div v-if="keyRequired" class="hint warn">没有密钥时只能看状态和收开关事件，控制窗帘、插座和门铃都需要它。</div>
          <button class="help-toggle" @click="showHelp = !showHelp">
            怎么获取局域网密钥 <component :is="showHelp ? ChevronUp : ChevronDown" :size="14" />
          </button>
          <ol v-if="showHelp" class="help">
            <li>在米家 App 里打开这个网关，点右上角「⋯」，进入「关于」。</li>
            <li>连续快速点击页面下方的版本号区域，直到出现开发者选项。</li>
            <li>进入「局域网通信协议」，打开开关。</li>
            <li>下方显示的 16 位「密码」就是局域网密钥，填到这里。</li>
          </ol>
        </div>
      </template>

      <div class="sheet-actions">
        <van-button block round type="primary" :disabled="!choice || (keyRequired && !isCurrent && !lanKey)" :loading="saving" @click="save">
          {{ isCurrent ? '保存' : '使用这个网关' }}
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
.empty {
  display: flex;
  gap: 8px;
  padding: 14px;
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.5;
}
.options {
  display: grid;
  gap: 8px;
}
.option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  text-align: left;
  transition: box-shadow 0.15s;
}
.option.selected {
  box-shadow: 0 0 0 2px var(--accent), var(--shadow-1);
}
.option.disabled {
  opacity: 0.5;
}
.option-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  color: var(--text-3);
}
.selected .option-icon {
  background: var(--accent-soft);
  color: var(--accent);
}
.option-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.option-name {
  font-size: 15px;
  font-weight: 600;
}
.option-meta {
  font-size: 12px;
  color: var(--text-3);
  margin-top: 2px;
}
.radio {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  flex: none;
  box-shadow: inset 0 0 0 2px var(--surface-3);
}
.selected .radio {
  box-shadow: inset 0 0 0 6px var(--accent);
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
