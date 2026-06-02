"""TerminalSanitizer - Regex-based ANSI injection defense.

Provides TerminalSanitizer (strips ANSI/VT escape sequences),
VerifiableOutput (SHA-256 integrity), and AgentPTY (isolated pseudo-terminal).
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][AB012]|\x1b\[[\d;]*m")
VT_CONTROL_RE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f]")


class TerminalSanitizer:
    """Strips ANSI escape sequences and VT control characters."""

    def __init__(self, allow_newlines: bool = True) -> None:
        self._allow_newlines = allow_newlines

    def sanitize(self, text: str) -> str:
        result = ANSI_ESCAPE_RE.sub("", text)
        if self._allow_newlines:
            result = re.sub(r"[\x00-\x08\x0e-\x1f\x7f]", "", result)
        else:
            result = VT_CONTROL_RE.sub("", result)
            result = result.replace("\n", " ").replace("\r", " ")
        return result

    def is_clean(self, text: str) -> bool:
        return self.sanitize(text) == text


@dataclass
class VerifiableOutput:
    """SHA-256 integrity wrapper for agent outputs."""

    content: str
    sha256: str
    timestamp: float = field(default_factory=time.time)
    agent_id: str = ""

    @classmethod
    def create(cls, content: str, agent_id: str = "") -> VerifiableOutput:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return cls(content=content, sha256=digest, agent_id=agent_id)

    def verify(self) -> bool:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest() == self.sha256


@dataclass
class AgentPTY:
    """Isolated pseudo-terminal record for agent execution."""

    agent_id: str
    pty_id: str
    created_at: float = field(default_factory=time.time)
    active: bool = True
    output_buffer: list[str] = field(default_factory=list)

    def write(self, data: str) -> None:
        if not self.active:
            raise RuntimeError(f"PTY {self.pty_id} is closed")
        self.output_buffer.append(data)

    def read_all(self) -> str:
        return "".join(self.output_buffer)

    def close(self) -> None:
        self.active = False
