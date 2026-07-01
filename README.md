<img width="1280" height="720" alt="8ddbe9cf-228e-4086-bd4a-dd925476e49a (1)" src="https://github.com/user-attachments/assets/f6ac3954-3d5d-4b86-8315-5471c797d8e2" />


# NEXUS OS — Governed Agent Operating System

Nexus OS is a governed, local-first agent operating system whose Python core makes every agent action proposal-bound, test-gated, trust-scored, and auditable.

> Scope note: this repository is the Python governance core (`nexus_os`). The broader dashboard, dataset pipeline, and multi-provider routing system are described in `NEXUS_OS_V4_MASTER_PLAN.md` and `01_PROJECT_STATE.md`; they are not implemented here.

## Table of Contents

- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Module Guide](#module-guide)
- [Testing](#testing)
- [Contributing](#contributing)
- [Documentation Index](#documentation-index)
- [License](#license)
- [Attribution](#attribution)

## Architecture

Nexus OS is organized as a small governance core around the `nexus_os` package:

```text
bridge -> governor -> engine -> relay
   |         |          |        |
   |         |          |        +-> security
   |         |          +-> monitoring / observability
   |         +-> vault
   +-> external JSON-RPC boundary

stresslab, swarm, and twave provide specialized execution, benchmarking, and routing logic.
```

- **Bridge** handles JSON-RPC ingress and structured error propagation.
- **Governor** enforces KAIJU gates and TrustEngine scoring.
- **Vault** stores governed memory with encryption policy enforcement.
- **Engine** routes tasks through Hermes and executes them through the bridge.
- **Monitoring** enforces token budgets through TokenGuard.
- **Observability** provides tracing and log compression.
- **Relay** exposes the transparent model relay proxy.
- **Security** strips terminal escapes, isolates PTYs, and verifies output integrity.
- **StressLab** runs ISC benchmark jobs.
- **Swarm** executes worker/task coordination.
- **TWAVE** handles routing, prompt analysis, and hallucination tracking.

For system-wide port and service planning, refer to the design docs rather than this repository.

## Repository Structure

```text
.
├── README.md
├── AGENTS.md
├── SECURITY.md
├── knowledge.md
├── 01_PROJECT_STATE.md
├── NEXUS_OS_V4_MASTER_PLAN.md
├── worklog.md
├── pyproject.toml
├── .gitignore
├── nexus_os/
│   ├── __init__.py
│   ├── exceptions.py
│   ├── bridge/
│   │   ├── __init__.py
│   │   └── server.py
│   ├── db/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── executor.py
│   │   └── hermes.py
│   ├── governor/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── trust_engine.py
│   ├── monitoring/
│   │   ├── __init__.py
│   │   └── token_guard.py
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── squeez.py
│   │   └── tracing.py
│   ├── relay/
│   │   ├── __init__.py
│   │   └── model_relay.py
│   ├── security/
│   │   ├── __init__.py
│   │   └── sanitizer.py
│   ├── stresslab/
│   │   ├── __init__.py
│   │   └── isc_runner.py
│   ├── swarm/
│   │   ├── __init__.py
│   │   └── worker.py
│   ├── twave/
│   │   ├── __init__.py
│   │   ├── chimera_router.py
│   │   ├── prompt_analyzer.py
│   │   └── tracker.py
│   ├── vault/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── cron/            # placeholder package; __init__.py only
│   ├── gmr/             # placeholder package; __init__.py only
│   └── team/            # placeholder package; __init__.py only
└── tests/
    ├── db/
    ├── observability/
    ├── relay/
    ├── stresslab/
    ├── twave/
    └── test_error_handling.py
```

There is no `src/`, `prisma/`, `benchmarks/`, `docs/`, `scripts/`, `bin/`, `foundry_datasets/`, `research/`, frontend app, or `package.json` in this repository.

## Requirements

- Python 3.11 or newer
- Runtime dependencies: none
- Development dependencies: `pytest>=7.0`, `ruff>=0.4`
- Build backend: `setuptools.build_meta`
- Ruff configuration: line length 120, target `py311`, lint select `E,F,W,I`

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest tests/ -q --ignore=tests/relay/test_model_relay.py
ruff check nexus_os tests
ruff format --check nexus_os tests
```

If editable install is unavailable in a constrained environment, install the dev tools directly with `pip install pytest ruff`.

## Module Guide

| Module | Purpose |
| --- | --- |
| `nexus_os/__init__.py` | Nexus OS package root. |
| `nexus_os/exceptions.py` | Central exception hierarchy for governed errors. |
| `nexus_os/bridge/server.py` | JSON-RPC 2.0 bridge server with structured `BridgeError` propagation. |
| `nexus_os/db/manager.py` | Thread-safe SQLite/PostgreSQL manager with connection pooling and encryption policy enforcement. |
| `nexus_os/engine/executor.py` | Task executor wired to Bridge RPC that surfaces `ExecutionError`. |
| `nexus_os/engine/hermes.py` | Hermes router and task classifier with structured `TaskDomain` classification. |
| `nexus_os/governor/base.py` | KAIJU gates and Core Value Alignment verification. |
| `nexus_os/governor/trust_engine.py` | TrustEngine v2.2 HARDWALL defense with 6-stage CDR lifecycle. |
| `nexus_os/monitoring/token_guard.py` | TokenGuard budget enforcement with ECO, BALANCED, FAST, and UNLIMITED strategies. |
| `nexus_os/observability/squeez.py` | Squeez structured-log compression via pattern dedup, field extraction, and RLE. |
| `nexus_os/observability/tracing.py` | Tracing utilities for governance operations. |
| `nexus_os/relay/model_relay.py` | Transparent model relay proxy. |
| `nexus_os/security/sanitizer.py` | TerminalSanitizer, AgentPTY isolation, and VerifiableOutput integrity checks. |
| `nexus_os/stresslab/isc_runner.py` | ISC benchmark runner. |
| `nexus_os/swarm/worker.py` | Swarm worker execution and coordination. |
| `nexus_os/twave/chimera_router.py` | ChimeraRouterV2 tiered model routing with ERNIE callback. |
| `nexus_os/twave/prompt_analyzer.py` | PromptAnalyzer for complexity, safety, and code detection. |
| `nexus_os/twave/tracker.py` | Landau-Ginzburg hallucination tracker with EDT, LEAD, EPR, LED, and CK-PLUG controllers. |
| `nexus_os/vault/manager.py` | Vault 5-track memory manager with encryption policy enforcement. |
| `nexus_os/cron/` | Placeholder package; `__init__.py` only. |
| `nexus_os/gmr/` | Placeholder package; `__init__.py` only. |
| `nexus_os/team/` | Placeholder package; `__init__.py` only. |

## Testing

Current local baseline:

- `python -m pytest tests/ -q --ignore=tests/relay/test_model_relay.py` → **208 passed**
- `ruff check nexus_os tests` → currently reports existing import and formatting issues in `nexus_os/bridge/server.py`, `nexus_os/engine/executor.py`, `nexus_os/engine/hermes.py`, `nexus_os/governor/base.py`, `nexus_os/vault/manager.py`, and `tests/test_error_handling.py`
- `ruff format --check nexus_os tests` → currently reports 22 files would be reformatted

The full test command, `python -m pytest tests/ -q`, currently hits one collection error in `tests/relay/test_model_relay.py`. That test imports `BackendConfig`, `BackendType`, `HealthSnapshot`, and `RelayStatus`, but `nexus_os.relay.model_relay` exports `ProviderStatus`, `ProviderHealth`, `RelayRequest`, `RelayResponse`, and `ModelRelay`. The relay test and relay module API are not aligned yet.

## Contributing

Follow `AGENTS.md` for operating rules: work from filesystem reality, keep changes bounded, use explicit-path staging, avoid `git add .`, and keep changes test-gated and auditable. Refer to `SECURITY.md` before making security-sensitive edits.

## Documentation Index

| Document | Purpose |
| --- | --- |
| `AGENTS.md` | Agent operating protocol and git discipline. |
| `SECURITY.md` | Security guidance and handling expectations. |
| `knowledge.md` | Project knowledge base and historical context. |
| `01_PROJECT_STATE.md` | Canonical current state of the project. |
| `NEXUS_OS_V4_MASTER_PLAN.md` | Larger design and roadmap reference. |
| `worklog.md` | Work history and session notes. |

## License

Internal — R&D (no public license declared).

## Attribution

_Originally written and maintained by contributors and [Devin](https://app.devin.ai)._