<script setup>
// Brouillons de candidature : préparés par /candidatures, relus ici, déposés dans Gmail.
// Rien ne part d'ici : Julien envoie lui-même chaque brouillon depuis Gmail.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { api, DRAFT_STATUSES } from '../api.js'
import RichEditor from '../components/RichEditor.vue'

const route = useRoute()
const router = useRouter()

const drafts = ref([])
const filter = ref('active')
const draft = ref(null)
const offer = ref(null)
const cvs = ref([])
const saved = ref('')  // dernier état enregistré, pour repérer les modifications
const busy = ref(false)
const error = ref('')
const message = ref('')
const checks = ref(null)  // refus du dépôt : { blocking, warnings }

const EDITABLE = ['recipient', 'cc', 'subject', 'email_html', 'letter_html', 'cv_file']
const snapshot = (d) => JSON.stringify(EDITABLE.map((k) => d[k]))
const dirty = computed(() => draft.value && snapshot(draft.value) !== saved.value)
const editable = computed(() => draft.value && ['draft', 'deposited'].includes(draft.value.status))
const ccText = computed({
  get: () => (draft.value?.cc ?? []).join(', '),
  set: (v) => { draft.value.cc = v.split(/[,;\s]+/).filter(Boolean) },
})
const shown = computed(() => drafts.value.filter((d) =>
  filter.value === 'all' || (filter.value === 'active' ? ['draft', 'deposited'].includes(d.status) : d.status === filter.value)))

// réponse du serveur : on garde le texte local de l'éditeur (le serveur le nettoie à l'identique à
// chaque enregistrement) pour ne pas réinitialiser l'éditeur, son curseur et son historique
function applyServer(out) {
  const { email_html: _e, letter_html: _l, ...rest } = out
  Object.assign(draft.value, rest)
  saved.value = snapshot(draft.value)
}

async function loadList() {
  error.value = ''
  try {
    const sync = await api.post('/drafts/sync')
    if (sync.sent || sync.discarded)
      message.value = `${sync.sent} candidature(s) envoyée(s) depuis Gmail, ${sync.discarded} brouillon(s) supprimé(s)`
  } catch (e) {
    error.value = `Synchronisation Gmail impossible : ${e.message}`
  }
  try {
    drafts.value = await api.get('/drafts')
  } catch (e) {
    error.value = e.message
  }
}

async function loadDraft(id) {
  error.value = ''
  checks.value = null
  try {
    draft.value = await api.get(`/drafts/${id}`)
    saved.value = snapshot(draft.value)
    offer.value = draft.value.offer_id ? await api.get(`/offers/${draft.value.offer_id}`) : null
    if (!cvs.value.length) cvs.value = await api.get('/cvs')
  } catch (e) {
    error.value = e.message
  }
}

async function save() {
  if (!dirty.value) return true
  try {
    const body = Object.fromEntries(EDITABLE.map((k) => [k, draft.value[k]]))
    applyServer(await api.patch(`/drafts/${draft.value.id}`, body))
    message.value = 'Enregistré'
    return true
  } catch (e) {
    error.value = e.message
    return false
  }
}

async function preview() {
  if (await save()) window.open(`/api/drafts/${draft.value.id}/letter.pdf`, '_blank')
}

async function deposit(force = false) {
  const replacing = draft.value.gmail_draft_id
  const question = replacing
    ? 'Remplacer le brouillon Gmail par cette version ? Les modifications faites directement dans Gmail seront perdues.'
    : `Déposer ce brouillon dans Gmail (à ${draft.value.recipient}) ? Rien ne sera envoyé : tu l'enverras depuis Gmail.`
  if (!force && !window.confirm(question)) return
  busy.value = true
  error.value = ''
  checks.value = null
  try {
    if (!(await save())) return
    const out = await api.post(`/drafts/${draft.value.id}/deposit`, { force })
    applyServer(out.draft)
    message.value = 'Brouillon déposé dans Gmail : relis-le et envoie-le depuis Gmail.'
    window.open(out.gmail_url, '_blank')
  } catch (e) {
    if (e.status === 422 && e.detail?.blocking) checks.value = e.detail
    else error.value = e.message
  } finally {
    busy.value = false
  }
}

