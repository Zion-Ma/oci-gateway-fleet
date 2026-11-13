"""Load probe: call the load balancer's /health every 100 ms and count what happens."""
import argparse
import sys
import time
from typing import Callable

import requests


class ProbeCounter:
    """Counts probe results. Pure, so tests can feed it fake results."""

    def __init__(self) -> None:
        """Start with nothing counted."""
        # Number of requests that got a 200.
        self.ok: int = 0
        # Failures by type, like {"timeout": 2, "http_502": 1}.
        self.failures: dict[str, int] = {}
        # Versions seen in OK responses, like {"v1": 921}.
        self.versions: dict[str, int] = {}

    @property
    def failed(self) -> int:
        """Total failures of every type."""
        return sum(self.failures.values())

    @property
    def total(self) -> int:
        """Every request counted."""
        return self.ok + self.failed

    def add(self, outcome: str, version: str | None = None) -> None:
        """Count one result. outcome is "ok", "timeout", "connection_error", "http_<code>"."""
        if outcome == "ok":
            # A good answer, and which version gave it.
            self.ok += 1
            key: str = version or "unknown"
            self.versions[key] = self.versions.get(key, 0) + 1
        else:
            # A failure, counted by type.
            self.failures[outcome] = self.failures.get(outcome, 0) + 1

    def summary(self) -> str:
        """One line, like: total 1834 ok 1834 failed 0 | versions v1:921 v2:913."""
        line: str = f"total {self.total} ok {self.ok} failed {self.failed}"
        if self.failures:
            # Failure types in alphabetical order, so the line is stable.
            kinds: str = " ".join(f"{k}:{v}" for k, v in sorted(self.failures.items()))
            line += f" ({kinds})"
        versions: str = " ".join(f"{k}:{v}" for k, v in sorted(self.versions.items()))
        return f"{line} | versions {versions}"


def fetch_health(url: str, timeout_s: float = 2.0) -> tuple[str, str | None]:
    """Call <url>/health once. Return (outcome, version)."""
    try:
        res: requests.Response = requests.get(f"{url}/health", timeout=timeout_s)
    except requests.Timeout:
        return ("timeout", None)
    except requests.ConnectionError:
        return ("connection_error", None)
    except requests.RequestException:
        return ("error", None)
    # Anything but 200 is a failure named by its status code.
    if res.status_code != 200:
        return (f"http_{res.status_code}", None)
    try:
        # The app reports its version in the body.
        return ("ok", str(res.json().get("version", "unknown")))
    except ValueError:
        # A 200 that is not JSON still counts as ok, with no version.
        return ("ok", None)


def run_probe(
    url: str,
    duration_s: float | None,
    interval_s: float = 0.1,
    fetch: Callable[[str], tuple[str, str | None]] = fetch_health,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = lambda message: None,
    wall_clock: Callable[[], str] = lambda: time.strftime("%H:%M:%S", time.gmtime()),
    progress_every_s: float = 10.0,
) -> ProbeCounter:
    """Probe on a fixed beat until the duration ends, or Ctrl+C. Return the counts.

    Every failure is logged with its UTC time, and a progress line is logged every
    `progress_every_s` seconds, so a failure can be matched to a rollout step.
    """
    counter: ProbeCounter = ProbeCounter()
    start: float = now()
    # The time the next request is due.
    next_tick: float = start
    # The time the next progress line is due.
    next_progress: float = start + progress_every_s
    try:
        while duration_s is None or now() - start < duration_s:
            # One request, counted.
            outcome, version = fetch(url)
            counter.add(outcome, version)
            # A failure is logged at once, with the time it was noticed.
            if outcome != "ok":
                log(f"{wall_clock()} UTC  FAILED {outcome}")
            # A short running summary every few seconds.
            if now() >= next_progress:
                log(f"{wall_clock()} UTC  progress: {counter.summary()}")
                next_progress += progress_every_s
            # Keep the beat. If a slow request made us late, do not try to catch up.
            next_tick += interval_s
            delay: float = next_tick - now()
            if delay > 0:
                sleep(delay)
            else:
                next_tick = now()
    except KeyboardInterrupt:
        # Ctrl+C is the normal way to stop. Fall through to return the counts.
        pass
    return counter


def main(argv: list[str]) -> int:
    """Command line: run the probe and print the summary. Return 0 when nothing failed."""
    parser = argparse.ArgumentParser(description="Probe the load balancer's /health.")
    parser.add_argument("lb", help="load balancer address, like http://129.80.16.54")
    parser.add_argument("--duration", type=float, default=None,
                        help="seconds to run (default: until Ctrl+C)")
    args = parser.parse_args(argv)
    # Allow a bare IP.
    url: str = args.lb if args.lb.startswith("http") else f"http://{args.lb}"
    # Log lines go to the screen at once (flush), so they show while the probe runs.
    counter: ProbeCounter = run_probe(
        url.rstrip("/"), args.duration, log=lambda m: print(m, flush=True)
    )
    print(counter.summary())
    return 0 if counter.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
