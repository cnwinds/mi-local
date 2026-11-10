/**
 * Live camera playback over the hub's relay to go2rtc's stream socket.
 *
 * Fragmented MP4 goes into Media Source Extensions (ManagedMediaSource on iPhone, which has no plain
 * MediaSource). Browsers that cannot decode the camera's codec get MJPEG frames instead, which go2rtc
 * transcodes on the hub: slower and heavier, but it plays everywhere.
 */

export type PlayerState = 'connecting' | 'live' | 'error'

const VIDEO_CODECS = ['avc1.640029', 'avc1.64002A', 'avc1.640033', 'hvc1.1.6.L153.B0']
const STALL_TIMEOUT = 20_000
const RECONNECT_DELAY = 5_000
const KEEP_SECONDS = 5

type MSClass = typeof MediaSource
const ManagedMS = (window as unknown as { ManagedMediaSource?: MSClass }).ManagedMediaSource
const MS: MSClass | undefined = ManagedMS ?? window.MediaSource

/** What the hub or go2rtc said went wrong, in words for the user; fatal errors are not retried. */
export function describeError(message: string): { text: string; fatal: boolean } {
  if (message.includes('unsupported model')) return { text: '这款摄像头暂不支持', fatal: true }
  if (message.includes('unavailable')) return { text: '监控服务没有运行', fatal: false }
  if (message.includes('timeout')) return { text: '摄像头没有响应', fatal: false }
  return { text: '画面加载失败', fatal: false }
}

export class CameraPlayer {
  private ws: WebSocket | null = null
  private mediaSource: MediaSource | null = null
  private mode: 'mse' | 'mjpeg' | null = null
  private stopped = false
  private stallTimer = 0
  private retryTimer = 0
  private frameUrl = ''

  private video: HTMLVideoElement
  private url: string
  private onState: (state: PlayerState, detail?: { text: string; fatal: boolean }) => void
  private onFrame: (url: string) => void
  private retry: boolean

  constructor(
    video: HTMLVideoElement,
    url: string,
    onState: (state: PlayerState, detail?: { text: string; fatal: boolean }) => void,
    onFrame: (url: string) => void,
    retry = true,
  ) {
    this.video = video
    this.url = url
    this.onState = onState
    this.onFrame = onFrame
    this.retry = retry
  }

  start() {
    this.stopped = false
    this.connect()
  }

  stop() {
    this.stopped = true
    clearTimeout(this.stallTimer)
    clearTimeout(this.retryTimer)
    this.ws?.close()
    this.ws = null
    this.video.removeAttribute('src')
    this.video.srcObject = null
    if (this.frameUrl) URL.revokeObjectURL(this.frameUrl)
    this.frameUrl = ''
  }

  private connect() {
    this.onState('connecting')
    this.mode = null
    const ws = new WebSocket(this.url)
    ws.binaryType = 'arraybuffer'
    this.ws = ws
    let feed: ((data: ArrayBuffer) => void) | null = null

    ws.onopen = () => {
      const codecs = MS ? VIDEO_CODECS.filter((c) => MS!.isTypeSupported(`video/mp4; codecs="${c}"`)) : []
      if (codecs.length) this.startMse(ws, codecs.join())
      else this.startMjpeg(ws)
      this.armStallTimer()
    }
    ws.onmessage = (ev) => {
      if (typeof ev.data !== 'string') {
        this.armStallTimer()
        if (this.mode === 'mjpeg') this.showFrame(ev.data)
        else feed?.(ev.data)
        return
      }
      const msg = JSON.parse(ev.data)
      if (msg.type === 'mse') feed = this.attachBuffer(msg.value)
      else if (msg.type === 'error') {
        // The camera's codec is not one this browser can decode: fall back to frames.
        if (this.mode === 'mse' && String(msg.value).startsWith('mse')) this.startMjpeg(ws)
        else this.fail(describeError(String(msg.value)))
      }
    }
    ws.onclose = () => {
      if (this.ws === ws && !this.stopped) this.fail(describeError('closed'))
    }
  }

  private startMse(ws: WebSocket, codecs: string) {
    this.mode = 'mse'
    const ms = new MS!()
    this.mediaSource = ms
    ms.addEventListener(
      'sourceopen',
      () => {
        if (!ManagedMS) URL.revokeObjectURL(this.video.src)
        ws.send(JSON.stringify({ type: 'mse', value: codecs }))
      },
      { once: true },
    )
    if (ManagedMS) {
      this.video.disableRemotePlayback = true
      this.video.srcObject = ms
    } else {
      this.video.src = URL.createObjectURL(ms)
    }
    this.video.play().catch(() => {})
  }

  private attachBuffer(mime: string): (data: ArrayBuffer) => void {
    const ms = this.mediaSource!
    const sb = ms.addSourceBuffer(mime)
    sb.mode = 'segments'
    const queue: ArrayBuffer[] = []
    const video = this.video
    sb.addEventListener('updateend', () => {
      if (!sb.updating && queue.length) {
        try {
          sb.appendBuffer(queue.shift()!)
        } catch {
          queue.length = 0
        }
        return
      }
      if (!sb.updating && sb.buffered.length) {
        const end = sb.buffered.end(sb.buffered.length - 1)
        const start = end - KEEP_SECONDS
        if (start > sb.buffered.start(0)) sb.remove(sb.buffered.start(0), start)
        if (video.currentTime < start) video.currentTime = start
        // Stay at the live edge: play a little faster when behind instead of piling up delay.
        const gap = end - video.currentTime
        video.playbackRate = gap > 1 ? Math.min(gap, 2) : 1
      }
    })
    video.addEventListener('playing', () => this.onState('live'), { once: true })
    return (data) => {
      if (sb.updating || queue.length) queue.push(data)
      else {
        try {
          sb.appendBuffer(data)
        } catch {
          // A full or closed buffer: the stall timer reconnects if frames stop arriving.
        }
      }
    }
  }

  private startMjpeg(ws: WebSocket) {
    this.mode = 'mjpeg'
    this.video.removeAttribute('src')
    this.video.srcObject = null
    ws.send(JSON.stringify({ type: 'mjpeg' }))
  }

  private showFrame(data: ArrayBuffer) {
    if (this.frameUrl) URL.revokeObjectURL(this.frameUrl)
    else this.onState('live')
    this.frameUrl = URL.createObjectURL(new Blob([data], { type: 'image/jpeg' }))
    this.onFrame(this.frameUrl)
  }

  private armStallTimer() {
    clearTimeout(this.stallTimer)
    this.stallTimer = window.setTimeout(() => this.fail(describeError('timeout')), STALL_TIMEOUT)
  }

  private fail(error: { text: string; fatal: boolean }) {
    if (this.stopped) return
    clearTimeout(this.stallTimer)
    const ws = this.ws
    this.ws = null
    ws?.close()
    this.onState('error', error)
    if (!error.fatal && this.retry) {
      this.retryTimer = window.setTimeout(() => !this.stopped && this.connect(), RECONNECT_DELAY)
    }
  }
}
