from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl


@dataclass(frozen=True, slots=True)
class RequestFingerprint:
    key: str
    method: str
    path: str
    query: tuple[tuple[str, str], ...]
    body: Any


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def fingerprint_request(
    method: str,
    path: str,
    query: str,
    body: Any,
) -> RequestFingerprint:
    normalized_method = method.upper()
    normalized_path = f"/{path.lstrip('/')}"
    normalized_query = tuple(sorted(parse_qsl(query, keep_blank_values=True)))
    fingerprint_payload = {
        "body": body,
        "method": normalized_method,
        "path": normalized_path,
        "query": normalized_query,
    }
    key = hashlib.sha256(canonical_json(fingerprint_payload).encode("utf-8")).hexdigest()
    return RequestFingerprint(
        key=key,
        method=normalized_method,
        path=normalized_path,
        query=normalized_query,
        body=body,
    )
