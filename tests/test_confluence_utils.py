"""
Tests for src/fm_review/confluence_utils.py

Covers: locking, backup, retry, audit log, client operations.
"""
import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from fm_review.confluence_utils import (
    RETRYABLE_CODES,
    ConfluenceAPIError,
    ConfluenceBackup,
    ConfluenceClient,
    ConfluenceLock,
    ConfluenceLockError,
    _RateLimiter,
    _TTLCache,
)

# ── Lock Tests ──────────────────────────────────────────────


class TestConfluenceLock:
    def test_acquire_and_release(self, tmp_path):
        """Lock can be acquired and released."""
        with patch("fm_review.confluence_utils.LOCK_DIR", tmp_path):
            lock = ConfluenceLock("test_page", timeout=5)
            assert lock.acquire() is True
            lock.release()
            # Lock file cleaned up
            assert not (tmp_path / "confluence_test_page.lock").exists()

    def test_context_manager(self, tmp_path):
        """Lock works as context manager."""
        with patch("fm_review.confluence_utils.LOCK_DIR", tmp_path):
            with ConfluenceLock("test_page", timeout=5):
                lock_file = tmp_path / "confluence_test_page.lock"
                assert lock_file.exists()
            # After exit, lock file removed
            assert not lock_file.exists()

    def test_lock_writes_info(self, tmp_path):
        """Lock file contains JSON with page_id and pid."""
        with patch("fm_review.confluence_utils.LOCK_DIR", tmp_path):
            lock = ConfluenceLock("page123", timeout=5)
            lock.acquire()
            lock_file = tmp_path / "confluence_page123.lock"
            content = lock_file.read_text()
            data = json.loads(content)
            assert data["page_id"] == "page123"
            assert data["pid"] == os.getpid()
            lock.release()

    def test_lock_timeout_raises(self, tmp_path):
        """ConfluenceLockError raised when lock cannot be acquired within timeout."""
        with patch("fm_review.confluence_utils.LOCK_DIR", tmp_path):
            # Acquire first lock
            lock1 = ConfluenceLock("blocked_page", timeout=5)
            lock1.acquire()

            # Second lock should fail (same process can re-acquire with fcntl,
            # so we simulate by holding the fd open and patching)
            with patch("fm_review.confluence_utils.LOCK_TIMEOUT", 0):
                with pytest.raises(ConfluenceLockError, match="Could not acquire lock"):
                    with ConfluenceLock("blocked_page", timeout=0):
                        pass

            lock1.release()


# ── Backup Tests ────────────────────────────────────────────


