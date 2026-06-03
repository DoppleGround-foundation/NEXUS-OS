"""Vault 5-track memory manager with proper error handling.

Implements the canonical ``store_track`` / ``retrieve_track`` interface
with encryption hard-fail by default.  Replaces all bare ``except: pass``
blocks with structured ``VaultError`` variants.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nexus_os.exceptions import (
    EncryptionFailed,
    EncryptionRequired,
    StorageCorrupted,
    TrackNotFound,
    VaultError,
)

logger = logging.getLogger(__name__)


class Track(Enum):
    EVENT = "event"
    TRUST = "trust"
    CAP = "cap"
    FAIL = "fail"
    GOV = "gov"


@dataclass
class VaultEntry:
    track: Track
    key: str
    value: Any
    timestamp: float
    encrypted: bool
    integrity_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


class VaultManager:
    """Thread-safe 5-track memory vault.

    Encryption policy
    -----------------
    ``allow_unencrypted`` defaults to ``False``.  When encryption is
    required but no encryptor is configured, ``EncryptionRequired`` is
    raised instead of silently storing plaintext.
    """

    def __init__(
        self,
        *,
        encryptor: Any | None = None,
        allow_unencrypted: bool = False,
    ) -> None:
        self._encryptor = encryptor
        self._allow_unencrypted = allow_unencrypted
        self._stores: dict[Track, dict[str, VaultEntry]] = {t: {} for t in Track}
        self._lock = threading.Lock()

    def store_track(
        self,
        track: Track | str,
        key: str,
        value: Any,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> VaultEntry:
        """Store a value in the specified memory track.

        Raises
        ------
        TrackNotFound
            If the track name is invalid.
        EncryptionRequired
            If encryption is required but not available.
        EncryptionFailed
            If the encryptor raises during encryption.
        """
        track_enum = self._resolve_track(track)

        raw = str(value).encode()
        integrity = hashlib.sha256(raw).hexdigest()

        encrypted = False
        stored_value = value

        if self._encryptor is not None:
            try:
                stored_value = self._encryptor.encrypt(raw)
                encrypted = True
            except Exception as exc:
                raise EncryptionFailed(
                    f"Failed to encrypt value for {track_enum.value}/{key}: {exc}",
                    details={"track": track_enum.value, "key": key},
                    cause=exc,
                ) from exc
        elif not self._allow_unencrypted:
            raise EncryptionRequired(
                f"Encryption is required but no encryptor is configured. "
                f"Set allow_unencrypted=True for plaintext storage.",
                details={"track": track_enum.value, "key": key},
            )

        entry = VaultEntry(
            track=track_enum,
            key=key,
            value=stored_value,
            timestamp=time.time(),
            encrypted=encrypted,
            integrity_hash=integrity,
            metadata=metadata or {},
        )

        with self._lock:
            self._stores[track_enum][key] = entry

        logger.debug(
            "Stored %s/%s (encrypted=%s)", track_enum.value, key, encrypted,
        )
        return entry

    def retrieve_track(
        self,
        track: Track | str,
        key: str,
    ) -> Any:
        """Retrieve a value from the specified memory track.

        Raises
        ------
        TrackNotFound
            If the track name is invalid.
        VaultError
            If the key does not exist in the track.
        StorageCorrupted
            If the integrity hash does not match after decryption.
        EncryptionFailed
            If decryption fails.
        """
        track_enum = self._resolve_track(track)

        with self._lock:
            entry = self._stores[track_enum].get(key)

        if entry is None:
            raise VaultError(
                f"Key {key!r} not found in track {track_enum.value!r}",
                details={"track": track_enum.value, "key": key},
            )

        value = entry.value
        if entry.encrypted:
            if self._encryptor is None:
                raise EncryptionFailed(
                    f"Entry {track_enum.value}/{key} is encrypted but no "
                    f"encryptor is configured for decryption",
                    details={"track": track_enum.value, "key": key},
                )
            try:
                raw = self._encryptor.decrypt(value)
                value = raw.decode() if isinstance(raw, bytes) else raw
            except Exception as exc:
                raise EncryptionFailed(
                    f"Failed to decrypt {track_enum.value}/{key}: {exc}",
                    details={"track": track_enum.value, "key": key},
                    cause=exc,
                ) from exc

            # Verify integrity
            check_hash = hashlib.sha256(
                value.encode() if isinstance(value, str) else value
            ).hexdigest()
            if check_hash != entry.integrity_hash:
                raise StorageCorrupted(
                    f"Integrity check failed for {track_enum.value}/{key}: "
                    f"expected {entry.integrity_hash}, got {check_hash}",
                    details={
                        "track": track_enum.value,
                        "key": key,
                        "expected": entry.integrity_hash,
                        "actual": check_hash,
                    },
                )

        return value

    def list_keys(self, track: Track | str) -> list[str]:
        track_enum = self._resolve_track(track)
        with self._lock:
            return list(self._stores[track_enum].keys())

    def delete(self, track: Track | str, key: str) -> bool:
        track_enum = self._resolve_track(track)
        with self._lock:
            return self._stores[track_enum].pop(key, None) is not None

    def _resolve_track(self, track: Track | str) -> Track:
        if isinstance(track, Track):
            return track
        try:
            return Track(track.lower())
        except ValueError:
            valid = [t.value for t in Track]
            raise TrackNotFound(
                f"Unknown track {track!r}; valid tracks: {valid}",
                details={"track": track, "valid_tracks": valid},
            ) from None
