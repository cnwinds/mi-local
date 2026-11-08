import { createApp } from 'vue'
import Vant from 'vant'
import 'vant/lib/index.css'
import App from './App.vue'
import { connect } from './store'

createApp(App).use(Vant).mount('#app')
connect()
