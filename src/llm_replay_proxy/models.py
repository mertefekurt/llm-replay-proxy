from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class CassetteFormatError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status_code: int
    headers: dict[str, str]
    body: str

    @classmethod
    def from_dict(cls, value: object) -> StoredResponse:
        if not isinstance(value, dict):
            raise CassetteFormatError("response must be an object")
        status_code = value.get("status_code")
        headers = value.get("headers")
        body = value.get("body")
        if not isinstance(status_code, int):
            raise CassetteFormatError("response.status_code must be an integer")
        if not isinstance(headers, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in headers.items()
        ):
            raise CassetteFormatError("response.headers must contain string keys and values")
        if not isinstance(body, str):
            raise CassetteFormatError("response.body must be a string")
        return cls(status_code=status_code, headers=dict(headers), body=body)

    def to_dict(self) -> dict[str, object]:
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
        }


@dataclass(frozen=True, slots=True)
class Cassette:
    key: str
    method: str
    path: str
    query: tuple[tuple[str, str], ...]
    request_body: Any
    response: StoredResponse
    recorded_at: str

    @classmethod
    def create(
        cls,
        *,
        key: str,
        method: str,
        path: str,
        query: tuple[tuple[str, str], ...],
        request_body: Any,
        response: StoredResponse,
    ) -> Cassette:
        return cls(
            key=key,
            method=method,
            path=path,
            query=query,
            request_body=request_body,
            response=response,
            recorded_at=datetime.now(UTC).isoformat(),
        )

    @classmethod
    def from_dict(cls, value: object) -> Cassette:
        if not isinstance(value, dict):
            raise CassetteFormatError("cassette must be an object")
        key = value.get("key")
        method = value.get("method")
        path = value.get("path")
        query = value.get("query")
        recorded_at = value.get("recorded_at")
        if not isinstance(key, str) or len(key) != 64:
            raise CassetteFormatError("cassette.key must be a SHA-256 hex digest")
        if not isinstance(method, str) or not isinstance(path, str):
            raise CassetteFormatError("cassette method and path must be strings")
        if not isinstance(query, list) or not all(
            isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(item, str) for item in pair)
            for pair in query
        ):
            raise CassetteFormatError("cassette.query must contain string pairs")
        if not isinstance(recorded_at, str):
            raise CassetteFormatError("cassette.recorded_at must be a string")
        return cls(
            key=key,
            method=method,
            path=path,
            query=tuple((pair[0], pair[1]) for pair in query),
            request_body=value.get("request_body"),
            response=StoredResponse.from_dict(value.get("response")),
            recorded_at=recorded_at,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "format_version": 1,
            "key": self.key,
            "method": self.method,
            "path": self.path,
            "query": [list(pair) for pair in self.query],
            "request_body": self.request_body,
            "response": self.response.to_dict(),
            "recorded_at": self.recorded_at,
        }
