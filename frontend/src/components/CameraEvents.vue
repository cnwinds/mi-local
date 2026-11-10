<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { History, Play } from 'lucide-vue-next'
import { api, type CameraEvent } from '../api'

const props = defineProps<{ cameraId: string }>()

const KIND_LABELS: Record<CameraEvent['kind'], string> = {
  person: '有人',
  face: '人脸',
  cry: '哭声',
  pet: '宠物',
  sound: '声音',
  motion: '画面变动',
  other: '事件',
}

const events = ref<CameraEvent[]>([])
const more = ref(false)
const loading = ref(false)
const failed = ref('')
const selected = ref<CameraEvent | null>(null)
const parts = ref<number[]>([])
const part = ref(0)
const clipError = ref('')
const video = ref<HTMLVideoElement>()

const base = computed(() => `/api/cameras/${encodeURIComponent(props.cameraId)}/events`)
const thumb = (e: CameraEvent) => `${base.value}/${e.id}/thumb.jpg?t=${Math.round(e.time * 1000)}`
const clipUrl = computed(() => (selected.value && parts.value.length ? `${base.value}/${selected.value.id}/clip/${part.value}.mp4` : ''))

const timeFmt = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
const dayFmt = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })
function dayLabel(t: number) {
  const day = new Date(t * 1000).toDateString()
  const today = new Date()
  if (day === today.toDateString()) return '今天'
  if (day === new Date(today.getTime() - 86400000).toDateString()) return '昨天'
  return dayFmt.format(new Date(t * 1000))
}
const groups = computed(() => {
  const out: { day: string; items: CameraEvent[] }[] = []
  for (const e of events.value) {
    const day = dayLabel(e.time)
    if (out[out.length - 1]?.day !== day) out.push({ day, items: [] })
    out[out.length - 1].items.push(e)
  }
  return out
})
const seconds = (d: number) => (d >= 60 ? `${Math.floor(d / 60)}分${Math.round(d % 60)}秒` : `${Math.max(1, Math.round(d))}秒`)

