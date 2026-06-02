# <p align="center">🛡️ S E C U R I T Y &nbsp; P O L I C Y 🛡️</p>

<p align="center">
  <strong>NEXUS OS & Doppleground Collective Cryptographic & Coordinated Disclosure Standard</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Security-ASRCP--Q2%20Immune-6842f4?style=for-the-badge&logo=quantcast&logoColor=white" alt="ASRCP-Q2 Immune" />
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/Cryptography-Libgcrypt%20Standard-00bcd4?style=for-the-badge&logo=gnupg&logoColor=white" alt="Libgcrypt Standard" />
  &nbsp;&nbsp;
  <img src="https://img.shields.io/badge/Governance-Evidence--Gated-ff69b4?style=for-the-badge&logo=target&logoColor=white" alt="Evidence-Gated" />
</p>

---

## 🧬 1. Core Security Philosophy

NEXUS OS is engineered as a local-first, zero-trust multi-agent orchestrator. Rather than delegating authorization and state tracking to central cloud services, NEXUS OS establishes local cryptographic boundaries. Every agentic command is proposal-bound, execution-gated, and immutable-provenance-tracked.

> [!TIP]
> ### 💡 What is Post-Quantum Cryptography? (For Non-Technical Users)
> Standard encryption methods rely on math problems that today's computers find nearly impossible to solve. However, future **quantum computers** (extremely fast, powerful machines being built today) will easily crack these standard math problems.
>
> **Post-Quantum Cryptography** uses entirely new, complex mathematical structures (like lattices) that are specifically designed to remain uncrackable—even by the most advanced future quantum computers. Implementing this now ensures your private vaults remain secure long into the future (preventing "harvest now, decrypt later" attacks).

---

## 🛠️ 2. Cryptographic Standards & Library Integration

Our implementation enforces strict cryptographic algorithms and library standards to secure user workspaces:

### A. Low-Level Memory Hardening (Libgcrypt Fit)
*   **Protocol Standard**: We target the GNU **Libgcrypt** core library (`libgcrypt.so.20` / `libgcrypt-20.dll`) via Python-CFFI wrappers to allocate secure, unswappable memory blocks (`gcry_malloc_secure`) for raw environment keys and post-quantum keys.
*   **Physical Locking (`mlock`)**: Key buffers are locked in physical RAM, preventing the host operating system from writing sensitive credentials to unencrypted swap partitions on local disk storage.

### B. Storage Cipher Diversification (Serpent & Twofish Vault Primitives)
*   **Multi-Cipher Agnostic Schema**: To secure our 5-track Vault memory structure (`store_track`/`retrieve_track` in `nexus_os/vault/`), we integrate alternative symmetric ciphers alongside standard AES-256.
*   **Cipher Selection**: We mount **Serpent** (32-round SPN cipher) and **Twofish** (16-round Feistel cipher) in CTR and GCM modes. Sensitive data tracks (e.g. Track 3: Credentials and Track 4: Multi-Turn Logs) rotate ciphers dynamically based on metadata block hashes to ensure cipher-redundancy.

### C. Verifiable Action Provenance (Merkle–Damgård & Whirlpool VAP Ledger)
*   **Integrity Hashing**: System event streams committed by the task executor (`nexus_os/engine/executor.py`) generate a sequential hash chain.
*   **Double-Hash Chaining**: Each audit block is linked via double-hash layers using **Whirlpool** (512-bit AES-based W-cipher output) and **SHA-256** one-way compression functions, preventing retroactive tampering of local agent history logs.

---

## 🔒 3. Threat Mitigation Matrix

NEXUS OS contains dedicated mitigations against real-world privilege escalations, model exploits, and zero-click network vectors:

| Threat / Vulnerability | CVE / Reference | Primary Attack Vector | Codebase Mitigation Layer |
| :--- | :--- | :--- | :--- |
| **Linux Kernel Copy Fail** | `CVE-2026-31431` | Unprivileged local user writes 4 controlled bytes into page cache to elevate permissions to `root`. | **Subsystem Isolation**: Enforces sandboxed task runs (`executor.py`) inside isolated container namespaces with zero host access. |
| **Linux Kernel Dirty Frag** | `VU#980487` | Local privilege escalation utilizing fragment exploitation in system sockets. | **Process Isolation & PTY Limits**: Enforces restricted process boundaries and limits socket exposures on loopback adapters. |
| **SGLang Engine Exploits** | `VU#777338` | Prompts craft arbitrary directory traversals or remote code executions on server endpoints. | **Input & Output Sanitization**: Strips path tags (`../`) in the model relay (`model_relay.py`) and validates responses via Pydantic. |
| **Pegasus Zero-Click** | `CVE-2021-30860` | Emulated computer architectures crafted inside stream attachments (e.g. JBIG2 *FORCEDENTRY*). | **Pydantic Validation & Context Tracing**: Standardizes all JSON-RPC payloads; checks logs for logical execution shifts. |
| **Pickle Deserialization** | `HF Picklescan` | Serialized model files (`training_args.bin`) execute arbitrary Python logic during standard import. | **Workspace Static Scanner**: Runs pre-execution checks (`picklescan`) and Talos **EvidenceForge** bytecode scan rules. |
| **Clock Replay Attacks** | `Kerberos Default` | Attackers capture signed loopback messages and replay them later to authorize actions. | **Kerberos Clock Skew Enforcement**: Enforces a strict 300-second (5 minutes) maximum timestamp tolerance in the FastAPI bridge. |

---

## 📈 4. Supported Versions

We actively maintain and support versions that incorporate our post-quantum and local-first security infrastructure.

| Version Range | Supported | Description |
| :--- | :---: | :--- |
| **v7.x.x** | :white_check_mark: | Current Mainline (ASRCP-Q2 Immune, TrustEngine v2.2, FastAPI Governance REST Plane). |
| **v6.x.x** | :white_check_mark: | Previous Stable (Phase 0 Hardened, stdio MCP Server base). Security patches backported. |
| **v5.x.x and legacy** | :x: | Legacy releases. Legacy versions are deprecated; users are strongly encouraged to upgrade. |

---

## 🚨 5. Reporting a Vulnerability

We take the security of our decentralized, local-first ecosystem extremely seriously. If you discover a vulnerability or potential exploit, please follow our coordinated disclosure policy:

### A. How to Report
Please do **not** open a public GitHub Issue for security bugs. Instead, submit reports through our secure private channel:
*   📧 **Email**: [specimba@gmail.com](mailto:specimba@gmail.com)
*   🔑 **PGP Encryption**: For highly sensitive reports, please encrypt your payload using our Security Public Key (available upon request or via our key registries).

### B. What to Include in Your Report
To help us evaluate and patch the bug efficiently, please provide:
*   A detailed description of the vulnerability and its potential impact.
*   Clear steps to reproduce the issue (including proof-of-concept scripts or payload examples).
*   Your details for proper attribution in our security ledger (you may remain anonymous if preferred).

### C. Our Response Commitment
Upon receiving a report, the Doppleground Foundation security team will:
*   Acknowledge receipt of the vulnerability within **24 hours**.
*   Provide a status update and initial assessment within **72 hours**.
*   Work collaboratively with you to validate the issue, prepare a patch, and coordinate a public release with proper credit.

---

## ⚖️ License & Attribution
Doppleground Foundation © 2026. Governed by the Commons. Distributed under the Apache 2.0 License.
