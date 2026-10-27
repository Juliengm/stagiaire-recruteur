import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Offers from './views/Offers.vue'
import Applications from './views/Applications.vue'
import Sources from './views/Sources.vue'
const Drafts = () => import('./views/Drafts.vue')  // éditeur Tiptap : chargé à la demande
import './style.css'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/offres' },
    { path: '/offres', component: Offers },
    { path: '/candidatures', component: Applications },
    { path: '/sources', component: Sources },
    { path: '/brouillons', component: Drafts },
    { path: '/brouillons/:id', component: Drafts },
  ],
})

createApp(App).use(router).mount('#app')
