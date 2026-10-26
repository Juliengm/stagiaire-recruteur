<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api.js'

const sources = ref([])
const health = ref({})
const kinds = ref([])
const error = ref('')
const message = ref('')
const draft = ref({ id: '', name: '', kind: 'html_list', region: 'mdg', priority: 2, config: '{\n  "url": ""\n}' })

async function load() {
  error.value = ''
  try {
    const [list, states] = await Promise.all([api.get('/sources'), api.get('/health/sources')])
    sources.value = list
    health.value = Object.fromEntries(states.map((s) => [s.id, s]))
  } catch (e) {
    error.value = e.message
  }
}

async function toggle(source) {
  try {
    Object.assign(source, await api.patch(`/sources/${source.id}`, { enabled: !source.enabled }))
    message.value = `${source.id} ${source.enabled ? 'activée' : 'désactivée'} (pris en compte au prochain passage de la mise à jour des sources)`
  } catch (e) {
    error.value = e.message
  }
}

async function run(job, sourceId) {
  error.value = ''
  try {
    const out = await api.post('/runs', { job, source_id: sourceId })
    message.value = `Lancé dans Dagster (run ${out.run_id.slice(0, 8)})`
  } catch (e) {
    error.value = e.message
  }
}

async function addSource() {
  error.value = ''
  let config
  try {
    config = JSON.parse(draft.value.config || '{}')
  } catch {
    error.value = 'Configuration : JSON invalide'
    return
  }
  try {
    await api.post('/sources', {
      id: draft.value.id, name: draft.value.name, kind: draft.value.kind,
      region: [draft.value.region], priority: Number(draft.value.priority), config,
    })
    message.value = `Source ${draft.value.id} ajoutée ; lancer « Mettre à jour la liste des sources » pour l'ingérer`
    await load()
  } catch (e) {
    error.value = e.message
  }
}

function ago(ts) {
  if (!ts) return 'jamais'
  const days = Math.floor((Date.now() - new Date(ts)) / 86400000)
  return days === 0 ? "aujourd'hui" : `il y a ${days} j`
}

onMounted(async () => {
  await load()
  kinds.value = await api.get('/sources/kinds').catch(() => [])
})
</script>

<template>
  <div class="bar">
    <button @click="run('registry')">Mettre à jour la liste des sources</button>
    <button @click="run('process')">Traiter les offres (normaliser, dédoublonner, noter)</button>
    <button @click="load">Rafraîchir</button>
    <span class="hint">{{ sources.length }} source(s), {{ sources.filter((s) => s.enabled).length }} active(s)</span>
  </div>
  <p v-if="error" class="error">{{ error }}</p>
  <p v-else-if="message" class="ok">{{ message }}</p>
  <table>
    <thead>
      <tr><th>Active</th><th>Source</th><th>Type</th><th class="num">Priorité</th><th>Zones</th>
        <th>Dernière réussite</th><th class="num">Échecs</th><th class="num">Passages à vide</th>
        <th>Dernière erreur</th><th></th></tr>
    </thead>
    <tbody>
      <tr v-for="s in sources" :key="s.id" :class="{ late: health[s.id]?.failing }">
        <td><input type="checkbox" :checked="s.enabled" :aria-label="`activer ${s.id}`" @change="toggle(s)" /></td>
        <td>
          {{ s.name ?? s.id }} <span class="hint">{{ s.id }}</span>
          <span v-if="s.origin === 'api'" class="badge">ajoutée ici</span>
        </td>
        <td>
          {{ s.kind }}
          <span v-if="kinds.length && !kinds.includes(s.kind)" class="badge">pas de connecteur</span>
        </td>
        <td class="num">{{ s.priority ?? '' }}</td>
        <td>{{ s.region.join(', ') }}</td>
        <td>{{ ago(s.last_success_at) }}</td>
        <td class="num">
          {{ s.consecutive_failures }}
          <span v-if="health[s.id]?.failing" class="badge warn">en échec</span>
        </td>
        <td class="num">
          {{ s.consecutive_empty_runs }}
          <span v-if="s.enabled && health[s.id]?.silent" class="badge warn">muette</span>
        </td>
        <td class="hint">{{ s.last_error ?? '' }}</td>
        <td><button :disabled="!s.enabled || (kinds.length && !kinds.includes(s.kind))" @click="run('ingest', s.id)">Lancer maintenant</button></td>
      </tr>
    </tbody>
  </table>

  <details>
    <summary>Ajouter une source</summary>
    <form class="bar" @submit.prevent="addSource">
      <input v-model="draft.id" placeholder="identifiant (ex. ong_x_mdg)" required pattern="[a-z0-9_]{2,64}" />
      <input v-model="draft.name" placeholder="nom" required />
      <select v-model="draft.kind"><option v-for="k in kinds" :key="k">{{ k }}</option></select>
      <select v-model="draft.region">
        <option value="mdg">Madagascar</option><option value="lille">Lille</option>
        <option value="remote">Télétravail</option><option value="global">International</option>
      </select>
      <label>priorité <input v-model="draft.priority" type="number" min="1" max="3" style="width: 3em" /></label>
      <textarea v-model="draft.config" rows="4" cols="50" aria-label="configuration JSON"></textarea>
      <button type="submit">Ajouter</button>
    </form>
    <p class="hint">La configuration attendue par chaque type est décrite dans SOURCES.md ; vérifier la source en réel avant de l'activer.</p>
  </details>
</template>
