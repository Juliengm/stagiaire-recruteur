<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const views = { 1: '/offres', 2: '/candidatures', 3: '/sources', 4: '/brouillons' }

function onKey(e) {
  if (e.altKey && views[e.key]) {
    e.preventDefault()
    router.push(views[e.key])
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <header>
    <strong>Stagiaire recruteur</strong>
    <nav>
      <RouterLink to="/offres">Offres <kbd>Alt+1</kbd></RouterLink>
      <RouterLink to="/candidatures">Candidatures <kbd>Alt+2</kbd></RouterLink>
      <RouterLink to="/sources">Sources <kbd>Alt+3</kbd></RouterLink>
      <RouterLink to="/brouillons">Brouillons <kbd>Alt+4</kbd></RouterLink>
    </nav>
  </header>
  <main><RouterView /></main>
</template>
