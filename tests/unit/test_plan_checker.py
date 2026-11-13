"""Unit tests for tools/plan_checker.py (written first, so they start red)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Repo root, two levels above tests/unit.
ROOT: Path = Path(__file__).resolve().parents[2]
# Folder that holds the hand-written plan JSON files.
FIXTURES: Path = ROOT / "tests" / "fixtures"
# Make tools/ importable without a package.
sys.path.insert(0, str(ROOT / "tools"))

from plan_checker import check_plan  # noqa: E402


def load(name: str) -> dict:
    """Load one fixture plan by file name."""
    # Read and parse the JSON file.
    return json.loads((FIXTURES / name).read_text())


def test_safe_plan() -> None:
    """A plain instance create has no violations."""
    # Expect an empty list.
    assert check_plan(load("safe.json")) == []


def test_nat_deleted() -> None:
    """Deleting the NAT gateway is one violation naming the resource."""
    # Run the check on the plan.
    violations: list[str] = check_plan(load("deletes_nat.json"))
    # Exactly one violation, and it names the address.
    assert len(violations) == 1
    assert "module.network.oci_core_nat_gateway.nat" in violations[0]


def test_nat_deleted_allowed() -> None:
    """allow_destroy=True lets the NAT delete through."""
    # No violations expected.
    assert check_plan(load("deletes_nat.json"), allow_destroy=True) == []


def test_subnet_replaced() -> None:
    """Replacing (delete + create) a subnet is one violation."""
    # One violation expected.
    assert len(check_plan(load("replaces_subnet.json"))) == 1


def test_ssh_open() -> None:
    """SSH open to the world is blocked, even with allow_destroy=True."""
    # Without the flag.
    assert len(check_plan(load("opens_ssh.json"))) == 1
    # With the flag: still blocked.
    assert len(check_plan(load("opens_ssh.json"), allow_destroy=True)) == 1


def test_all_ports_open() -> None:
    """Ports 1 to 65535 open to the world is one violation."""
    # One violation expected.
    assert len(check_plan(load("opens_all_ports.json"))) == 1


def test_cli_exit_code() -> None:
    """The command line exits with 1 when the plan is blocked."""
    # Run the script as a subprocess.
    result: subprocess.CompletedProcess = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "plan_checker.py"),
         str(FIXTURES / "deletes_nat.json")],
        capture_output=True, text=True,
    )
    # Blocked means exit code 1.
    assert result.returncode == 1
