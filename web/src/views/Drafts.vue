<script setup>
// Dossiers de candidature : créés vides depuis une offre ou préparés par /candidatures, relus ici,
// déposés dans Gmail.
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

const EDITABLE = ['recipient', 'cc', 'subject', 'email_html', 'letter_html', 'cv_file', 'company_info']
const snapshot = (d) => JSON.stringify(EDITABLE.map((k) => d[k]))
const dirty = computed(() => draft.value && snapshot(draft.value) !== saved.value)
const editable = computed(() => draft.value && ['draft', 'deposited'].includes(draft.value.status))
const ccText = computed({
  get: () => (draft.value?.cc ?? []).join(', '),
  set: (v) => { draft.value.cc = v.split(/[,;\s]+/).filter(Boolean) },
})
// onglets du dossier, gardés dans l'URL ; un dossier vide s'ouvre sur l'offre
const TABS = { candidature: 'Candidature', offre: "L'offre", entreprise: "L'entreprise" }
const tab = computed({
  get: () => (TABS[route.query.onglet] ? route.query.onglet : draft.value?.empty ? 'offre' : 'candidature'),
  set: (onglet) => router.replace({ query: { ...route.query, onglet } }),
})
const announceUrl = computed(() => (offer.value?.canonical_url?.startsWith('http') ? offer.value.canonical_url : null))
const applyUrl = computed(() => draft.value?.apply_url || offer.value?.apply_url || null)
// texte de l'offre, liens cliquables (les sources d'une candidature spontanée), sans v-html
const URL_RE = /(https?:\/\/[^\s<>()"']*[^\s<>()"'.,;:!?])/
const offerParts = computed(() => (offer.value?.description ?? '').split(URL_RE)
  .map((text, i) => ({ text, link: i % 2 === 1 })))
const letterEmpty = computed(() => !draft.value?.letter_html?.replace(/<[^>]*>/g, '').trim())
const daysLeft = computed(() => (offer.value?.deadline ? (new Date(offer.value.deadline) - new Date()) / 864e5 : null))

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

// la lettre est rendue côté serveur : on enregistre d'abord pour qu'elle suive le texte affiché
async function letter(download) {
  if (!(await save())) return
  const url = `/api/drafts/${draft.value.id}/letter.pdf`
  if (download) window.location.href = `${url}?download=true`
  else window.open(url, '_blank')
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

// candidature faite ailleurs que par un dépôt Gmail (portail, formulaire) : « postulé », relance à 10 jours
async function markSent() {
  const today = new Date().toLocaleDateString('fr-CA')  // AAAA-MM-JJ
  const answer = window.prompt('Date d\'envoi de la candidature (AAAA-MM-JJ) :', today)
  if (answer === null) return
  if (!/^\d{4}-\d{2}-\d{2}$/.test(answer.trim())) { error.value = 'Date attendue au format AAAA-MM-JJ'; return }
  try {
    if (!(await save())) return
    applyServer(await api.post(`/drafts/${draft.value.id}/sent`, { sent_at: answer.trim() }))
    message.value = 'Candidature enregistrée comme envoyée : relance dans 10 jours (vue Candidatures).'
  } catch (e) {
    error.value = e.message
  }
}

// suppression à toute étape : le dossier, sa candidature ; l'offre passe en « écartée »
async function remove() {
  const gmail = ['deposited', 'sent'].includes(draft.value.status)
    ? '\n\nLe brouillon ou le message dans Gmail n\'est pas touché.' : ''
  if (!window.confirm(`Supprimer définitivement ce dossier et sa candidature ? L'offre passera en « écartée ».${gmail}`)) return
  try {
    await api.del(`/drafts/${draft.value.id}`)
    draft.value = null  // plus rien à enregistrer : pas d'alerte en quittant
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
      <span class="hint">{{ shown.length }} dossier(s) · créés depuis les offres, remplis dans Claude Code avec <code>/candidatures</code></span>
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
            <span v-if="d.empty" class="badge warn" title="Dossier créé depuis l'interface, pas encore rédigé">vide</span>
            <span v-if="d.stale" class="badge warn" title="Modifié depuis le dépôt">Gmail pas à jour</span>
          </td>
          <td class="hint">{{ new Date(d.created_at).toLocaleDateString('fr-FR') }}</td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- un dossier : en-tête (liens, points d'attention), onglets, actions -->
  <section v-else-if="draft" class="draft">
    <div class="head">
      <p><RouterLink to="/brouillons">← Dossiers</RouterLink></p>
      <h2>{{ draft.position }}
        <span class="badge">{{ DRAFT_STATUSES[draft.status] }}</span>
        <span v-if="draft.empty" class="badge warn">vide</span>
        <span v-if="draft.stale" class="badge warn" title="Modifié depuis le dépôt">Gmail pas à jour : redéposer</span>
      </h2>
      <p class="meta">
        <strong>{{ draft.organization }}</strong>
        <template v-if="offer?.location_text"> · {{ offer.location_text }}</template>
        <template v-if="offer?.deadline"> · <span :class="{ 'late-fg': daysLeft < 7 }">date limite
          {{ new Date(offer.deadline).toLocaleDateString('fr-FR') }}</span></template>
      </p>
      <p class="links">
        <a v-if="announceUrl" :href="announceUrl" target="_blank" rel="noopener">Voir l'annonce ↗</a>
        <span v-else-if="offer" class="hint">Pas d'annonce en ligne (candidature spontanée ou texte collé) :
          texte et sources dans <a href="#" @click.prevent="tab = 'offre'">l'onglet « L'offre »</a></span>
        <a v-if="applyUrl" :href="applyUrl" target="_blank" rel="noopener">Portail de candidature ↗</a>
        <span v-if="draft.recipient">E-mail à <strong>{{ draft.recipient }}</strong></span>
        <a v-if="draft.cv_file" :href="`/api/cvs/${draft.cv_file}`" target="_blank">CV joint ↗</a>
      </p>
      <div v-if="draft.required_documents || draft.weaknesses" class="notes">
        <div v-if="draft.required_documents" class="note"><strong>Pièces à joindre toi-même</strong><p>{{ draft.required_documents }}</p></div>
        <div v-if="draft.weaknesses" class="note"><strong>Points faibles face à l'offre</strong><p>{{ draft.weaknesses }}</p></div>
      </div>
      <p v-if="draft.empty" class="note">Dossier vide : lance <code>/candidatures {{ draft.offer_id ?? '' }}</code> dans
        Claude Code pour rédiger l'e-mail, la lettre et la note sur l'entreprise, ou rédige-les toi-même ici.</p>
    </div>

    <nav class="tabs">
      <button v-for="(label, code) in TABS" :key="code" type="button" :class="{ on: tab === code }" @click="tab = code">{{ label }}</button>
      <span v-if="dirty" class="hint">modifications non enregistrées</span>
      <span v-if="message" class="ok">{{ message }}</span>
      <span v-if="error" class="error">{{ error }}</span>
    </nav>

    <div v-if="checks" class="checks">
      <p v-for="c in checks.blocking" :key="c" class="error">⛔ {{ c }}</p>
      <p v-for="c in checks.warnings" :key="c">⚠️ {{ c }}</p>
      <button v-if="!checks.blocking.length" :disabled="busy" @click="deposit(true)">Déposer quand même</button>
    </div>

    <!-- v-show : les éditeurs gardent leur curseur et leur historique d'un onglet à l'autre -->
    <div v-show="tab === 'offre'" class="pane">
      <p v-if="offer?.description" class="offer-text"><template v-for="(part, i) in offerParts" :key="i"><a
        v-if="part.link" :href="part.text" target="_blank" rel="noopener">{{ part.text }}</a><template v-else>{{ part.text }}</template></template></p>
      <p v-else class="hint">Pas de texte enregistré pour cette offre.</p>
    </div>

    <div v-show="tab === 'entreprise'" class="pane">
      <p class="hint">Ce qu'on sait de l'organisation, vu sous l'angle du poste (rempli par <code>/candidatures</code>, modifiable).</p>
      <textarea v-model="draft.company_info" rows="18" :disabled="!editable" placeholder="Activité, projets, bailleurs, interlocuteurs…"></textarea>
    </div>

    <fieldset v-show="tab === 'candidature'" :disabled="!editable" class="pane">
      <label>Destinataire <input v-model="draft.recipient" type="email" placeholder="vide : candidature par portail" /></label>
      <label>Copie <input v-model="ccText" placeholder="adresses séparées par des virgules" /></label>
      <label>Objet <input v-model="draft.subject" /></label>
      <label>CV
        <select v-model="draft.cv_file">
          <option :value="null">aucun CV (prise de contact)</option>
          <option v-for="cv in cvs" :key="cv" :value="cv">{{ cv.replace('CV_Julien_Gasser_Morlay_', '').replace('.pdf', '').replaceAll('_', ' ') }}</option>
        </select>
        <a v-if="draft.cv_file" :href="`/api/cvs/${draft.cv_file}`" target="_blank">voir le CV</a>
      </label>
      <div class="row">
        <span>Lettre</span>
        <span v-if="letterEmpty" class="hint">vide : pas de lettre jointe</span>
        <span v-else class="file">{{ draft.letter_filename }}
          <a href="#" @click.prevent="letter(true)">télécharger</a>
          <a href="#" @click.prevent="letter(false)">voir</a></span>
      </div>
      <h3>E-mail</h3>
      <RichEditor v-model="draft.email_html" :editable="editable" />
      <h3>Lettre de motivation <span class="hint">({{ draft.letter_filename }}, une page au plus ; vide : pas de lettre jointe)</span></h3>
      <RichEditor v-model="draft.letter_html" page :editable="editable" />
    </fieldset>

    <div class="bar actions">
      <button :disabled="!dirty || !editable" @click="save">Enregistrer <kbd>Ctrl+S</kbd></button>
      <button v-if="draft.recipient" class="primary" :disabled="busy || !editable" @click="deposit(false)">
        {{ busy ? 'Dépôt…' : draft.gmail_draft_id ? 'Redéposer dans Gmail' : 'Déposer dans Gmail' }}</button>
      <button v-if="!draft.recipient && editable" class="primary" @click="markSent">J'ai postulé sur le portail</button>
      <button v-else-if="editable" @click="markSent" title="Envoyée autrement que par le brouillon Gmail">Marquer comme envoyée</button>
      <a v-if="draft.status === 'deposited'" href="https://mail.google.com/mail/u/0/#drafts" target="_blank">Ouvrir les brouillons Gmail</a>
      <button class="link" @click="remove">Supprimer le dossier</button>
    </div>
  </section>
  <p v-else-if="error" class="error">{{ error }}</p>
</template>

<style scoped>
.draft { max-width: 60rem; }
.head p { margin: .3rem 0; }
.head h2 { margin: .2rem 0; font-size: 1.15rem; }
.head h2 .badge { font-size: 12px; font-weight: normal; vertical-align: middle; }
.links { display: flex; flex-wrap: wrap; gap: .4rem 1.2rem; }
.notes { display: grid; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: .6rem; }
.tabs { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; border-bottom: 1px solid var(--line); margin: 1rem 0 .8rem; }
.tabs button { background: none; border: 0; border-bottom: 2px solid transparent; padding: .4rem .2rem; margin-bottom: -1px; font: inherit; cursor: pointer; color: var(--muted); }
.tabs button.on { border-bottom-color: var(--accent); color: var(--fg); font-weight: 600; }
.pane textarea { width: 100%; box-sizing: border-box; }
.offer-text { white-space: pre-wrap; line-height: 1.45; overflow-wrap: anywhere; }
.note { background: #fff8e1; border-radius: 4px; padding: .4rem .6rem; margin: .5rem 0; }
.note p { margin: .2rem 0 0; white-space: pre-wrap; }
fieldset { border: 0; padding: 0; margin: 0; display: grid; gap: .5rem; }
label { display: grid; grid-template-columns: 7rem 1fr auto; gap: .5rem; align-items: center; }
label input, label select { padding: 3px 5px; }
.row { display: grid; grid-template-columns: 7rem 1fr; gap: .5rem; align-items: center; }
.row .file a { margin-left: .8rem; }
textarea { font: inherit; padding: 4px 6px; resize: vertical; }
h3 { margin: .8rem 0 .2rem; font-size: 14px; }
.checks { border: 1px solid var(--late-fg); border-radius: 4px; padding: .4rem .8rem; margin-bottom: .6rem; }
.checks p { margin: .2rem 0; }
.actions { position: sticky; bottom: 0; background: var(--bg); border-top: 1px solid var(--line); padding: .6rem 0; margin: 1rem 0 0; }
button.primary { background: var(--accent); color: #fff; border: 1px solid var(--accent); border-radius: 4px; padding: 4px 12px; }
button.primary:disabled { opacity: .6; }
button.link { background: none; border: 0; color: var(--late-fg); text-decoration: underline; }
tr.clickable { cursor: pointer; }
tr.clickable:hover { background: var(--sel); }
</style>
