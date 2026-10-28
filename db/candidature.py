"""Candidatures : contrôles des textes, rendu de la lettre, brouillon e-mail (partagé API / scripts).

Les faits autorisés et les termes interdits sont lus dans `cv/` (hors dépôt) : rien de personnel ici.
WeasyPrint et pypdf ne sont importés qu'au rendu de la lettre.
"""
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from email.message import EmailMessage
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

# nombres écrits « 1 285 », « 110 000+ », « 0,8 » : espaces (y compris insécables) entre milliers
_NUMBER = re.compile(r"\d{1,3}(?:[   ]\d{3})+|\d+(?:[.,]\d+)?")
_YEAR = re.compile(r"(19|20)\d\d")
# mots d'annonce qui ne font pas partie de l'intitulé (« Recrutement d'un(e) … »)
_NOISE = {"recrutement", "recrute", "recherche", "poste", "avis", "appel", "candidatures", "offre",
          "hiring", "vacancy", "position", "call", "for", "the", "of", "and", "in", "un", "une", "de",
          "du", "des", "la", "le", "les", "et", "en", "au", "aux", "pour"}
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path: Path) -> str:
    """Paragraphes du corps du document (tableaux compris), un par ligne."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = ("".join(t.text or "" for t in p.iter(f"{_W}t")).strip() for p in root.iter(f"{_W}p"))
    return "\n".join(p for p in paragraphs if p)


def slug(text: str, max_len: int = 40) -> str:
    """« Banque mondiale – Antananarivo » → « Banque_mondiale_Antananarivo » (noms de fichiers)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "_".join(re.findall(r"[A-Za-z0-9]+", ascii_text))[:max_len].strip("_") or "sans_nom"


def words(text: str) -> set[str]:
    """Mots sans accents ni casse, deux lettres au moins (« RIZ+ » → {"riz"})."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z0-9]+", ascii_text) if len(w) >= 2}


def mentions(name: str, text: str, *, share: float) -> bool:
    """`text` reprend-il au moins `share` des mots significatifs de `name` (hors parenthèses) ?"""
    wanted = {w for w in words(re.sub(r"\([^)]*\)", " ", name))
              if w not in _NOISE and not w.isdigit()}
    return not wanted or len(wanted & words(text)) / len(wanted) >= share


def load_forbidden(path: Path) -> list[re.Pattern[str]]:
    """Une expression régulière par ligne (insensible à la casse) ; `#` = commentaire."""
    lines = path.read_text(encoding="utf8").splitlines()
    return [re.compile(line.strip(), re.IGNORECASE) for line in lines
            if line.strip() and not line.lstrip().startswith("#")]


def numbers(text: str) -> set[str]:
    return {re.sub(r"[   ]", "", n).replace(",", ".") for n in _NUMBER.findall(text)}


class _Text(HTMLParser):
    BREAKS = frozenset({"p", "br", "li", "ul", "ol", "h1", "h2", "h3", "div", "blockquote"})

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BREAKS - {"br", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str) -> str:
    """Version texte d'un e-mail ou d'une lettre HTML (contrôles, partie text/plain)."""
    parser = _Text()
    parser.feed(html)
    text = re.sub(r"[ \t]+\n", "\n", "".join(parser.parts))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


@dataclass
class Checks:
    blocking: list[str] = field(default_factory=list)  # empêchent le dépôt
    warnings: list[str] = field(default_factory=list)  # à confirmer par Julien


def check_texts(texts: dict[str, str], *, forbidden: list[re.Pattern[str]], organization: str | None,
                title: str, allowed_sources: list[str]) -> Checks:
    """Contrôles avant dépôt (textes en clair, pas en HTML).

    Bloquant : terme ou tournure interdits. Avertissements : organisation ou intitulé absents,
    nombre absent des faits, du CV et de l'offre (chiffre peut-être inventé), hors années.
    """
    checks = Checks()
    for name, text in texts.items():
        for pattern in forbidden:
            if found := pattern.search(text):
                checks.blocking.append(f"{name} : terme interdit « {found.group(0)} »")
    letter = texts.get("lettre")  # absente : e-mail sans lettre jointe
    if organization and letter is not None and not mentions(organization, letter, share=0.67):
        checks.warnings.append(f"lettre : l'organisation « {organization} » n'est pas citée")
    if not mentions(title, " ".join(texts.values()), share=0.75):
        checks.warnings.append(
            f"l'intitulé du poste « {title} » n'apparaît ni dans l'e-mail ni dans la lettre")
    allowed = set().union(*(numbers(s) for s in allowed_sources)) if allowed_sources else set()
    for name, text in texts.items():
        for n in sorted(numbers(text) - allowed):
            if not _YEAR.fullmatch(n):
                checks.warnings.append(
                    f"{name} : le nombre {n} ne figure ni dans les faits, ni dans le CV, ni dans l'offre")
    return checks


def _no_fetch(url: str) -> dict:
    raise ValueError(f"ressource externe refusée : {url}")  # la lettre n'a rien à charger


def render_letter(html: str, css: str) -> tuple[bytes, int]:
    """Lettre HTML → PDF (WeasyPrint) et nombre de pages."""
    import weasyprint
    from pypdf import PdfReader

    page = f'<!doctype html><html lang="fr"><meta charset="utf-8"><style>{css}</style><body>{html}</body></html>'
    pdf = weasyprint.HTML(string=page, url_fetcher=_no_fetch).write_pdf()
    assert pdf is not None
    return pdf, len(PdfReader(BytesIO(pdf)).pages)


def build_draft(*, sender: str, to: str, subject: str, html: str,
                attachments: list[tuple[str, bytes]], cc: list[str] | None = None) -> EmailMessage:
    """E-mail texte + HTML et pièces jointes PDF (nom de fichier, contenu)."""
    msg = EmailMessage()  # politique par défaut : objet et noms de fichiers accentués bien encodés
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(html_to_text(html))
    msg.add_alternative(html, subtype="html")
    for filename, content in attachments:
        msg.add_attachment(content, maintype="application", subtype="pdf", filename=filename)
    return msg
