"""Récapitulatif HTML des nouvelles offres pertinentes (SPEC §3.5)."""
import smtplib
from collections import defaultdict
from datetime import date
from email.message import EmailMessage
from typing import Any

import httpx
from db.rules import CLOSED_STATUSES, ZONES, zone_code
from jinja2 import Environment, select_autoescape

_TEMPLATE = """\
<h2>Rapport du stagiaire</h2>
{% if interface_url %}<p><a href="{{ interface_url }}">Trier les offres et suivre les candidatures dans l'interface</a></p>{% endif %}
{% if follow_ups %}
<h3>Relances à faire</h3>
<ul>
{% for f in follow_ups %}
  <li><b>{{ f.organization or "?" }}</b> — {{ f.position or "poste non précisé" }}
    {% if f.sent_at %}(candidature du {{ f.sent_at }}){% endif %},
    relance prévue le <span style="{% if f.overdue_days > 0 %}color:#c00{% endif %}">{{ f.follow_up_at }}</span>
    {% if f.overdue_days > 0 %}({{ f.overdue_days }} j de retard){% endif %}
    {% if f.contact %}· contact : {{ f.contact }}{% endif %}
  </li>
{% endfor %}
</ul>
{% endif %}
{% if not groups and not follow_ups %}<p>Rien de neuf aujourd'hui. Je continue de chercher.</p>{% endif %}
{% for zone, offers in groups.items() %}
<h3>{{ zone }}</h3>
<ul>
{% for o in offers %}
  <li>
    <a href="{{ o.canonical_url }}"><b>{{ o.title_short }}</b></a>
    — {{ o.organization or "?" }}, {{ o.location_text or "lieu non précisé" }}
    ({{ o.contract_label }}){% if o.deadline %}, date limite :
    <span style="{% if (o.deadline - today).days < 7 %}color:#c00{% endif %}">{{ o.deadline }}</span>{% endif %}
    <br><small>CV conseillé : {{ o.recommended_cv or "—" }} · score {{ "%.2f"|format(o.final_score) }}
    · {{ o.matched_keywords|join(", ") }}</small>
  </li>
{% endfor %}
</ul>
{% endfor %}
"""


def zone_of(offer: dict[str, Any]) -> str:
    return ZONES[zone_code(offer.get("country"), offer.get("city"), offer.get("remote"))]


ZONE_ORDER = list(ZONES.values())
CONTRACT_LABELS = {
    "cdi": "CDI", "cdd": "CDD", "consultancy": "consultance", "roster": "roster",
    "volunteer": "volontariat", "internship": "stage", "tender": "appel d'offres",
    "unknown": "contrat non précisé",
}


def _shorten(title: str, limit: int = 110) -> str:
    return title if len(title) <= limit else title[: limit - 1].rstrip() + "…"


def subject_for(count: int, follow_ups: int = 0) -> str:
    parts = [f"{count} offre{'s' if count > 1 else ''}"] if count or not follow_ups else []
    if follow_ups:
        parts.append(f"{follow_ups} relance{'s' if follow_ups > 1 else ''}")
    return "Rapport du stagiaire — " + ", ".join(parts)


def due_follow_ups(applications: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """Candidatures dont la relance est due (date atteinte), les plus en retard d'abord."""
    due = [
        {**a, "overdue_days": (today - a["follow_up_at"]).days}
        for a in applications
        if a.get("follow_up_at") and a["follow_up_at"] <= today
        and (a.get("status") or "").lower() not in CLOSED_STATUSES
    ]
    return sorted(due, key=lambda a: (-a["overdue_days"], a.get("organization") or ""))


def render_digest(offers: list[dict[str, Any]], today: date,
                  follow_ups: list[dict[str, Any]] | None = None,
                  interface_url: str | None = None) -> str:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for offer in sorted(offers, key=lambda o: -o["final_score"]):
        enriched = {
            **offer,
            "title_short": _shorten(offer["title"]),
            "contract_label": CONTRACT_LABELS.get(offer.get("contract_type") or "unknown", "contrat non précisé"),
        }
        groups[zone_of(offer)].append(enriched)
    ordered = {zone: groups[zone] for zone in ZONE_ORDER if zone in groups}
    env = Environment(autoescape=select_autoescape(default=True))
    return env.from_string(_TEMPLATE).render(groups=ordered, today=today, follow_ups=follow_ups or [],
                                             interface_url=interface_url)


def send_email(html: str, subject: str, to: str, host: str, port: int) -> None:
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, "stagiaire@localhost", to
    msg.set_content("Ce message est au format HTML.")
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(host, port) as smtp:
        smtp.send_message(msg)


DISCORD_LIMIT = 2000
DISCORD_MAX_OFFERS = 10
_ZONE_ICON = {"Madagascar": "🇲🇬", "Lille": "📍", "Télétravail / international": "🌍", "Autres": "▫️"}


def render_discord(offers: list[dict[str, Any]], today: date,
                   follow_ups: list[dict[str, Any]] | None = None,
                   interface_url: str | None = None) -> str:
    """Message Discord compact : 10 offres au plus (les mieux notées), moins de 2 000 caractères."""
    head = [f"**{subject_for(len(offers), len(follow_ups or []))}**"]
    if follow_ups:
        head.append("**Relances à faire**")
        for f in follow_ups[:5]:
            late = f" ({f['overdue_days']} j de retard)" if f["overdue_days"] > 0 else ""
            head.append(f"• {f.get('organization') or '?'} — {f.get('position') or 'poste ?'}"
                        f", relance du {f['follow_up_at']}{late}")
    lines = list(head)
    footer = [f"Interface : <{interface_url}>"] if interface_url else []
    reserve = 60 + sum(len(f) + 1 for f in footer)  # « … et N autres » + lien vers l'interface
    kept = 0
    for o in sorted(offers, key=lambda o: -o["final_score"])[:DISCORD_MAX_OFFERS]:
        deadline = f" · avant le {o['deadline']}" if o.get("deadline") else ""
        where = o.get("city") or o.get("country") or ("télétravail" if o.get("remote") else "?")
        line = (f"{_ZONE_ICON[zone_of(o)]} [{_shorten(o['title'], 80)}](<{o['canonical_url']}>)"
                f" — {o.get('organization') or '?'}, {where}{deadline}")
        if len("\n".join([*lines, line])) > DISCORD_LIMIT - reserve:
            break
        lines.append(line)
        kept += 1
    if len(offers) > kept:
        lines.append(f"… et {len(offers) - kept} autres dans l'e-mail.")
    return "\n".join([*lines, *footer])


def send_discord(webhook_url: str, content: str) -> None:
    """Poste le message via un webhook de salon (réponse 204)."""
    httpx.post(webhook_url, json={"content": content, "allowed_mentions": {"parse": []}},
               timeout=15).raise_for_status()
