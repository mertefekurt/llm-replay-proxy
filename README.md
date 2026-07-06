# LLM Replay Proxy

![LLM Replay Proxy cover](assets/readme-cover.svg)

![stack](https://img.shields.io/badge/stack-Python-16a34a?style=flat-square) ![python](https://img.shields.io/badge/python-3.11-dc2626?style=flat-square) ![license](https://img.shields.io/badge/license-MIT-7c3aed?style=flat-square) ![ci](https://img.shields.io/badge/ci-GitHub%20Actions-0891b2?style=flat-square)

> Record and replay OpenAI-compatible API calls for deterministic local tests

## How I use it

The project stays focused on one job: take a small input, produce a clear result, and avoid adding a heavy service around a problem that fits in a command line.

## Quick start

```bash
python -m pip install -e ".[dev]"
llm-replay examples/request.json
```

## What is inside

```text
.github/        CI workflow
examples/       sample inputs
src/            package source
tests/          test coverage
.gitignore      project file
pyproject.toml  package metadata
```

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
python -m llm_replay_proxy --help
```
