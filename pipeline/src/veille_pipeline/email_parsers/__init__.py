"""Un parseur par expéditeur : message e-mail → offres (dictionnaires bruts)."""
from collections.abc import Callable
from email.message import EmailMessage
from typing import Any

from veille_pipeline.email_parsers.developmentaid import parse_developmentaid
from veille_pipeline.email_parsers.linkedin import parse_linkedin
from veille_pipeline.email_parsers.unvacancies import parse_unvacancies

EmailParser = Callable[[EmailMessage], list[dict[str, Any]]]
PARSERS: dict[str, EmailParser] = {
    "linkedin": parse_linkedin,
    "developmentaid": parse_developmentaid,
    "unvacancies": parse_unvacancies,
}
