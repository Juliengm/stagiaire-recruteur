"""Connecteur d'alertes e-mail via l'API Gmail : lit le libellé `alertes-emploi` du compte.

Le jeton OAuth (scope gmail.modify) donne accès à toute la boîte : seul le libellé configuré est
lu, et chaque message traité reçoit le libellé `traité` APRÈS l'écriture en base (`finalize`).
"""
import base64
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import Any

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.email_parsers import PARSERS
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def build_gmail_service(token_file: str) -> Any:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def sender_address(msg: EmailMessage) -> str:
    return str(msg["From"] or "").lower()


class GmailAlertConnector:
    kind = "gmail_alert"

    def __init__(self, service_factory: Callable[[str], Any] = build_gmail_service) -> None:
        self._service_factory = service_factory
        self._service: Any = None
        self._to_mark: list[str] = []

    def parse_message(self, msg: EmailMessage, source: SourceConfig, now: datetime) -> list[RawOffer]:
        sender = sender_address(msg)
        parsers = source["config"].get("parsers", {})
        offers: list[RawOffer] = []
        for name, rule in parsers.items():
            if rule["from_contains"].lower() in sender and name in PARSERS:
                for item in PARSERS[name](msg):
                    offers.append(RawOffer(
                        source_id=source["id"], external_id=f"{item['platform']}:{item['job_id']}",
                        url=item["url"], fetched_at=now, payload=item,
                    ))
        return offers

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        config = source["config"]
        if not config.get("oauth_token_file"):
            raise RuntimeError("GMAIL_TOKEN_FILE manquant (lancer scripts/gmail_auth.py)")
        self._service = self._service_factory(config["oauth_token_file"])
        users = self._service.users()
        label, done = config.get("label", "alertes-emploi"), config.get("processed_label", "traité")
        query = f"label:{label} -label:{done}"
        now = datetime.now(UTC)
        offers: list[RawOffer] = []
        self._to_mark = []
        token = None
        while True:
            page = users.messages().list(userId="me", q=query, pageToken=token).execute()
            for ref in page.get("messages", []):
                raw = users.messages().get(userId="me", id=ref["id"], format="raw").execute()["raw"]
                msg = message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)
                assert isinstance(msg, EmailMessage)
                offers += self.parse_message(msg, source, now)
                self._to_mark.append(ref["id"])  # même sans offre reconnue : ne pas relire sans fin
            token = page.get("nextPageToken")
            if not token:
                return offers

    def finalize(self, source: SourceConfig) -> int:
        """Pose le libellé `traité` sur les messages lus ; à appeler une fois les offres en base."""
        if not self._to_mark or self._service is None:
            return 0
        done = source["config"].get("processed_label", "traité")
        users = self._service.users()
        labels = {x["name"]: x["id"] for x in users.labels().list(userId="me").execute()["labels"]}
        label_id = labels.get(done) or users.labels().create(
            userId="me", body={"name": done}).execute()["id"]
        users.messages().batchModify(
            userId="me", body={"ids": self._to_mark, "addLabelIds": [label_id]}).execute()
        count, self._to_mark = len(self._to_mark), []
        return count
