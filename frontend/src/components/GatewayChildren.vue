<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, type Device, type GatewayChild } from '../api'
import { pairing } from '../store'
import DeviceIcon from './DeviceIcon.vue'
import { miHomeLabel } from '../naming'

const emit = defineEmits<{ edit: [device: Device] }>()

const children = ref<GatewayChild[]>([])
const loading = ref(false)
const error = ref('')

const KIND_ORDER: Record<string, number> = { switch: 0, curtain: 1, plug: 2 }
const sorted = computed(() =>
  [...children.value].sort(
    (a, b) =>
      Number(!a.device) - Number(!b.device) ||
      (KIND_ORDER[a.device?.kind ?? ''] ?? 9) - (KIND_ORDER[b.device?.kind ?? ''] ?? 9) ||
      (a.device?.name ?? '').localeCompare(b.device?.name ?? '', 'zh'),
  ),
)
const onlineCount = computed(() => children.value.filter((c) => c.online).length)

async function load() {
  loading.value = true
  try {
    children.value = await api.gatewayChildren()
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function label(c: GatewayChild) {
  const where = c.device ? `${c.device.room} · ` : ''
  const mi = c.device ? miHomeLabel(c.device) : ''
  return `${where}${c.online ? '在线' : '离线'} · …${c.sid.slice(-6)}${mi ? `\n${mi}` : ''}`
}

onMounted(load)
// A pairing session ending is when the table is most likely to have changed.
watch(() => pairing.value?.active, (active, was) => was && !active && load())
watch(() => pairing.value?.found.length, load)
</script>

<template>
  <div>
    <div class="tip">
      网关 2 自己记录的子设备，共 {{ children.length }} 个，{{ onlineCount }} 个在线。
      <span class="reload" @click="load">{{ loading ? '刷新中…' : '刷新' }}</span>
    </div>
    <div v-if="error" class="tip error">{{ error }}</div>
    <van-cell-group inset>
      <template v-for="c in sorted" :key="c.sid">
        <van-cell v-if="c.device" class="multiline" :title="c.device.name" :label="label(c)" is-link center @click="emit('edit', c.device)">
          <template #icon><DeviceIcon :kind="c.device.kind" :active="c.online" class="cell-icon" /></template>
        </van-cell>
        <van-cell v-else title="未知设备" :label="label(c)" center>
          <template #icon><DeviceIcon kind="other" class="cell-icon" /></template>
          <template #value><span class="stale">米家里没有，可能是残留</span></template>
        </van-cell>
      </template>
      <van-cell v-if="!children.length && !loading && !error" title="网关下还没有子设备" />
    </van-cell-group>
  </div>
</template>

<style scoped>
.tip {
  font-size: 12px;
  color: #8f959e;
  padding: 12px 20px 8px;
}
.error {
  color: #ee0a24;
}
.reload {
  color: #3e7bfa;
  margin-left: 6px;
}
.multiline :deep(.van-cell__label) {
  white-space: pre-line;
}
.cell-icon {
  margin-right: 12px;
  transform: scale(0.85);
}
.stale {
  font-size: 12px;
  color: #c4c7cc;
}
</style>
