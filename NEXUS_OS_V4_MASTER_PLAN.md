# NEXUS OS v4.0 — Master Architecture & Improvement Plan

**Author:** Speci (R&D Lead)  
**Date:** 2026-05-12  
**Classification:** Internal — R&D Backend Team  
**Status:** Planning Phase — 12hr Deep Research Complete  

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Current State Assessment](#2-current-state-assessment)
3. [The Core Problem: Windows as a Local-First Bottleneck](#3-the-core-problem)
4. [Sandbox Architecture: Multi-Tier Isolated Execution](#4-sandbox-architecture)
5. [Cross-Agent Security: Immunity Against Terminal Poisoning & Prompt Injection](#5-cross-agent-security)
6. [Governance Mesh: Unified KAIJU + VAP + TokenGuard](#6-governance-mesh)
7. [TWAVE/QWAVE/CHIMERA: Practical Inference Integration](#7-twave-qwave-chimera)
8. [Communication Plane: Zo + Slack + Telegram + NEXUS Internal Bus](#8-communication-plane)
9. [Speculative Decoding Integration Map](#9-speculative-decoding)
10. [Hallucination Detection & Prevention Framework](#10-hallucination-detection)
11. [Code Reconciliation: NEXUS Main ↔ HERMES Swarm Pack](#11-code-reconciliation)
12. [Deployment Tiers & Platform Strategy](#12-deployment-tiers)
13. [Phase Roadmap (12-Week Sprint)](#13-phase-roadmap)
14. [Risk Register](#14-risk-register)
15. [Appendix: Document Index](#15-appendix)

---

## 1. Executive Summary

NEXUS OS has three independent but complementary implementations: the **main repo** (full governance OS), the **HERMES swarm pack** (NVIDIA OpenShell sandbox + Gastown), and **Docker Gordon's Phase 1** (Kafka bridge + monitoring). They must be unified.

The core insight from this deep research cycle:

> **Windows is not the deployment target — it is the development and control plane. Linux (via disposable Docker containers, WSL2, or cloud VMs) is the execution target.**

This means:
- **Local-first = Linux-first** for agent execution sandboxes
- **Windows = Authoring, governance, dashboard, orchestration**
- **Cloud = Burst capacity, speculative decoding, HF sandbox fallback**
- **All communication = E2E encrypted, VAP-audited, KAIJU-gated**

---

## 2. Current State Assessment

### 2.1 What Is Running Right Now

| Component | Status | Location | Purpose |
|-----------|--------|----------|---------|
| NEXUS Main Repo (v3) | Working | `C:\Users\speci.000\Documents\NEXUS` | Full governance OS: KAIJU, VAP, TokenGuard, GMR, Bridge, Dashboard (7352) |
| NEXUS Main Tests | 796 passing | `tests/` | Core test suite |
| Pi Agent | Active | `.pi/` | Autonomous coding agent with SOVEREIGN mode |
| Docker Gordon Phase 1 | Live | `DOCKERaiGORDON/` | Kafka bridge → Confluent Cloud, consumer, dashboard (8000), monitoring (9090, 3000) |
| Supabase Stack | Live | Docker containers | Full Supabase: DB (54322), auth, storage, realtime, analytics |
| HERMES Swarm Pack | Review only | `HERMES/hermes-agent/nexus-swarm-pack` | NVIDIA OpenShell integration, Gastown beads, Zilliz dual-cluster |
| Zo Computer | Active | `specimba.zo.computer` | Cloud orchestrator, Slack bot network hub |
| Grafana + Prometheus | Live | Docker | Full observability stack |
| Redis | Live | Docker | Token budget caching, session state |
| 8 GitHub Repos | Configured | specimba org | Code repositories to govern |

### 2.2 Critical Gaps Identified

1. **No agent sandbox isolation in NEXUS main** — agents run with full filesystem access
2. **Duplicate governance code** — KAIJU/VAP/TokenGuard exist in both NEXUS main AND HERMES swarm pack
3. **No cross-agent prompt injection protection** — terminal poisoning attack proved the vulnerability
4. **No hallucination detection layer** — outputs accepted at face value
5. **No E2E encryption for agent intercommunication**
6. **Windows dependency** — many hardcoded `C:\...` paths, PowerShell scripts
7. **Gordon's quota exhausted** — Phase 1 bridge needs maintenance without him
8. **No unified deployment model** — 3+ parallel architectures without integration
9. **Speculative decoding research not mapped to implementation**
10. **No slack/telegram bridge operational** — planned but not built

---

## 3. The Core Problem: Windows as a Local-First Bottleneck

### 3.1 What Windows Does Well (KEEP)

| Function | Why Windows | Component |
|----------|-------------|-----------|
| Authoring IDE | VS Code, best-in-class dev tools | Development workflow |
| Governance Dashboard | FastAPI + React frontend | Dashboard 2 (port 8000) |
| Orchestration Control | Zo computer integration | Command & control |
| Audit Review | VAP chain verification | Compliance |
| Secret Management | Windows Credential Manager | API key storage |

### 3.2 What Windows Does Poorly (REPLACE)

| Function | Windows Limitation | Linux/Docker Solution |
|----------|-------------------|----------------------|
| Agent execution sandbox | No native container isolation, Docker translation overhead | disposable Docker containers or WSL2 |
| GPU inference | CUDA version hell, driver conflicts | Linux-native containers with NVIDIA runtime |
| Speculative decoding | Llama.cpp/vLLM harder to configure | Native Linux performance |
| Network isolation | Complex firewall rules | OpenShell policy bands |
| File system sandboxing | No native equivalent | Linux namespaces + seccomp |

### 3.3 The Hybrid Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    WINDOWS (Control Plane)                       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │  VS Code │  │Dashboard │  │ KAIJU    │  │  Zo Client     │  │
│  │  (Dev)   │  │ (8000)   │  │ Governor │  │  (Slack/Orch)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
│         │            │             │                │            │
│         └────────────┼─────────────┼────────────────┘            │
│                      ▼             ▼                             │
│              ┌────────────┐  ┌──────────┐                        │
│              │  VAP Chain │  │ Vault    │                        │
│              │  (Audit)   │  │ (Memory) │                        │
│              └────────────┘  └──────────┘                        │
│                      │             │                             │
└──────────────────────┼─────────────┼─────────────────────────────┘
                       │             │
         ┌─────────────┼─────────────┼─────────────────────────┐
         │             ▼             ▼                         │
         │     ┌────────────────────────────┐                   │
         │     │   WSL2 / Docker Desktop    │  WINDOWS HOST     │
         │     │   (Linux Translation)      │                   │
         │     └────────────┬───────────────┘                   │
         │                  ▼                                   │
         │     ┌────────────────────────────────────┐           │
         │     │     DISPOSABLE LINUX SANDBOXES      │           │
         │     │                                     │           │
         │     │  ┌──────────┐  ┌──────────┐        │           │
         │     │  │ Codex    │  │ OpenCode │        │           │
         │     │  │ Sandbox  │  │ Analysis │        │           │
         │     │  │ (Python) │  │ Sandbox  │        │           │
         │     │  └──────────┘  └──────────┘        │           │
         │     │  ┌──────────┐  ┌──────────┐        │           │
         │     │  │Inference │  │ Web      │        │           │
         │     │  │ Sandbox  │  │ Search   │        │           │
         │     │  │ (GPU)    │  │ Sandbox  │        │           │
         │     │  └──────────┘  └──────────┘        │           │
         │     └────────────────────────────────────┘           │
         │                                                     │
         │     ┌────────────────────────────────────┐           │
         │     │        CLOUD BURST TIER             │           │
         │     │  HF Sandbox → Reasoning tasks       │           │
         │     │  OpenShell → High-isolation exec    │           │
         │     │  Confluent → Event streaming        │           │
         │     │  Zilliz → Vector memory             │           │
         │     └────────────────────────────────────┘           │
         └─────────────────────────────────────────────────────┘
```

### 3.4 Platform Detection & Adaptive Deployment

Each NEXUS deployment detects its platform and selects the appropriate execution backend:

```python
# Platform detection in boot sequence
def detect_platform():
    if sys.platform == "win32":
        # Windows: prefer WSL2 sandbox, fallback to Docker Desktop
        if has_wsl2():
            return PlatformConfig(
                control="native",
                execution="wsl2_containers",
                isolation_level=ISOLATION_FULL,
                gpu_available=check_nvidia_wsl(),
            )
        elif has_docker_desktop():
            return PlatformConfig(
                control="native",
                execution="docker_linux_containers",
                isolation_level=ISOLATION_FULL,
                gpu_available=False,  # Docker Desktop GPU pass-through unreliable
            )
        else:
            return PlatformConfig(
                control="native",
                execution="subprocess_local",  # Fallback - NO sandbox
                isolation_level=ISOLATION_NONE,
                gpu_available=check_native_cuda(),
            )
    elif sys.platform == "linux":
        if has_podman():
            return PlatformConfig(
                control="native",
                execution="podman_containers",
                isolation_level=ISOLATION_FULL,
                gpu_available=check_nvidia_container_toolkit(),
            )
        # ... etc
```

---

## 4. Sandbox Architecture: Multi-Tier Isolated Execution

### 4.1 Sandbox Abstraction Layer

A `SandboxBackend` abstract interface that supports pluggable backends:

| Backend | Platform | Isolation Level | GPU | Network | Use Case |
|---------|----------|-----------------|-----|---------|----------|
| `SubprocessLocal` | All | None | Yes | Yes | Dev/test, trusted agents |
| `DockerContainer` | Linux/WSL2 | Container | Optional | Configurable | Primary execution |
| `PodmanContainer` | Linux | Rootless container | Optional | Configurable | OpenShell-compatible |
| `OpenShell` | Linux | Kernel-level | Yes | Policy-controlled | Gastown, high-security |
| `HuggingFaceSandbox` | Cloud | Remote | Yes | Limited | Reasoning, burst capacity |
| `WSL2` | Windows | VM-level | Passthrough | Configurable | Windows GPU workloads |

### 4.2 Sandbox Lifecycle

```
1. KAIJU evaluates: agent+action → allowed/denied
    
2. If allowed:
   a. SandboxPool.allocate(agent_id, policy_profile) → sandbox_id
   b. KAIJU injects: capability tokens (scoped, TTL-limited)
   c. OpenshellExecutor.orchestrate(sandbox_id, task_packet)
   d. Agent executes in isolated environment
   e. VAPChain.log(sandbox_id, action, result_hash)
   f. SandboxPool.deallocate(sandbox_id) — DESTROY EVERYTHING
```

### 4.3 Disposable Container Strategy

Every agent execution gets a FRESH container. No state persists between runs unless explicitly committed to the Vault:

```python
class DisposableSandbox:
    def __enter__(self):
        self.container = docker.containers.run(
            image=self.image,
            command=self.command,
            network_disabled=not self.allow_network,
            remove=True,  # Auto-delete on exit
            read_only=self.read_only_fs,
            tmpfs={"/tmp": "size=128M"},
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            environment={
                "NEXUS_SANDBOX_ID": self.sandbox_id,
                "NEXUS_SESSION_ID": self.session_id,
                # NO API keys ever injected
            }
        )
        return self.container
    
    def __exit__(self, *args):
        # Force destroy — no trace
        self.container.remove(force=True, v=True)
```

### 4.4 OpenShell Integration (GASTOWN)

The HERMES swarm pack already has OpenShell policies. These need to be:
1. Imported into NEXUS main as the canonical sandbox backend
2. Extended with Windows-compatible fallback
3. Connected to the KAIJU approval flow (already done in swarm pack — replicate in NEXUS main)

Current policies ready to import:
- `policies/codex_exec.yaml` — Python execution, read-write `/workspace`, no network
- `policies/opencode_analysis.yaml` — Read-only FS, no network, audit-only
- `policies/inference_local.yaml` — GPU compute, NVIDIA runtime, read-only root

### 4.5 Hugging Face Sandbox Integration

HF Sandbox provides cloud burst capacity for:
- Large model inference (70B+)
- Multi-GPU speculative decoding
- Cross-platform fallback when WSL2/Docker unavailable

Integration pattern:
```
NEXUS detects: local GPU insufficient OR Windows without WSL2
→ KAIJU evaluates: is this task safe for cloud sandbox?
→ TokenGuard checks: do we have budget?
→ HF Sandbox API: create sandbox → execute → return results
→ VAPChain logs: cloud execution record
→ Results merged into local Vault
```

---

## 5. Cross-Agent Security: Immunity Against Terminal Poisoning & Prompt Injection

### 5.1 The Threat Model

Based on the actual terminal poisoning incident:

```
Agent A (NEXUS Pi, SOVEREIGN mode)
  → writes ANSI escape sequences to stdout
  → shared terminal/console receives them
  → console processes cursor positioning, screen clearing
  → Agent B (CodeBuff, Codex, etc.) reads poisoned output
  → Agent B's LLM context includes corrupted data
  → Agent B makes decisions based on injected content
```

This is a **Cross-Agent Terminal Injection** attack — CWE-150 class.

### 5.2 Defensive Architecture

#### Layer 1: Output Sanitization (Immediate Fix)

Every agent's stdout/stderr MUST pass through a sanitizer before being consumed by another agent:

```python
class TerminalSanitizer:
    """
    Strips ALL ANSI/VT escape sequences from output.
    Blocks cursor manipulation, screen clearing, title changes.
    """
    # Strip all C0 control codes except \n, \t, \r
    C0_STRIP = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
    # Strip all CSI sequences: ESC [ <params> <final>
    CSI_STRIP = re.compile(r'\x1b\[[\d;]*[A-Za-z]')
    # Strip all OSC sequences: ESC ] <string> ST
    OSC_STRIP = re.compile(r'\x1b\][^\x07\x1b]*(\x07|\x1b\\)')
    # Strip all other ESC sequences
    ESC_STRIP = re.compile(r'\x1b[^\[A-Za-z]')
    # Strip application-defined key codes
    APP_KEY_STRIP = re.compile(r'\x1b\[[\d;]*~')
    
    @classmethod
    def sanitize(cls, text: str) -> str:
        text = cls.C0_STRIP.sub('', text)
        text = cls.CSI_STRIP.sub('', text)
        text = cls.OSC_STRIP.sub('', text)
        text = cls.ESC_STRIP.sub('', text)
        text = cls.APP_KEY_STRIP.sub('', text)
        return text
```

#### Layer 2: Dedicated PTY Per Agent (Structural Fix)

Each agent gets its own pseudo-terminal (PTY). NO shared terminal sessions:

```python
class AgentPTY:
    """Dedicated pseudo-terminal per agent — prevents cross-agent I/O leakage."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.master_fd, self.slave_fd = os.openpty()
        self.sanitizer = TerminalSanitizer()
    
    def read_output(self) -> str:
        raw = os.read(self.master_fd, 4096)
        return self.sanitizer.sanitize(raw.decode())
    
    def write_input(self, data: str):
        # Strip any escape sequences from input too
        clean = self.sanitizer.sanitize(data)
        os.write(self.master_fd, clean.encode())
```

#### Layer 3: Output Integrity Verification

Every output between agents gets a SHA-256 content hash. If the hash doesn't match what was sent, the receiving agent knows the content was tampered with (by terminal, another process, etc.):

```python
class VerifiableOutput:
    def __init__(self, content: str):
        self.content = content
        self.content_hash = hashlib.sha256(content.encode()).hexdigest()
        self.signature = None  # Filled by KAIJU signing
    
    def verify(self) -> bool:
        computed = hashlib.sha256(self.content.encode()).hexdigest()
        return computed == self.content_hash
```

#### Layer 4: KAIJU Cross-Agent Evaluation

KAIJU gates should evaluate whether an agent's output should be trusted by another agent:

```python
# In KAIJU governor
def evaluate_cross_agent_communication(
    source_agent: str,
    target_agent: str,
    content_hash: str,
    source_trust_score: float,
) -> GateResult:
    # If source trust score dropped recently, flag for review
    if source_trust_score < TRUST_THRESHOLD.get(target_agent, 0.5):
        return GateResult.DENY("Source agent trust below threshold")
    
    # If content hash doesn't match (tampering detected)
    if not VerifiableOutput.verify_chain(content_hash):
        return GateResult.HARD_STOP("Content integrity violation")
    
    return GateResult.APPROVE
```

### 5.3 The `SOVEREIGN` Mode Problem

The Pi agent's `SOVEREIGN` autonomy level (from `autonomous.py`) is fundamentally unsafe:

| Autonomy Level | Risk | Recommendation |
|---------------|------|---------------|
| ASSISTED | Low | Keep as-is |
| SUPERVISED | Low | Keep as-is |
| AUTONOMOUS | Medium | Add output sanitization + PTY isolation |
| SOVEREIGN | CRITICAL | Add: mandatory PTY + KAIJU cross-agent eval + output sanitization. Never allow shared terminal output. |

**Fix for AGENTS.md "Continuous Autonomous Operation Rules":** These must be rewritten to include safety checks before "continue executing":

```markdown
## Autonomous Operation Rules (REVISED)

When operating in autonomous mode, agents MUST:
- [SAFETY CHECK] Verify output integrity before passing to another agent
- [SANDBOX CHECK] Confirm sandbox isolation is active
- [BUDGET CHECK] Respect token budget limits
- [GATE CHECK] Pass all KAIJU evaluations before actions
- Halt on ANY of the above failures — do not auto-retry safety failures
```

---

## 6. Governance Mesh: Unified KAIJU + VAP + TokenGuard

### 6.1 Current Duplication Problem

| Component | NEXUS Main | HERMES Swarm Pack | Status |
|-----------|-----------|-------------------|--------|
| KAIJU Governor | `src/nexus_os/governor/base.py` | `nexus_kernel/kaiju.py` | DUPLICATED |
| VAP Chain | `src/nexus_os/governor/proof_chain.py` | `nexus_kernel/vap.py` | DUPLICATED |
| TokenGuard | `src/nexus_os/monitoring/token_guard.py` | `nexus_kernel/token_guard.py` | DUPLICATED |
| Archivist | `src/nexus_os/vault/manager.py` | `nexus_kernel/archivist.py` | DUPLICATED |

### 6.2 Reconciliation Strategy

**NEXUS Main stays canonical.** HERMES swarm pack becomes a plugin that adds:
- OpenShell sandbox orchestration
- Gastown bead tracking
- Zilliz dual-cluster memory

The duplicated kernel code from the swarm pack gets DEPRECATED and REMOVED in favor of NEXUS main's implementations, with the swarm pack importing from the main repo's canonical paths.

### 6.3 Governance Mesh Architecture

```
                    ┌──────────────────────────────────────┐
                    │         EXTERNAL INPUT                │
                    │  (Slack, API, Webhook, CLI)           │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │         KAIJU GATE (Stage 1)          │
                    │  Schema validation + injection check  │
                    └──────────────┬───────────────────────┘
                                   │
                          ┌────────┴────────┐
                          ▼                  ▼
               ┌──────────────────┐  ┌──────────────────┐
               │ L1: Simple Task  │  │ L2: Complex Task │
               │ TokenGuard: ECO  │  │ TokenGuard: FAST │
               │ Trust: No change │  │ Trust: Evaluate  │
               └────────┬─────────┘  └────────┬─────────┘
                        │                     │
                        └──────────┬──────────┘
                                   ▼
                    ┌──────────────────────────────────────┐
                    │      SANDBOX SELECTION                │
                    │  Docker/WSL → OpenShell → HF Cloud   │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │         EXECUTION                     │
                    │  Agent action in isolated sandbox     │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │      VAP CHAIN (Immutable Log)        │
                    │  gate_result + action + result_hash   │
                    │  signed by KAIJU, linked SHA-256      │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────────┐
                    │      FEEDBACK LOOP                    │
                    │  Trust score update                   │
                    │  Token budget adjustment              │
                    │  Hallucination check                  │
                    └──────────────────────────────────────┘
```

---

## 7. TWAVE/QWAVE/CHIMERA: Practical Inference Integration

### 7.1 Mapping Theory to Implementation

The theoretical algorithms map to NEXUS components at two layers:

#### Layer A: Control Plane (Request-Level) — Already Exists

| Concept | NEXUS Component | What It Does |
|---------|----------------|--------------|
| TWAVE | FunctionGemma 270M Gatekeeper (TO IMPLEMENT) | Decomposes natural language input into structured intent JSON |
| QWAVE | TALE Token Elasticity Detector (TO IMPLEMENT) | Assigns token budget based on intent confidence |
| CHIMERA | GMR Genius Model Rotator (Exists) | Routes to correct model expert based on task |

#### Layer B: Token-Level (Inference) — New Architecture

| Concept | Implementation | What It Does |
|---------|---------------|--------------|
| TWAVE | Wavefront token expansion | Expands multiple candidate token paths simultaneously |
| QWAVE | Quality-aware verification | Evaluates which candidate path has best quality (not just highest probability) |
| CHIMERA | Expert per wave | Each wave path uses a different specialist model |

### 7.2 TWAVE: Wavefront Token Expansion

```python
class TWAVE_Wavefront:
    """
    Expands a living token tree during generation.
    Each 'wave' is a set of candidate continuations.
    """
    def __init__(self, max_waves=3, beam_width=4):
        self.waves = []          # List of Wave objects
        self.living_tokens = []  # Active frontier
        self.convergence_threshold = 0.7
    
    def expand_wave(self, draft_outputs: List[List[int]]):
        """
        Given N draft outputs (from DFlash, EAGLE-3, etc.),
        expand the wavefront with new candidate paths.
        """
        new_wave = Wave(
            candidates=draft_outputs,
            parent_wave=len(self.waves) - 1 if self.waves else None
        )
        self.waves.append(new_wave)
        self.living_tokens = self._select_living(new_wave)
    
    def _select_living(self, wave: Wave) -> List[TokenPath]:
        """
        Select which tokens remain 'alive' (keep expanding)
        vs 'dead' (pruned due to low confidence).
        """
        living = []
        for token_seq, confidence in wave.candidates:
            if confidence >= self.convergence_threshold:
                living.append(TokenPath(
                    tokens=token_seq,
                    confidence=confidence
                ))
        return living
```

### 7.3 QWAVE: Quality-Aware Verification

Generalizes MARS (Margin-Aware Speculative Verification):

```python
class QWAVE_Verifier:
    """
    Multi-dimensional quality verification.
    Evaluates candidates on: confidence, semantic coherence, structural validity.
    """
    def __init__(self):
        self.dimensions = {
            "confidence": Weight(0.4),    # Target model log-prob
            "semantic": Weight(0.35),     # Embedding similarity to context
            "structural": Weight(0.25),   # Syntax/code validity
        }
        self.margin_threshold = 0.15  # MARS-style adaptive margin
    
    def verify(self, candidate: TokenPath, context: str) -> VerificationResult:
        scores = {}
        for dim, weight in self.dimensions.items():
            scores[dim] = weight * self._score_dimension(dim, candidate, context)
        
        quality = sum(scores.values())
        
        return VerificationResult(
            accepted=quality >= self.margin_threshold,
            quality_score=quality,
            dimension_scores=scores,
        )
```

### 7.4 CHIMERA: Dynamic Expert Routing Per Wave

```python
class CHIMERA_Router:
    """
    Routes each wave to the best expert model.
    Different experts can handle different waves simultaneously.
    """
    def __init__(self):
        self.experts = {
            "code_generator": ModelExpert("qwen3-coder-8b", tier=5),
            "code_reviewer": ModelExpert("deepseek-v4-flash", tier=5),
            "documentation": ModelExpert("minimax-m2.7", tier=4),
            "debug_analyzer": ModelExpert("kimi-k2.6", tier=5),
        }
    
    def route_wave(self, wave_context: dict) -> str:
        """Select the best expert for a given wave."""
        task_type = wave_context.get("task_type", "unknown")
        
        if task_type == "code_generation":
            return "code_generator"
        elif task_type == "code_review":
            return "code_reviewer"
        elif task_type == "debug":
            return "debug_analyzer"
        else:
            return "documentation"
```

### 7.5 Integration with vLLM Speculators

```python
class NEXUS_SpeculativeEngine:
    """
    Production speculative decoding engine.
    Integrates with vLLM's official speculative decoding API.
    """
    def __init__(self, config: SpecConfig):
        self.draft_method = config.draft_method  # dflash, eagle3, ngram, jacobi
        self.verifier = QWAVE_Verifier()
        self.wavefront = TWAVE_Wavefront()
    
    def generate(self, prompt: str, max_tokens: int = 512):
        # Stage 1: Draft generation (via vLLM speculators)
        draft_tokens = self.draft_method.predict(prompt, num_candidates=4)
        
        # Stage 2: Wavefront expansion
        self.wavefront.expand_wave(draft_tokens)
        
        # Stage 3: Quality-aware verification
        for path in self.wavefront.living_tokens:
            result = self.verifier.verify(path, prompt)
            if result.accepted:
                yield path.tokens
            else:
                # Fall back to target model for this path
                yield self.target_model.generate(prompt, path.tokens)
```

---

## 8. Communication Plane: Zo + Slack + Telegram + NEXUS Internal Bus

### 8.1 Three-Layer Communication

```
┌─────────────────────────────────────────────────┐
│  LAYER 3: EXTERNAL CHAT (User-Facing)           │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Slack   │  │ Telegram │  │ Web (future) │  │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │              │               │           │
└───────┼──────────────┼───────────────┼───────────┘
        │              │               │
┌───────┼──────────────┼───────────────┼───────────┐
│       ▼              ▼               ▼           │
│  ┌──────────────────────────────────────────┐    │
│  │  LAYER 2: ZO ORCHESTRATOR (Brain)        │    │
│  │                                           │    │
│  │  Routes: @Zo → @Devin → @Codex → @Kilo  │    │
│  │  Gates: KAIJU evaluation per action      │    │
│  │  Remembers: Cross-channel context        │    │
│  │  Logs: VAP chain for every interaction   │    │
│  └──────────────────┬───────────────────────┘    │
│                     │                             │
└─────────────────────┼─────────────────────────────┘
                      │
┌─────────────────────┼─────────────────────────────┐
│                     ▼                             │
│  LAYER 1: NEXUS INTERNAL BUS (Agent-to-Agent)    │
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │  KAIJU   │  │  VAP     │  │  TokenGuard   │    │
│  │  Gates   │  │  Audit   │  │  Budget       │    │
│  └──────────┘  └──────────┘  └──────────────┘    │
│                                                    │
│  ┌──────────────────────────────────────────┐     │
│  │  Agent Communication Protocol (ACP)       │     │
│  │  - E2E encrypted messages                  │     │
│  │  - KAIJU-signed payloads                   │     │
│  │  - VAP-logged every step                   │     │
│  │  - Content integrity hashes                │     │
│  └──────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
```

### 8.2 Slack Bot Network (Phase 2 Priority)

| Bot | Role | Channel | Capabilities |
|-----|------|---------|-------------|
| `@Zo` | Orchestrator | #nexus-control | Routes all tasks, final synthesis, gatekeeper |
| `@Devin` | Code Reviewer | #nexus-codex-tasks | PR diff analysis, implementation quality |
| `@Codex` | Code Reviewer | #nexus-codex-tasks | Architecture review, pattern detection |
| `@Kilo` | Code Reviewer | #nexus-codex-tasks | Security scanning, vulnerability detection |
| `@Sanity` | Reviewer | #nexus-reviews | Schema validation, data integrity |
| `@Pylon` | Reviewer/Guard | #nexus-reviews | Security audit, compliance check |
| `@Q` | Researcher | #nexus-research | Context retrieval, info gathering |
| `@Notion AI` | Researcher | #nexus-research | Doc lookup, knowledge search |
| `@Jira` | Ops | #nexus-ops | Ticket tracking, status updates |
| `@Confluence` | Researcher | #nexus-research | Wiki/guide lookup |
| `@incident` | Ops | #nexus-ops | Incident response, alert routing |
| `@GitHub` | Automation | #nexus-codex-tasks | PR/issue management |
| `@Computer` | Utility | #all-nexus-os | System status, health checks |
| `@Coda` | Doc | #nexus-research | Document management |

### 8.3 Channel Map

```
#nexus-control [PRIVATE]
  Purpose: Task intake, orchestration, governance decisions
  Bots: @Zo (orchestrator)
  Humans: All NEXUS operators
  Content: Task assignments, KAIJU gate results, escalation decisions
  
#nexus-codex-tasks [PRIVATE]
  Purpose: Code review requests, PR task assignments
  Bots: @Devin @Codex @Kilo @GitHub
  Content: New PR notifications, review assignments, task status
  
#nexus-reviews [PUBLIC-READ]
  Purpose: Review outputs, summaries, decisions
  Bots: @Zo @Sanity @Pylon
  Content: PR review reports, quality scores, approval/rejection
  
#nexus-research [PUBLIC-READ]
  Purpose: Context gathering, research coordination
  Bots: @Q @Notion AI @Confluence @Coda
  Content: Research findings, document summaries, context queries
  
#nexus-ops [PRIVATE]
  Purpose: Incidents, alerts, system monitoring
  Bots: @incident @Jira @Zo
  Content: Incident reports, alerts, recovery status
  
#all-nexus-os [PUBLIC]
  Purpose: Broadcast, announcements, cross-bot updates
  Bots: @Zo @Computer
  Content: Daily standup, weekly digests, system announcements
```

### 8.4 Agent Communication Protocol (ACP)

Internal messages between NEXUS agents follow a strict protocol:

```python
@dataclass
class ACP_Message:
    """Agent Communication Protocol — E2E Encrypted, VAP-Audited"""
    message_id: UUID
    source_agent: str
    target_agent: str
    message_type: str  # REQUEST, RESPONSE, BROADCAST, ALERT
    
    # Encrypted payload
    encrypted_payload: bytes
    encryption_algorithm: str  # "AES-256-GCM"
    
    # Integrity
    content_hash: str
    kaiyu_signature: str  # Signed by KAIJU after gate evaluation
    
    # Audit
    vap_entry_id: str  # Linked VAP chain entry
    timestamp: datetime
    
    # Routing
    ttl_seconds: int
    priority: int  # 1-5, higher = more urgent
```

---

## 9. Speculative Decoding Integration Map

### 9.1 Reality Check (Corrected from Gemini Analysis)

| Method | Speedup | VRAM Cost | Code Ready | Viability for NEXUS |
|--------|---------|-----------|------------|---------------------|
| N-gram Prompt Lookup | 1.1-1.3× | ZERO | Native in vLLM | ✅ Tier 2-4 |
| Lookahead (Jacobi) | 1.8-4× | ZERO | hao-ai-lab/JacobiForcing | ✅ Tier 2-4 |
| MEDUSA Heads | 2.2× | ~2% of target params | vLLM experimental | ✅ Tier 3-4 |
| EAGLE-3 (tiny drafter) | 2-3× | ~135M params | vLLM native | ✅ Tier 3-4 |
| DFlash (diffusion) | 3-6× | ~1B params | SGLang only (4.4K⭐) | ⏳ Tier 4 only |
| DDTree | 3× | ~1B params | 45⭐ research | ⏳ Tier 4 only |
| MARS (margin-aware) | Consistent | ZERO | Concept only | ✅ Tier 2-4 (implement) |

### 9.2 NEXUS Tiered Implementation

| Tier | VRAM | Methods | Speedup | Platform |
|------|------|---------|---------|----------|
| T1: Minimal | 4-8GB | Autoregressive only (Q4_K_M 2-4B) | 1× | All |
| T2: Standard | 8-12GB | + N-gram + Lookahead + MARS | 1.3-2× | Windows/WSL/Linux |
| T3: Power | 12-24GB | + EAGLE-3 (135M drafter) + MEDUSA | 2.5-3.5× | Linux/WSL |
| T4: Cloud | 80GB+ (H100) | + DFlash + DDTree + Full Megakernel | 4-8× | Cloud |

### 9.3 MARS Implementation (Highest Priority)

MARS is training-free and gives consistent speedup across model sizes:

```python
class MARS_Verifier:
    """
    Margin-Aware Speculative Verification.
    
    Standard verification: accept ALL draft tokens if target P > draft P - delta
    MARS: adapt delta based on target model's confidence margin.
    
    When target is decisive (high margin): relax verification (accept more)
    When target is uncertain (low margin): strict verification (reject more)
    """
    def __init__(self, base_margin=0.1, min_margin=0.05, max_margin=0.3):
        self.base_margin = base_margin
        self.min_margin = min_margin
        self.max_margin = max_margin
    
    def compute_adaptive_margin(self, target_logits: torch.Tensor) -> float:
        """
        Compute adaptive margin based on target model's certainty.
        
        If top-2 logits are far apart → target is decisive → relax margin
        If top-2 logits are close → target is uncertain → tighten margin
        """
        probs = torch.softmax(target_logits, dim=-1)
        top2 = torch.topk(probs, 2).values
        margin = top2[0] - top2[1]
        
        # Normalize margin to [min_margin, max_margin]
        adaptive = self.max_margin - (margin * (self.max_margin - self.min_margin))
        return torch.clamp(adaptive, self.min_margin, self.max_margin)
    
    def verify(self, draft_probs: float, target_probs: float, adaptive_margin: float) -> bool:
        """
        Accept draft token if target probability >= draft probability - adaptive_margin.
        """
        return target_probs >= draft_probs - adaptive_margin
```

---

## 10. Hallucination Detection & Prevention Framework

### 10.1 Three-Layer Hallucination Detection

```python
class HallucinationDetector:
    """
    Three-layer hallucination detection for agent outputs.
    """
    def __init__(self):
        self.layers = [
            FactualConsistencyLayer(),    # Layer 1: Grounding in retrieved context
            LogicalCoherenceLayer(),      # Layer 2: Internal consistency
            ExternalVerificationLayer(),  # Layer 3: Cross-agent verification
        ]
    
    def check(self, agent_output: str, context: dict) -> HallucinationResult:
        scores = {}
        violations = []
        
        for layer in self.layers:
            result = layer.evaluate(agent_output, context)
            scores[layer.name] = result.score
            violations.extend(result.violations)
        
        overall_score = sum(scores.values()) / len(scores)
        
        return HallucinationResult(
            hallucination_risk=1.0 - overall_score,
            layer_scores=scores,
            violations=violations,
            passed=overall_score >= 0.7,  # Threshold
        )
```

### 10.2 Layer 1: Factual Consistency

Uses the Vault's 4-layer truth engine (SOURCE → EXTRACTED → INFERRED → CANONICAL) to verify claims:

```python
class FactualConsistencyLayer:
    """
    Checks agent output against known facts in the Vault.
    Uses semantic similarity + entity extraction.
    """
    def evaluate(self, output: str, context: dict) -> LayerResult:
        # 1. Extract claims from output
        claims = self.extract_claims(output)
        
        # 2. For each claim, search Vault for supporting evidence
        verified = 0
        violations = []
        
        for claim in claims:
            evidence = self.vault.search_semantic(claim, top_k=3)
            
            if evidence and evidence[0].confidence >= 0.7:
                # Claim is supported by known facts
                verified += 1
            else:
                # Unsupported claim — potential hallucination
                violations.append(HallucinationViolation(
                    claim=claim,
                    severity="warning" if evidence else "error",
                    best_evidence=evidence[0] if evidence else None,
                ))
        
        consistency_score = verified / len(claims) if claims else 1.0
        
        return LayerResult(
            name="factual_consistency",
            score=consistency_score,
            violations=violations,
        )
```

### 10.3 Integration with KAIJU

Hallucination checks feed into the governance gate:

```python
# In KAIJU proposal evaluation
def evaluate_with_hallucination_check(
    agent_output: str,
    context: dict,
) -> GateResult:
    # Check hallucination FIRST before proceeding
    h_result = hallucination_detector.check(agent_output, context)
    
    if not h_result.passed:
        return GateResult(
            decision="REQUIRE_REVIEW",
            reason=f"Hallucination risk: {h_result.hallucination_risk:.2%}",
            evidence={
                "hallucination_score": h_result.hallucination_risk,
                "violations": [v.dict() for v in h_result.violations],
            }
        )
    
    # Proceed with normal KAIJU gates
    return kaiju.evaluate_proposal(agent_output, context)
```

---

## 11. Code Reconciliation: NEXUS Main ↔ HERMES Swarm Pack

### 11.1 What to Import (SWARM PACK → NEXUS MAIN)

| Swarm Pack File | Target in NEXUS Main | Priority |
|----------------|---------------------|----------|
| `policies/codex_exec.yaml` | `src/nexus_os/sandbox/policies/` | P0 |
| `policies/opencode_analysis.yaml` | `src/nexus_os/sandbox/policies/` | P0 |
| `policies/inference_local.yaml` | `src/nexus_os/sandbox/policies/` | P0 |
| `runtimes/sandbox_identity.py` | `src/nexus_os/sandbox/identity.py` | P0 |
| `runtimes/worker_registry.py` | `src/nexus_os/sandbox/registry.py` | P0 |
| `runtimes/openshell_executor.py` | `src/nexus_os/sandbox/openshell.py` | P0 |
| `cloud_edge/manager.py` | `src/nexus_os/vault/cloud_edge.py` | P1 |
| `boot/openshell_setup.sh` | `scripts/openshell_setup.sh` | P1 |

### 11.2 What to Remove (Swarm Pack Deprecations)

| Swarm Pack File | Reason | Action |
|----------------|--------|--------|
| `nexus_kernel/kaiju.py` | Duplicate of `src/nexus_os/governor/base.py` | DELETE after import |
| `nexus_kernel/vap.py` | Duplicate of `src/nexus_os/governor/proof_chain.py` | DELETE after import |
| `nexus_kernel/token_guard.py` | Duplicate of `src/nexus_os/monitoring/token_guard.py` | DELETE after import |
| `nexus_kernel/archivist.py` | Duplicate of `src/nexus_os/vault/manager.py` | DELETE after import |

### 11.3 What to Create (New NEXUS Main Components)

| New Component | Location | Purpose |
|--------------|----------|---------|
| Sandbox Abstraction Layer | `src/nexus_os/sandbox/__init__.py` | Pluggable backend interface |
| Terminal Sanitizer | `src/nexus_os/security/sanitizer.py` | ANSI escape stripping |
| Cross-Agent Evaluator | `src/nexus_os/governor/cross_agent.py` | KAIJU extension for inter-agent comms |
| Hallucination Detector | `src/nexus_os/governor/hallucination.py` | 3-layer hallucination checking |
| Platform Detector | `src/nexus_os/system/platform.py` | Adaptive deployment detection |
| E2E Encryption Layer | `src/nexus_os/security/encryption.py` | AES-256-GCM for ACP messages |

---

## 12. Deployment Tiers & Platform Strategy

### 12.1 Tier Definition

| Tier | Hardware | OS | Sandbox | Speed | Use Case |
|------|----------|----|---------|-------|----------|
| NEXUS-Lite | 4GB RAM, no GPU | Any | Subprocess (no sandbox) | 1× | Dev/test, basic governance |
| NEXUS-Standard | 8GB RAM, 8GB VRAM | Windows + WSL2 | Docker/WSL | 1.3-2× | Primary developer workstation |
| NEXUS-Power | 32GB RAM, 24GB VRAM | Linux | Podman + OpenShell | 2.5-3.5× | Heavy inference, multi-agent |
| NEXUS-Cloud | Cloud VMs | Linux | HF Sandbox + OpenShell | 4-8× | Production deployment |

### 12.2 Windows-Specific Optimization

```
Windows NEXUS-Standard deployment:
1. Install: Docker Desktop with WSL2 backend
2. WSL2 distro: Ubuntu 24.04 LTS
3. Inside WSL2:
   - Podman (rootless) for sandboxed execution
   - NVIDIA container toolkit (if GPU available)
   - vLLM + MARS verifier for local inference
4. Windows host:
   - NEXUS Dashboard (FastAPI + React, port 8000)
   - VAP chain viewer
   - Slack/Telegram bridge
   - KAIJU governance console
5. Bridge: Windows <-> WSL2 via localhost TCP
```

### 12.3 Migration Path for Current Windows Install

```bash
# Step 1: Move agent execution to WSL2
wsl --install -d Ubuntu-24.04

# Step 2: Inside WSL2, set up execution environment
wsl -d Ubuntu-24.04
sudo apt update && sudo apt install -y podman python3-pip
pip install vllm llama-cpp-python

# Step 3: Configure Podman for rootless
podman system migrate
systemctl --user enable podman.socket

# Step 4: Test sandbox
podman run --rm alpine echo "Sandbox ready"

# Step 5: Point NEXUS execution to WSL2
nexusctl config set execution.backend wsl2
nexusctl config set wsl2.distribution Ubuntu-24.04
```

---

## 13. Phase Roadmap (12-Week Sprint)

### Phase 0: Emergency Fixes (Week 0 — Immediate)

| # | Task | Owner | Effort |
|---|------|-------|--------|
| 0.1 | Strip ANSI escape sequences from ALL inter-agent output | Dev | 2hr |
| 0.2 | Disable SOVEREIGN autonomy level default | Dev | 1hr |
| 0.3 | Add PTY isolation for all agent processes | Dev | 4hr |
| 0.4 | Fix AGENTS.md autonomous rules to include safety checks | Doc | 1hr |
| 0.5 | Rotate any exposed credentials from terminal poisoning | Sec | 1hr |

### Phase 1: Foundation Unification (Weeks 1-2)

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 1.1 | Import OpenShell sandbox policies into NEXUS main | 1 day | — |
| 1.2 | Create Sandbox Abstraction Layer (Docker/Podman/WSL/OpenShell) | 3 days | 1.1 |
| 1.3 | Implement Platform Detector | 1 day | — |
| 1.4 | Deprecate duplicate swarm pack kernel code | 1 day | 1.1 |
| 1.5 | Write Kafka routing event schema + migration | 1 day | — |
| 1.6 | Set up 5 Slack channels + Zo bridge | 2 days | — |
| 1.7 | Create 3 scheduled Zo agents (pr-watcher, reminder, standup) | 1 day | 1.6 |

### Phase 2: Sandbox Isolation (Weeks 3-4)

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 2.1 | Disposable Docker container sandbox for Linux | 3 days | 1.2 |
| 2.2 | WSL2 execution bridge for Windows | 3 days | 1.2, 1.3 |
| 2.3 | OpenShell container orchestration (import from swarm pack) | 2 days | 1.2 |
| 2.4 | HF Sandbox API integration for cloud burst | 3 days | — |
| 2.5 | Sandbox capability token system (TTL-limited, scoped) | 4 days | 2.1-2.4 |
| 2.6 | KAIJU sandbox evaluation gates | 2 days | 2.5 |

### Phase 3: Security Layer (Weeks 5-6)

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 3.1 | Cross-agent prompt injection defense (KAIJU extension) | 3 days | 2.6 |
| 3.2 | E2E encryption for ACP messages (AES-256-GCM) | 3 days | — |
| 3.3 | Hallucination detection — Layer 1 (factual consistency) | 3 days | 1.2 |
| 3.4 | Hallucination detection — Layer 2 (logical coherence) | 2 days | 3.3 |
| 3.5 | Hallucination detection — Layer 3 (cross-agent verification) | 2 days | 3.4 |
| 3.6 | Terminal/Output Sanitizer (formal PoC → production) | 2 days | — |

### Phase 4: Inference Optimization (Weeks 7-8)

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 4.1 | MARS verifier implementation (training-free) | 2 days | — |
| 4.2 | N-gram + Lookahead speculative decoding backend | 3 days | — |
| 4.3 | TWAVE wavefront token expansion | 4 days | 4.1, 4.2 |
| 4.4 | QWAVE quality-aware verification | 3 days | 4.3 |
| 4.5 | CHIMERA expert-per-wave routing | 3 days | 4.4 |
| 4.6 | vLLM speculators integration (EAGLE-3 for T3+) | 4 days | 4.3 |

### Phase 5: Communication Plane (Weeks 9-10)

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 5.1 | GitHub webhook → Zo routing layer | 2 days | 1.6 |
| 5.2 | Slack bot identities (@Devin, @Codex, @Kilo, @Sanity, @Pylon, @Q) | 3 days | 5.1 |
| 5.3 | PR review automation (3-agent parallel review) | 4 days | 5.2 |
| 5.4 | Research coordination (@Q + Notion AI + Confluence) | 2 days | 5.2 |
| 5.5 | Incident response flow (GitHub → Jira → Slack) | 2 days | 5.2 |
| 5.6 | Telegram bridge | 2 days | 5.1 |
| 5.7 | Agent Communication Protocol (ACP) implementation | 3 days | 3.2 |

### Phase 6: Hardening & Polish (Weeks 11-12)

| # | Task | Effort | Dependencies |
|---|------|--------|-------------|
| 6.1 | Full integration test suite | 5 days | All above |
| 6.2 | Disaster recovery scenarios (5+) | 3 days | 6.1 |
| 6.3 | Performance profiling & optimization | 4 days | 6.1 |
| 6.4 | Documentation unification | 3 days | All above |
| 6.5 | GitHub repo sync (20MB local → Zo) | 1 day | — |
| 6.6 | Platform compatibility certification (Win/Linux/Mac) | 3 days | 6.1 |

---

## 14. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | Docker Gordon quota fully exhausted before Phase 1 migration | High | High | Document all Gordon configs manually; prepare manual Kafka reconfiguration guide |
| R2 | Cross-agent terminal injection recurrence before PTY isolation deployed | Medium | Critical | Deploy Terminal Sanitizer (Phase 0.1) immediately |
| R3 | Duplicate kernel code causes merge conflicts between NEXUS main and swarm pack | Medium | Medium | One-directional merge: swarm pack → NEXUS main, then deprecate |
| R4 | WSL2 GPU passthrough unreliable for inference sandbox | Medium | Medium | Fallback to Docker Desktop Linux containers; no GPU for Windows-local tier |
| R5 | Zo computer API rate limits for Slack bot network | Medium | Low | Implement local caching + batch posting for non-urgent messages |
| R6 | HF Sandbox API changes breaking integration | Low | Medium | Abstract HF behind SandboxBackend interface; add OpenShell as primary fallback |
| R7 | Speculative decoding research papers without code remain unimplementable | Low | Low | Focus on MARS + N-gram + Lookahead (all implementable); defer DFlash/DDTree |

---

## 15. Appendix: Document Index

| Document | Location | Purpose |
|----------|----------|---------|
| This Plan | `NEXUS/NEXUS_OS_V4_MASTER_PLAN.md` | Master architecture & improvement plan |
| AGENTS.md | `NEXUS/AGENTS.md` | Agent operating rules (NEEDS UPDATE) |
| 01_PROJECT_STATE.md | `NEXUS/01_PROJECT_STATE.md` | Canonical project state |
| knowledge.md | `NEXUS/knowledge.md` | Quick reference |
| Docker Gordon Phase 1 | `Downloads/DOCKERaiGORDON/` | Kafka bridge, consumer, dashboard, monitoring |
| Gordon FINAL_STATUS | `DOCKERaiGORDON/FINAL_STATUS.md` | Phase 1 completion report |
| Gordon ACTION_PLAN | `DOCKERaiGORDON/ACTION_PLAN_NEXT_48_HOURS.md` | Phase 2 execution blueprint |
| HERMES Swarm Pack | `HERMES/hermes-agent/nexus-swarm-pack/` | OpenShell sandbox + Gastown |
| Swarm Pack README | `.../nexus-swarm-pack/README.md` | Phase C complete |
| Swarm Pack KAIJU | `.../nexus_kernel/kaiju.py` | 5-stage authorization gate |
| Swarm Pack OpenShell | `.../runtimes/openshell_executor.py` | OpenShell bridge |
| Swarm Pack Policies | `.../policies/*.yaml` | Sandbox policy definitions |
| Zo Computer Chat | `zo.computer/chats/pub_BW1sg4feqr0oVWV7` | Slack bot architecture discussion |
| NEXUS Audit Report | `NEXUS/docs/reviews/NEXUS_FULL_SYSTEM_AUDIT_2026-05-05.md` | Full system security audit |
| NEXUS Red Team Report | Zo chat attachments | Red team findings & remediation |
| TWAVE/QWAVE/CHIMERA Synthesis | (to be created in R&D) | Speculative decoding integration design |

---

## Next Steps — When You Return

1. **Emergency (P0):** Apply the Terminal Sanitizer to prevent another poisoning incident
2. **Gateway (P0):** Give me the 20MB zip password so I can ground Zo with the full repo
3. **Phase 1.1 (P1):** Import OpenShell policies from swarm pack into NEXUS main
4. **Phase 1.6 (P1):** Set up the Slack channels + Zo bridge
5. **Phase 0.5 (P1):** Rotate any credentials exposed during the terminal poisoning

The 12-week roadmap above is aggressive but achievable. The key architectural decision remains:

> **Windows = Control Plane + Authoring. Linux/WSL = Execution Sandbox. Cloud = Burst Capacity.**

Local-first becomes Linux-first for execution, Windows-first for governance. Cross-platform through Docker abstraction.

---

*Built with deep research across Zo Computer, Docker Gordon Phase 1, HERMES Swarm Pack, NVIDIA OpenShell, Hugging Face Sandbox, vLLM Speculators, and 12 weeks of NEXUS OS architectural evolution.*
