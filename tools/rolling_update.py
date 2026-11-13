"""Rolling update: drain, update, wait for health, undrain, one server at a time."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from lb_client import LoadBalancerClient
from ssh_deploy import make_update_server

# Repo root, one level above tools/.
ROOT: Path = Path(__file__).resolve().parents[1]
# Where the dev Terraform outputs come from.
DEFAULT_TF_DIR: Path = ROOT / "terraform" / "envs" / "dev"


class RollingUpdateError(Exception):
    """Raised when a server does not become healthy and the rollout stops."""


class RollbackError(RollingUpdateError):
    """Raised when the rollback also fails. The server stays drained and needs a person."""


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
    log: Callable[[str], None] = lambda message: None,
) -> None:
    """Update each backend in order. On failure, roll that one back and stop."""
    for backend in backends:
        # Stop new traffic to this server.
        log(f"{backend}: drain")
        lb.set_drain(backend, True)
        # Let in-flight requests finish (skipped when zero, e.g. in tests).
        if drain_wait_s > 0:
            sleep(drain_wait_s)
        # Why this server failed, if it did. Kept so the operator can see it.
        reason: str = ""
        try:
            # Put the new version on the server.
            log(f"{backend}: update to {new_version}")
            update_server(backend, new_version)
            # Wait for the load balancer to see it healthy.
            healthy: bool = _wait_healthy(backend, lb, max_attempts, base_delay_s, sleep)
            if not healthy:
                reason = "the load balancer never reported it healthy"
        except Exception as e:
            # An update error counts as a failed rollout for this server.
            healthy = False
            reason = str(e)
        if not healthy:
            # Put the old version back, return the server to service, and stop.
            log(f"{backend}: FAILED ({reason}); rolling back to {old_version}")
            try:
                update_server(backend, old_version)
            except Exception as rollback_error:
                # Do not undrain: this server may be broken and must not get traffic.
                log(f"{backend}: ROLLBACK FAILED ({rollback_error}); left drained")
                raise RollbackError(
                    f"{backend} is still drained and may be broken. First error: {reason}. "
                    f"Rollback error: {rollback_error}. Fix it by hand, then undrain it."
                ) from rollback_error
            log(f"{backend}: undrain")
            lb.set_drain(backend, False)
            raise RollingUpdateError(
                f"{backend} failed ({reason}); rolled back to {old_version}"
            )
        # Healthy: send traffic to it again, then move on.
        log(f"{backend}: healthy on {new_version}")
        log(f"{backend}: undrain")
        lb.set_drain(backend, False)


def backends_from_outputs(outputs: dict) -> list[str]:
    """Turn `terraform output -json` into backend names like "10.0.2.204:8000"."""
    # Each fleet server is a backend on port 8000, in Terraform's order.
    return [f"{ip}:8000" for ip in outputs["fleet_private_ips"]["value"]]


def main(argv: list[str]) -> int:
    """Command line: roll the real fleet to a new version.

    Return 0 on success, 1 if a server failed and was rolled back, and 2 if a rollback
    also failed (a server is left drained and needs a person).
    """
    parser = argparse.ArgumentParser(description="Roll the fleet to a new app version.")
    parser.add_argument("--version", required=True, help="new version, like v2")
    parser.add_argument("--old-version", default="v1", help="version to roll back to")
    parser.add_argument("--crash-version", default=None,
                        help="make this release crash on purpose (for the broken-release drill)")
    parser.add_argument("--tf-dir", default=str(DEFAULT_TF_DIR), help="Terraform env folder")
    parser.add_argument("--max-attempts", type=int, default=8, help="health polls per server")
    parser.add_argument("--base-delay", type=float, default=2.0, help="first poll wait, doubles each time")
    parser.add_argument("--drain-wait", type=float, default=30.0, help="seconds to let requests finish")
    args = parser.parse_args(argv)

    # Read lb_id, bastion_public_ip and fleet_private_ips from Terraform.
    raw: bytes = subprocess.check_output(["terraform", f"-chdir={args.tf_dir}", "output", "-json"])
    outputs: dict = json.loads(raw)
    # Real load balancer client and real SSH update (imported here so tests stay light).
    from lb_client import OciLoadBalancerClient

    lb: OciLoadBalancerClient = OciLoadBalancerClient(outputs["lb_id"]["value"], "fleet")
    crash: frozenset[str] = frozenset({args.crash_version}) if args.crash_version else frozenset()
    update_server = make_update_server(outputs["bastion_public_ip"]["value"], crash_versions=crash)

    def log(message: str) -> None:
        """Print one progress line with a UTC time."""
        print(f"{time.strftime('%H:%M:%S', time.gmtime())} UTC  {message}", flush=True)

    try:
        rolling_update(
            backends_from_outputs(outputs), lb, update_server, args.version, args.old_version,
            max_attempts=args.max_attempts, base_delay_s=args.base_delay,
            drain_wait_s=args.drain_wait, log=log,
        )
    except RollbackError as e:
        # A server is left drained and possibly broken: a different exit code, so scripts can tell.
        log(f"STOPPED, NEEDS A PERSON: {e}")
        return 2
    except RollingUpdateError as e:
        log(f"STOPPED: {e}")
        return 1
    log(f"DONE: all servers are on {args.version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
