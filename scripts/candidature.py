"""Outils de la commande /candidatures, sur le poste : CV en PDF, aperçu de la lettre, pré-contrôle.

    uv run --project api python scripts/candidature.py <commande> …

    cv-pdf [cv.docx …]                         CV en PDF dans cv/pdf/ (tous par défaut)
    lettre <lettre.html> <lettre.pdf>          lettre en PDF, rendu identique à l'API ; une page au plus
    verifier --offre offre.json --objet … --email email.html --lettre lettre.html [--cv cv.pdf]

Le dépôt dans Gmail se fait depuis l'interface (API) : ce script ne touche pas à Gmail.
Après un `cv-pdf`, recopier cv/pdf/ sur le serveur (voir docs/deploiement.md).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # paquet partagé `db`

from db.candidature import check_texts, html_to_text, load_forbidden, render_letter

CV_DIR = ROOT / "cv"


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


def verify(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    from pypdf import PdfReader

    offer = json.loads(Path(args.offre).read_text(encoding="utf8"))
    sources = [(CV_DIR / "faits.md").read_text(encoding="utf8"),
               f"{offer['title']} {offer.get('description') or ''}"]
    if args.cv:
        reader = PdfReader(BytesIO(Path(args.cv).read_bytes()))
        sources.append("\n".join(page.extract_text() or "" for page in reader.pages))
    texts = {"objet": args.objet,
             "e-mail": html_to_text(Path(args.email).read_text(encoding="utf8")),
             "lettre": html_to_text(Path(args.lettre).read_text(encoding="utf8"))}
    checks = check_texts(texts, forbidden=load_forbidden(CV_DIR / "interdits.txt"),
                         organization=offer.get("organization"), title=offer["title"],
                         allowed_sources=sources)
    return checks.blocking, checks.warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cv-pdf").add_argument("docx", nargs="*")
    p = sub.add_parser("lettre")
    p.add_argument("html")
    p.add_argument("pdf")
    p = sub.add_parser("verifier")
    for name in ("--offre", "--objet", "--email", "--lettre"):
        p.add_argument(name, required=True)
    p.add_argument("--cv")
    args = parser.parse_args()

    if args.cmd == "cv-pdf":
        for docx in [Path(d) for d in args.docx] or sorted(CV_DIR.glob("*.docx")):
            print(cv_pdf(docx))
    elif args.cmd == "lettre":
        css = (ROOT / "templates" / "lettre.css").read_text(encoding="utf8")
        pdf, pages = render_letter(Path(args.html).read_text(encoding="utf8"), css)
        Path(args.pdf).write_bytes(pdf)
        print(json.dumps({"pdf": args.pdf, "pages": pages}))
        return 0 if pages == 1 else 1
    elif args.cmd == "verifier":
        blocking, warnings = verify(args)
        for line in blocking:
            print(f"BLOQUANT  {line}")
        for line in warnings:
            print(f"À VÉRIFIER  {line}")
        if not blocking and not warnings:
            print("aucun problème")
        return 1 if blocking or warnings else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
