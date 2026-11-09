<script setup lang="ts">
import { computed } from 'vue'
import { api } from '../api'
import { cloud, voice } from '../store'
import { Mic } from 'lucide-vue-next'

const onlineSpeakers = computed(() => voice.value?.speakers.filter((s) => s.online) ?? [])
const timeFmt = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' })

const subtitle = computed(() => {
  const v = voice.value
  if (!v) return ''
  if (!cloud.value?.logged_in) return '需要登录米家账号才能听到小爱音箱'
  if (!v.enabled) return '已关闭'
  if (v.error) return `暂时连不上小爱服务：${v.error}`
  return `正在听 ${onlineSpeakers.value.length} 台音箱 · 可以说「打开${v.devices[0]}」`
})

async function toggle(enabled: boolean) {
  voice.value = await api.setVoice(enabled)
}
</script>

<template>
  <div class="voice card" v-if="voice?.devices.length">
    <div class="row">
      <div class="badge" :class="{ on: voice.active }"><Mic :size="20" /></div>
      <div class="text">
        <div class="title">小爱语音控制</div>
        <div class="sub">{{ subtitle }}</div>
      </div>
      <van-switch :model-value="voice.enabled" size="20px" @update:model-value="toggle" />
    </div>
    <div class="result" v-if="voice.last">
      {{ timeFmt.format(new Date(voice.last.ts * 1000)) }} {{ voice.last.speaker }}听到「{{ voice.last.query }}」→ {{ voice.last.reply }}
    </div>
  </div>
</template>

<style scoped>
.voice {
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
.result {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-2);
  background: var(--surface-2);
  border-radius: 10px;
  padding: 8px 12px;
}
</style>