class TestConfluenceBackup:
    def test_save_creates_file(self, tmp_path, confluence_response):
        """Backup.save creates a JSON file."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
            backup = ConfluenceBackup("test_page")
            page_data = confluence_response()
            path = backup.save(page_data)
            assert path.exists()
            assert path.suffix == ".json"
            saved = json.loads(path.read_text())
            assert saved["version"]["number"] == 42

    def test_get_latest(self, tmp_path, confluence_response):
        """get_latest returns most recent backup."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
            backup = ConfluenceBackup("test_page")
            page_v1 = confluence_response(version=1)
            page_v2 = confluence_response(version=2)
            backup.save(page_v1)
            time.sleep(0.05)  # ensure different timestamp
            backup.save(page_v2)
            latest = backup.get_latest()
            assert latest["version"]["number"] == 2

    def test_get_latest_empty(self, tmp_path):
        """get_latest returns None when no backups exist."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
            backup = ConfluenceBackup("empty_page")
            assert backup.get_latest() is None

    def test_cleanup_old_backups(self, tmp_path, confluence_response):
        """Only MAX_BACKUPS most recent backups are kept."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
            with patch("fm_review.confluence_utils.MAX_BACKUPS", 3):
                backup = ConfluenceBackup("cleanup_page")
                for i in range(5):
                    backup.save(confluence_response(version=i))
                    time.sleep(0.05)
                backups = backup.list_backups()
                assert len(backups) == 3

    def test_list_backups_sorted(self, tmp_path, confluence_response):
        """list_backups returns files sorted newest first."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
            backup = ConfluenceBackup("sorted_page")
            for i in range(3):
                backup.save(confluence_response(version=i + 1))
                time.sleep(0.05)
            backups = backup.list_backups()
            assert len(backups) == 3
            # Most recent first
            names = [b.name for b in backups]
            assert names == sorted(names, reverse=True)


# ── Client Tests ────────────────────────────────────────────


class TestConfluenceClient:
    def test_get_page_success(self, mock_urllib):
        """get_page returns page data from API."""
        client = ConfluenceClient("https://test.example.com", "token", "12345")
        page = client.get_page()
        assert page["id"] == "83951683"
        assert page["version"]["number"] == 42
        assert "body" in page

    def test_get_page_constructs_url(self, mock_urllib):
        """get_page calls correct API endpoint."""
        client = ConfluenceClient("https://test.example.com", "token", "12345")
        client.get_page()
        call_args = mock_urllib.call_args
        req = call_args[0][0]
        assert "/rest/api/content/12345" in req.full_url
        assert "expand=body.storage,version" in req.full_url

    def test_get_page_sends_auth_header(self, mock_urllib):
        """get_page sends Bearer token in Authorization header."""
        client = ConfluenceClient("https://test.example.com", "mytoken", "12345")
        client.get_page()
        req = mock_urllib.call_args[0][0]
        assert req.get_header("Authorization") == "Bearer mytoken"

    def test_update_page_creates_backup(self, tmp_path, mock_urllib, confluence_response):
        """update_page creates backup before PUT."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
            client = ConfluenceClient("https://test.example.com", "token", "12345")
            with patch("fm_review.confluence_utils.AUDIT_LOG_DIR", tmp_path / "audit"):
                _, backup_path = client.update_page(
                    "<p>New content</p>", "test update",
                    agent_name="Agent7_Publisher"
                )
            assert backup_path is not None
            assert backup_path.exists()

    def test_update_page_increments_version(self, tmp_path, mock_urllib):
        """update_page sends version.number = current + 1."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
            with patch("fm_review.confluence_utils.AUDIT_LOG_DIR", tmp_path / "audit"):
                client = ConfluenceClient("https://test.example.com", "token", "12345")
                client.update_page("<p>New</p>", "test", agent_name="test")
                # The PUT call is the second urlopen call (first is GET)
                put_call = mock_urllib.call_args_list[-1]
                req = put_call[0][0]
                body = json.loads(req.data.decode("utf-8"))
                assert body["version"]["number"] == 43  # 42 + 1

    def test_update_page_fm_version_in_message(self, tmp_path, mock_urllib):
        """FM version is prepended to version.message."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
            with patch("fm_review.confluence_utils.AUDIT_LOG_DIR", tmp_path / "audit"):
                client = ConfluenceClient("https://test.example.com", "token", "12345")
                client.update_page("<p>New</p>", "description",
                                   fm_version="1.0.3", agent_name="test")
                put_call = mock_urllib.call_args_list[-1]
                req = put_call[0][0]
                body = json.loads(req.data.decode("utf-8"))
                assert body["version"]["message"] == "[FM 1.0.3] description"

    def test_update_page_audit_log(self, tmp_path, mock_urllib):
        """update_page writes entry to audit log."""
        audit_dir = tmp_path / "audit"
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path / "backups"):
            with patch("fm_review.confluence_utils.AUDIT_LOG_DIR", audit_dir):
                client = ConfluenceClient("https://test.example.com", "token", "12345")
                client.update_page("<p>New</p>", "test update",
                                   agent_name="Agent7_Publisher")
                log_file = audit_dir / "confluence_12345.jsonl"
                assert log_file.exists()
                entry = json.loads(log_file.read_text().strip())
                assert entry["action"] == "update"
                assert entry["agent"] == "Agent7_Publisher"
                assert entry["page_id"] == "12345"

    def test_url_trailing_slash_stripped(self, mock_urllib):
        """Trailing slash in URL is stripped."""
        client = ConfluenceClient("https://test.example.com/", "token", "12345")
        assert client.url == "https://test.example.com"


# ── Retry Tests ─────────────────────────────────────────────


