# NEXUS OS — Canonical Knowledge Base

**Compiled:** 2026-05-15 | **Branch:** clean/security-phase-0 | **HEAD:** b41bb37 (rewritten, no exposed keys)

---

## PROJECT IDENTITY

Nexus OS is a governed, local-first agent operating system. Python/FastAPI governance is canonical. Next.js dashboard (port 3000) is the UI proxy. Windows = control/authoring plane; Linux/WSL = execution sandbox.

---

## 8-PILLAR ARCHITECTURE

| Pillar | Path | Purpose |
|--------|------|---------|
| Bridge | `nexus_os/bridge/` | JSON-RPC server, SDK, secrets, MCP auth, vault bridge |
| Governor | `nexus_os/governor/` | KAIJU gates, TrustEngine v2.2, VAP proof chain, compliance |
| Vault | `nexus_os/vault/` | 5-track memory (EVENT/TRUST/CAP/FAIL/GOV), encryption |
| Engine | `nexus_os/engine/` | Hermes router, executor, skillsmith, tool discipline |
| GMR | `nexus_os/gmr/` | Model rotation, circuit breaker, telemetry, domain mapping |
| Swarm | `nexus_os/swarm/` | Foreman, worker pool, auction, OpenClaw spawner |
| Monitoring | `nexus_os/monitoring/` | TokenGuard, counters, strategies |
| Observability | `nexus_os/observability/` | Tracing, log compression (Squeez) |

---

## WHAT WE BUILT (Full Inventory)

### Phase 0 Security (May 12-14)
- **Terminal Sanitizer** — `src/nexus_os/security/sanitizer.py` (256 lines): TerminalSanitizer (ANSI/VT escape stripper), AgentPTY (dedicated PTY per agent), VerifiableOutput (SHA-256 integrity)
- **AGENTS.md** — Safety-gated autonomous operation rules v2.0 with Pre-Execution Safety Gates (SAFETY-1 through SAFETY-4)
- **AFK Workflow Style** — `docs/handbook/05_NEXUS_AFK_WORKFLOW_STYLE.md`: 5-phase autonomous loop (SCAN→DIGEST→SYNTHESIZE→PRODUCE→VERIFY)
- **Test suite** — 23 security tests in `tests/security/test_sanitizer.py`

### Architecture Plans
- **v4 Master Plan** — `NEXUS_OS_V4_MASTER_PLAN.md` (1,182 lines): 15-section architecture plan. Covers sandbox abstraction, cross-agent security (4-layer), governance mesh unification, TWAVE/QWAVE/CHIMERA speculative decoding, 14-bot Slack network, hallucination detection, 12-week roadmap (Phases 0-6). Core insight: Windows=control, Linux=execution, Cloud=burst.
- **Zo/Claw A2A Integration** — `NEXUS_ZO_CLAW_INTEGRATION_PLAN.md` (374 lines): 4-layer protocol stack (Tailscale→MCP→A2A→OpenClaw), 3 OsmanClaw agents, Kafka bridge decision, MCP tool provider design. **Confluent key redacted from git history.**
- **Full Asset Inventory** — `docs/reviews/...md` (417 lines): Complete resource map. **Azure resources marked DEAD (sub blocked).** 3 Horsemen strategy cancelled.

### Dataset Creation Pipeline (Massive)
**6 versions of stress lab datasets** evolving through v1→v6:

| Version | Rows | Size | Source |
|---------|------|------|--------|
| v1 ISC-Bench | 1,164 | Baseline | 84 ISC templates |
| v2 ISC Expander | 10,000 | 10 phases | Combinatorial expansion |
| v3 Multi-source | 484 | 4 benchmarks | AgentHazard+SOS+Gov+Claws |
| v4 Regenerator | 536,530 | ~385 MB | 13 governance × 13 templates × 12 domains |
| v5 Frontier | 181,000 | ~117 MB scored | 7 frontier types, 11 research sources |
| v6 TAMAS | 6,840 | ~4 MB | 7 attack types, 3 topologies, 5 domains |

