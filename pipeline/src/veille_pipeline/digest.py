"""Récapitulatif HTML des nouvelles offres pertinentes (SPEC §3.5)."""
import smtplib
from collections import defaultdict
from datetime import date
from email.message import EmailMessage
from typing import Any

from jinja2 import Environment, select_autoescape

_TEMPLATE = """\
<h2>Rapport du stagiaire</h2>
{% if not groups %}<p>Rien de neuf aujourd'hui. Je continue de chercher.</p>{% endif %}
{% for zone, offers in groups.items() %}
<h3>{{ zone }}</h3>
<ul>
{% for o in offers %}
  <li>
    <a href="{{ o.canonical_url }}"><b>{{ o.title }}</b></a>
    — {{ o.organization or "?" }}, {{ o.location_text or "lieu non précisé" }}
    ({{ o.contract_type }}){% if o.deadline %}, date limite :
    <span style="{% if (o.deadline - today).days < 7 %}color:#c00{% endif %}">{{ o.deadline }}</span>{% endif %}
    <br><small>CV conseillé : {{ o.recommended_cv or "—" }} · score {{ "%.2f"|format(o.final_score) }}
    · {{ o.matched_keywords|join(", ") }}</small>
  </li>
{% endfor %}
</ul>
{% endfor %}
"""


def zone_of(offer: dict[str, Any]) -> str:
    if offer.get("country") == "Madagascar":
        return "Madagascar"
    if (offer.get("city") or "").lower() == "lille":
        return "Lille"
    return "Télétravail / international" if offer.get("remote") else "Autres"


def render_digest(offers: list[dict[str, Any]], today: date) -> str:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for offer in sorted(offers, key=lambda o: -o["final_score"]):
        groups[zone_of(offer)].append(offer)
    env = Environment(autoescape=select_autoescape(default=True))
    return env.from_string(_TEMPLATE).render(groups=dict(groups), today=today)


def send_email(html: str, subject: str, to: str, host: str, port: int) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, "stagiaire@localhost", to
    msg.set_content("Ce message est au format HTML.")
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(host, port) as smtp:
        smtp.send_message(msg)
