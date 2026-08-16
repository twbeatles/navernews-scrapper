import hashlib
import os
from pathlib import Path
from unittest import mock

import pytest

from core import update_installer
from ui.main_window_update import _MainWindowUpdateMixin, _UpdateBridge


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_update_result_is_consumed_once(tmp_path: Path):
    result_path = tmp_path / "last-update-result.json"

    update_installer.write_update_result(result_path, {"status": "rolled_back", "error": "smoke failed"})

    assert update_installer.consume_update_result(result_path) == {
        "status": "rolled_back",
        "error": "smoke failed",
    }
    assert update_installer.consume_update_result(result_path) is None


def test_apply_staged_update_rolls_back_when_smoke_fails(tmp_path: Path):
    target = tmp_path / "NewsScraperPro_Safe.exe"
    staged = tmp_path / "staged.exe"
    backup = tmp_path / "NewsScraperPro_Safe.exe.v1.bak"
    target.write_bytes(b"old")
    staged.write_bytes(b"new")

    with mock.patch("core.update_installer.subprocess.run", return_value=mock.Mock(returncode=1)):
        with pytest.raises(RuntimeError, match="복구"):
            update_installer.apply_staged_update(
                target=target,
                staged=staged,
                backup=backup,
                expected_sha256=_sha256(b"new"),
                expected_size=3,
            )

    assert target.read_bytes() == b"old"


def test_apply_staged_update_restarts_verified_executable(tmp_path: Path):
    target = tmp_path / "NewsScraperPro_Safe.exe"
    staged = tmp_path / "staged.exe"
    backup = tmp_path / "NewsScraperPro_Safe.exe.v1.bak"
    target.write_bytes(b"old")
    staged.write_bytes(b"new")

    with mock.patch("core.update_installer.subprocess.run", return_value=mock.Mock(returncode=0)) as smoke:
        with mock.patch("core.update_installer.subprocess.Popen") as restart:
            update_installer.apply_staged_update(
                target=target,
                staged=staged,
                backup=backup,
                expected_sha256=_sha256(b"new"),
                expected_size=3,
            )

    assert target.read_bytes() == b"new"
    smoke.assert_called_once_with([str(target.resolve()), "--smoke"], timeout=60, check=False, capture_output=True)
    restart.assert_called_once()


def test_cleanup_update_artifacts_removes_only_stale_helper_and_staged_files(tmp_path: Path):
    stale_helper = tmp_path / "update-helper-old.exe"
    stale_staged = tmp_path / "update-1-old.exe"
    recent_staged = tmp_path / "update-1-recent.exe"
    unrelated = tmp_path / "notes.txt"
    for path in (stale_helper, stale_staged, recent_staged, unrelated):
        path.write_bytes(b"x")
    old = 1
    os.utime(stale_helper, (old, old))
    os.utime(stale_staged, (old, old))

    removed = update_installer.cleanup_update_artifacts(tmp_path, max_age_seconds=10)

    assert set(removed) == {stale_helper, stale_staged}
    assert recent_staged.exists()
    assert unrelated.exists()


def test_update_shutdown_suppresses_late_worker_result():
    class DummyUpdate(_MainWindowUpdateMixin):
        pass

    dummy = DummyUpdate()
    dummy._update_shutdown_requested = False
    dummy._update_bridge = _UpdateBridge()
    received: list[object] = []
    dummy._update_bridge.checked.connect(lambda manifest, *_args: received.append(manifest))

    dummy._emit_checked("before-close", None, False)
    dummy.shutdown_update_support()
    dummy._emit_checked("after-close", None, False)

    assert received == ["before-close"]
