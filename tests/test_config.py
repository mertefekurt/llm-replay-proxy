from pathlib import Path

import pytest

from llm_replay_proxy.config import ReplayMode, Settings


def test_auto_mode_requires_upstream() -> None:
    with pytest.raises(ValueError, match="upstream_base_url"):
        Settings(cassette_dir=Path("cassettes"))


def test_replay_mode_can_run_offline() -> None:
    settings = Settings(cassette_dir=Path("cassettes"), mode=ReplayMode.REPLAY)

    assert settings.upstream_base_url is None


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("api.example.com", "absolute"),
        ("ftp://api.example.com", "HTTP"),
    ],
)
def test_upstream_url_must_be_http(url: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Settings(cassette_dir=Path("cassettes"), upstream_base_url=url)


def test_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        Settings(
            cassette_dir=Path("cassettes"),
            upstream_base_url="https://api.example.com",
            timeout_seconds=0,
        )
