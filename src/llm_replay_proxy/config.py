from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse


class ReplayMode(StrEnum):
    RECORD = "record"
    REPLAY = "replay"
    AUTO = "auto"


@dataclass(frozen=True, slots=True)
class Settings:
    cassette_dir: Path
    mode: ReplayMode = ReplayMode.AUTO
    upstream_base_url: str | None = None
    timeout_seconds: float = 60.0
    auth_env: str | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.mode is not ReplayMode.REPLAY and not self.upstream_base_url:
            raise ValueError("upstream_base_url is required in auto and record modes")
        if self.upstream_base_url:
            parsed = urlparse(self.upstream_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("upstream_base_url must be an absolute HTTP(S) URL")
