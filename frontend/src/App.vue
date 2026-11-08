<script setup lang="ts">
import { ref, watch } from 'vue'
import HomeView from './views/HomeView.vue'
import RoomPanel from './views/RoomPanel.vue'
import SwitchesView from './views/SwitchesView.vue'
import DevicesView from './views/DevicesView.vue'
import { route } from './router'

const tab = ref('home')
watch(
  () => route.value.name,
  (name) => name !== 'home' && (tab.value = 'home'),
)
</script>

<template>
  <RoomPanel v-if="route.name === 'wall'" :room="route.room" wall class="wall-page" />
  <template v-else>
    <main class="page">
      <template v-if="tab === 'home'">
        <RoomPanel v-if="route.name === 'room'" :key="route.room" :room="route.room" />
        <HomeView v-else />
      </template>
      <SwitchesView v-if="tab === 'switches'" />
      <DevicesView v-if="tab === 'devices'" />
    </main>
    <van-tabbar v-model="tab" safe-area-inset-bottom active-color="#3e7bfa">
      <van-tabbar-item name="home" icon="wap-home-o">家</van-tabbar-item>
      <van-tabbar-item name="switches" icon="aim">开关</van-tabbar-item>
      <van-tabbar-item name="devices" icon="apps-o">设备</van-tabbar-item>
    </van-tabbar>
  </template>
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
.wall-page {
  min-height: 100vh;
}
</style>
