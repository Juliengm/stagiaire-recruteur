"""Brouillons de candidature : relus et corrigés dans l'interface, déposés dans Gmail.

`/candidatures` (Claude Code) les crée ; Julien modifie l'e-mail, la lettre et le CV, puis les dépose
en brouillon Gmail et les envoie lui-même depuis Gmail. **Cette API n'envoie jamais rien** : le
client Gmail ne sait que créer ou remplacer un brouillon et lire un fil (vérifié par un test).
"""
import base64
import os
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

import nh3
from db.candidature import build_draft, check_texts, html_to_text, load_forbidden, render_letter
from db.models import Application, ApplicationDraft, Offer, UserStatus
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from veille_api.db import get_session

router = APIRouter(tags=["brouillons"])

ROOT = Path(__file__).resolve().parents[3]
FOLLOW_UP_DAYS = 10
DraftStatus = Literal["draft", "deposited", "sent", "discarded"]

# HTML accepté de l'éditeur (et de /candidatures) : mise en forme simple, alignement seulement
ALLOWED_TAGS = {"p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "a", "h2", "h3",
                "blockquote"}


def clean_html(html: str) -> str:
    return nh3.clean(html, tags=ALLOWED_TAGS, attributes={"*": {"style"}, "a": {"href"}},
                     filter_style_properties={"text-align"}, url_schemes={"https", "mailto"})


def cv_dir() -> Path:
    return Path(os.environ.get("CV_DIR", "/app/cv"))


def letter_css() -> str:
    path = Path(os.environ.get("LETTER_CSS", ROOT / "templates" / "lettre.css"))
    return path.read_text(encoding="utf8")


class Gmail(Protocol):
    def account(self) -> str: ...
    def save_draft(self, raw: str, draft_id: str | None) -> tuple[str, str]: ...
    def thread_state(self, thread_id: str) -> tuple[str, date | None]: ...


class GoogleGmail:
    """Brouillons et fils seulement : drafts.create / update, threads.get, getProfile."""

    def __init__(self, token_file: str) -> None:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(
            token_file, ["https://www.googleapis.com/auth/gmail.modify"])
        self.users = build("gmail", "v1", credentials=creds, cache_discovery=False).users()

    def account(self) -> str:
        return str(self.users.getProfile(userId="me").execute()["emailAddress"])

    def save_draft(self, raw: str, draft_id: str | None) -> tuple[str, str]:
        from googleapiclient.errors import HttpError

        body = {"message": {"raw": raw}}
        if draft_id:
            try:
                saved = self.users.drafts().update(userId="me", id=draft_id, body=body).execute()
                return saved["id"], saved["message"]["threadId"]
            except HttpError as exc:
                if exc.resp.status != 404:  # brouillon supprimé dans Gmail : on en recrée un
                    raise
        saved = self.users.drafts().create(userId="me", body=body).execute()
        return saved["id"], saved["message"]["threadId"]

    def thread_state(self, thread_id: str) -> tuple[str, date | None]:
        """("sent", date) si un message du fil est parti, ("pending", None), ou ("missing", None)."""
        from googleapiclient.errors import HttpError

        try:
            thread = self.users.threads().get(userId="me", id=thread_id, format="minimal").execute()
        except HttpError as exc:
            if exc.resp.status == 404:
                return "missing", None
            raise
        sent = [int(m["internalDate"]) for m in thread.get("messages", [])
                if "SENT" in m.get("labelIds", [])]
        if not sent:
            return "pending", None
        return "sent", datetime.fromtimestamp(min(sent) / 1000, UTC).date()


def get_gmail() -> Gmail:
    return GoogleGmail(os.environ.get("GMAIL_TOKEN_FILE", "/app/credentials/gmail_token.json"))


class DraftIn(BaseModel):
    offer_id: int | None = None
    organization: str | None = None
    position: str
    language: Literal["fr", "en"] | None = None
    segment: Literal["tech", "institutionnel"] | None = None
    cv_file: str | None = None
    recipient: str | None = None
    cc: list[str] = []
    subject: str
    email_html: str
    letter_html: str
    letter_filename: str
    required_documents: str | None = None
    weaknesses: str | None = None
    apply_url: str | None = None

    @field_validator("email_html", "letter_html")
    @classmethod
    def sanitize(cls, html: str) -> str:
        return clean_html(html)


class DraftPatch(BaseModel):
    cv_file: str | None = None
    recipient: str | None = None
    cc: list[str] | None = None
    subject: str | None = None
    email_html: str | None = None
    letter_html: str | None = None
    status: Literal["draft", "discarded"] | None = None

    @field_validator("email_html", "letter_html")
    @classmethod
    def sanitize(cls, html: str | None) -> str | None:
        return clean_html(html) if html is not None else None


