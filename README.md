![LLM Replay Proxy cover](assets/readme-cover.svg)

# LLM Replay Proxy

Record and replay OpenAI-compatible API calls for deterministic local tests.

## Working shape

The repo is meant to be opened, understood, and run quickly. The command surface is deliberately narrow: `llm-replay`.

## Fresh clone

```bash
git clone https://github.com/mertefekurt/llm-replay-proxy.git
cd llm-replay-proxy
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## First command

```bash
llm-replay examples/request.json
```

## Local confidence

```bash
ruff check .
pytest
python -m llm_replay_proxy --help
```
