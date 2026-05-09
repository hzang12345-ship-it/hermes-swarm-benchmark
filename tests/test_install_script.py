"""Tests for scripts/install_skill.sh — the public installer."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "install_skill.sh"


def test_install_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK), f"{SCRIPT} must be executable"


def test_install_script_passes_bash_n() -> None:
    """Static syntax check — the script must parse with `bash -n`."""
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


def test_install_script_dry_run_default(tmp_path: Path) -> None:
    """Without --apply, the script must not touch the destination."""
    dest = tmp_path / "skills" / "hermes-swarm-benchmark"
    proc = subprocess.run(
        [str(SCRIPT), "--dest", str(dest)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "DRY-RUN" in proc.stdout
    assert not dest.exists(), "dry-run must not create the destination"


def test_install_script_apply_copies_files(tmp_path: Path) -> None:
    dest = tmp_path / "skills" / "hermes-swarm-benchmark"
    proc = subprocess.run(
        [str(SCRIPT), "--apply", "--dest", str(dest)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert (dest / "SKILL.md").is_file()
    assert (dest / "src" / "hermes_benchmark" / "report.py").is_file()
    assert (dest / "src" / "hermes_benchmark" / "cli.py").is_file()


def test_install_script_refuses_dangerous_dest(tmp_path: Path) -> None:
    """Refuse to write into obviously-system paths."""
    proc = subprocess.run(
        [str(SCRIPT), "--apply", "--dest", "/etc/passwd"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode != 0
    assert "refusing" in proc.stderr.lower()


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_install_script_help(flag: str) -> None:
    proc = subprocess.run(
        [str(SCRIPT), flag], capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0
    assert "install_skill.sh" in proc.stdout
    assert "--apply" in proc.stdout
