from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

from llm_replay_proxy.models import Cassette, CassetteFormatError

_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class CassetteStoreError(RuntimeError):
    pass


class CassetteStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path_for(self, key: str) -> Path:
        if not _KEY_PATTERN.fullmatch(key):
            raise ValueError("cassette key must be a SHA-256 hex digest")
        return self.directory / f"{key}.json"

    def load(self, key: str) -> Cassette | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cassette = Cassette.from_dict(payload)
        except (OSError, json.JSONDecodeError, CassetteFormatError) as exc:
            raise CassetteStoreError(f"cannot read cassette {path}: {exc}") from exc
        if cassette.key != key:
            raise CassetteStoreError(f"cassette key does not match filename: {path}")
        return cassette

    def save(self, cassette: Cassette) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self._path_for(cassette.key)
        temporary = destination.with_suffix(".json.tmp")
        payload = json.dumps(cassette.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
        try:
            temporary.write_text(f"{payload}\n", encoding="utf-8")
            temporary.replace(destination)
        except OSError as exc:
            raise CassetteStoreError(f"cannot write cassette {destination}: {exc}") from exc
        return destination

    def __len__(self) -> int:
        if not self.directory.exists():
            return 0
        return sum(1 for _ in self.directory.glob("*.json"))

    def __iter__(self) -> Iterator[Cassette]:
        if not self.directory.exists():
            return
        for path in sorted(self.directory.glob("*.json")):
            if not _KEY_PATTERN.fullmatch(path.stem):
                raise CassetteStoreError(f"unexpected cassette filename: {path}")
            cassette = self.load(path.stem)
            if cassette is not None:
                yield cassette
