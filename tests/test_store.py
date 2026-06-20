import json
from pathlib import Path

import pytest

from llm_replay_proxy.models import Cassette, StoredResponse
from llm_replay_proxy.store import CassetteStore, CassetteStoreError


def make_cassette(key: str = "a" * 64) -> Cassette:
    return Cassette.create(
        key=key,
        method="POST",
        path="/v1/responses",
        query=(),
        request_body={"model": "demo"},
        response=StoredResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body='{"ok":true}',
        ),
    )


def test_store_round_trip_and_iteration(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    cassette = make_cassette()

    path = store.save(cassette)
    loaded = store.load(cassette.key)

    assert path.exists()
    assert loaded == cassette
    assert list(store) == [cassette]
    assert len(store) == 1


def test_store_returns_none_for_missing_key(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)

    assert store.load("b" * 64) is None
    assert len(store) == 0


def test_store_rejects_invalid_key(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)

    with pytest.raises(ValueError, match="SHA-256"):
        store.load("../secret")


def test_store_reports_malformed_cassette(tmp_path: Path) -> None:
    path = tmp_path / f"{'c' * 64}.json"
    path.write_text(json.dumps({"key": "wrong"}), encoding="utf-8")

    with pytest.raises(CassetteStoreError, match="cannot read cassette"):
        CassetteStore(tmp_path).load("c" * 64)


def test_store_detects_filename_key_mismatch(tmp_path: Path) -> None:
    cassette = make_cassette("d" * 64)
    path = tmp_path / f"{'e' * 64}.json"
    path.write_text(json.dumps(cassette.to_dict()), encoding="utf-8")

    with pytest.raises(CassetteStoreError, match="does not match"):
        CassetteStore(tmp_path).load("e" * 64)


def test_store_reports_unexpected_json_filename(tmp_path: Path) -> None:
    (tmp_path / "notes.json").write_text("{}", encoding="utf-8")

    with pytest.raises(CassetteStoreError, match="unexpected cassette filename"):
        list(CassetteStore(tmp_path))
