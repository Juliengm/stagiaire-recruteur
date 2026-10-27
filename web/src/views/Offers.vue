<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api, REGIONS, STATUSES } from '../api.js'

// touche -> statut (e = entretien)
const KEYS = { n: 'new', i: 'interesting', a: 'applied', g: 'ghosted', x: 'ignored', r: 'rejected', e: 'interview' }

const filters = ref({ status: 'new', region: '', min_score: '', q: '', include_expired: false })
const offers = ref([])
const selected = ref(0)
const message = ref('')
const error = ref('')
const search = ref(null)
const rows = ref([])

async function load() {
  error.value = ''
  try {
    offers.value = await api.get('/offers', filters.value)
    selected.value = Math.min(selected.value, Math.max(offers.value.length - 1, 0))
  } catch (e) {
    error.value = e.message
  }
}

let timer
watch(filters, () => {
  clearTimeout(timer)
  timer = setTimeout(() => { selected.value = 0; load() }, 250)
}, { deep: true })

async function setStatus(offer, status) {
  try {
    const out = await api.patch(`/offers/${offer.id}/status`, { status })
    offer.status = out.status  // la ligne reste affichée jusqu'au prochain rechargement
    message.value = `« ${offer.title.slice(0, 60)} » : ${STATUSES[status]}`
    move(1)
  } catch (e) {
    error.value = e.message
  }
}

async function createApplication(offer) {
  try {
    await api.post('/applications', {
      offer_id: offer.id, organization: offer.organization, position: offer.title,
      cv_sent: offer.recommended_cv, contact: offer.canonical_url, status: 'interesting',
    })
    message.value = `Candidature créée pour « ${offer.title.slice(0, 60)} »`
  } catch (e) {
    error.value = e.message
  }
}

function move(delta) {
  if (!offers.value.length) return
  selected.value = Math.max(0, Math.min(offers.value.length - 1, selected.value + delta))
  nextTick(() => rows.value[selected.value]?.scrollIntoView({ block: 'nearest' }))
}

function onKey(e) {
  const tag = e.target.tagName
  if (e.key === 'Escape') { e.target.blur?.(); return }
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tag) || e.altKey || e.ctrlKey || e.metaKey) return
  const offer = offers.value[selected.value]
  if (e.key === '/') { e.preventDefault(); search.value.focus(); return }
  if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); move(1); return }
  if (e.key === 'k' || e.key === 'ArrowUp') { e.preventDefault(); move(-1); return }
  if (!offer) return
  if (e.key === 'o' || e.key === 'Enter') { window.open(offer.canonical_url, '_blank', 'noopener'); return }
  if (e.key === 'c') { createApplication(offer); return }
  if (KEYS[e.key]) setStatus(offer, KEYS[e.key])
}

function daysLeft(deadline) {
  return deadline ? Math.ceil((new Date(deadline) - new Date()) / 86400000) : null
}

onMounted(() => { load(); window.addEventListener('keydown', onKey) })
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="bar">
    <select v-model="filters.status" aria-label="Statut">
      <option value="">tous les statuts</option>
      <option v-for="(label, code) in STATUSES" :key="code" :value="code">{{ label }}</option>
    </select>
    <select v-model="filters.region" aria-label="Zone">
      <option value="">toutes les zones</option>
      <option v-for="(label, code) in REGIONS" :key="code" :value="code">{{ label }}</option>
    </select>
    <label>score ≥ <input v-model="filters.min_score" type="number" step="0.05" min="0" max="1" style="width: 5em" placeholder="seuil" title="Vide : seuil de config/scoring.yaml (les offres avec un statut restent affichées). 0 : tout afficher." /></label>
    <input ref="search" v-model="filters.q" type="search" placeholder="Rechercher (/)" />
    <label><input v-model="filters.include_expired" type="checkbox" /> afficher les offres expirées</label>
    <span class="hint">{{ offers.length }} offre(s)</span>
  </div>
  <p class="hint">
    <kbd>j</kbd>/<kbd>k</kbd> naviguer · <kbd>o</kbd> ouvrir · <kbd>i</kbd> intéressante · <kbd>a</kbd> envoyée ·
    <kbd>e</kbd> entretien · <kbd>g</kbd> sans réponse · <kbd>r</kbd> refusée · <kbd>x</kbd> écartée · <kbd>n</kbd> nouvelle ·
    <kbd>c</kbd> créer une candidature
  </p>
  <p v-if="error" class="error">{{ error }}</p>
  <p v-else-if="message" class="ok">{{ message }}</p>
  <table>
    <thead>
      <tr><th class="num">Score</th><th>Offre</th><th>Organisation</th><th>Lieu</th><th>Contrat</th>
        <th>Date limite</th><th>CV conseillé</th><th>Statut</th></tr>
    </thead>
    <tbody>
      <tr v-for="(o, i) in offers" :key="o.id" :ref="(el) => (rows[i] = el)"
          :class="{ selected: i === selected }" @click="selected = i">
        <td class="num">{{ o.final_score?.toFixed(2) ?? '—' }}</td>
        <td>
          <a :href="o.canonical_url" target="_blank" rel="noopener">{{ o.title }}</a>
          <div v-if="o.matched_keywords.length" class="hint">{{ o.matched_keywords.join(', ') }}</div>
        </td>
        <td>{{ o.organization ?? '—' }}</td>
        <td>{{ o.location_text ?? REGIONS[o.region] }}</td>
        <td>{{ o.contract_type }}</td>
        <td :class="{ 'late-fg': daysLeft(o.deadline) !== null && daysLeft(o.deadline) < 7 }">{{ o.deadline ?? '' }}</td>
        <td>{{ o.recommended_cv ?? '—' }}</td>
        <td><span class="badge">{{ STATUSES[o.status] ?? o.status }}</span></td>
      </tr>
    </tbody>
  </table>
</template>
