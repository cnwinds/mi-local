<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showToast } from 'vant'
import { api, type Rule } from '../api'
import { EVENT_NAMES, devices, loadRules, rules } from '../store'
import RuleEditor from '../components/RuleEditor.vue'

const editing = ref<Rule | null>(null)

onMounted(loadRules)

function create() {
  editing.value = { name: '', enabled: true, trigger: { type: 'device_event', device: '', event: 'click' }, actions: [] }
}

async function toggleEnabled(rule: Rule, enabled: boolean) {
  await api.updateRule(rule.id!, { ...rule, enabled })
  await loadRules()
}

async function run(rule: Rule) {
  await api.runRule(rule.id!)
  showToast('已执行')
}

function describe(rule: Rule) {
  const sw = devices[rule.trigger.device]?.name ?? '未知开关'
  const names = rule.actions.map((a) => devices[a.device]?.name ?? '?').join('、')
  return `${EVENT_NAMES[rule.trigger.event] ?? rule.trigger.event}「${sw}」→ ${names}`
}
</script>

<template>
  <div class="rules">
    <header class="hero">
      <div class="title">自动化</div>
      <van-icon name="plus" class="add" @click="create" />
    </header>
    <div class="note">所有自动化都在家里的 NAS 上本地运行，断网也能用。</div>

    <div v-for="rule in rules" :key="rule.id" class="rule" @click="editing = rule">
      <div class="info">
        <div class="name">{{ rule.name }}</div>
        <div class="desc">{{ describe(rule) }}</div>
      </div>
      <van-icon name="play-circle-o" class="run" @click.stop="run(rule)" />
      <van-switch :model-value="rule.enabled" size="22px" @click.stop @update:model-value="(v: boolean) => toggleEnabled(rule, v)" />
    </div>

    <van-empty v-if="!rules.length" description="还没有自动化">
      <van-button round type="primary" @click="create">用无线开关控制灯</van-button>
    </van-empty>

    <RuleEditor :rule="editing" @close="editing = null" />
  </div>
</template>

<style scoped>
.hero {
  padding: calc(20px + env(safe-area-inset-top)) 20px 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 26px;
  font-weight: 700;
}
.add {
  font-size: 24px;
  color: #1f2329;
}
.note {
  font-size: 12px;
  color: #8f959e;
  padding: 0 20px 12px;
}
.rule {
  margin: 0 16px 12px;
  background: #fff;
  border-radius: 16px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.info {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 15px;
  font-weight: 500;
}
.desc {
  margin-top: 4px;
  font-size: 12px;
  color: #8f959e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.run {
  font-size: 24px;
  color: #3e7bfa;
}
</style>
