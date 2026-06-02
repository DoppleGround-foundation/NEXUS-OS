"""Tests for nexus_os.db.manager — Thread-safe database manager."""

import threading

import pytest

from nexus_os.db.manager import (
    ConnectionPool,
    DatabaseManager,
    DBConfig,
    EncryptionPolicyError,
    QueryResult,
)


class TestDBConfig:
    def test_defaults(self):
        cfg = DBConfig()
        assert cfg.db_path == ":memory:"
        assert cfg.allow_unencrypted is False
        assert cfg.max_connections == 5
        assert cfg.journal_mode == "wal"

    def test_custom_values(self):
        cfg = DBConfig(db_path="/tmp/test.db", allow_unencrypted=True, max_connections=10)
        assert cfg.db_path == "/tmp/test.db"
        assert cfg.allow_unencrypted is True
        assert cfg.max_connections == 10


class TestConnectionPool:
    def test_acquire_release(self):
        pool = ConnectionPool(DBConfig())
        conn = pool.acquire()
        assert pool.active_count == 1
        pool.release(conn)
        assert pool.active_count == 0
        assert pool.pool_size == 1

    def test_reuse_connection(self):
        pool = ConnectionPool(DBConfig())
        conn1 = pool.acquire()
        pool.release(conn1)
        conn2 = pool.acquire()
        assert conn1 is conn2

    def test_max_connections(self):
        cfg = DBConfig(max_connections=2)
        pool = ConnectionPool(cfg)
        c1 = pool.acquire()
        c2 = pool.acquire()
        with pytest.raises(RuntimeError, match="exhausted"):
            pool.acquire()
        pool.release(c1)
        pool.release(c2)

    def test_close_all(self):
        pool = ConnectionPool(DBConfig())
        c1 = pool.acquire()
        pool.release(c1)
        pool.close_all()
        assert pool.pool_size == 0
        assert pool.active_count == 0


class TestDatabaseManager:
    def test_execute_create_and_insert(self):
        db = DatabaseManager()
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO test (name) VALUES (?)", ("alice",))
        result = db.execute("SELECT * FROM test")
        assert len(result.rows) == 1
        assert result.rows[0]["name"] == "alice"
        db.close()

    def test_execute_returns_query_result(self):
        db = DatabaseManager()
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        result = db.execute("INSERT INTO t (val) VALUES (?)", ("x",))
        assert isinstance(result, QueryResult)
        assert result.lastrowid == 1
        db.close()

    def test_execute_many(self):
        db = DatabaseManager()
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        db.execute_many("INSERT INTO t (val) VALUES (?)", [("a",), ("b",), ("c",)])
        result = db.execute("SELECT COUNT(*) as cnt FROM t")
        assert result.rows[0]["cnt"] == 3
        db.close()

    def test_transaction_commit(self):
        db = DatabaseManager()
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        with db.transaction() as conn:
            conn.execute("INSERT INTO t (val) VALUES (?)", ("tx",))
        result = db.execute("SELECT * FROM t")
        assert len(result.rows) == 1
        db.close()

    def test_transaction_rollback_on_error(self):
        db = DatabaseManager()
        db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT NOT NULL)")
        with pytest.raises(Exception):
            with db.transaction() as conn:
                conn.execute("INSERT INTO t (val) VALUES (?)", ("ok",))
                conn.execute("INSERT INTO t (val) VALUES (?)", (None,))
        result = db.execute("SELECT * FROM t")
        assert len(result.rows) == 0
        db.close()

    def test_init_schema(self):
        db = DatabaseManager()
        assert db.is_initialized is False
        db.init_schema("CREATE TABLE schema_test (id INTEGER PRIMARY KEY)")
        assert db.is_initialized is True
        db.close()

    def test_encryption_policy_memory_ok(self):
        db = DatabaseManager(DBConfig(db_path=":memory:"))
        assert db.check_encryption_policy() is True

    def test_encryption_policy_unencrypted_allowed(self):
        db = DatabaseManager(DBConfig(db_path="/tmp/test.db", allow_unencrypted=True))
        assert db.check_encryption_policy() is True

    def test_encryption_policy_hard_fail(self):
        db = DatabaseManager(DBConfig(db_path="/tmp/test.db", allow_unencrypted=False))
        with pytest.raises(EncryptionPolicyError, match="Encryption required"):
            db.check_encryption_policy()

    def test_thread_safety(self):
        db = DatabaseManager()
        db.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, val INTEGER)")
        db.execute("INSERT INTO counter (val) VALUES (0)")

        errors = []

        def increment():
            try:
                for _ in range(50):
                    db.execute("UPDATE counter SET val = val + 1 WHERE id = 1")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=increment) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        result = db.execute("SELECT val FROM counter WHERE id = 1")
        assert result.rows[0]["val"] == 200
        db.close()

    def test_connection_context_manager(self):
        db = DatabaseManager()
        with db.connection() as conn:
            conn.execute("CREATE TABLE ctx (id INTEGER)")
            conn.execute("INSERT INTO ctx VALUES (1)")
        result = db.execute("SELECT * FROM ctx")
        assert len(result.rows) == 1
        db.close()

    def test_active_connections(self):
        db = DatabaseManager()
        assert db.active_connections == 0
        db.close()
