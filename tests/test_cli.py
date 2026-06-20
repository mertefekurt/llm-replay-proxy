from pathlib import Path

from llm_replay_proxy.cli import build_parser, main
from llm_replay_proxy.models import Cassette, StoredResponse
from llm_replay_proxy.store import CassetteStore


def test_parser_exposes_serve_and_inspect_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["serve", "--mode", "replay"]).command == "serve"
    assert parser.parse_args(["inspect"]).command == "inspect"


def test_inspect_empty_directory(capsys, tmp_path: Path) -> None:
    exit_code = main(["inspect", str(tmp_path)])

    assert exit_code == 0
    assert capsys.readouterr().out == f"0 cassettes in {tmp_path}\n"


def test_inspect_json_includes_model(capsys, tmp_path: Path) -> None:
    cassette = Cassette.create(
        key="f" * 64,
        method="POST",
        path="/v1/chat/completions",
        query=(),
        request_body={"model": "portfolio-model"},
        response=StoredResponse(status_code=200, headers={}, body="{}"),
    )
    CassetteStore(tmp_path).save(cassette)

    exit_code = main(["inspect", str(tmp_path), "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"model": "portfolio-model"' in output
    assert '"status_code": 200' in output
