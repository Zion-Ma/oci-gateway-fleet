"""Unit tests for tools/rolling_update.py (written first, so they start red)."""
import sys
from pathlib import Path

import pytest

# Repo root, two levels above tests/unit.
ROOT: Path = Path(__file__).resolve().parents[2]
# Make tools/ and the fakes importable without packages.
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests" / "fakes"))

from fake_lb import FakeLoadBalancer  # noqa: E402
from rolling_update import RollingUpdateError, rolling_update  # noqa: E402

# Three fake backends, in rollout order.
BACKENDS: list[str] = ["b1", "b2", "b3"]


def test_all_healthy() -> None:
    """Every backend is updated in order, drained during the update, and undrained at the end."""
    # Everything reports OK.
    lb: FakeLoadBalancer = FakeLoadBalancer({})
    # Record (backend, version, was_drained_at_that_moment) for each update.
    updates: list[tuple[str, str, bool]] = []

    def update_server(backend: str, version: str) -> None:
        """Fake update: note whether the backend was drained when we got here."""
        updates.append((backend, version, backend in lb.drained))

    # Run the rollout with no real waiting.
    rolling_update(BACKENDS, lb, update_server, "v2", "v1", sleep=lambda s: None)
    # All three updated in order, each while drained.
    assert updates == [("b1", "v2", True), ("b2", "v2", True), ("b3", "v2", True)]
    # Nothing is left drained.
    assert lb.drained == set()
    # Each backend was drained and then undrained, in order.
    drain_calls: list[tuple] = [c for c in lb.calls if c[0] == "set_drain"]
    assert drain_calls == [
        ("set_drain", "b1", True), ("set_drain", "b1", False),
        ("set_drain", "b2", True), ("set_drain", "b2", False),
        ("set_drain", "b3", True), ("set_drain", "b3", False),
    ]


def test_server_never_healthy_rolls_back() -> None:
    """If b2 never gets healthy: roll b2 back, undrain it, skip b3, raise."""
    # b2 is always CRITICAL.
    lb: FakeLoadBalancer = FakeLoadBalancer({"b2": ["CRITICAL"]})
    # Record every update call.
    updates: list[tuple[str, str]] = []

    def update_server(backend: str, version: str) -> None:
        """Fake update: just record it."""
        updates.append((backend, version))

    # The rollout must stop with an error.
    with pytest.raises(RollingUpdateError):
        rolling_update(BACKENDS, lb, update_server, "v2", "v1",
                       max_attempts=3, sleep=lambda s: None)
    # b1 updated, b2 updated then rolled back to the old version.
    assert updates == [("b1", "v2"), ("b2", "v2"), ("b2", "v1")]
    # b2 is undrained again.
    assert lb.drained == set()
    # b3 was never touched.
    assert not any(c[1] == "b3" for c in lb.calls)


def test_health_timeouts_retry_with_backoff() -> None:
    """b1 is unhealthy twice, then OK: retry with growing waits and finish."""
    # Two bad answers, then OK.
    lb: FakeLoadBalancer = FakeLoadBalancer({"b1": ["CRITICAL", "CRITICAL", "OK"]})
    # Record every wait.
    sleeps: list[float] = []
    # Run with no drain wait, so only the health retries sleep.
    rolling_update(BACKENDS, lb, lambda b, v: None, "v2", "v1",
                   drain_wait_s=0, base_delay_s=1, sleep=sleeps.append)
    # Two retries, and the second wait is longer than the first.
    assert sleeps == [1, 2]
    # The rollout still finished.
    assert lb.drained == set()
