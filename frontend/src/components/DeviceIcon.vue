<script setup lang="ts">
import { computed, type Component } from 'vue'
import {
  AirVent, BellRing, Blinds, Box, CircleDot, CookingPot, Droplets, Fish, Heater, Lightbulb, Lock, Plug,
  Router, Shirt, Speaker, WashingMachine, Wind,
} from 'lucide-vue-next'
import type { Kind } from '../api'

// tone: which accent the active state uses; defaults by kind (lights warm, AC cool).
const props = defineProps<{ kind: Kind; model?: string; active?: boolean; tone?: 'warm' | 'cool' | 'heat' | 'accent'; size?: number }>()

const BY_KIND: Partial<Record<Kind, Component>> = {
  light: Lightbulb, curtain: Blinds, plug: Plug, switch: CircleDot, doorbell: BellRing, ac: AirVent,
  bath_heater: Heater, airer: Shirt, gateway: Router, lock: Lock,
}
const BY_MODEL: [string, Component][] = [
  ['wifispeaker', Speaker], ['washer', WashingMachine], ['fishbowl', Fish], ['waterheater', Droplets],
  ['waterpuri', Droplets], ['hood', Wind], ['cooker', CookingPot], ['microwave', CookingPot], ['fan', Wind],
  ['airpurifier', Wind], ['derh', Droplets],
]

const icon = computed(() => {
  if (props.kind === 'other' && props.model) {
    const hit = BY_MODEL.find(([key]) => props.model!.includes(key))
    if (hit) return hit[1]
  }
  return BY_KIND[props.kind] ?? Box
})
const tone = computed(() => props.tone ?? ({ light: 'warm', bath_heater: 'heat', ac: 'cool', lock: 'heat' } as Record<string, string>)[props.kind] ?? 'accent')
const px = computed(() => props.size ?? 40)
</script>

<template>
  <div class="device-icon" :class="[tone, { active }]" :style="{ width: `${px}px`, height: `${px}px` }">
    <component :is="icon" :size="Math.round(px * 0.5)" :stroke-width="1.9" />
  </div>
</template>

<style scoped>
.device-icon {
  flex: none;
  border-radius: 34%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  color: var(--text-3);
  transition: background 0.25s, color 0.25s, box-shadow 0.25s;
}
.device-icon.active.warm {
  background: var(--warm);
  color: #fff;
  box-shadow: var(--shadow-warm);
}
.device-icon.active.cool {
  background: var(--cool);
  color: #fff;
}
.device-icon.active.heat {
  background: var(--heat);
  color: #fff;
}
.device-icon.active.accent {
  background: var(--accent);
  color: #fff;
}
</style>