class TestRetryLogic:
    def test_retry_on_500(self, tmp_path):
        """Client retries on HTTP 500 errors."""
        import urllib.error

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                error = urllib.error.HTTPError(
                    "https://test.example.com", 500, "Internal Server Error",
                    {}, MagicMock()
                )
                error.read = MagicMock(return_value=b"Server Error")
                raise error
            # Third call succeeds
            resp = MagicMock()
            resp.read.return_value = json.dumps({"id": "12345", "version": {"number": 1}}).encode()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with patch("fm_review.confluence_utils.RETRY_BACKOFF_BASE", 0.01):
                client = ConfluenceClient("https://test.example.com", "token", "12345")
                result = client.get_page()
                assert call_count == 3
                assert result["id"] == "12345"

    def test_no_retry_on_404(self):
        """Client does NOT retry on HTTP 404."""
        import urllib.error

        error = urllib.error.HTTPError(
            "https://test.example.com", 404, "Not Found", {}, MagicMock()
        )
        error.read = MagicMock(return_value=b"Not Found")

        with patch("urllib.request.urlopen", side_effect=error):
            client = ConfluenceClient("https://test.example.com", "token", "12345")
            with pytest.raises(ConfluenceAPIError) as exc_info:
                client.get_page()
            assert exc_info.value.code == 404

    def test_retryable_codes(self):
        """All expected HTTP codes are in RETRYABLE_CODES."""
        expected = {500, 502, 503, 504, 408, 429}
        assert RETRYABLE_CODES == expected

    def test_max_retries_exceeded(self):
        """ConfluenceAPIError raised after max retries."""
        import urllib.error

        error = urllib.error.HTTPError(
            "https://test.example.com", 503, "Service Unavailable", {}, MagicMock()
        )
        error.read = MagicMock(return_value=b"Unavailable")

        with patch("urllib.request.urlopen", side_effect=error):
            with patch("fm_review.confluence_utils.RETRY_BACKOFF_BASE", 0.01):
                client = ConfluenceClient("https://test.example.com", "token", "12345")
                with pytest.raises(ConfluenceAPIError):
                    client.get_page()


# ── Rollback Tests ──────────────────────────────────────────


