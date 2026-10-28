<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, REGIONS, STATUSES } from '../api.js'

const router = useRouter()

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
    if (status === 'interesting') await openDossier(offer)
    move(1)
  } catch (e) {
    error.value = e.message
  }
}

// dossier de candidature (vue Brouillons) : vide ici, rempli par /candidatures dans Claude Code
async function openDossier(offer, go = false) {
  try {
    const draft = await api.post(`/offers/${offer.id}/draft`)
    const created = !offer.draft_id
    offer.draft_id = draft.id
    if (offer.status === 'new') offer.status = 'interesting'
    if (go) router.push(`/brouillons/${draft.id}`)
    else if (created) message.value = `Dossier créé pour « ${offer.title.slice(0, 60)} » (à remplir avec /candidatures)`
  } catch (e) {
    error.value = e.message
  }
}

// une offre saisie à la main (candidature spontanée) n'a pas de page : son texte est dans le dossier
const hasPage = (offer) => offer.canonical_url?.startsWith('http')
function openOffer(offer) {
  if (hasPage(offer)) window.open(offer.canonical_url, '_blank', 'noopener')
  else openDossier(offer, true)
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
  if (e.key === 'o' || e.key === 'Enter') { openOffer(offer); return }
  if (e.key === 'c') { openDossier(offer, true); return }
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
    <kbd>c</kbd> dossier de candidature (créé aussi par <kbd>i</kbd>)
  </p>
  <p v-if="error" class="error">{{ error }}</p>
  <p v-else-if="message" class="ok">{{ message }}</p>
  <table>
    <thead>
      <tr><th class="num">Score</th><th>Offre</th><th>Organisation</th><th>Lieu</th><th>Contrat</th>
        <th>Date limite</th><th>CV conseillé</th><th>Statut</th><th>Dossier</th></tr>
    </thead>
    <tbody>
      <tr v-for="(o, i) in offers" :key="o.id" :ref="(el) => (rows[i] = el)"
          :class="{ selected: i === selected }" @click="selected = i">
        <td class="num">{{ o.final_score?.toFixed(2) ?? '—' }}</td>
        <td>
          <a v-if="hasPage(o)" :href="o.canonical_url" target="_blank" rel="noopener">{{ o.title }}</a>
          <a v-else href="#" title="Pas de page : ouvre le dossier (texte de l'offre)" @click.prevent="openOffer(o)">{{ o.title }}</a>
          <div v-if="o.matched_keywords.length" class="hint">{{ o.matched_keywords.join(', ') }}</div>
        </td>
        <td>{{ o.organization ?? '—' }}</td>
        <td>{{ o.location_text ?? REGIONS[o.region] }}</td>
        <td>{{ o.contract_type }}</td>
        <td :class="{ 'late-fg': daysLeft(o.deadline) !== null && daysLeft(o.deadline) < 7 }">{{ o.deadline ?? '' }}</td>
        <td>{{ o.recommended_cv ?? '—' }}</td>
        <td><span class="badge">{{ STATUSES[o.status] ?? o.status }}</span></td>
        <td>
          <RouterLink v-if="o.draft_id" :to="`/brouillons/${o.draft_id}`">ouvrir</RouterLink>
          <button v-else class="link" title="Créer le dossier de candidature (c)" @click.stop="openDossier(o, true)">créer</button>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
button.link { background: none; border: 0; padding: 0; color: var(--accent); text-decoration: underline; cursor: pointer; }
</style>