**Key files:** `benchmarks/regenerate_datasets.py` (v4), `benchmarks/regenerate_frontier_v5.py` (v5), `benchmarks/stres6_tamas_generator.py` (v6), `benchmarks/stres5_final.py`, `benchmarks/stres5_payload_generator.py`

**Eggroll configs:** 7 per-model MultiReward configs in `foundry_datasets/stress_lab/`. 64 sources scored in `state/dataset_quality/`. Gap analysis found dual_use_detection (21.5%) and tool_misuse (20.7%) as weak spots.

**Total dataset volume:** ~1.5+ GB across 85+ JSONL files, 17 parquet files.

### Dashboard (Next.js, 107 TS files, ~16,800 lines)
26 custom components, 19 API endpoints, 8+1 tab panels, Prisma SQLite with 12 models, Socket.io WebSocket mini-service (port 3003). All tabs wired to real API data. Zero lint errors.

### GitHub Integration
- 12 API providers integrated (NVIDIA, SambaNova, SiliconFlow, OpenCode, Groq, OpenRouter, etc.)
- 14 free provider models routed through AI Provider Bridge
- 4 provider call functions (Nvidia, Sambanova, Siliconflow, Opencode)
- Branch `release/v3.1-dashboard` pushed to `github.com/specimba/nexusalpha`

### Trust Engine v2.2
HARDWALL defense: logistic scaling, adaptive decay, non-compensatory CRITICAL, 6-stage CDR (Nominal→Caution→Restricted→High Risk→Critical→Collapsed). Baseline 25.0, max 99.5.

### GMR System Design
Full rotation engine, telemetry ingest, savings tracker, domain mapping with fallback chains. 74 online models across 10 providers. 15 local Ollama models (62.2 GB).

### .pi/ Agent Workspace
Full architecture deep-dive, expert report synthesis, swarm team design, model registry, rotation table, critical integration review. Pi Agent profile with 6 task patterns.

### STRES5.0 Research
10 new dimensions from 28 forked repos: decensored models, payload conversion matrix, synthetic agent traces, orchestration schema, multi-provider stress, PDF injection, dimension-aware rubrics, data darwinism, speculative decoding probe, MCP tool attacks.

### STRES6.0 (TAMAS Integration)
6 attack types × 3 interaction topologies × 5 domains. 12 base scenarios, 6,840 total rows. ERS metric.

### TWAVE v2.0 + ChimeraRouterV2 — Integrated 2026-05-15
R&D team's HF dataset `specimba/nexus-os-v2` integrated into main repo. New `nexus_os/twave/` package:
- **ChimeraRouterV2** — Tiered model routing (Control→Local Std→Local Power→Cloud) with ERNIE external agent callback, PromptAnalyzer (complexity/safety/code detection), QWAVE budget allocator, 6 temperature policies (FIXED/EDT/EAD/LEAD/AUTO/ERNIE)
- **TWAVE v2.0 Landau-Ginzburg Tracker** — Token-level hallucination control with 5 sub-controllers: EDT (entropy→temperature), LEAD (latent↔discrete switching), EPR (black-box entropy detection), LED (layer-wise exploration), CK-PLUG (retrieval chemical potential)
- **8 model profiles** with capability flags (black-box/white-box, layer access, attention weights)
- **25 tests** all passing. 7 SOTA papers referenced (arXiv 2403.14541, 2603.13366, 2602.01698, 2509.04492, 2503.15888, 2510.05251, 2510.26697)
- Source preserved at `nexus-os-v2-hf/` (gitignored)