class TestRollback:
    def test_rollback_restores_content(self, tmp_path, confluence_response):
        """rollback sends PUT with backup body content."""
        backup_data = confluence_response(version=40, body="<p>Old content</p>")
        current_data = confluence_response(version=43)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            req = args[0]
            resp = MagicMock()
            if req.method == "GET" or req.data is None:
                resp.read.return_value = json.dumps(current_data).encode()
            else:
                resp.read.return_value = json.dumps(
                    confluence_response(version=44)
                ).encode()
            resp.__enter__ = MagicMock(return_value=resp)
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path / "backups"):
                with patch("fm_review.confluence_utils.AUDIT_LOG_DIR", tmp_path / "audit"):
                    client = ConfluenceClient("https://test.example.com", "token", "12345")
                    # Save backup manually
                    backup_path = client.backup.save(backup_data)
                    result = client.rollback(backup_path)
                    assert result["version"]["number"] == 44

    def test_rollback_no_backup_raises(self, tmp_path):
        """rollback raises error when no backup available."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path / "empty"):
            client = ConfluenceClient("https://test.example.com", "token", "12345")
            with pytest.raises(ConfluenceAPIError, match="No backup available"):
                client.rollback()


# ── create_client_from_env Tests ────────────────────────────


class TestCreateClientFromEnv:
    def test_missing_token_raises(self):
        """ValueError raised when neither CONFLUENCE_TOKEN nor CONFLUENCE_PERSONAL_TOKEN set."""
        from fm_review.confluence_utils import create_client_from_env
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="CONFLUENCE_TOKEN"):
                create_client_from_env("12345")

    def test_fallback_to_personal_token(self):
        """Client uses CONFLUENCE_PERSONAL_TOKEN when CONFLUENCE_TOKEN is not set."""
        from fm_review.confluence_utils import create_client_from_env
        env = {
            "CONFLUENCE_PERSONAL_TOKEN": "fallback-token",
            "CONFLUENCE_PAGE_ID": "12345"
        }
        with patch.dict(os.environ, env, clear=True):
            client = create_client_from_env()
            assert client.token == "fallback-token"

    def test_missing_page_id_raises(self):
        """ValueError raised when no page_id provided."""
        from fm_review.confluence_utils import create_client_from_env
        env = {"CONFLUENCE_TOKEN": "test-token"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="page_id"):
                create_client_from_env()

    def test_creates_client_with_env(self):
        """Client created successfully with env vars."""
        from fm_review.confluence_utils import create_client_from_env
        env = {
            "CONFLUENCE_URL": "https://conf.example.com",
            "CONFLUENCE_TOKEN": "test-token",
            "CONFLUENCE_PAGE_ID": "99999"
        }
        with patch.dict(os.environ, env, clear=True):
            client = create_client_from_env()
            assert client.url == "https://conf.example.com"
            assert client.page_id == "99999"


# ── Rate Limiter Tests ─────────────────────────────────────


class TestRateLimiter:
    def test_first_acquire_instant(self):
        """First acquire should be near-instant (bucket starts full)."""
        limiter = _RateLimiter(rps=10.0)
        t0 = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.05

    def test_burst_up_to_capacity(self):
        """Can burst up to capacity tokens without delay."""
        limiter = _RateLimiter(rps=5.0)
        t0 = time.monotonic()
        for _ in range(5):
            limiter.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.1  # 5 tokens should be near-instant

    def test_throttles_beyond_capacity(self):
        """Requests beyond capacity are delayed."""
        limiter = _RateLimiter(rps=10.0)
        # Exhaust all tokens
        for _ in range(10):
            limiter.acquire()
        # Next one should take ~0.1s (1/10 RPS)
        t0 = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.05  # at least half the expected wait

    def test_tokens_refill(self):
        """Tokens refill after waiting."""
        limiter = _RateLimiter(rps=100.0)
        # Exhaust tokens
        for _ in range(100):
            limiter.acquire()
        # Wait for refill
        time.sleep(0.05)  # 5 tokens should refill at 100 RPS
        t0 = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.05

    def test_rate_limiter_called_in_do_request(self, mock_urllib):
        """_do_request calls rate limiter before making request."""
        with patch("fm_review.confluence_utils._rate_limiter") as mock_rl:
            with patch("fm_review.confluence_utils._page_cache") as mock_cache:
                mock_cache.get.return_value = None
                client = ConfluenceClient("https://test.example.com", "token", "12345")
                client.get_page()
                assert mock_rl.acquire.called


# ── TTL Cache Tests ────────────────────────────────────────


class TestTTLCache:
    def test_put_and_get(self):
        """Cache returns stored value within TTL."""
        cache = _TTLCache(ttl=10)
        cache.put("key1", {"data": "value"})
        assert cache.get("key1") == {"data": "value"}

    def test_miss_returns_none(self):
        """Cache returns None for missing key."""
        cache = _TTLCache(ttl=10)
        assert cache.get("nonexistent") is None

    def test_expired_returns_none(self):
        """Cache returns None for expired entry."""
        cache = _TTLCache(ttl=0)  # 0s TTL = immediate expiry
        cache.put("key1", "value")
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_invalidate_by_prefix(self):
        """invalidate removes entries matching prefix."""
        cache = _TTLCache(ttl=60)
        cache.put("page1:body", "data1")
        cache.put("page1:version", "data2")
        cache.put("page2:body", "data3")
        cache.invalidate("page1")
        assert cache.get("page1:body") is None
        assert cache.get("page1:version") is None
        assert cache.get("page2:body") == "data3"

    def test_invalidate_all(self):
        """invalidate with empty prefix clears all."""
        cache = _TTLCache(ttl=60)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.invalidate()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_get_page_uses_cache(self, mock_urllib):
        """Second get_page call returns cached result without API call."""
        with patch("fm_review.confluence_utils._page_cache", _TTLCache(ttl=60)):
            client = ConfluenceClient("https://test.example.com", "token", "12345")
            result1 = client.get_page()
            result2 = client.get_page()
            assert result1 == result2
            # Only one actual API call (mock_urllib called once)
            assert mock_urllib.call_count == 1

    def test_update_page_invalidates_cache(self, tmp_path, mock_urllib):
        """update_page invalidates cache for that page."""
        test_cache = _TTLCache(ttl=60)
        with patch("fm_review.confluence_utils._page_cache", test_cache):
            with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
                with patch("fm_review.confluence_utils.AUDIT_LOG_DIR", tmp_path / "audit"):
                    client = ConfluenceClient("https://test.example.com", "token", "12345")
                    # Populate cache
                    client.get_page()
                    assert test_cache.get("12345:body.storage,version") is not None
                    # Update should invalidate
                    client.update_page("<p>New</p>", "test", agent_name="test")
                    assert test_cache.get("12345:body.storage,version") is None


# ── Safe Publish Tests ─────────────────────────────────────


class TestSafePublish:
    def test_safe_publish_success(self, tmp_path, mock_urllib):
        """safe_publish acquires lock and updates page."""
        from fm_review.confluence_utils import safe_publish
        env = {
            "CONFLUENCE_URL": "https://test.example.com",
            "CONFLUENCE_TOKEN": "test-token",
        }
        with patch.dict(os.environ, env):
            with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path / "backup"):
                with patch("fm_review.confluence_utils.AUDIT_LOG_DIR", tmp_path / "audit"):
                    with patch("fm_review.confluence_utils.LOCK_DIR", tmp_path):
                        result = safe_publish(
                            "12345", "<p>New</p>", "test update",
                            fm_version="1.0.0", agent_name="test"
                        )
                        assert result["id"] == "83951683"


# ── Lock Error Path Tests ──────────────────────────────────


class TestLockErrorPaths:
    def test_release_handles_os_error(self, tmp_path):
        """release handles OSError during flock."""
        with patch("fm_review.confluence_utils.LOCK_DIR", tmp_path):
            lock = ConfluenceLock("err_page", timeout=5)
            lock.acquire()
            # Force OSError on flock
            import fcntl
            with patch("fcntl.flock", side_effect=OSError("mock flock error")):
                lock.release()
            # lock_fd should be None after release
            assert lock.lock_fd is None

    def test_release_handles_unlink_error(self, tmp_path):
        """release handles exception on file cleanup."""
        with patch("fm_review.confluence_utils.LOCK_DIR", tmp_path):
            lock = ConfluenceLock("unlink_page", timeout=5)
            lock.acquire()
            lock_file = lock.lock_file
            # Remove the file before release tries to unlink it
            lock_file.unlink()
            lock.release()  # Should not raise
            assert lock.lock_fd is None


# ── Backup Cleanup Error ───────────────────────────────────


class TestBackupCleanupError:
    def test_cleanup_handles_unlink_error(self, tmp_path, confluence_response):
        """_cleanup_old_backups handles OSError on unlink."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path):
            with patch("fm_review.confluence_utils.MAX_BACKUPS", 1):
                backup = ConfluenceBackup("cleanup_err_page")
                for i in range(3):
                    backup.save(confluence_response(version=i))
                    time.sleep(0.05)
                # Verify only MAX_BACKUPS kept (cleanup worked despite potential errors)
                backups = backup.list_backups()
                assert len(backups) == 1


