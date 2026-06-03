"""Terminal sanitizer, PTY isolation, and output integrity verification.

Adds proper error handling around PTY I/O operations and sanitization
where the previous implementation had no error handling for OS-level
failures (fd read/write errors, PTY allocation failures, etc.).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass

from nexus_os.exceptions import (
    IntegrityViolation,
    PTYError,
    SanitizationError,
)

logger = logging.getLogger(__name__)


class TerminalSanitizer:
    """Strips ALL ANSI/VT escape sequences from output.

    Blocks cursor manipulation, screen clearing, and title changes
    to prevent cross-agent terminal injection (CWE-150).
    """

    # Strip C0 control codes except newline, tab, carriage return, and ESC
    # (ESC is handled by the CSI/OSC/ESC-specific patterns below)
    C0_STRIP = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1a\x1c-\x1f\x7f]")
    # Strip all CSI sequences: ESC [ <params> <final>
    CSI_STRIP = re.compile(r"\x1b\[[\d;]*[A-Za-z]")
    # Strip all OSC sequences: ESC ] <string> ST
    OSC_STRIP = re.compile(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)")
    # Strip remaining ESC + single-char sequences (SS2, SS3, etc.)
    ESC_STRIP = re.compile(r"\x1b.")
    # Strip application-defined key codes
    APP_KEY_STRIP = re.compile(r"\x1b\[[\d;]*~")
    # Catch any lone ESC left over
    LONE_ESC = re.compile(r"\x1b")

    @classmethod
    def sanitize(cls, text: str) -> str:
        """Remove all escape sequences from *text*.

        Raises
        ------
        SanitizationError
            If sanitization produces an invalid result (e.g., null bytes remain
            after stripping).
        """
        if not isinstance(text, str):
            raise SanitizationError(
                f"Expected str, got {type(text).__name__}",
                details={"type": type(text).__name__},
            )

        result = text
        result = cls.C0_STRIP.sub("", result)
        result = cls.CSI_STRIP.sub("", result)
        result = cls.OSC_STRIP.sub("", result)
        result = cls.ESC_STRIP.sub("", result)
        result = cls.APP_KEY_STRIP.sub("", result)
        result = cls.LONE_ESC.sub("", result)

        # Final safety check: ensure no null bytes leaked through
        if "\x00" in result:
            raise SanitizationError(
                "Sanitized output still contains null bytes",
                details={"length": len(result)},
            )

        return result


class AgentPTY:
    """Dedicated pseudo-terminal per agent — prevents cross-agent I/O leakage.

    Wraps PTY allocation and I/O with proper error handling.  The previous
    implementation had no error handling around ``os.openpty()``,
    ``os.read()``, or ``os.write()`` calls.
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._sanitizer = TerminalSanitizer()
        self._master_fd: int | None = None
        self._slave_fd: int | None = None

    def open(self) -> None:
        """Allocate a new PTY pair.

        Raises
        ------
        PTYError
            If the OS refuses to allocate a PTY (e.g., out of PTY devices).
        """
        if self._master_fd is not None:
            logger.debug("PTY already open for agent %s", self.agent_id)
            return

        try:
            self._master_fd, self._slave_fd = os.openpty()
        except OSError as exc:
            raise PTYError(
                f"Failed to allocate PTY for agent {self.agent_id}: {exc}",
                details={"agent_id": self.agent_id},
                cause=exc,
            ) from exc

        logger.debug(
            "PTY opened for agent %s (master=%d, slave=%d)",
            self.agent_id, self._master_fd, self._slave_fd,
        )

    def read_output(self, max_bytes: int = 4096) -> str:
        """Read and sanitize output from the PTY.

        Raises
        ------
        PTYError
            If the PTY is not open or the read fails.
        SanitizationError
            If sanitization fails on the read data.
        """
        if self._master_fd is None:
            raise PTYError(
                f"PTY not open for agent {self.agent_id}; call open() first",
                details={"agent_id": self.agent_id},
            )

        try:
            raw = os.read(self._master_fd, max_bytes)
        except OSError as exc:
            raise PTYError(
                f"PTY read failed for agent {self.agent_id}: {exc}",
                details={"agent_id": self.agent_id, "fd": self._master_fd},
                cause=exc,
            ) from exc

        try:
            decoded = raw.decode("utf-8", errors="replace")
        except Exception as exc:
            raise PTYError(
                f"Failed to decode PTY output for agent {self.agent_id}: {exc}",
                details={"agent_id": self.agent_id, "raw_length": len(raw)},
                cause=exc,
            ) from exc

        return self._sanitizer.sanitize(decoded)

    def write_input(self, data: str) -> int:
        """Write sanitized input to the PTY.

        Raises
        ------
        PTYError
            If the PTY is not open or the write fails.
        """
        if self._master_fd is None:
            raise PTYError(
                f"PTY not open for agent {self.agent_id}; call open() first",
                details={"agent_id": self.agent_id},
            )

        clean = self._sanitizer.sanitize(data)
        try:
            return os.write(self._master_fd, clean.encode("utf-8"))
        except OSError as exc:
            raise PTYError(
                f"PTY write failed for agent {self.agent_id}: {exc}",
                details={"agent_id": self.agent_id, "fd": self._master_fd},
                cause=exc,
            ) from exc

    def close(self) -> None:
        """Close the PTY file descriptors."""
        for fd_attr in ("_master_fd", "_slave_fd"):
            fd = getattr(self, fd_attr, None)
            if fd is not None:
                try:
                    os.close(fd)
                except OSError as exc:
                    logger.warning(
                        "Error closing PTY fd %d for agent %s: %s",
                        fd, self.agent_id, exc,
                    )
                setattr(self, fd_attr, None)

    def __enter__(self) -> AgentPTY:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


@dataclass(frozen=True)
class VerifiableOutput:
    """SHA-256 content integrity wrapper.

    Every output between agents gets a content hash.  If the hash doesn't
    match what was sent, ``IntegrityViolation`` is raised instead of
    silently accepting tampered content.
    """

    content: str
    content_hash: str

    @classmethod
    def create(cls, content: str) -> VerifiableOutput:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return cls(content=content, content_hash=content_hash)

    def verify(self) -> None:
        """Verify content integrity.

        Raises
        ------
        IntegrityViolation
            If the recomputed hash does not match the stored hash.
        """
        computed = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if computed != self.content_hash:
            raise IntegrityViolation(
                f"Content integrity check failed: "
                f"expected {self.content_hash}, got {computed}",
                details={
                    "expected_hash": self.content_hash,
                    "computed_hash": computed,
                    "content_length": len(self.content),
                },
            )

    @classmethod
    def verify_chain(cls, content: str, expected_hash: str) -> None:
        """Verify content against an expected hash.

        Raises
        ------
        IntegrityViolation
            On hash mismatch.
        """
        computed = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if computed != expected_hash:
            raise IntegrityViolation(
                f"Chain integrity check failed: expected {expected_hash}, got {computed}",
                details={
                    "expected_hash": expected_hash,
                    "computed_hash": computed,
                },
            )
