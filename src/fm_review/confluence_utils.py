#!/usr/bin/env python3
"""
Confluence Utilities Library v1.1 (FC-12B: audit log)
- File-based locking (R-01)
- Rollback mechanism (R-02)
- Retry policy with exponential backoff (R-06)
- Version management (R-05)
- Audit log for write operations (FC-12B)

Usage:
    from fm_review.confluence_utils import ConfluenceClient

    client = ConfluenceClient(url, token, page_id)
    with client.lock():
        page = client.get_page()
        client.update_page(new_body, "Description of changes")
"""

import os
import json
import time
import fcntl
import urllib.request
import urllib.error
import ssl
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

def _make_ssl_context():
    """Create a per-request SSL context that skips certificate verification.

    Corporate Confluence uses self-signed certificates.
    This is scoped to our requests only — does not affect other modules.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# Lock settings
LOCK_DIR = Path(__file__).parent.parent / ".locks"
LOCK_TIMEOUT = 60  # seconds
LOCK_RETRY_INTERVAL = 2  # seconds

# Retry settings
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1  # seconds (1, 2, 4)
RETRYABLE_CODES = {500, 502, 503, 504, 408, 429}

# Backup settings
BACKUP_DIR = Path(__file__).parent.parent / ".backups"
MAX_BACKUPS = 10

# Audit log settings (FC-12B)
AUDIT_LOG_DIR = Path(__file__).parent.parent / ".audit_log"


class ConfluenceLockError(Exception):
    """Raised when lock cannot be acquired"""
    pass


class ConfluenceAPIError(Exception):
    """Raised on API errors after retries exhausted"""
    def __init__(self, message: str, code: int = 0, response: str = ""):
        super().__init__(message)
        self.code = code
        self.response = response


class ConfluenceLock:
    """
    File-based lock for Confluence page operations.
    Prevents race conditions when multiple agents access same page.
    """

    def __init__(self, page_id: str, timeout: int = LOCK_TIMEOUT):
        self.page_id = page_id
        self.timeout = timeout
        self.lock_file = LOCK_DIR / f"confluence_{page_id}.lock"
        self.lock_fd = None

        # Ensure lock directory exists
        LOCK_DIR.mkdir(parents=True, exist_ok=True)

    def acquire(self) -> bool:
        """Acquire lock with timeout. Returns True if acquired."""
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                # Open or create lock file
                self.lock_fd = open(self.lock_file, 'w')

                # Try to acquire exclusive lock (non-blocking)
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Write lock info
                lock_info = {
                    "page_id": self.page_id,
                    "acquired_at": datetime.now().isoformat(),
                    "pid": os.getpid()
                }
                self.lock_fd.write(json.dumps(lock_info))
                self.lock_fd.flush()

                return True

            except (IOError, OSError):
                # Lock held by another process
                if self.lock_fd:
                    self.lock_fd.close()
                    self.lock_fd = None
                time.sleep(LOCK_RETRY_INTERVAL)

        return False

    def release(self):
        """Release the lock."""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
            except OSError:
                pass
            finally:
                self.lock_fd = None
                # Clean up lock file
                try:
                    self.lock_file.unlink()
                except Exception:
                    pass

    def __enter__(self):
        if not self.acquire():
            raise ConfluenceLockError(
                f"Could not acquire lock for page {self.page_id} within {self.timeout}s. "
                f"Another agent may be updating this page."
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class ConfluenceBackup:
    """
    Local backup before Confluence PUT — safety net for rollback.

    Why not rely on Confluence version history alone:
    - Admin can purge history; local copy is under our control
    - MCP server does raw PUT with no rollback; this catches partial writes
    - Enables offline diff/audit even when Confluence is unreachable
    Max 10 backups per page (auto-rotated).
    """

    def __init__(self, page_id: str):
        self.page_id = page_id
        self.backup_dir = BACKUP_DIR / page_id
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def save(self, page_data: Dict[str, Any]) -> Path:
        """Save page state to backup file. Returns backup path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version = page_data.get("version", {}).get("number", 0)

        backup_file = self.backup_dir / f"v{version}_{timestamp}.json"

        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(page_data, f, ensure_ascii=False, indent=2)

        # Cleanup old backups
        self._cleanup_old_backups()

        return backup_file

    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Get latest backup data."""
        backups = sorted(self.backup_dir.glob("*.json"), reverse=True)
        if backups:
            with open(backups[0], 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def list_backups(self) -> list:
        """List all available backups."""
        return sorted(self.backup_dir.glob("*.json"), reverse=True)

    def _cleanup_old_backups(self):
        """Keep only MAX_BACKUPS most recent backups."""
        backups = sorted(self.backup_dir.glob("*.json"), reverse=True)
        for old_backup in backups[MAX_BACKUPS:]:
            try:
                old_backup.unlink()
            except OSError:
                pass


class ConfluenceClient:
    """
    Confluence REST API client with:
    - Automatic locking (prevents race conditions)
    - Retry with exponential backoff (handles transient errors)
    - Backup/rollback (recovers from failed updates)
    - FM version tracking (syncs semantic version with Confluence)
    """

    def __init__(self, url: str, token: str, page_id: str):
        self.url = url.rstrip('/')
        self.token = token
        self.page_id = page_id
        self.backup = ConfluenceBackup(page_id)
        self._current_backup: Optional[Path] = None

    def lock(self, timeout: int = LOCK_TIMEOUT) -> ConfluenceLock:
        """Return a lock context manager for this page."""
        return ConfluenceLock(self.page_id, timeout)

    @retry(
        stop=stop_after_attempt(MAX_RETRIES + 1),
        wait=wait_random_exponential(multiplier=RETRY_BACKOFF_BASE, max=60),
        retry=retry_if_exception_type(urllib.error.URLError),
        reraise=True
    )
    def _do_request(self, req: urllib.request.Request) -> Dict:
        try:
            with urllib.request.urlopen(req, timeout=30, context=_make_ssl_context()) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code not in RETRYABLE_CODES:
                error_body = e.read().decode('utf-8', errors='replace')[:500]
                raise ConfluenceAPIError(
                    f"HTTP {e.code}: {error_body}",
                    code=e.code,
                    response=error_body
                ) from e
            print(f"  Transient HTTP error {e.code}, scheduling retry with tenacity...")
            raise
        except urllib.error.URLError as e:
            print(f"  Network error: {e.reason}, scheduling retry with tenacity...")
            raise

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Make HTTP request with retry logic.
        Retries on transient errors with exponential backoff and jitter via tenacity.
        """
        url = f"{self.url}{endpoint}"
        req = urllib.request.Request(url, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")

        if data:
            req.data = json.dumps(data).encode('utf-8')

        try:
            return self._do_request(req)
        except Exception as e:
            if isinstance(e, ConfluenceAPIError):
                raise
            raise ConfluenceAPIError(f"Max retries exceeded or fatal error: {str(e)}") from e

    def get_page(self, expand: str = "body.storage,version") -> Dict:
        """Get page content and metadata."""
        return self._request("GET", f"/rest/api/content/{self.page_id}?expand={expand}")

    def update_page(
        self,
        new_body: str,
        version_message: str,
        fm_version: Optional[str] = None,
        create_backup: bool = True,
        agent_name: str = "unknown"
    ) -> Tuple[Dict, Optional[Path]]:
        """
        Update page with new content.

        Args:
            new_body: New XHTML content for page body
            version_message: Description of changes (for Confluence history)
            fm_version: Optional FM semantic version (e.g., "1.2.3")
            create_backup: Whether to backup current state before update
            agent_name: Name of the agent performing the update (FC-12B)

        Returns:
            Tuple of (response_dict, backup_path or None)
        """
        # Get current page
        current = self.get_page()
        current_version = current["version"]["number"]
        title = current["title"]

        # Create backup before update
        backup_path = None
        if create_backup:
            backup_path = self.backup.save(current)
            self._current_backup = backup_path
            print(f"  Backup created: {backup_path.name}")

        # Prepare update payload
        update_data = {
            "id": self.page_id,
            "type": "page",
            "title": title,
            "version": {
                "number": current_version + 1,
                "message": version_message
            },
            "body": {
                "storage": {
                    "value": new_body,
                    "representation": "storage"
                }
            }
        }

        # Add FM version as page property if provided
        if fm_version:
            # Store FM version in version message for traceability
            update_data["version"]["message"] = f"[FM {fm_version}] {version_message}"

        try:
            result = self._request("PUT", f"/rest/api/content/{self.page_id}", update_data)

            # Audit log (FC-12B)
            new_version = result.get("version", {}).get("number", current_version + 1)
            self._audit_log("update", agent_name, version_message, new_version)

            return result, backup_path

        except ConfluenceAPIError as e:
            print(f"  ERROR during update: {e}")
            if backup_path:
                print(f"  Backup available for rollback: {backup_path}")
            raise

    def rollback(self, backup_path: Optional[Path] = None) -> Dict:
        """
        Rollback to previous page state.

        Args:
            backup_path: Specific backup to restore. If None, uses latest.

        Returns:
            Response from restore operation
        """
        if backup_path is None:
            backup_path = self._current_backup

        if backup_path is None:
            backup_data = self.backup.get_latest()
            if backup_data is None:
                raise ConfluenceAPIError("No backup available for rollback")
        else:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

        # Get current version for increment
        current = self.get_page()
        current_version = current["version"]["number"]

        # Restore from backup
        restore_body = backup_data.get("body", {}).get("storage", {}).get("value", "")

        restore_data = {
            "id": self.page_id,
            "type": "page",
            "title": backup_data.get("title", current["title"]),
            "version": {
                "number": current_version + 1,
                "message": f"ROLLBACK to version {backup_data.get('version', {}).get('number', '?')}"
            },
            "body": {
                "storage": {
                    "value": restore_body,
                    "representation": "storage"
                }
            }
        }

        result = self._request("PUT", f"/rest/api/content/{self.page_id}", restore_data)
        print(f"  Rollback complete. New version: {result.get('version', {}).get('number')}")

        # Audit log (FC-12B)
        new_version = result.get("version", {}).get("number", 0)
        self._audit_log("rollback", "system", f"ROLLBACK to version {backup_data.get('version', {}).get('number', '?')}", new_version)

        return result

    def _audit_log(self, action: str, agent_name: str, version_message: str, version_number: int):
        """Write audit entry for every Confluence write operation (FC-12B)."""
        AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = AUDIT_LOG_DIR / f"confluence_{self.page_id}.jsonl"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "page_id": self.page_id,
            "action": action,
            "agent": agent_name,
            "version_message": version_message,
            "version_number": version_number,
            "pid": os.getpid()
        }
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# Convenience functions for scripts

