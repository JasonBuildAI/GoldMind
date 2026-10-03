import { createPinia } from 'pinia'
import { createApp } from 'vue'

import ResearchPage from '@/views/research/ResearchPage.vue'

import '@/styles/tokens.css'
import '@/styles/base.css'

createApp(ResearchPage).use(createPinia()).mount('#root')
