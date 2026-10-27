"""Lecture du texte des CV (`cv/`), au format Word ou Markdown."""
from pathlib import Path

from db.candidature import docx_text


def read_cv(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return docx_text(path)
    return path.read_text(encoding="utf-8")
