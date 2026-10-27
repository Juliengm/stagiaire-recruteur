<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, STATUSES } from '../api.js'

const apps = ref([])
const sheet = ref('')
const dueOnly = ref(false)
const error = ref('')
const message = ref('')
const report = ref(null)

const FIELDS = ['organization', 'position', 'contact', 'cv_sent', 'status', 'sent_at', 'follow_up_at', 'notes']
const dueCount = computed(() => apps.value.filter((a) => a.follow_up_due).length)

async function load() {
  error.value = ''
  try {  // brouillons envoyés depuis Gmail : « postulé » et relance (sans bloquer la vue si Gmail échoue)
    await api.post('/drafts/sync')
  } catch (e) {
    message.value = `Synchronisation Gmail impossible : ${e.message}`
  }
  try {
    apps.value = await api.get('/applications', { sheet: sheet.value, due: dueOnly.value || '' })
  } catch (e) {
    error.value = e.message
  }
}

async function save(app, field) {
  const value = app[field] === '' ? null : app[field]
  if (field === 'status' && !value) return
  try {
    const out = await api.patch(`/applications/${app.id}`, { [field]: value })
    Object.assign(app, out)
    message.value = 'Enregistré'
  } catch (e) {
    error.value = e.message
  }
}

async function add() {
  try {
    const out = await api.post('/applications', { status: 'interesting' })
    apps.value.unshift(out)
  } catch (e) {
    error.value = e.message
  }
}

async function importFile(event) {
  const file = event.target.files[0]
  if (!file) return
  const form = new FormData()
  form.append('file', file)
  try {
    report.value = await api.post('/applications/import-xlsx', form)
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    event.target.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="bar">
    <select v-model="sheet" aria-label="Onglet" @change="load">
      <option value="">tous les onglets</option>
      <option>Madagascar</option>
      <option>Lille</option>
    </select>
    <label><input v-model="dueOnly" type="checkbox" @change="load" /> relances à faire seulement</label>
    <span class="hint">{{ apps.length }} candidature(s)</span>
    <span v-if="dueCount" class="badge warn">{{ dueCount }} relance(s) en retard</span>
    <button @click="add">Ajouter une ligne</button>
    <label class="hint">Importer le fichier Excel : <input type="file" accept=".xlsx" @change="importFile" /></label>
  </div>
  <p v-if="error" class="error">{{ error }}</p>
  <p v-else-if="message" class="ok">{{ message }}</p>
  <div v-if="report" class="hint">
    Import : {{ report.imported }} ligne(s) ajoutée(s), {{ report.already_present }} déjà présente(s).
    <ul v-if="report.skipped.length">
      <li v-for="s in report.skipped" :key="`${s.sheet}-${s.row}`">{{ s.sheet }} ligne {{ s.row ?? '—' }} : {{ s.reason }}</li>
    </ul>
  </div>
  <table>
    <thead>
      <tr><th>Onglet</th><th>Organisation</th><th>Poste visé</th><th>Contact / lien</th><th>CV envoyé</th>
        <th>Statut</th><th>Envoyée le</th><th>Relance</th><th>Notes</th></tr>
    </thead>
    <tbody>
      <tr v-for="a in apps" :key="a.id" :class="{ late: a.follow_up_due }">
        <td class="hint">{{ a.sheet ?? '' }} {{ a.sheet_row ?? '' }}</td>
        <template v-for="f in FIELDS" :key="f">
          <td v-if="f === 'status'">
            <select v-model="a.status" @change="save(a, 'status')">
              <option v-for="(label, code) in STATUSES" :key="code" :value="code">{{ label }}</option>
            </select>
          </td>
          <td v-else-if="f === 'sent_at' || f === 'follow_up_at'" :class="{ 'late-fg': f === 'follow_up_at' && a.follow_up_due }">
            <input v-model="a[f]" type="date" @change="save(a, f)" />
          </td>
          <td v-else><input v-model="a[f]" @change="save(a, f)" /></td>
        </template>
      </tr>
    </tbody>
  </table>
</template>
