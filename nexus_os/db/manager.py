"""Thread-safe database manager for SQLite/PostgreSQL.

Provides connection pooling, encryption policy enforcement, and
thread-safe CRUD operations for the Nexus OS governance layer.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator


@dataclass
class DBConfig:
    db_path: str = ":memory:"
    allow_unencrypted: bool = False
    max_connections: int = 5
    timeout: float = 30.0
    journal_mode: str = "wal"


class EncryptionPolicyError(Exception):
    pass


class ConnectionPool:
    """Thread-safe SQLite connection pool."""

    def __init__(self, config: DBConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._pool: list[sqlite3.Connection] = []
        self._active: int = 0

    def acquire(self) -> sqlite3.Connection:
        with self._lock:
            if self._pool:
                self._active += 1
                return self._pool.pop()
            if self._active < self._config.max_connections:
                conn = sqlite3.connect(
                    self._config.db_path,
                    timeout=self._config.timeout,
                    check_same_thread=False,
                )
                conn.row_factory = sqlite3.Row
                conn.execute(f"PRAGMA journal_mode={self._config.journal_mode}")
                self._active += 1
                return conn
        raise RuntimeError("Connection pool exhausted")

    def release(self, conn: sqlite3.Connection) -> None:
        with self._lock:
            self._pool.append(conn)
            self._active -= 1

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active

    @property
    def pool_size(self) -> int:
        with self._lock:
            return len(self._pool)

    def close_all(self) -> None:
        with self._lock:
            for conn in self._pool:
                conn.close()
            self._pool.clear()
            self._active = 0


@dataclass
class QueryResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    rowcount: int = 0
    lastrowid: int | None = None


class DatabaseManager:
    """Thread-safe database manager with encryption policy enforcement."""

    def __init__(self, config: DBConfig | None = None) -> None:
        self._config = config or DBConfig()
        self._pool = ConnectionPool(self._config)
        self._lock = threading.RLock()
        self._initialized = False

    @property
    def config(self) -> DBConfig:
        return self._config

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._pool.acquire()
        try:
            yield conn
        finally:
            self._pool.release(conn)

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._pool.acquire()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.release(conn)

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> QueryResult:
        with self._lock:
            with self.connection() as conn:
                cursor = conn.execute(sql, params or ())
                result = QueryResult(
                    rowcount=cursor.rowcount,
                    lastrowid=cursor.lastrowid,
                )
                if cursor.description:
                    result.rows = [dict(row) for row in cursor.fetchall()]
                conn.commit()
                return result

    def execute_many(self, sql: str, params_list: list[tuple[Any, ...]]) -> QueryResult:
        with self._lock:
            with self.transaction() as conn:
                cursor = conn.executemany(sql, params_list)
                return QueryResult(rowcount=cursor.rowcount)

    def init_schema(self, schema_sql: str) -> None:
        self.execute(schema_sql)
        self._initialized = True

    def check_encryption_policy(self) -> bool:
        """Hard-fail if encryption is required but not available.

        Returns True if policy is satisfied, raises EncryptionPolicyError otherwise.
        """
        if self._config.allow_unencrypted:
            return True
        if self._config.db_path == ":memory:":
            return True
        raise EncryptionPolicyError(
            "Encryption required but not configured. "
            "Set allow_unencrypted=True for development or configure encryption."
        )

    def close(self) -> None:
        self._pool.close_all()

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def active_connections(self) -> int:
        return self._pool.active_count
