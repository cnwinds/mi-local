<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck } from 'lucide-vue-next'
import { can, cloud, deviceList } from '../../store'
import CloudCard from '../CloudCard.vue'

// A fresh install: walk the owner through getting devices in; everyone else just waits for them.
const admin = can('admin')
const steps = computed(() => [
  { title: '登录米家账号', desc: '用米家 App 扫码。设备的名称、房间和局域网密钥都从这里来', done: !!cloud.value?.logged_in },
  { title: '同步设备', desc: '登录后会自动同步一次，之后在「设备」页随时可以再同步', done: deviceList.value.length > 0 },
])
</script>

<template>
  <div class="get-started card">
    <template v-if="admin">
      <div class="title">开始使用</div>
      <ol class="steps">
        <li v-for="(s, i) in steps" :key="s.title" :class="{ done: s.done }">
          <span class="badge"><CircleCheck v-if="s.done" :size="18" /><template v-else>{{ i + 1 }}</template></span>
          <div>
            <div class="step-title">{{ s.title }}</div>
            <div class="step-desc">{{ s.desc }}</div>
          </div>
        </li>
      </ol>
      <CloudCard class="cloud" />
      <div class="later">
        之后还可以：在电脑上创建户型图；在「设备」页的「已授权设备」给家人的手机和墙上的平板配对；部署 go2rtc 后在「监控」页看摄像头。
      </div>
    </template>
    <div v-else class="waiting">还没有设备。请管理员在「设备」页登录米家并同步。</div>
  </div>
</template>

<style scoped>
.get-started {
  margin: 8px 16px 0;
  padding: 22px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.title {
  font-size: 18px;
  font-weight: 700;
}
.steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.steps li {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.badge {
  flex: none;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 650;
  background: var(--accent-soft);
  color: var(--accent-text);
}
.done .badge {
  background: color-mix(in srgb, var(--green) 14%, transparent);
  color: var(--green);
}
.step-title {
  font-size: 15px;
  font-weight: 600;
}
.done .step-title {
  color: var(--text-3);
}
.step-desc {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-3);
  margin-top: 2px;
}
.cloud {
  background: var(--surface-2);
  box-shadow: none;
}
.later {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-3);
}
.waiting {
  font-size: 14px;
  color: var(--text-2);
  text-align: center;
  padding: 12px 0;
}
@media (min-width: 900px) {
  .get-started {
    margin: 8px 0 0;
    max-width: 560px;
  }
}
</style>
