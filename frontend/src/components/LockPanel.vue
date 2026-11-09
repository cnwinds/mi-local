<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronRight, DoorClosed, DoorOpen } from 'lucide-vue-next'
import type { Device } from '../api'
import { devices, loadRules, rules } from '../store'
import { describeAction, sinceText } from '../rooms'
import BindingEditor from './BindingEditor.vue'

const props = defineProps<{ device: Device }>()
const s = computed(() => props.device.state)
const editing = ref<string | null>(null)

const TRIGGERS: [string, string][] = [['unlock', '有人开锁时'], ['door_open', '门打开时'], ['door_close', '门关上时']]

function summary(event: string) {
  const rule = rules.value.find((r) => r.trigger.device === props.device.id && r.trigger.event === event)
  if (!rule?.actions.length) return '未设置'
  return rule.actions.map((a) => describeAction(a, devices[a.device])).join('、')
}

onMounted(loadRules)
</script>

<template>
  <div class="lock">
    <div class="hero" :class="{ open: s.door === 'open' }">
      <component :is="s.door === 'open' ? DoorOpen : DoorClosed" :size="44" :stroke-width="1.8" />
      <div class="door">{{ s.door === 'open' ? '门开着' : s.door === 'closed' ? '门已关' : '门状态未知' }}</div>
      <div class="facts">
        <span v-if="typeof s.battery === 'number'">电量 {{ s.battery }}%</span>
        <span v-if="s.lock_online === false">门锁休眠中</span>
      </div>
    </div>

    <div class="row-label">最近开锁</div>
    <div class="card-row">{{ s.last_event ? `${sinceText(s.last_event_ts)}${s.last_event}` : '暂无记录' }}</div>

    <div class="row-label">联动</div>
    <div class="links">
      <div v-for="[event, label] in TRIGGERS" :key="event" class="link" @click="editing = event">
        <span class="when">{{ label }}</span>
        <span class="what" :class="{ unset: summary(event) === '未设置' }">{{ summary(event) }}</span>
        <ChevronRight :size="16" class="arrow" />
      </div>
    </div>
    <div class="tip">门锁通过鹿客云只读接入：能看状态、做联动，不能远程开锁。状态最多延迟约 30 秒。</div>

    <BindingEditor :switch-id="editing ? device.id : null" :event="editing ?? 'unlock'" @close="editing = null" />
  </div>
</template>

<style scoped>
.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 0 8px;
  color: var(--text-2);
}
.hero.open {
  color: var(--heat);
}
.door {
  font-size: 22px;
  font-weight: 600;
}
.facts {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: var(--text-3);
}
.row-label {
  font-size: 14px;
  font-weight: 500;
  margin: 20px 0 10px;
}
.card-row {
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--surface-2);
  font-size: 14px;
}
.links {
  border-radius: 12px;
  background: var(--surface-2);
  overflow: hidden;
}
.link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 14px;
  cursor: pointer;
}
.link + .link {
  border-top: 1px solid var(--line);
}
.when {
  flex: none;
  font-size: 14px;
}
.what {
  flex: 1;
  min-width: 0;
  text-align: right;
  font-size: 13px;
  color: var(--accent-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.what.unset {
  color: var(--text-3);
}
.arrow {
  flex: none;
  color: var(--text-3);
}
.tip {
  margin-top: 16px;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.6;
}
</style>
