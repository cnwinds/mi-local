<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'
import { api, type PanelSize } from '../api'
import { loadPanels } from '../store'
import { panelLayout } from '../rooms'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import DeviceIcon from './DeviceIcon.vue'

const props = defineProps<{ room: string; show: boolean }>()
const emit = defineEmits<{ close: [] }>()

const visible = computed({ get: () => props.show, set: (v) => !v && emit('close') })
const SIZES: [PanelSize, string][] = [['large', '大'], ['small', '小'], ['hidden', '隐藏']]

const items = ref<ReturnType<typeof panelLayout>>([])
watch(
  () => props.show,
  (v) => v && (items.value = panelLayout(props.room).map((i) => ({ ...i }))),
)

function move(index: number, delta: number) {
  const target = index + delta
  if (target < 0 || target >= items.value.length) return
  const list = [...items.value]
  ;[list[index], list[target]] = [list[target], list[index]]
  items.value = list
}

async function save() {
  await api.setPanel(props.room, items.value.map(({ id, size }) => ({ id, size })))
  await loadPanels()
  showToast('已保存')
  emit('close')
}

async function reset() {
  await api.setPanel(props.room, [])
  await loadPanels()
  showToast('已恢复默认')
  emit('close')
}
</script>

<template>
  <van-popup v-model:show="visible" position="bottom" round :style="{ height: '80%' }">
    <div class="editor">
      <div class="bar">
        <span class="cancel" @click="emit('close')">取消</span>
        <span class="heading">编辑「{{ room }}」面板</span>
        <span class="save" @click="save">保存</span>
      </div>
      <div class="tip">「大」是可以直接操作的大卡片，「小」放在下方的小格子里，「隐藏」不在面板显示。用箭头调整顺序。</div>
      <div class="scroll">
        <div v-for="(item, i) in items" :key="item.id" class="row" :class="{ hidden: item.size === 'hidden' }">
          <DeviceIcon :kind="item.device.kind" :model="item.device.model" :name="item.device.name" :size="34" class="icon" />
          <div class="name">{{ item.device.name }}</div>
          <div class="sizes">
            <button v-for="[size, label] in SIZES" :key="size" :class="{ selected: item.size === size }"
              @click="item.size = size">{{ label }}</button>
          </div>
          <div class="order">
            <button :disabled="i === 0" @click="move(i, -1)"><ChevronUp :size="16" /></button>
            <button :disabled="i === items.length - 1" @click="move(i, 1)"><ChevronDown :size="16" /></button>
          </div>
        </div>
        <div class="reset" @click="reset">恢复默认布局</div>
      </div>
    </div>
  </van-popup>
</template>

<style scoped>
.editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px 8px;
  background: var(--surface);
}
.heading {
  font-weight: 650;
  font-size: 16px;
}
.cancel {
  color: var(--text-2);
  cursor: pointer;
}
.save {
  color: var(--accent);
  font-weight: 650;
  cursor: pointer;
}
.tip {
  background: var(--surface);
  font-size: 12px;
  color: var(--text-3);
  padding: 0 20px 14px;
  line-height: 1.6;
}
.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px 40px;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow-1);
  padding: 10px 10px 10px 12px;
  margin-bottom: 8px;
}
.row.hidden .name,
.row.hidden .icon {
  opacity: 0.35;
}
.icon {
  flex: none;
}
.name {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sizes {
  display: flex;
  background: var(--surface-2);
  border-radius: 10px;
  padding: 3px;
}
.sizes button {
  font-size: 12px;
  padding: 5px 10px;
  border-radius: 8px;
  color: var(--text-2);
}
.sizes button.selected {
  background: var(--surface);
  color: var(--accent-text);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}
.order {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.order button {
  width: 28px;
  height: 20px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-2);
  background: var(--surface-2);
}
.order button:disabled {
  opacity: 0.25;
}
.reset {
  text-align: center;
  color: var(--accent);
  font-size: 14px;
  padding: 16px;
  cursor: pointer;
}
</style>

