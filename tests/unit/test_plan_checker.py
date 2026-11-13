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


def test_route_rule_removed() -> None:
    """Removing a route rule from a route table (an update) is one violation."""
    # Run the check on the plan.
    violations: list[str] = check_plan(load("removes_route_rule.json"))
    # One violation, and it names the route table.
    assert len(violations) == 1
    assert "module.network.oci_core_route_table.private" in violations[0]


def test_route_rule_removed_allowed() -> None:
    """allow_destroy=True lets a removed route rule through."""
    # No violations expected.
    assert check_plan(load("removes_route_rule.json"), allow_destroy=True) == []


def test_route_rule_added_ok() -> None:
    """Keeping every rule and adding one is safe, even if a computed field is unset."""
    # No violations expected.
    assert check_plan(load("adds_route_rule.json")) == []


def test_nat_blocked() -> None:
    """Setting block_traffic from false to true on the NAT gateway is one violation."""
    # Run the check on the plan.
    violations: list[str] = check_plan(load("blocks_nat.json"))
    # One violation, and it names the gateway.
    assert len(violations) == 1
    assert "module.network.oci_core_nat_gateway.main" in violations[0]


def test_service_gateway_blocked() -> None:
    """The same change on the Service Gateway is one violation."""
    # One violation expected.
    assert len(check_plan(load("blocks_service_gateway.json"))) == 1


def test_block_traffic_allowed() -> None:
    """allow_destroy=True lets block_traffic through on both gateways."""
    # Neither plan should give a violation.
    assert check_plan(load("blocks_nat.json"), allow_destroy=True) == []
    assert check_plan(load("blocks_service_gateway.json"), allow_destroy=True) == []


def test_nat_unblocked_ok() -> None:
    """Going from blocked back to open (the undo) is safe."""
    # No violations expected.
    assert check_plan(load("unblocks_nat.json")) == []
