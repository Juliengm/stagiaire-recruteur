"""Client HTTP poli : UA identifiable, délai par domaine, retries, robots.txt."""
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


class PoliteHttpClient:
    def __init__(self, user_agent: str, min_delay_seconds: float = 2.0) -> None:
        self.user_agent = user_agent
        self.min_delay = min_delay_seconds
        self._last_call: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self._client = httpx.Client(
            headers={"User-Agent": user_agent}, timeout=30, follow_redirects=True
        )

    def _wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last_call.get(host, 0.0)
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self._last_call[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser = RobotFileParser()
            try:
                self._wait(parts.netloc)
                resp = self._client.get(f"{origin}/robots.txt")
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    parser.parse([])  # pas de robots.txt : tout est permis
            except httpx.HTTPError:
                parser.parse(["User-agent: *", "Disallow: /"])  # dans le doute, on s'abstient
            self._robots[origin] = parser
        return self._robots[origin].can_fetch(self.user_agent, url)

    @retry(
        retry=retry_if_exception(_retryable),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, max=30),
        reraise=True,
    )
    def request(
        self, method: str, url: str, *, check_robots: bool = True, **kwargs
    ) -> httpx.Response:
        # check_robots=False uniquement pour une API officielle dont l'accès est autorisé
        # par l'opérateur (clé ou appname validé) : robots.txt vise les robots d'indexation.
        if check_robots and not self.allowed(url):
            raise PermissionError(f"robots.txt interdit {url}")
        self._wait(urlparse(url).netloc)
        resp = self._client.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)
