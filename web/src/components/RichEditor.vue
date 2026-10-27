<script setup>
// Éditeur WYSIWYG (Tiptap) : gras, italique, listes, alignement, liens. HTML en v-model.
import { onBeforeUnmount, watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import TextAlign from '@tiptap/extension-text-align'
import Link from '@tiptap/extension-link'

const props = defineProps({
  modelValue: { type: String, default: '' }, page: Boolean, editable: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])
let applying = false  // contenu posé par le parent : pas une modification de Julien

const editor = useEditor({
  content: props.modelValue,
  editable: props.editable,
  extensions: [
    StarterKit.configure({ heading: { levels: [2, 3] }, codeBlock: false, code: false, horizontalRule: false }),
    TextAlign.configure({ types: ['paragraph', 'heading'], alignments: ['left', 'right', 'justify'] }),
    Link.configure({ openOnClick: false, autolink: true }),
  ],
  onUpdate: ({ editor }) => { if (!applying) emit('update:modelValue', editor.getHTML()) },
})

watch(() => props.modelValue, (html) => {
  if (!editor.value || html === editor.value.getHTML()) return
  applying = true  // les extensions (liens) peuvent normaliser le contenu posé : on ne le renvoie pas
  editor.value.commands.setContent(html, false)
  applying = false
})
watch(() => props.editable, (on) => editor.value?.setEditable(on))
onBeforeUnmount(() => editor.value?.destroy())

function setLink() {
  const previous = editor.value.getAttributes('link').href
  const url = window.prompt('Adresse du lien (vide pour le retirer)', previous ?? 'https://')
  if (url === null) return
  if (url === '') editor.value.chain().focus().unsetLink().run()
  else editor.value.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
}

const BUTTONS = [
  { label: 'G', title: 'Gras (Ctrl+B)', run: (c) => c.toggleBold(), active: 'bold', style: 'font-weight:700' },
  { label: 'I', title: 'Italique (Ctrl+I)', run: (c) => c.toggleItalic(), active: 'italic', style: 'font-style:italic' },
  { label: '•', title: 'Liste à puces', run: (c) => c.toggleBulletList(), active: 'bulletList' },
  { label: '1.', title: 'Liste numérotée', run: (c) => c.toggleOrderedList(), active: 'orderedList' },
  { label: '⇤', title: 'Aligner à gauche', run: (c) => c.setTextAlign('left'), active: { textAlign: 'left' } },
  { label: '≡', title: 'Justifier', run: (c) => c.setTextAlign('justify'), active: { textAlign: 'justify' } },
  { label: '⇥', title: 'Aligner à droite (destinataire, date)', run: (c) => c.setTextAlign('right'), active: { textAlign: 'right' } },
]
</script>

<template>
  <div class="rich" :class="{ page }">
    <div v-if="editor && editable" class="toolbar">
      <button v-for="b in BUTTONS" :key="b.title" type="button" :title="b.title" :style="b.style"
              :class="{ on: editor.isActive(b.active) }" @click="b.run(editor.chain().focus()).run()">{{ b.label }}</button>
      <button type="button" title="Lien" :class="{ on: editor.isActive('link') }" @click="setLink">🔗</button>
      <button type="button" title="Annuler (Ctrl+Z)" @click="editor.chain().focus().undo().run()">↶</button>
      <button type="button" title="Rétablir (Ctrl+Maj+Z)" @click="editor.chain().focus().redo().run()">↷</button>
    </div>
    <EditorContent :editor="editor" class="content" />
  </div>
</template>

<style scoped>
.rich { border: 1px solid var(--line); border-radius: 4px; background: #fff; }
.toolbar { display: flex; gap: 2px; padding: 3px; border-bottom: 1px solid var(--line); background: #fafbfc; }
.toolbar button { min-width: 2em; border: 1px solid transparent; background: none; border-radius: 3px; padding: 1px 6px; }
.toolbar button:hover { border-color: var(--line); }
.toolbar button.on { background: var(--sel); border-color: var(--accent); }
.content :deep(.ProseMirror) { min-height: 8em; padding: .6rem .8rem; outline: none; }
.content :deep(.ProseMirror p) { margin: 0 0 .65em; }
/* lettre : largeur et police proches de la page A4 rendue */
.page .content :deep(.ProseMirror) { max-width: 16.6cm; margin: 0 auto; padding: 1.2rem 1.4rem;
  font: 11pt/1.42 "Liberation Sans", Helvetica, Arial, sans-serif; }
.page .content :deep(.ProseMirror p:not([style])) { text-align: justify; }
</style>
