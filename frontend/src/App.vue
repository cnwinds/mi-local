<script setup lang="ts">
import { ref } from 'vue'
import HomeView from './views/HomeView.vue'
import RulesView from './views/RulesView.vue'
import DevicesView from './views/DevicesView.vue'

const tab = ref('home')
</script>

<template>
  <main class="page">
    <HomeView v-show="tab === 'home'" />
    <RulesView v-if="tab === 'rules'" />
    <DevicesView v-if="tab === 'devices'" />
  </main>
  <van-tabbar v-model="tab" safe-area-inset-bottom active-color="#3e7bfa">
    <van-tabbar-item name="home" icon="wap-home-o">家</van-tabbar-item>
    <van-tabbar-item name="rules" icon="underway-o">自动化</van-tabbar-item>
    <van-tabbar-item name="devices" icon="apps-o">设备</van-tabbar-item>
  </van-tabbar>
</template>

<style>
html,
body {
  margin: 0;
  background: #f6f7f9;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'HarmonyOS Sans SC', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
}
.page {
  padding-bottom: calc(60px + env(safe-area-inset-bottom));
  min-height: 100vh;
  box-sizing: border-box;
}
</style>
