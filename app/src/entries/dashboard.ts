import { createPinia } from 'pinia'
import { createApp } from 'vue'

import DashboardPage from '@/views/dashboard/DashboardPage.vue'

import '@/styles/tokens.css'
import '@/styles/base.css'

createApp(DashboardPage).use(createPinia()).mount('#root')