async function discard() {
  if (!window.confirm('Abandonner cette candidature ? (un brouillon déjà déposé reste dans Gmail)')) return
  try {
    applyServer(await api.patch(`/drafts/${draft.value.id}`, { status: 'discarded' }))
    router.push('/brouillons')
  } catch (e) {
    error.value = e.message
  }
}

function onKey(e) {
  if (draft.value && (e.ctrlKey || e.metaKey) && e.key === 's') {
    e.preventDefault()
    save()
  }
}
function beforeUnload(e) {
  if (dirty.value) e.preventDefault()
}

watch(() => route.params.id, (id) => (id ? loadDraft(id) : loadList()), { immediate: true })
onBeforeRouteLeave(() => !dirty.value || window.confirm('Modifications non enregistrées : quitter quand même ?'))
onMounted(() => { window.addEventListener('keydown', onKey); window.addEventListener('beforeunload', beforeUnload) })
onBeforeUnmount(() => { window.removeEventListener('keydown', onKey); window.removeEventListener('beforeunload', beforeUnload) })
</script>

<template>
  <!-- liste -->
  <section v-if="!route.params.id">
    <div class="bar">
      <select v-model="filter" aria-label="Statut">
        <option value="active">à relire ou dans Gmail</option>
        <option v-for="(label, code) in DRAFT_STATUSES" :key="code" :value="code">{{ label }}</option>
        <option value="all">tous</option>
      </select>
      <span class="hint">{{ shown.length }} brouillon(s) · préparés dans Claude Code avec <code>/candidatures</code></span>
      <span v-if="message" class="ok">{{ message }}</span>
      <span v-if="error" class="error">{{ error }}</span>
    </div>
    <table>
      <thead><tr><th>Poste</th><th>Organisation</th><th>CV</th><th>Destinataire</th><th>Statut</th><th>Préparé le</th></tr></thead>
      <tbody>
        <tr v-for="d in shown" :key="d.id" class="clickable" @click="router.push(`/brouillons/${d.id}`)">
          <td><RouterLink :to="`/brouillons/${d.id}`">{{ d.position }}</RouterLink></td>
          <td>{{ d.organization }}</td>
          <td class="hint">{{ d.cv_file?.replace('CV_Julien_Gasser_Morlay_', '').replace('.pdf', '') }}</td>
          <td>{{ d.recipient || 'portail' }}</td>
          <td>
            <span class="badge">{{ DRAFT_STATUSES[d.status] }}</span>
            <span v-if="d.stale" class="badge warn" title="Modifié depuis le dépôt">Gmail pas à jour</span>
          </td>
          <td class="hint">{{ new Date(d.created_at).toLocaleDateString('fr-FR') }}</td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- une candidature -->
  <section v-else-if="draft" class="draft">
    <aside>
      <p><RouterLink to="/brouillons">← Brouillons</RouterLink></p>
      <h2>{{ draft.position }}</h2>
      <p>{{ draft.organization }}<template v-if="offer"> · {{ offer.location_text }}</template></p>
      <p v-if="offer?.deadline" :class="{ 'late-fg': new Date(offer.deadline) - new Date() < 7 * 864e5 }">
        Date limite : {{ new Date(offer.deadline).toLocaleDateString('fr-FR') }}</p>
      <p v-if="offer?.canonical_url?.startsWith('http')"><a :href="offer.canonical_url" target="_blank" rel="noopener">Voir l'offre</a></p>
      <p v-if="draft.apply_url">Candidature par portail : <a :href="draft.apply_url" target="_blank" rel="noopener">{{ draft.apply_url }}</a></p>
      <div v-if="draft.required_documents" class="note"><strong>Pièces à joindre toi-même</strong><p>{{ draft.required_documents }}</p></div>
      <div v-if="draft.weaknesses" class="note"><strong>Points faibles face à l'offre</strong><p>{{ draft.weaknesses }}</p></div>
      <details v-if="offer?.description" open><summary>Texte de l'offre</summary><p class="offer-text">{{ offer.description }}</p></details>
    </aside>

    <div class="form">
      <div class="bar">
        <span class="badge">{{ DRAFT_STATUSES[draft.status] }}</span>
        <span v-if="draft.stale" class="badge warn">Gmail contient une version plus ancienne : redéposer</span>
        <span v-if="dirty" class="hint">modifications non enregistrées</span>
        <span v-if="message" class="ok">{{ message }}</span>
        <span v-if="error" class="error">{{ error }}</span>
      </div>

      <div v-if="checks" class="checks">
        <p v-for="c in checks.blocking" :key="c" class="error">⛔ {{ c }}</p>
        <p v-for="c in checks.warnings" :key="c">⚠️ {{ c }}</p>
        <button v-if="!checks.blocking.length" :disabled="busy" @click="deposit(true)">Déposer quand même</button>
      </div>

      <fieldset :disabled="!editable">
        <label>Destinataire <input v-model="draft.recipient" type="email" placeholder="vide : candidature par portail" /></label>
        <label>Copie <input v-model="ccText" placeholder="adresses séparées par des virgules" /></label>
        <label>Objet <input v-model="draft.subject" /></label>
        <label>CV
          <select v-model="draft.cv_file">
            <option v-for="cv in cvs" :key="cv" :value="cv">{{ cv.replace('CV_Julien_Gasser_Morlay_', '').replace('.pdf', '').replaceAll('_', ' ') }}</option>
          </select>
          <a v-if="draft.cv_file" :href="`/api/cvs/${draft.cv_file}`" target="_blank">voir le CV</a>
        </label>

        <h3>E-mail</h3>
        <RichEditor v-model="draft.email_html" :editable="editable" />
        <h3>Lettre de motivation <span class="hint">({{ draft.letter_filename }}, une page au plus)</span></h3>
        <RichEditor v-model="draft.letter_html" page :editable="editable" />
      </fieldset>

      <div class="bar actions">
        <button :disabled="!dirty || !editable" @click="save">Enregistrer <kbd>Ctrl+S</kbd></button>
        <button @click="preview">Aperçu de la lettre (PDF)</button>
        <button v-if="draft.recipient" class="primary" :disabled="busy || !editable" @click="deposit(false)">
          {{ busy ? 'Dépôt…' : draft.gmail_draft_id ? 'Redéposer dans Gmail' : 'Déposer dans Gmail' }}</button>
        <a v-if="draft.status === 'deposited'" href="https://mail.google.com/mail/u/0/#drafts" target="_blank">Ouvrir les brouillons Gmail</a>
        <button v-if="editable" class="link" @click="discard">Abandonner</button>
      </div>
    </div>
  </section>
  <p v-else-if="error" class="error">{{ error }}</p>
