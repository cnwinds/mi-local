import { createApp } from 'vue'
import Vant from 'vant'
import 'vant/lib/index.css'
import './theme.css'
import App from './App.vue'
import { checkAuth, connect, me } from './store'

createApp(App).use(Vant).mount('#app')

// Only a paired browser opens the live connection; an unpaired one sees the pairing page.
async function start() {
  if (!(await checkAuth())) return setTimeout(start, 2000)
  if (me.value?.paired) connect()
}
start()
