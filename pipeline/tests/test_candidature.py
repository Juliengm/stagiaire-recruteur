import re
from email import message_from_bytes
from email.policy import default

from veille_pipeline.candidature import build_draft, check_texts, numbers, slug

FORBIDDEN = [re.compile(r"motinterdit", re.IGNORECASE),
             re.compile(r"j'ai (conduit|dirigé) (la|des) réinstallations?", re.IGNORECASE)]
FACTS = "10 ans d'expérience, 33 pays, enquête auprès de 1 285 ménages, 110 000+ questionnaires."


def _check(email: str, letter: str) -> list[str]:
    return check_texts({"e-mail": email, "lettre": letter}, forbidden=FORBIDDEN,
                       organization="ONG A", title="Chargé de suivi-évaluation",
                       allowed_sources=[FACTS])


def test_names_match_on_significant_words():
    letter = ("Candidature au poste de Responsable en Gestion des Risques Environnementaux "
              "du projet RIZ PLUS : 10 ans d'expérience dans 33 pays.")
    assert check_texts({"lettre": letter}, forbidden=[], organization="RIZ+",
                       title="Recrutement d'un(e) Responsable Gestion des Risques Environnementaux (RGRE)",
                       allowed_sources=[FACTS]) == []


def test_slug_for_file_names():
    assert slug("Banque mondiale – Antananarivo (Réf. 42)") == "Banque_mondiale_Antananarivo_Ref_42"
    assert slug("***") == "sans_nom"


def test_numbers_are_normalised():
    assert numbers("1 285 ménages, 110 000+ questionnaires, score 0,8") == {"1285", "110000", "0.8"}


def test_clean_texts_pass():
    letter = ("Candidature au poste de Chargé de suivi-évaluation chez ONG A : 10 ans d'expérience "
              "dans 33 pays, dont une enquête auprès de 1 285 ménages, disponible en janvier 2027.")
    assert _check("Bonjour, voici ma candidature.", letter) == []


def test_forbidden_terms_missing_names_and_unknown_numbers_are_reported():
    problems = _check("Le MotInterdit vous salue.",
                      "J'ai conduit des réinstallations pour 45 000 ménages.")
    assert any("MotInterdit" in p for p in problems)
    assert any("conduit des réinstallations" in p for p in problems)
    assert any("ONG A" in p for p in problems)
    assert any("Chargé de suivi-évaluation" in p for p in problems)
    assert any("45000" in p for p in problems)


def test_draft_encodes_accents_and_attachments(tmp_path):
    pdf = tmp_path / "LM_Julien_Gasser_Morlay_ONG_A.pdf"
    pdf.write_bytes(b"%PDF-1.4 essai")
    msg = build_draft(sender="moi@example.org", to="rh@example.org",
                      subject="Candidature — Chargé de suivi-évaluation", body="Bonjour,\n\nÉtienne",
                      attachments=[pdf], cc=["copie@example.org"])
    parsed = message_from_bytes(msg.as_bytes(), policy=default)
    assert parsed["Subject"] == "Candidature — Chargé de suivi-évaluation"
    assert parsed["Cc"] == "copie@example.org"
    files = [(p.get_filename(), p.get_content_type()) for p in parsed.iter_attachments()]
    assert files == [("LM_Julien_Gasser_Morlay_ONG_A.pdf", "application/pdf")]