</template>

<style scoped>
.draft { display: grid; grid-template-columns: minmax(16rem, 1fr) 2.2fr; gap: 1.5rem; align-items: start; }
aside { position: sticky; top: .5rem; max-height: calc(100vh - 5rem); overflow: auto; }
aside h2 { margin: .2rem 0; font-size: 1.1rem; }
.offer-text { white-space: pre-wrap; font-size: 12px; color: var(--muted); }
.note { background: #fff8e1; border-radius: 4px; padding: .4rem .6rem; margin: .5rem 0; }
.note p { margin: .2rem 0 0; white-space: pre-wrap; }
fieldset { border: 0; padding: 0; margin: 0; display: grid; gap: .5rem; }
label { display: grid; grid-template-columns: 7rem 1fr auto; gap: .5rem; align-items: center; }
label input, label select { padding: 3px 5px; }
h3 { margin: .8rem 0 .2rem; font-size: 14px; }
.checks { border: 1px solid var(--late-fg); border-radius: 4px; padding: .4rem .8rem; margin-bottom: .6rem; }
.checks p { margin: .2rem 0; }
.actions { margin-top: 1rem; }
button.primary { background: var(--accent); color: #fff; border: 1px solid var(--accent); border-radius: 4px; padding: 4px 12px; }
button.primary:disabled { opacity: .6; }
button.link { background: none; border: 0; color: var(--late-fg); text-decoration: underline; }
tr.clickable { cursor: pointer; }
tr.clickable:hover { background: var(--sel); }
@media (max-width: 900px) { .draft { grid-template-columns: 1fr; } aside { position: static; max-height: none; } }
</style>
