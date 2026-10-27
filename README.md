# agent-workbench

A bounded tool-calling loop with explicit approvals and replayable event metadata.
Python 3.12–3.14; macOS and Linux. The offline demo runs without API keys.

```console
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip install --no-deps -e .
agent-workbench demo --offline
```

The demo asks the runtime to multiply 6 by 7. The calculator executes, its validated
result goes back to the fixture provider, and the CLI prints `6 × 7 = 42` after a
stream of JSON events. It is a deterministic fixture, not a live model demonstration.
Each run prints its run ID. Replay metadata without repeating the tool operation:

```console
agent-workbench replay RUN_ID --database trace.sqlite3
```

## What works

- Provider interface with an offline fixture and an opt-in Ollama adapter.
- Step, elapsed-time, output-token and tool-result size budgets.
- Strict Pydantic input/output contracts and a per-run tool allowlist.
- Runtime approval checks bound to the run, call, tool and normalized arguments.
- Duplicate call IDs reuse successful results within a run; changed arguments fail.
- Cooperative cancellation during async providers and tools.
- SQLite metadata journal and live event callbacks. Prompts, document text, outputs,
  and exception messages are not persisted.
- Calculator and read-only, 8 KiB document tool using POSIX directory descriptors
  and no-follow opens to reject traversal and symlink escapes.

## Local model

Install and start Ollama separately and select a model already on your machine:

```console
agent-workbench local 'Read overview.md and summarize it' --model YOUR_INSTALLED_MODEL --documents examples/documents
```

This adapter contacts only `127.0.0.1:11434`, disables environment proxies, requests a
bounded response, and does not download weights. Its HTTP contract is tested with a
mock transport; a live model run has not been performed. Model quality and instruction
following are not established by the fixture tests. No paid provider is enabled.

## Development

```console
ruff check .
ruff format --check .
mypy src
pytest --cov=agent_workbench --cov-report=term-missing
python -m build
pip-audit -r requirements-dev.lock --disable-pip
```

`uv.lock` and the hashed pip export lock dependencies. Regenerate both together using
`uv lock` and `uv export --frozen --extra dev --no-emit-project --format requirements-txt --output-file requirements-dev.lock`.
CI runs checks on Python 3.12 and 3.14, builds the wheel/sdist, and smoke-tests the
wheel in a fresh environment. CI has not run on GitHub until this repository is published.

## Boundaries

This is a small library and CLI, not an OS sandbox or hosted agent service. Registered
Python tools are trusted application code and must cooperate with cancellation.
A process that owns the document root can still alter regular files; do not point it
at secrets or attacker-controlled mounts. Token limits use provider-reported output
usage, not a billing guarantee. There is no paid-provider cost estimator.

Replay reads a metadata journal; it does not resume computation after a crash.
Idempotency is per live session, not durable exactly-once delivery. A side effect may
occur before an output-validation failure; the runtime never automatically retries it.
The current adapter returns complete model turns; events stream, model tokens do not.

See [architecture](docs/architecture.md), [approval example](examples/approval.py),
[threat model](docs/threat-model.md), and [roadmap](docs/roadmap.md).

## Ownership and release status

The original source is licensed under [MIT](LICENSE). This is the v0.1.0 source
candidate; no package registry release has been published. Implementation was prepared
with AI assistance. Live-model validation remains a documented follow-up.
