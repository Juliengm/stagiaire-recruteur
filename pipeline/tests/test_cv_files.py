import zipfile
from pathlib import Path

from veille_pipeline.cv_files import docx_text, read_cv
from veille_pipeline.embeddings import chunk_words
from veille_pipeline.scoring import load_scoring_config

CFG = load_scoring_config(Path(__file__).resolve().parents[2] / "config" / "scoring.yaml")
_DOC = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        "<w:p><w:r><w:t>Profil</w:t></w:r><w:r><w:t xml:space=\"preserve\"> fictif</w:t></w:r></w:p>"
        "<w:p/><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Cellule de tableau</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        "</w:body></w:document>")


def _make_docx(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as z:  # docx minimal et factice
        z.writestr("word/document.xml", _DOC)
    return path


def test_docx_text_joins_runs_and_reads_tables(tmp_path):
    assert docx_text(_make_docx(tmp_path / "cv.docx")) == "Profil fictif\nCellule de tableau"


def test_read_cv_markdown_and_docx(tmp_path):
    md = tmp_path / "cv.md"
    md.write_text("# Titre\ntexte", encoding="utf-8")
    assert read_cv(md) == "# Titre\ntexte"
    assert read_cv(_make_docx(tmp_path / "cv.docx")).startswith("Profil")


def test_chunk_words():
    assert chunk_words("") == [""]
    chunks = chunk_words(" ".join(["mot"] * 600), size=250)
    assert [len(c.split()) for c in chunks] == [250, 250, 100]


def test_configured_cvs_are_profile_codes_and_exclude_full_cvs():
    cvs = CFG["cvs"]
    assert set(CFG["profiles"]) <= set(cvs)  # chaque profil par mots-clés a son CV
    assert all("Complet" not in pattern for pattern in cvs.values())
    assert all(pattern.startswith("*") for pattern in cvs.values())  # pas de nom de personne en clair
