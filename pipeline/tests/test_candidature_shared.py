import re
from email import message_from_bytes
from email.policy import default

from db.candidature import build_draft, check_texts, html_to_text, numbers, slug

FORBIDDEN = [re.compile(r"motinterdit", re.IGNORECASE),
             re.compile(r"j'ai (conduit|dirigé) (la|des) réinstallations?", re.IGNORECASE)]
FACTS = "10 ans d'expérience, 33 pays, enquête auprès de 1 285 ménages, 110 000+ questionnaires."


def _check(email: str, letter: str):
    return check_texts({"e-mail": email, "lettre": letter}, forbidden=FORBIDDEN,
                       organization="ONG A", title="Chargé de suivi-évaluation",
                       allowed_sources=[FACTS])


def test_slug_for_file_names():
    assert slug("Banque mondiale – Antananarivo (Réf. 42)") == "Banque_mondiale_Antananarivo_Ref_42"
    assert slug("***") == "sans_nom"


def test_numbers_are_normalised():
    assert numbers("1 285 ménages, 110 000+ questionnaires, score 0,8") == {"1285", "110000", "0.8"}


def test_html_to_text_keeps_paragraphs_and_lists():
    html = "<p>Bonjour,</p><p>Deux points :</p><ul><li>un</li><li>deux</li></ul><p>A<br>B</p>"
    assert html_to_text(html) == "Bonjour,\n\nDeux points :\n\n- un\n- deux\n\nA\nB"


def test_clean_texts_pass():
    letter = ("Candidature au poste de Chargé de suivi-évaluation chez ONG A : 10 ans d'expérience "
              "dans 33 pays, dont une enquête auprès de 1 285 ménages, disponible en janvier 2027.")
    checks = _check("Bonjour, voici ma candidature.", letter)
    assert checks.blocking == [] and checks.warnings == []


def test_forbidden_terms_block_and_doubts_warn():
    checks = _check("Le MotInterdit vous salue.", "J'ai conduit des réinstallations pour 45 000 ménages.")
    assert any("MotInterdit" in p for p in checks.blocking)
    assert any("conduit des réinstallations" in p for p in checks.blocking)
    assert any("ONG A" in p for p in checks.warnings)
    assert any("Chargé de suivi-évaluation" in p for p in checks.warnings)
    assert any("45000" in p for p in checks.warnings)


def test_names_match_on_significant_words():
    letter = ("Candidature au poste de Responsable en Gestion des Risques Environnementaux "
              "du projet RIZ PLUS : 10 ans d'expérience dans 33 pays.")
    checks = check_texts({"lettre": letter}, forbidden=[], organization="RIZ+",
                         title="Recrutement d'un(e) Responsable Gestion des Risques Environnementaux (RGRE)",
                         allowed_sources=[FACTS])
    assert checks.warnings == []


def test_draft_is_text_and_html_with_attachments():
    msg = build_draft(sender="moi@example.org", to="rh@example.org",
                      subject="Candidature — Chargé de suivi-évaluation",
                      html="<p>Bonjour,</p><p>Étienne</p>", cc=["copie@example.org"],
                      attachments=[("LM_Julien_Gasser_Morlay_ONG_A.pdf", b"%PDF-1.4 essai")])
    parsed = message_from_bytes(msg.as_bytes(), policy=default)
    assert parsed["Subject"] == "Candidature — Chargé de suivi-évaluation"
    assert parsed["Cc"] == "copie@example.org"
    assert parsed.get_body(("plain",)).get_content().strip() == "Bonjour,\n\nÉtienne"
    assert "<p>Étienne</p>" in parsed.get_body(("html",)).get_content()
    files = [(p.get_filename(), p.get_content_type()) for p in parsed.iter_attachments()]
    assert files == [("LM_Julien_Gasser_Morlay_ONG_A.pdf", "application/pdf")]
