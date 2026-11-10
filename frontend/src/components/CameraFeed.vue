<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { VideoOff } from 'lucide-vue-next'
import { CameraPlayer, type PlayerState } from '../cameraPlayer'

const props = withDefaults(
  defineProps<{ cameraId: string; quality: 'sd' | 'hd' | 'hd3'; fit?: 'cover' | 'contain'; retry?: boolean }>(),
  { fit: 'cover', retry: true },
)
const emit = defineEmits<{ state: [state: PlayerState, error: { text: string; fatal: boolean } | null] }>()

const video = ref<HTMLVideoElement>()
const frame = ref('')
const state = ref<PlayerState>('connecting')
const error = ref<{ text: string; fatal: boolean } | null>(null)
let player: CameraPlayer | null = null

function streamUrl() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/api/cameras/${encodeURIComponent(props.cameraId)}/ws?quality=${props.quality}`
}

function start() {
  player?.stop()
  frame.value = ''
  player = new CameraPlayer(
    video.value!,
    streamUrl(),
    (s, detail) => {
      state.value = s
      error.value = s === 'error' ? (detail ?? null) : null
      emit('state', s, error.value)
    },
    (url) => (frame.value = url),
    props.retry,
  )
  player.start()
}

function stop() {
  player?.stop()
  player = null
}

// A backgrounded tab keeps nothing streaming: cameras and the hub only work while someone watches.
const onVisibility = () => (document.hidden ? stop() : start())

onMounted(() => {
  start()
  document.addEventListener('visibilitychange', onVisibility)
})
onBeforeUnmount(() => {
  stop()
  document.removeEventListener('visibilitychange', onVisibility)
})
watch(() => [props.cameraId, props.quality], start)
</script>

<template>
  <div class="feed" :class="fit">
    <video v-show="!frame" ref="video" muted playsinline autoplay disablepictureinpicture />
    <img v-if="frame" :src="frame" alt="" />
    <div v-if="state === 'connecting'" class="status"><van-loading size="22px" color="rgba(255,255,255,0.8)" /></div>
    <div v-else-if="state === 'error'" class="status">
      <VideoOff :size="22" />
      <span>{{ error?.text }}</span>
    </div>
  </div>
</template>

<style scoped>
.feed {
  position: relative;
  width: 100%;
  height: 100%;
  background: #0d0f13;
  overflow: hidden;
}
video,
img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.contain video,
.contain img {
  object-fit: contain;
}
.status {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}
</style>