async function load(older = false) {
  loading.value = true
  failed.value = ''
  try {
    const last = events.value[events.value.length - 1]
    const page = await api.cameraEvents(props.cameraId, older && last ? Math.round(last.time * 1000) - 1 : undefined)
    events.value = older ? [...events.value, ...page.items] : page.items
    more.value = page.more
    if (!older && !selected.value && page.items.length) play(page.items[0], false)
  } catch (e) {
    failed.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function play(event: CameraEvent, autoplay = true) {
  selected.value = event
  parts.value = []
  part.value = 0
  clipError.value = ''
  try {
    const clip = await api.cameraEventClip(props.cameraId, event.id)
    if (selected.value !== event) return
    parts.value = clip.parts.length ? clip.parts : [event.duration]
    if (autoplay) requestAnimationFrame(() => video.value?.play().catch(() => {}))
  } catch (e) {
    if (selected.value === event) clipError.value = e instanceof Error ? e.message : '视频取不到'
  }
}

// A longer event arrives as several files; play them back to back.
function onEnded() {
  if (part.value + 1 < parts.value.length) {
    part.value += 1
    requestAnimationFrame(() => video.value?.play().catch(() => {}))
  }
}

onMounted(() => load())
watch(
  () => props.cameraId,
  () => {
    events.value = []
    selected.value = null
    load()
  },
)
</script>

<template>
  <div class="events-view">
    <div class="player">
      <video v-if="clipUrl" ref="video" :key="clipUrl" :src="clipUrl" :poster="selected ? thumb(selected) : undefined"
        controls playsinline preload="metadata" @ended="onEnded" @error="clipError = '这段视频播放不了'" />
      <img v-else-if="selected" :src="thumb(selected)" alt="" class="poster" />
      <div v-if="selected && !clipUrl && !clipError" class="overlay"><van-loading size="24px" color="rgba(255,255,255,0.8)" /></div>
      <div v-if="clipError" class="overlay">{{ clipError }}</div>
      <div v-if="!selected && !loading" class="overlay empty-player">
        <History :size="26" />
      </div>
      <div v-if="selected" class="player-caption">
        <span class="kind" :class="selected.kind">{{ KIND_LABELS[selected.kind] }}</span>
        {{ dayLabel(selected.time) }} {{ timeFmt.format(new Date(selected.time * 1000)) }}
        <span v-if="parts.length > 1" class="parts">{{ part + 1 }}/{{ parts.length }}</span>
      </div>
    </div>

    <div class="list">
      <div v-if="failed" class="note">
        {{ failed }}
        <button @click="load()">重试</button>
      </div>
      <div v-else-if="!loading && !events.length" class="note">
        最近没有看家记录。<br />在米家 App 里打开这台摄像头的「看家」，有人或有动静时会记录在这里。
      </div>
      <section v-for="g in groups" :key="g.day" class="day">
        <div class="day-label">{{ g.day }}</div>
        <button v-for="e in g.items" :key="e.id" class="event" :class="{ active: selected?.id === e.id }" @click="play(e)">
          <span class="thumb">
            <img :src="thumb(e)" alt="" loading="lazy" />
            <Play v-if="selected?.id !== e.id" :size="14" class="play" />
          </span>
          <span class="event-text">
            <span class="event-time num">{{ timeFmt.format(new Date(e.time * 1000)) }}</span>
            <span class="event-meta"><span class="kind" :class="e.kind">{{ KIND_LABELS[e.kind] }}</span>{{ seconds(e.duration) }}</span>
          </span>
        </button>
      </section>
      <van-loading v-if="loading" class="list-loading" size="20px" color="rgba(255,255,255,0.6)" />
      <button v-else-if="more" class="older" @click="load(true)">加载更早的记录</button>
    </div>
  </div>
</template>

<style scoped>
.events-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  color: #fff;
}
.player {
  position: relative;
  flex: none;
  aspect-ratio: 16 / 9;
  max-height: 56vh;
  background: #000;
}
.player video,
.poster {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}
.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  pointer-events: none;
}
.empty-player {
  color: rgba(255, 255, 255, 0.25);
}
.player-caption {
  position: absolute;
  left: 12px;
  top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.6);
  pointer-events: none;
}
.parts {
  opacity: 0.7;
}
.kind {
  padding: 1px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.14);
  color: rgba(255, 255, 255, 0.85);
  text-shadow: none;
}
.kind.person,
.kind.face {
  background: rgba(247, 168, 35, 0.22);
  color: #ffc35c;
}
.kind.cry,
.kind.sound {
  background: rgba(111, 134, 255, 0.24);
  color: #a9b8ff;
}
.list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 12px calc(16px + env(safe-area-inset-bottom));
}
.day-label {
  position: sticky;
  top: 0;
  padding: 12px 4px 8px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.55);
  background: #000;
  z-index: 1;
}
.event {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px;
  border-radius: 12px;
  text-align: left;
  color: #fff;
  transition: background 0.15s;
}
.event.active {
  background: rgba(255, 255, 255, 0.1);
}
.thumb {
  position: relative;
  flex: none;
  width: 112px;
  aspect-ratio: 16 / 9;
  border-radius: 8px;
  overflow: hidden;
  background: #16181d;
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.play {
  position: absolute;
  right: 6px;
  bottom: 6px;
  color: #fff;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.6));
}
.event-text {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.event-time {
  font-size: 15px;
  font-weight: 600;
}
.event-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}
.note {
  padding: 32px 12px;
  text-align: center;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.55);
}
.note button,
.older {
  color: #8fa2ff;
  font-size: 13px;
}
.older {
  width: 100%;
  padding: 14px;
}
.list-loading {
  display: flex;
  justify-content: center;
  padding: 16px;
}

@media (min-width: 900px) {
  .events-view {
    flex-direction: row;
  }
  .player {
    flex: 1;
    aspect-ratio: auto;
    max-height: none;
  }
  .list {
    flex: none;
    width: 340px;
    border-left: 1px solid rgba(255, 255, 255, 0.08);
  }
}
</style>
