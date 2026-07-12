from __future__ import annotations

from dataclasses import dataclass, field

import requests
from requests.adapters import HTTPAdapter

from core.constants import VERSION


def _default_user_agent() -> str:
    return f"NewsScraperPro/{VERSION}"


@dataclass(frozen=True)
class HttpClientConfig:
    pool_connections: int = 20
    pool_maxsize: int = 20
    max_retries: int = 0
    user_agent: str = field(default_factory=_default_user_agent)

    def create_session(self) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=max(1, int(self.pool_connections)),
            pool_maxsize=max(1, int(self.pool_maxsize)),
            max_retries=max(0, int(self.max_retries)),
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"User-Agent": self.user_agent})
        return session
