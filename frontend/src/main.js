import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { Icon } from '@iconify/vue'

import App from './App.vue'
import router from './router'
import './style.css'



const app = createApp(App)
app.component('Icon', Icon)
app.use(router).use(ElementPlus).mount('#app')
