"""Outils de la commande /candidatures : PDF du CV et de la lettre, contrôles, brouillon Gmail, suivi.

    cd pipeline && uv run --with weasyprint python ../scripts/candidature.py <commande> …

    cv-pdf <cv.docx>                       PDF du CV (mis en cache dans cv/pdf/)
    lettre <lettre.md> <lettre.pdf>        lettre en PDF (templates/lettre.css), une page au plus
    verifier --offre offre.json --objet … --email corps.txt --lettre lettre.md
    brouillon --expediteur … --a … [--cc …] --objet … --corps corps.txt --pj fichier.pdf …
    suivi <thread_id>                      envoyé ? (message du fil marqué SENT)

N'envoie jamais rien : le script crée des brouillons, Julien les envoie lui-même depuis Gmail.
Tout ce qu'il produit de personnel reste dans cv/ (hors dépôt).
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from veille_pipeline.candidature import build_draft, check_texts, load_forbidden
from veille_pipeline.connectors.gmail_alert import build_gmail_service
from veille_pipeline.cv_files import read_cv

ROOT = Path(__file__).resolve().parents[1]
CV_DIR = ROOT / "cv"
TOKEN = os.environ.get("GMAIL_TOKEN_FILE_LOCAL", str(ROOT / "credentials" / "gmail_token.json"))


def attachment_name(stem: str) -> str:
    """« CV_Complet_FR_202610 » → « CV_Julien_Gasser_Morlay_Complet_FR » : le nom vu par le recruteur."""
    profile = re.sub(r"^CV_(Julien_GASSER_MORLAY_)?", "", stem, flags=re.IGNORECASE)
    return "CV_Julien_Gasser_Morlay_" + re.sub(r"_\d{6}$", "", profile)


def cv_pdf(docx: Path) -> Path:
    out_dir = CV_DIR / "pdf"
    out_dir.mkdir(exist_ok=True)
    pdf = out_dir / f"{attachment_name(docx.stem)}.pdf"
    if pdf.exists() and pdf.stat().st_mtime >= docx.stat().st_mtime:
        return pdf
    with tempfile.TemporaryDirectory() as tmp:  # profil isolé : marche même si LibreOffice est ouvert
        subprocess.run(["soffice", f"-env:UserInstallation=file://{tmp}/profil", "--headless",
                        "--convert-to", "pdf", "--outdir", tmp, str(docx)],
                       check=True, capture_output=True, timeout=180)
        shutil.move(Path(tmp) / f"{docx.stem}.pdf", pdf)
    return pdf


def letter_pdf(md: Path, pdf: Path) -> int:
    import weasyprint  # fourni par `uv run --with weasyprint`
    from pypdf import PdfReader

    body = subprocess.run(["pandoc", str(md), "-f", "markdown", "-t", "html"], check=True,
                          capture_output=True, text=True).stdout
    css = (ROOT / "templates" / "lettre.css").read_text(encoding="utf8")
    html = f'<!doctype html><html lang="fr"><meta charset="utf-8"><style>{css}</style><body>{body}</body></html>'
    weasyprint.HTML(string=html).write_pdf(pdf)
    return len(PdfReader(pdf).pages)


def verify(args: argparse.Namespace) -> list[str]:
    offer = json.loads(Path(args.offre).read_text(encoding="utf8"))
    sources = [(CV_DIR / "faits.md").read_text(encoding="utf8")]
    sources += [read_cv(p) for p in sorted(CV_DIR.glob("*.docx"))]
    sources.append(f"{offer['title']} {offer.get('description') or ''}")
    texts = {"objet": args.objet, "e-mail": Path(args.email).read_text(encoding="utf8"),
             "lettre": Path(args.lettre).read_text(encoding="utf8")}
    return check_texts(texts, forbidden=load_forbidden(CV_DIR / "interdits.txt"),
                       organization=offer.get("organization"), title=offer["title"],
                       allowed_sources=sources)


def gmail(expected_sender: str):  # type: ignore[no-untyped-def]
    service = build_gmail_service(TOKEN)
    account = service.users().getProfile(userId="me").execute()["emailAddress"]
    if account.lower() != expected_sender.lower():
        sys.exit(f"jeton Gmail de {account}, attendu {expected_sender} : rien n'est créé")
    return service


def draft(args: argparse.Namespace) -> dict[str, str]:
    service = gmail(args.expediteur)
    msg = build_draft(sender=args.expediteur, to=args.a, subject=args.objet,
                      body=Path(args.corps).read_text(encoding="utf8"),
                      attachments=[Path(p) for p in args.pj], cc=args.cc)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    created = service.users().drafts().create(  # création seulement : jamais d'envoi
        userId="me", body={"message": {"raw": raw}}).execute()
    return {"draft_id": created["id"], "thread_id": created["message"]["threadId"],
            "lien": "https://mail.google.com/mail/u/0/#drafts"}


def follow(args: argparse.Namespace) -> dict[str, str | None]:
    service = gmail(args.expediteur)
    thread = service.users().threads().get(userId="me", id=args.thread_id,
                                           format="minimal").execute()
    sent = [m for m in thread.get("messages", []) if "SENT" in m.get("labelIds", [])]
    if not sent:
        return {"etat": "en_attente", "envoye_le": None}
    first = min(int(m["internalDate"]) for m in sent) / 1000
    return {"etat": "envoye", "envoye_le": datetime.fromtimestamp(first, UTC).date().isoformat()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cv-pdf").add_argument("docx")
    p = sub.add_parser("lettre")
    p.add_argument("md")
    p.add_argument("pdf")
    p = sub.add_parser("verifier")
    for name in ("--offre", "--objet", "--email", "--lettre"):
        p.add_argument(name, required=True)
    p = sub.add_parser("brouillon")
    for name in ("--expediteur", "--a", "--objet", "--corps"):
        p.add_argument(name, required=True)
    p.add_argument("--pj", nargs="+", default=[])
    p.add_argument("--cc", nargs="+", default=[])
    p = sub.add_parser("suivi")
    p.add_argument("thread_id")
    p.add_argument("--expediteur", required=True)
    args = parser.parse_args()

    if args.cmd == "cv-pdf":
        print(cv_pdf(Path(args.docx)))
    elif args.cmd == "lettre":
        pages = letter_pdf(Path(args.md), Path(args.pdf))
        print(json.dumps({"pdf": args.pdf, "pages": pages}))
        return 0 if pages == 1 else 1
    elif args.cmd == "verifier":
        problems = verify(args)
        print("\n".join(problems) or "aucun problème")
        return 1 if problems else 0
    elif args.cmd == "brouillon":
        print(json.dumps(draft(args), ensure_ascii=False))
    elif args.cmd == "suivi":
        print(json.dumps(follow(args)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
