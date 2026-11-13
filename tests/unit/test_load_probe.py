"""Unit tests for tools/load_probe.py (written first, so they start red). No real HTTP runs."""
import sys
from pathlib import Path

# Repo root, two levels above tests/unit.
ROOT: Path = Path(__file__).resolve().parents[2]
# Make tools/ importable without a package.
sys.path.insert(0, str(ROOT / "tools"))

from load_probe import ProbeCounter, run_probe  # noqa: E402


def test_counter_mixed_results() -> None:
    """Totals, failures by type, and versions seen are all counted."""
    # Feed four results: two good (v1, v2), one timeout, one 502.
    counter: ProbeCounter = ProbeCounter()
    counter.add("ok", "v1")
    counter.add("ok", "v2")
    counter.add("timeout")
    counter.add("http_502")
    # Totals.
    assert counter.total == 4
    assert counter.ok == 2
    assert counter.failed == 2
    # Failures by type.
    assert counter.failures == {"timeout": 1, "http_502": 1}
    # Versions seen in OK responses only.
    assert counter.versions == {"v1": 1, "v2": 1}


def test_summary_no_failures() -> None:
    """The one-line summary matches the agreed format."""
    # 3 results, all ok.
    counter: ProbeCounter = ProbeCounter()
    for v in ["v1", "v1", "v2"]:
        counter.add("ok", v)
    # No failure breakdown when nothing failed.
    assert counter.summary() == "total 3 ok 3 failed 0 | versions v1:2 v2:1"


def test_summary_with_failures() -> None:
    """Failures are broken down by type in the summary."""
    # One ok, one timeout, one connection error.
    counter: ProbeCounter = ProbeCounter()
    counter.add("ok", "v1")
    counter.add("timeout")
    counter.add("connection_error")
    # The breakdown sits in brackets after the failed count.
    assert counter.summary() == (
        "total 3 ok 1 failed 2 (connection_error:1 timeout:1) | versions v1:1"
    )


def test_run_probe_stops_after_duration() -> None:
    """run_probe calls the fetch function on a 100 ms beat until the duration ends."""
    # A fake clock that moves only when the fake sleep is called.
    clock: list[float] = [0.0]
    # The results the fake server gives, in order.
    results: list[tuple[str, str | None]] = [("ok", "v1"), ("timeout", None), ("ok", "v2")]

    def fake_fetch(url: str) -> tuple[str, str | None]:
        """Return the next prepared result."""
        return results.pop(0)

    def fake_sleep(seconds: float) -> None:
        """Move the fake clock forward."""
        clock[0] += seconds

    # Run for 0.3 s with a 0.1 s beat: three requests.
    counter: ProbeCounter = run_probe(
        "http://lb", duration_s=0.3, interval_s=0.1,
        fetch=fake_fetch, sleep=fake_sleep, now=lambda: clock[0],
    )
    # All three results were counted.
    assert counter.total == 3
    assert counter.failures == {"timeout": 1}
    assert counter.versions == {"v1": 1, "v2": 1}


def test_failures_are_logged_with_the_time() -> None:
    """Each failure produces one log line with the UTC time and the failure type."""
    # A fake clock for the beat, and a fixed wall-clock string for the log.
    clock: list[float] = [0.0]
    # One good answer, one timeout.
    results: list[tuple[str, str | None]] = [("ok", "v1"), ("timeout", None)]
    # Collect the log lines.
    lines: list[str] = []

    run_probe(
        "http://lb", duration_s=0.2, interval_s=0.1,
        fetch=lambda url: results.pop(0),
        sleep=lambda s: clock.__setitem__(0, clock[0] + s),
        now=lambda: clock[0],
        log=lines.append,
        wall_clock=lambda: "06:35:12",
    )
    # Only the failure is logged, with its time and type.
    failed_lines: list[str] = [ln for ln in lines if "FAILED" in ln]
    assert len(failed_lines) == 1
    assert "06:35:12" in failed_lines[0] and "timeout" in failed_lines[0]


def test_progress_line_is_logged() -> None:
    """A progress line with the running summary appears at the chosen interval."""
    # A fake clock again.
    clock: list[float] = [0.0]
    # Collect the log lines.
    lines: list[str] = []

    run_probe(
        "http://lb", duration_s=0.5, interval_s=0.1,
        fetch=lambda url: ("ok", "v1"),
        sleep=lambda s: clock.__setitem__(0, clock[0] + s),
        now=lambda: clock[0],
        log=lines.append,
        wall_clock=lambda: "06:35:12",
        progress_every_s=0.2,
    )
    # At least one progress line shows the running totals.
    progress: list[str] = [ln for ln in lines if "progress" in ln]
    assert progress and "total" in progress[0] and "failed 0" in progress[0]