class DraftOut(DraftIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    gmail_draft_id: str | None
    gmail_thread_id: str | None
    deposited_at: datetime | None
    sent_at: date | None
    created_at: datetime
    updated_at: datetime
    stale: bool = False  # modifié depuis le dépôt : Gmail a une version plus ancienne

    @classmethod
    def of(cls, draft: ApplicationDraft) -> "DraftOut":
        out = cls.model_validate(draft)
        out.stale = bool(draft.status == "deposited" and draft.deposited_at
                         and draft.updated_at > draft.deposited_at)
        return out


class DepositIn(BaseModel):
    force: bool = False  # déposer malgré les avertissements (jamais malgré un blocage)


class DepositOut(BaseModel):
    draft: DraftOut
    warnings: list[str]
    gmail_url: str = "https://mail.google.com/mail/u/0/#drafts"


class SyncOut(BaseModel):
    sent: int
    discarded: int


def _get(session: Session, draft_id: int, lock: bool = False) -> ApplicationDraft:
    stmt = select(ApplicationDraft).where(ApplicationDraft.id == draft_id)
    draft = session.scalar(stmt.with_for_update() if lock else stmt)
    if draft is None:
        raise HTTPException(404, "brouillon inconnu")
    return draft


def _cv_path(name: str | None) -> Path:
    folder = cv_dir() / "pdf"
    if not name or name not in {p.name for p in folder.glob("*.pdf")}:  # jamais de chemin libre
        raise HTTPException(422, f"CV inconnu : {name}")
    return folder / name


@router.get("/cvs")
def list_cvs() -> list[str]:
    """CV disponibles en PDF (cv/pdf/, générés sur le poste par `candidature.py cv-pdf`)."""
    return sorted(p.name for p in (cv_dir() / "pdf").glob("*.pdf"))


@router.get("/cvs/{name}")
def get_cv(name: str) -> FileResponse:
    return FileResponse(_cv_path(name), media_type="application/pdf",
                        content_disposition_type="inline")


@router.post("/drafts", status_code=201)
def create_draft(body: DraftIn, session: Annotated[Session, Depends(get_session)]) -> DraftOut:
    if body.offer_id is not None and session.get(Offer, body.offer_id) is None:
        raise HTTPException(422, "offre inconnue")
    draft = ApplicationDraft(**body.model_dump())
    session.add(draft)
    session.commit()
    return DraftOut.of(draft)


@router.get("/drafts")
def list_drafts(session: Annotated[Session, Depends(get_session)],
                status: DraftStatus | None = None) -> list[DraftOut]:
    stmt = select(ApplicationDraft).order_by(ApplicationDraft.created_at.desc())
    if status:
        stmt = stmt.where(ApplicationDraft.status == status)
    return [DraftOut.of(d) for d in session.scalars(stmt)]


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: int, session: Annotated[Session, Depends(get_session)]) -> DraftOut:
    return DraftOut.of(_get(session, draft_id))


@router.patch("/drafts/{draft_id}")
def update_draft(draft_id: int, body: DraftPatch,
                 session: Annotated[Session, Depends(get_session)]) -> DraftOut:
    draft = _get(session, draft_id, lock=True)
    if draft.status in {"sent", "discarded"}:
        raise HTTPException(409, "candidature déjà envoyée ou abandonnée")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("cv_file"):
        _cv_path(changes["cv_file"])
    for key, value in changes.items():
        setattr(draft, key, value)
    draft.updated_at = datetime.now(UTC)
    session.commit()
    return DraftOut.of(draft)


@router.get("/drafts/{draft_id}/letter.pdf")
def letter_preview(draft_id: int, session: Annotated[Session, Depends(get_session)]) -> Response:
    draft = _get(session, draft_id)
    pdf, _ = render_letter(draft.letter_html, letter_css())
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{draft.letter_filename}"'})


def _checks(session: Session, draft: ApplicationDraft, letter_pages: int) -> tuple[list[str], list[str]]:
    folder = cv_dir()
    forbidden_file, facts_file = folder / "interdits.txt", folder / "faits.md"
    if not forbidden_file.exists() or not facts_file.exists():
        return [f"{forbidden_file.name} ou {facts_file.name} absent de {folder}"], []
    from pypdf import PdfReader

    cv_text = "\n".join(page.extract_text() or "" for page in
                        PdfReader(BytesIO(_cv_path(draft.cv_file).read_bytes())).pages)
    offer = session.get(Offer, draft.offer_id) if draft.offer_id else None
    sources = [facts_file.read_text(encoding="utf8"), cv_text,
               f"{offer.title} {offer.description or ''}" if offer else ""]
    texts = {"objet": draft.subject, "e-mail": html_to_text(draft.email_html),
             "lettre": html_to_text(draft.letter_html)}
    checks = check_texts(texts, forbidden=load_forbidden(forbidden_file),
                         organization=draft.organization, title=draft.position,
                         allowed_sources=sources)
    if letter_pages > 1:
        checks.blocking.append(f"lettre : {letter_pages} pages, une seule attendue")
    return checks.blocking, checks.warnings