def create_client_from_env(page_id: Optional[str] = None) -> ConfluenceClient:
    """Create client using environment variables."""
    url = os.environ.get("CONFLUENCE_URL", "https://confluence.ekf.su")
    token = os.environ.get("CONFLUENCE_TOKEN", "") or os.environ.get("CONFLUENCE_PERSONAL_TOKEN", "")

    if not token:
        raise ValueError("CONFLUENCE_TOKEN (or CONFLUENCE_PERSONAL_TOKEN) environment variable not set")

    if page_id is None:
        page_id = os.environ.get("CONFLUENCE_PAGE_ID")
        if not page_id:
            raise ValueError("page_id not provided and CONFLUENCE_PAGE_ID not set")

    return ConfluenceClient(url, token, page_id)


def safe_publish(page_id: str, new_body: str, version_message: str,
                 fm_version: Optional[str] = None, agent_name: str = "unknown") -> Dict:
    """
    Publish to Confluence with full safety:
    - Acquires lock
    - Creates backup
    - Retries on failure
    - Returns result or raises error

    Usage:
        result = safe_publish("12345", "<p>New content</p>", "Updated section 3")
    """
    client = create_client_from_env(page_id)

    with client.lock():
        result, backup = client.update_page(
            new_body=new_body,
            version_message=version_message,
            fm_version=fm_version,
            agent_name=agent_name
        )
        return result


if __name__ == "__main__":
    # Test the library
    print("Confluence Utils Library v1.1 (FC-12B: audit log)")
    print("=" * 40)
    print(f"Lock dir: {LOCK_DIR}")
    print(f"Backup dir: {BACKUP_DIR}")
    print(f"Audit log dir: {AUDIT_LOG_DIR}")
    print(f"Max retries: {MAX_RETRIES}")
    print(f"Lock timeout: {LOCK_TIMEOUT}s")
