"""Connecteur de pages qui publient leurs offres en PDF : détection des liens, extraction du texte."""
import io
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from urllib.parse import unquote, urljoin, urlparse

from pypdf import PdfReader
from selectolax.lexbor import LexborHTMLParser

from veille_pipeline.connectors.base import SourceConfig
from veille_pipeline.http import PoliteHttpClient
from veille_pipeline.models import RawOffer

MAX_PDFS = 20
MAX_PAGES = 15
MAX_CHARS = 20000


def extract_pdf(content: bytes) -> tuple[str, str | None]:
    """Texte (espaces normalisés, borné) et titre des métadonnées."""
    reader = PdfReader(io.BytesIO(content))
    pages = (page.extract_text() or "" for page in reader.pages[:MAX_PAGES])
    text = re.sub(r"\s+", " ", " ".join(pages)).strip()[:MAX_CHARS]
    title = (reader.metadata.title if reader.metadata else None) or None
    return text, title


class PdfPageConnector:
    kind = "pdf_page"

    def is_configured(self, source: SourceConfig) -> bool:
        return bool(source.get("config", {}).get("pdf_link_pattern"))

    def find_links(self, html: str, page_url: str, config: dict) -> dict[str, str]:
        """{url du PDF: texte du lien}, dans l'ordre de la page."""
        pattern = re.compile(config["pdf_link_pattern"])
        strip = re.compile(config.get("title_strip", r"\s*\(PDF\)\s*$"), re.IGNORECASE)
        links: dict[str, str] = {}
        for a in LexborHTMLParser(html).css(config.get("link_selector", "a[href]")):
            href = a.attributes.get("href") or ""
            if not pattern.search(href):
                continue
            url = urljoin(page_url, href)
            text = strip.sub("", re.sub(r"\s+", " ", a.text(separator=" ")).strip())
            links.setdefault(url, text)
        return links

    def build(self, source_id: str, url: str, link_text: str, content: bytes) -> RawOffer:
        text, meta_title = extract_pdf(content)
        filename = unquote(urlparse(url).path.rsplit("/", 1)[-1])
        return RawOffer(
            source_id=source_id, external_id=url, url=url, fetched_at=datetime.now(UTC),
            payload={"title": link_text or meta_title or filename, "url": url, "text": text})

    def fetch(
        self, source: SourceConfig, since: datetime | None, http: PoliteHttpClient
    ) -> Iterable[RawOffer]:
        config = source["config"]
        if not http.allowed(config["url"]):
            raise PermissionError(f"robots.txt interdit {config['url']}")
        links = self.find_links(http.get(config["url"]).text, config["url"], config)
        known = set(source.get("known_external_ids", ()))
        offers = []
        for url, text in list(links.items())[: int(config.get("max_pdfs", MAX_PDFS))]:
            if url in known:  # PDF déjà vu : pas de nouveau téléchargement
                continue
            response = http.get(url)
            if not response.content.startswith(b"%PDF"):
                continue
            offers.append(self.build(source["id"], url, text, response.content))
        return offers
