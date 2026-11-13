"""Rolling update: drain, update, wait for health, undrain, one server at a time."""
import time
from typing import Callable

from lb_client import LoadBalancerClient


class RollingUpdateError(Exception):
    """Raised when a server does not become healthy and the rollout stops."""


def _wait_healthy(
    backend: str,
    lb: LoadBalancerClient,
    max_attempts: int,
    base_delay_s: float,
    sleep: Callable[[float], None],
) -> bool:
    """Poll health with growing waits. Return True once OK, False if attempts run out."""
    for attempt in range(max_attempts):
        # Healthy: done.
        if lb.backend_health(backend) == "OK":
            return True
        # Not last attempt: wait 1x, 2x, 4x ... the base delay before retrying.
        if attempt < max_attempts - 1:
            sleep(base_delay_s * 2 ** attempt)
    # Never became healthy.
    return False


def rolling_update(
    backends: list[str],
    lb: LoadBalancerClient,
    update_server: Callable[[str, str], None],
    new_version: str,
    old_version: str,
    max_attempts: int = 10,
    base_delay_s: float = 5.0,
    drain_wait_s: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Update each backend in order. On failure, roll that one back and stop."""
    for backend in backends:
        # Stop new traffic to this server.
        lb.set_drain(backend, True)
        # Let in-flight requests finish (skipped when zero, e.g. in tests).
        if drain_wait_s > 0:
            sleep(drain_wait_s)
        try:
            # Put the new version on the server.
            update_server(backend, new_version)
            # Wait for the load balancer to see it healthy.
            healthy: bool = _wait_healthy(backend, lb, max_attempts, base_delay_s, sleep)
        except Exception:
            # An update error counts as a failed rollout for this server.
            healthy = False
        if not healthy:
            # Put the old version back, return the server to service, and stop.
            update_server(backend, old_version)
            lb.set_drain(backend, False)
            raise RollingUpdateError(f"{backend} did not become healthy; rolled back to {old_version}")
        # Healthy: send traffic to it again, then move on.
        lb.set_drain(backend, False)
