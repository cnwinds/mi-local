<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'
import { api, type PanelSize } from '../api'
import { loadPanels } from '../store'
import { panelLayout } from '../rooms'
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
          <DeviceIcon :kind="item.device.kind" class="icon" />
          <div class="name">{{ item.device.name }}</div>
          <div class="sizes">
            <button v-for="[size, label] in SIZES" :key="size" :class="{ selected: item.size === size }"
              @click="item.size = size">{{ label }}</button>
          </div>
          <div class="order">
            <van-icon name="arrow-up" :class="{ disabled: i === 0 }" @click="move(i, -1)" />
            <van-icon name="arrow-down" :class="{ disabled: i === items.length - 1 }" @click="move(i, 1)" />
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
  background: #f6f7f9;
}
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 8px;
  background: #fff;
}
.heading {
  font-weight: 600;
}
.cancel {
  color: #646a73;
}
.save {
  color: #3e7bfa;
  font-weight: 600;
}
.tip {
  background: #fff;
  font-size: 12px;
  color: #8f959e;
  padding: 0 20px 12px;
}
.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px 40px;
}
.row {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border-radius: 14px;
  padding: 10px 12px;
  margin-bottom: 8px;
}
.row.hidden .name,
.row.hidden .icon {
  opacity: 0.4;
}
.icon {
  transform: scale(0.8);
  flex: none;
}
.name {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sizes {
  display: flex;
  background: #f0f1f4;
  border-radius: 10px;
  padding: 2px;
}
.sizes button {
  border: none;
  font: inherit;
  font-size: 12px;
  padding: 5px 9px;
  border-radius: 8px;
  background: transparent;
  color: #646a73;
}
.sizes button.selected {
  background: #fff;
  color: #3e7bfa;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
.order {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #646a73;
  font-size: 16px;
}
.order .disabled {
  opacity: 0.2;
}
.reset {
  text-align: center;
  color: #3e7bfa;
  font-size: 14px;
  padding: 16px;
}
</style>