@router.post("/drafts/{draft_id}/deposit")
def deposit(draft_id: int, body: DepositIn, session: Annotated[Session, Depends(get_session)],
            gmail: Annotated[Gmail, Depends(get_gmail)]) -> DepositOut:
    """Contrôles, puis brouillon Gmail créé (ou remplacé) avec la lettre et le CV en PDF."""
    draft = _get(session, draft_id, lock=True)  # deux clics : le second attend et remplace le premier
    if draft.status in {"sent", "discarded"}:
        raise HTTPException(409, "candidature déjà envoyée ou abandonnée")
    if not draft.recipient:
        raise HTTPException(409, "pas de destinataire : candidature par portail")
    if draft.gmail_thread_id and gmail.thread_state(draft.gmail_thread_id)[0] == "sent":
        raise HTTPException(409, "déjà envoyée depuis Gmail : synchroniser plutôt que redéposer")
    cv = _cv_path(draft.cv_file)
    letter_pdf, pages = render_letter(draft.letter_html, letter_css())
    blocking, warnings = _checks(session, draft, pages)
    if blocking or (warnings and not body.force):
        raise HTTPException(422, {"blocking": blocking, "warnings": warnings})
    sender = os.environ.get("CANDIDATURES_FROM", "")
    if not sender or gmail.account().lower() != sender.lower():
        raise HTTPException(409, "le jeton Gmail n'est pas celui de CANDIDATURES_FROM : rien n'est créé")
    msg = build_draft(sender=sender, to=draft.recipient, cc=draft.cc, subject=draft.subject,
                      html=draft.email_html,
                      attachments=[(cv.name, cv.read_bytes()), (draft.letter_filename, letter_pdf)])
    draft.gmail_draft_id, draft.gmail_thread_id = gmail.save_draft(
        base64.urlsafe_b64encode(msg.as_bytes()).decode(), draft.gmail_draft_id)
    now = datetime.now(UTC)
    draft.status, draft.deposited_at, draft.updated_at = "deposited", now, now
    application = session.scalar(select(Application).where(Application.draft_id == draft.id))
    if application is None:
        session.add(Application(
            offer_id=draft.offer_id, organization=draft.organization, position=draft.position,
            contact=draft.recipient, cv_sent=draft.cv_file, status="new", draft_id=draft.id,
            notes=f"brouillon Gmail déposé le {now:%d/%m/%Y}"))
    session.commit()
    return DepositOut(draft=DraftOut.of(draft), warnings=warnings)


@router.post("/drafts/sync")
def sync_drafts(session: Annotated[Session, Depends(get_session)],
                gmail: Annotated[Gmail, Depends(get_gmail)]) -> SyncOut:
    """Brouillons déposés : envoyés par Julien → « postulé » et relance à 10 jours ; supprimés → abandon."""
    sent = discarded = 0
    for draft in session.scalars(select(ApplicationDraft).where(
            ApplicationDraft.status == "deposited", ApplicationDraft.gmail_thread_id.is_not(None))):
        state, sent_on = gmail.thread_state(draft.gmail_thread_id or "")
        application = session.scalar(select(Application).where(Application.draft_id == draft.id))
        if state == "sent" and sent_on:
            draft.status, draft.sent_at = "sent", sent_on
            values: dict[str, Any] = {"status": "applied", "sent_at": sent_on,
                                      "follow_up_at": sent_on + timedelta(days=FOLLOW_UP_DAYS)}
            sent += 1
        elif state == "missing":
            draft.status = "discarded"
            values = {"status": "ignored"}
            discarded += 1
        else:
            continue
        if application:
            for key, value in values.items():
                setattr(application, key, value)
        if draft.offer_id and state == "sent":
            stmt = insert(UserStatus).values(offer_id=draft.offer_id, status="applied")
            session.execute(stmt.on_conflict_do_update(index_elements=[UserStatus.offer_id],
                                                       set_={"status": "applied"}))
    session.commit()
    return SyncOut(sent=sent, discarded=discarded)
