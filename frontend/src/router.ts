import { ref } from 'vue'

export type Route = { name: 'home' } | { name: 'room' | 'wall'; room: string }

function parse(): Route {
  const m = location.hash.match(/^#\/(room|wall)\/(.+)$/)
  return m ? { name: m[1] as 'room' | 'wall', room: decodeURIComponent(m[2]) } : { name: 'home' }
}

export const route = ref<Route>(parse())
let openedFromHome = false
window.addEventListener('hashchange', () => {
  route.value = parse()
  if (route.value.name === 'home') openedFromHome = false
})

const roomHash = (name: 'room' | 'wall', room: string) => `#/${name}/${encodeURIComponent(room)}`

export function openRoom(room: string) {
  openedFromHome = true
  location.hash = roomHash('room', room)
}

/** Moving between rooms replaces the entry, so Back always returns to the overview. */
export function switchRoom(room: string) {
  const name = route.value.name === 'wall' ? 'wall' : 'room'
  history.replaceState(null, '', roomHash(name, room))
  route.value = { name, room }
}

export function goHome() {
  if (openedFromHome) {
    openedFromHome = false
    history.back()
  } else {
    history.replaceState(null, '', location.pathname)
    route.value = { name: 'home' }
  }
}

export const wallUrl = (room: string) => `${location.origin}${location.pathname}${roomHash('wall', room)}`
