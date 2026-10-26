"""Candidatures et relances (remplacent le fichier Excel de prospection)."""
from datetime import date
from typing import Annotated, Any

from db.models import Application, Offer
from db.rules import CLOSED_STATUSES, Status
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from veille_api.db import get_session
from veille_api.xlsx_import import parse_workbook

router = APIRouter(tags=["candidatures"])

MAX_UPLOAD_BYTES = 5_000_000


class ApplicationIn(BaseModel):
    offer_id: int | None = None
    organization: str | None = None
    contact: str | None = None
    position: str | None = None
    cv_sent: str | None = None
    status: Status = "new"
    sent_at: date | None = None
    follow_up_at: date | None = None
    notes: str | None = None


class ApplicationPatch(BaseModel):
    offer_id: int | None = None
    organization: str | None = None
    contact: str | None = None
    position: str | None = None
    cv_sent: str | None = None
    status: Status | None = None
    sent_at: date | None = None
    follow_up_at: date | None = None
    notes: str | None = None


class ApplicationOut(ApplicationIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str  # type: ignore[assignment]  # valeurs anciennes possibles en base
    sheet: str | None
    sheet_row: int | None
    follow_up_due: bool = False


class ImportReport(BaseModel):
    imported: int
    already_present: int
    skipped: list[dict[str, Any]]


def _out(app: Application, today: date) -> ApplicationOut:
    out = ApplicationOut.model_validate(app)
    out.follow_up_due = bool(app.follow_up_at and app.follow_up_at <= today
                             and (app.status or "") not in CLOSED_STATUSES)
    return out


def _check_offer(session: Session, offer_id: int | None) -> None:
    if offer_id is not None and session.get(Offer, offer_id) is None:
        raise HTTPException(422, "offre inconnue")


@router.get("/applications")
def list_applications(session: Annotated[Session, Depends(get_session)],
                      sheet: str | None = None, status: Status | None = None,
                      due: bool = False) -> list[ApplicationOut]:
    """Relances les plus anciennes d'abord ; `due=true` : seulement les relances à faire."""
    stmt = select(Application).order_by(Application.follow_up_at.asc().nulls_last(),
                                        Application.id)
    if sheet:
        stmt = stmt.where(Application.sheet == sheet)
    if status:
        stmt = stmt.where(Application.status == status)
    today = date.today()
    out = [_out(a, today) for a in session.scalars(stmt)]
    return [a for a in out if a.follow_up_due] if due else out


@router.post("/applications", status_code=201)
def create_application(body: ApplicationIn,
                       session: Annotated[Session, Depends(get_session)]) -> ApplicationOut:
    _check_offer(session, body.offer_id)
    app = Application(**body.model_dump())
    session.add(app)
    session.commit()
    return _out(app, date.today())


@router.patch("/applications/{application_id}")
def update_application(application_id: int, body: ApplicationPatch,
                       session: Annotated[Session, Depends(get_session)]) -> ApplicationOut:
    app = session.get(Application, application_id)
    if app is None:
        raise HTTPException(404, "candidature inconnue")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("status", "") is None:
        raise HTTPException(422, "statut obligatoire")
    if "offer_id" in changes:
        _check_offer(session, changes["offer_id"])
    for key, value in changes.items():
        setattr(app, key, value)
    session.commit()
    return _out(app, date.today())


@router.post("/applications/import-xlsx")
async def import_xlsx(file: UploadFile,
                      session: Annotated[Session, Depends(get_session)]) -> ImportReport:
    """Importe les onglets Madagascar et Lille ; une ligne déjà importée (onglet + N°) n'est
    pas modifiée, pour ne jamais écraser ce qui a été changé depuis dans l'interface."""
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "fichier trop volumineux")
    try:
        parsed = parse_workbook(content)
    except Exception as exc:  # fichier corrompu ou non xlsx
        raise HTTPException(422, f"fichier Excel illisible : {exc}") from exc
    imported = 0
    for row in parsed.rows:
        result = session.execute(insert(Application).values(**row).on_conflict_do_nothing(
            index_elements=[Application.sheet, Application.sheet_row]).returning(Application.id))
        imported += result.first() is not None
    session.commit()
    return ImportReport(imported=imported, already_present=len(parsed.rows) - imported,
                        skipped=parsed.skipped)
