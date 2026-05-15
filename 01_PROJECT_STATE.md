# NEXUS OS - Canonical Project State

Date: 2026-04-21
Current local HEAD: Cloud sandbox (synced via GVAW)
Status: M3 hardened baseline preserved; Phase 0 grounding in progress.

## Verification Gate

Latest local verification:

```text
617 passed in 24.09s
```

All `pytest.mark.skip` removed. Hermes, GMR, VaultManager, Coordinator, TokenGuard migrated to V3.
Vault uses the canonical 5-track schema (`store_track` / `retrieve_track`).
**2026-05-15: Fixed 2 pre-existing import errors** — test collection now clean at 617/617.

## Core Thesis

Nexus OS turns local models, research evidence, and external teams into a governed, audited, low-VRAM execution system where every action is proposal-bound, test-gated, and provenance-tracked.

- **DoppelGround** prepares evidence.
- **Nexus** governs, routes, audits, and approves.
- **TWAVE** executes within VRAM limits.
- **GeniusTurtle** makes it usable.
- **Model Arena** proves what actually works on local hardware.

## System Boundaries

| Layer | Canonical Role | Current Rule |
|-------|---------------|--------------|
| GeniusTurtle | Operator UX layer | UI/API integration only; no model weights, secrets, or governance internals. |
| Nexus OS | Governance and orchestration layer | Python/FastAPI governance is the canonical brain. |
| DoppelGround | Evidence preparation layer | USE MODE; outputs must be sanitized before handoff. |
| TWAVE | Low-VRAM execution layer | HOLD; wrapper/API work only, no algorithm changes. |
| Model Arena | Evidence/evaluation layer | Report-only; no automatic model deletion, fine-tuning, or promotion. |

## Core Architecture Map

| Pillar | Purpose | Canonical Areas |
|--------|---------|-----------------|
| Bridge | Protocol boundary, API ingress, SDK/MCP adapters | `nexus_os/bridge/`, `nexus_os/relay/` |
| Governor | KAIJU, policy, compliance, trust gates, TrustEngine v2.2 | `nexus_os/governor/` |
| Vault | Durable storage, 5-track memory, encryption policy | `nexus_os/vault/`, `nexus_os/db/` |
| Engine/GMR | DAG routing, Hermes/GMR decisions, execution flow | `nexus_os/engine/`, `nexus_os/gmr/` |
| Swarm | Worker orchestration, foreman coordination | `nexus_os/swarm/` |
| Monitoring | TokenGuard, VAP/audit, telemetry | `nexus_os/monitoring/`, `nexus_os/observability/` |

## What Is Verified

- Full test suite passes locally: **617 passed**.
- DB encryption policy hard-fails by default and allows plaintext fallback only when `allow_unencrypted=True`.
- Engine task dependency cycle detection is present and verified.
- TrustEngine v2.2 implements HARDWALL defenses: logistic scaling, adaptive decay, non-compensatory CRITICAL, 6-stage CDR.
- Vault uses canonical 5-track schema (`store_track` / `retrieve_track`).
- Bridge secrets management with per-provider health logging.

## Cloud Dashboard (Next.js)

Port 3000 — Full 8-pillar command center:
- Overview, StressLab, GMR Router, Governor, Vault, Research, Swarm, Token Budget
- AI Assistant (z-ai-web-dev-sdk LLM)
- Command Palette (Ctrl+K), System Logs (Ctrl+L)
- Interactive features: test runner, trust threshold adjustment, model toggle
- Prisma ORM + SQLite for data persistence

## Accepted Principles

- Governance Control Plane first: Python/FastAPI is canonical.
- Dashboard second: Bun/Next/relay layers must proxy governance state, not contain governance decisions.
- Retroactive provenance starts dry-run/report-only.
- Mini Model Arena starts in Phase 0 as a bounded evidence tool.
- GVAW is mandatory for externalized work: proposal-linked branches, VAP/trust trailers, reviewed merges.
- Public/private split is required before launch.
- Cloud/local OpenClaw coordination uses Git as the bus; cloud writes tasks/specs, local runs GPU/model/TWAVE work.

## Rejected Or Parked

- Bun relay calling Python classes directly.
- Auto-committing retroactive provenance.
- Broad `git add .` without review.
- Deleting model packs without inventory, backup, and rollback path.
- Heretic/uncensoring or fine-tuning in P0.
- External handoff before DoppelGround leak status is resolved.
- Claims of cryptographic VAP, full A2A, OWASP ASI, SkillFortify, or production ASBOM maturity unless locally verified.

## Critical Blockers

1. DoppelGround leak status must be resolved before external handoff or public repo flip.
2. Dashboard/relay still needs real governance API wiring.
3. GSPP reference assets need reconciliation before they become canonical.
4. Public launch files still need security/legal review before staging.
5. Sandbox/mock env files must not be committed without an explicit policy decision.

## Canonical P0 Sequence

1. Reverify the test baseline before core commits.
2. Keep Git clean with explicit-path staging only.
3. Triage DoppelGround gitleaks report to real secret vs false positive.
4. Add or update a canonical integration ledger for repos, ports, APIs, and protected files.
5. Build Python/FastAPI governance endpoints: `/skills/propose`, `/skills/status/{id}`, `/dashboard/stats`, `/governance/proposals`, `/governance/approve`.
6. Update dashboard/relay to consume the Python governance API.
7. Add `nexus-scan.py` as dry-run provenance inventory only.
8. Add `model_arena/mini_arena.py` as report-only evidence collection.
9. Build `nexus_knowledge_base/` from sanitized DoppelGround exports with evidence hashes and quality labels.
10. Handoff to external teams only after security and governance API gates pass.

## Port Map

| Port | Service | Protocol |
|------|---------|----------|
| 3000 | Next.js Dashboard (Cloud) | HTTP |
| 7352 | Nexus governance/control API | FastAPI |
| 7353 | TWAVE wrapper (`/twave/*`) | HTTP |
| 11434 | Local Ollama (internal only) | HTTP |

## TrustEngine v2.2 Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Baseline Score | 25.0 | Starting trust for new agents |
| Max Score | 99.5 | Asymptotic plateau (never 100) |
| Success Delta | 4.0 × logistic(T) | Anti-gaming via logistic scaling |
| Failure Delta | -10.0 | Standard failure penalty |
| CRITICAL Delta | -20.0 | Non-compensatory hard block |
| Base Decay λ | 0.02 | Temporal decay rate |
| CDR Collapse | <15.0 | Minimum trust for collapse |
| CDR Escalation | <30.0 | Threshold for degraded reasoning |
