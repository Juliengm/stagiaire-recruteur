"""Préparation des candidatures (commande /candidatures) : contrôles des textes et brouillon e-mail.

Les faits autorisés et les termes interdits sont lus dans `cv/` (hors dépôt) : rien de personnel ici.
"""
import mimetypes
import re
import unicodedata
from email.message import EmailMessage
from pathlib import Path

# nombres écrits « 1 285 », « 110 000+ », « 0,8 » : espaces (y compris insécables) entre milliers
_NUMBER = re.compile(r"\d{1,3}(?:[   ]\d{3})+|\d+(?:[.,]\d+)?")
_YEAR = re.compile(r"(19|20)\d\d")
# mots d'annonce qui ne font pas partie de l'intitulé (« Recrutement d'un(e) … »)
_NOISE = {"recrutement", "recrute", "recherche", "poste", "avis", "appel", "candidatures", "offre",
          "hiring", "vacancy", "position", "call", "for", "the", "of", "and", "in", "un", "une", "de",
          "du", "des", "la", "le", "les", "et", "en", "au", "aux", "pour"}


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
    return {re.sub(r"[   ]", "", n).replace(",", ".") for n in _NUMBER.findall(text)}


def check_texts(texts: dict[str, str], *, forbidden: list[re.Pattern[str]], organization: str | None,
                title: str, allowed_sources: list[str]) -> list[str]:
    """Problèmes à corriger avant de créer le brouillon (liste vide : tout va bien).

    - terme ou tournure interdits ;
    - organisation ou intitulé du poste absents de la lettre ;
    - nombre absent des faits, des CV et de l'offre (chiffre peut-être inventé), hors années.
    """
    problems = []
    for name, text in texts.items():
        for pattern in forbidden:
            if found := pattern.search(text):
                problems.append(f"{name} : terme interdit « {found.group(0)} »")
    letter = texts.get("lettre", "")
    if organization and not mentions(organization, letter, share=0.67):
        problems.append(f"lettre : l'organisation « {organization} » n'est pas citée")
    if not mentions(title, " ".join(texts.values()), share=0.75):
        problems.append(f"l'intitulé du poste « {title} » n'apparaît ni dans l'e-mail ni dans la lettre")
    allowed = set().union(*(numbers(s) for s in allowed_sources)) if allowed_sources else set()
    for name, text in texts.items():
        for n in sorted(numbers(text) - allowed):
            if not _YEAR.fullmatch(n):
                problems.append(f"{name} : le nombre {n} ne figure ni dans les faits, ni dans les CV, "
                                "ni dans l'offre")
    return problems


def build_draft(*, sender: str, to: str, subject: str, body: str, attachments: list[Path],
                cc: list[str] | None = None) -> EmailMessage:
    msg = EmailMessage()  # politique par défaut : objet et noms de fichiers accentués bien encodés
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(body)
    for path in attachments:
        kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        maintype, subtype = kind.split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype,
                           filename=path.name)
    return msg
