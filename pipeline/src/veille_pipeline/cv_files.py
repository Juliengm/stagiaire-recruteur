"""Lecture du texte des CV (`cv/`), au format Word ou Markdown."""
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path: Path) -> str:
    """Paragraphes du corps du document (tableaux compris), un par ligne."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = ("".join(t.text or "" for t in p.iter(f"{_W}t")).strip() for p in root.iter(f"{_W}p"))
    return "\n".join(p for p in paragraphs if p)


def read_cv(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return docx_text(path)
    return path.read_text(encoding="utf-8")