### STRES6.1 (Tool Taxonomy Expansion — 2026-05-15)
Closes the TAMAS tools gap: **240 tools across 12 categories** (vs TAMAS's 211). 7 attack types, 720 base scenarios, 7,200 total rows (3.68 MB). Generator at `benchmarks/stres6_tool_taxonomy.py`. Attack templates per tool category matched to vulnerability profiles.

---

## TESTS

| Suite | Count | Status |
|-------|-------|--------|
| Python pytest | 642 tests (632 passed, 10 heartbeat infra-dependent) | 0 collection errors |
| TWAVE v2.0 tests | 25 | All passing |
| Dashboard lint | 0 errors | Clean |

---

## GIT HISTORY CLEANUP (2026-05-15)
- **Confluent key** [REDACTED] scrubbed from `clean/security-phase-0` history via git-filter-repo
- **.env** (with API keys) removed from `clean/security-phase-0` history
- **AZURE_GROK_API_KEY** never committed (only existed locally) — quarantined to `.brv/azure_archive/`
- Full backup: `.brv/git_history_backup/nexus_full_2026-05-15.bundle` (312 MB)
- Other branches (master, main, etc.) have unrelated history and still contain old keys — add to cleanup if needed

---

## WHAT'S DEAD / QUARANTINED

| Asset | Status | Archive Location |
|-------|--------|-----------------|
| Azure subscription | DEAD | `.brv/azure_archive/` |
| Azure AI Gateway (nexus-os-gateway.azure-api.net) | DEAD | same |
| Azure Foundry (rg-OSMANclaw2) | DEAD | same |
| 13 Azure models (Claude Opus 4.7, DeepSeek R1, etc.) | DEAD | same |
| AZURE_GROK_API_KEY | DEAD | same |
| 3 Horsemen Foundry strategy | CANCELLED | same |
| `register_foundry_datasets.py` | DEPRECATED | Header updated |
| `custom_evaluators.py` | DEPRECATED | Header updated |
| v4 plans directory (stale build artifact) | IGNORED | Untracked, .pyc only |
| `docs/usefulthings-01/` (160 stale .pyc files) | ARCHIVED | `.brv/archive_static/docs-usefulthings-01/` |
| `download/` QA screenshots (34 PNG, 3.7 MB) | ARCHIVED | `.brv/archive_static/download/` |
| `session-ses_1e41.md` (590 KB session log) | ARCHIVED | `.brv/archive_static/` |
| `NEXUS.zip` + `NEXUS.zip.tmp` + `docs.zip` | ARCHIVED | `.brv/archive_static/` |
| `Modelfile` (Ollama local config) | ARCHIVED | `.brv/archive_static/` |

---

## WHAT'S PRESERVED (NEXUS-internal "Foundry" — NOT Azure)
- Prisma `FoundryAgent` model — local joker lane agents
- `src/app/api/foundry/route.ts` — uses ZAI SDK, not Azure
- Swarm/Foundry UI components — purely internal concept

---

## CRITICAL BLOCKERS

1. **Azure sub blocked** — All cloud model routing, Foundry pipelines dead. Need alternative inference strategy.
2. ~~**2 test import errors**~~ ✅ **FIXED 2026-05-15** — 617/617 passing
3. **Dashboard needs real Python governance API** — Still using mock/proxy layer on port 3000
4. **DoppelGround gitleaks** — Not resolved, blocks public repo flip
5. **Key still in old branches** — master, main branches not scrubbed
6. **AsyncBridgeExecutor is a stub** — `executor.py:115`, production executor not wired
7. **CVAVerifier is a stub** — `governor/base.py:329`, CVA always passes
8. **43 repair scripts in scripts/** — evidence of ongoing breakage cycles

---

## WHERE WE LEFT OFF

The **last active work** (from `session-ses_1e41.md`, 6,186 lines) was:
- **STRES6.0 TAMAS integration** — Successfully generated 6,840 rows across 3 topologies, 7 attack types
- **Session mid-conversation** — User was asking about TAMAS's "211 tools" and acknowledging "we are only behind at tools"

The **largest completed work items before that:**
1. v4 stress lab dataset regeneration (536K rows)
2. v5 frontier dataset generation (181K rows)  
3. 12 API provider integration
4. Dashboard 8+1 tab completion
5. Phase 0 security module
6. Full dashboard QA (34 screenshots, archived to `.brv/archive_static/download/`)

---

## PORT MAP

| Port | Service | Protocol |
|------|---------|----------|
| 3000 | Next.js Dashboard | HTTP |
| 7352 | Nexus governance API | FastAPI (canonical) |
| 7353 | TWAVE wrapper | HTTP |
| 3003 | WebSocket mini-service | Socket.io |
| 11434 | Local Ollama | HTTP |