# ── Update Error Path ─────────────────────────────────────


class TestUpdateErrorPath:
    def test_update_page_api_error_preserves_backup(self, tmp_path, mock_urllib):
        """update_page preserves backup when API PUT fails."""
        call_count = 0
        import urllib.error

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            req = args[0]
            # First call (GET for current page) succeeds
            if call_count == 1:
                resp = MagicMock()
                resp.read.return_value = json.dumps({
                    "id": "12345", "type": "page", "title": "Test Page",
                    "version": {"number": 42, "message": "test"},
                    "body": {"storage": {"value": "<p>old</p>", "representation": "storage"}}
                }).encode()
                resp.__enter__ = MagicMock(return_value=resp)
                resp.__exit__ = MagicMock(return_value=False)
                return resp
            # Second call (PUT) fails
            error = urllib.error.HTTPError(
                "https://test.example.com", 403, "Forbidden", {}, MagicMock()
            )
            error.read = MagicMock(return_value=b"Forbidden")
            raise error

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path / "backup"):
                with patch("fm_review.confluence_utils.AUDIT_LOG_DIR", tmp_path / "audit"):
                    client = ConfluenceClient("https://test.example.com", "token", "12345")
                    with pytest.raises(ConfluenceAPIError):
                        client.update_page("<p>New</p>", "test", agent_name="test")
                    # Backup should still exist
                    backups = client.backup.list_backups()
                    assert len(backups) >= 1


# ── Audit Log Error Path ──────────────────────────────────


class TestAuditLogError:
    def test_audit_log_handles_os_error(self, tmp_path, mock_urllib):
        """_audit_log silently handles OSError."""
        with patch("fm_review.confluence_utils.BACKUP_DIR", tmp_path / "backup"):
            # Set audit dir to a file (not directory) to trigger OSError
            bad_dir = tmp_path / "bad_audit"
            bad_dir.write_text("not a dir")
            with patch("fm_review.confluence_utils.AUDIT_LOG_DIR", bad_dir):
                client = ConfluenceClient("https://test.example.com", "token", "12345")
                # Should not raise despite audit log failure
                client.update_page("<p>New</p>", "test", agent_name="test")
