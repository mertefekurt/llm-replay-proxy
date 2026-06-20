from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from llm_replay_proxy.config import ReplayMode, Settings
from llm_replay_proxy.proxy import create_app
from llm_replay_proxy.store import CassetteStore, CassetteStoreError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-replay",
        description="Record and replay OpenAI-compatible API calls.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="start the record/replay proxy")
    serve.add_argument("--upstream", help="upstream base URL, such as https://api.openai.com")
    serve.add_argument(
        "--mode",
        choices=[mode.value for mode in ReplayMode],
        default=ReplayMode.AUTO.value,
        help="recording policy (default: auto)",
    )
    serve.add_argument(
        "--cassette-dir",
        type=Path,
        default=Path(".llm-replay"),
        help="directory for recorded responses (default: .llm-replay)",
    )
    serve.add_argument("--host", default="127.0.0.1", help="listen host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8787, help="listen port (default: 8787)")
    serve.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="upstream timeout in seconds (default: 60)",
    )
    serve.add_argument(
        "--auth-env",
        help="environment variable containing an upstream bearer token",
    )
    serve.add_argument(
        "--log-level",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        default="info",
        help="server log level (default: info)",
    )

    inspect = subparsers.add_parser("inspect", help="list recorded cassettes")
    inspect.add_argument(
        "cassette_dir",
        type=Path,
        nargs="?",
        default=Path(".llm-replay"),
        help="cassette directory (default: .llm-replay)",
    )
    inspect.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="report format (default: text)",
    )
    return parser


def _inspect(directory: Path, output_format: str) -> int:
    store = CassetteStore(directory)
    try:
        cassettes = list(store)
    except CassetteStoreError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    rows = [
        {
            "key": cassette.key,
            "method": cassette.method,
            "path": cassette.path,
            "model": (
                cassette.request_body.get("model")
                if isinstance(cassette.request_body, dict)
                else None
            ),
            "status_code": cassette.response.status_code,
            "recorded_at": cassette.recorded_at,
        }
        for cassette in cassettes
    ]
    if output_format == "json":
        print(json.dumps({"cassette_dir": str(directory), "cassettes": rows}, indent=2))
        return 0

    noun = "cassette" if len(rows) == 1 else "cassettes"
    print(f"{len(rows)} {noun} in {directory}")
    for row in rows:
        model = row["model"] or "-"
        print(
            f"{row['key'][:10]}  {row['method']:<4}  {row['status_code']}  "
            f"{row['path']}  model={model}"
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "inspect":
        return _inspect(args.cassette_dir, args.output_format)

    mode = ReplayMode(args.mode)
    try:
        settings = Settings(
            cassette_dir=args.cassette_dir,
            mode=mode,
            upstream_base_url=args.upstream,
            timeout_seconds=args.timeout,
            auth_env=args.auth_env,
        )
    except ValueError as exc:
        parser.error(str(exc))

    app = create_app(settings)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0
