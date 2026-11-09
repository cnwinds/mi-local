<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ChevronRight, RefreshCw } from 'lucide-vue-next'
import { api, type Device, type GatewayChild } from '../../api'
import { pairing } from '../../store'
import DeviceIcon from '../DeviceIcon.vue'
import { miHomeLabel } from '../../naming'

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

onMounted(load)
// A pairing session ending is when the table is most likely to have changed.
watch(() => pairing.value?.active, (active, was) => was && !active && load())
watch(() => pairing.value?.found.length, load)
</script>

<template>
  <div>
    <div class="tip">
      <span>网关自己记录的子设备 {{ children.length }} 个，{{ onlineCount }} 个在线</span>
      <button class="reload" :class="{ spinning: loading }" title="刷新" @click="load"><RefreshCw :size="14" /></button>
    </div>
    <div v-if="error" class="tip error">{{ error }}</div>
    <div v-if="sorted.length" class="list card">
      <template v-for="c in sorted" :key="c.sid">
        <div v-if="c.device" class="item" @click="emit('edit', c.device)">
          <DeviceIcon :kind="c.device.kind" :model="c.device.model" :name="c.device.name" :size="36" :class="{ dim: !c.online }" />
          <div class="text">
            <div class="name">{{ c.device.name }}</div>
            <div class="meta"><span class="dot" :class="{ on: c.online }" />{{ c.device.room }} · {{ c.online ? '在线' : '离线' }} · …{{ c.sid.slice(-6) }}</div>
            <div v-if="miHomeLabel(c.device)" class="meta">{{ miHomeLabel(c.device) }}</div>
          </div>
          <ChevronRight :size="18" class="arrow" />
        </div>
        <div v-else class="item stale">
          <DeviceIcon kind="other" :size="36" class="dim" />
          <div class="text">
            <div class="name">未知设备</div>
            <div class="meta">米家里没有，可能是残留 · …{{ c.sid.slice(-6) }}</div>
          </div>
        </div>
      </template>
    </div>
    <van-empty v-else-if="!loading && !error" description="网关下还没有子设备" />
  </div>
</template>

<style scoped>
.tip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-3);
  padding: 0 4px 8px;
}
.error {
  color: var(--danger);
}
.reload {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
}
.spinning svg {
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.list {
  overflow: hidden;
}
.item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  cursor: pointer;
}
.item + .item {
  border-top: 1px solid var(--line);
}
.item.stale {
  cursor: default;
}
.dim {
  opacity: 0.4;
  filter: grayscale(1);
}
.text {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 14px;
  font-weight: 500;
}
.stale .name {
  color: var(--text-3);
}
.meta {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-3);
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-3);
  opacity: 0.5;
}
.dot.on {
  background: var(--green);
  opacity: 1;
}
.arrow {
  color: var(--text-3);
  flex: none;
}
</style>
