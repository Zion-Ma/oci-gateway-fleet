"""Load balancer client: a small interface, plus the real OCI version."""
import time
from typing import Protocol


class LoadBalancerClient(Protocol):
    """Any class with these two methods counts as a load balancer client."""

    def set_drain(self, backend: str, drain: bool) -> None:
        """Turn draining on or off for one backend ("<ip>:8000")."""
        ...

    def backend_health(self, backend: str) -> str:
        """Return "OK", "WARNING", "CRITICAL", or "UNKNOWN"."""
        ...


class OciLoadBalancerClient:
    """Real client: calls the OCI load balancer API."""

    def __init__(self, lb_id: str, backend_set: str = "fleet") -> None:
        """Build the OCI client from ~/.oci/config."""
        # Import here so code that only needs the interface does not need the SDK.
        import oci

        # Keep the module for later calls.
        self._oci = oci
        # Read credentials from ~/.oci/config.
        config: dict = oci.config.from_file()
        # The SDK client that talks to OCI.
        self._client = oci.load_balancer.LoadBalancerClient(config)
        # Which load balancer and backend set to work on.
        self.lb_id: str = lb_id
        self.backend_set: str = backend_set

    def set_drain(self, backend: str, drain: bool, timeout_s: int = 300) -> None:
        """Set drain on a backend, keeping its other settings, and wait for OCI."""
        # Read the current settings so we do not change them.
        current = self._client.get_backend(
            self.lb_id, self.backend_set, backend
        ).data
        # Same weight, backup and offline. Only drain changes.
        details = self._oci.load_balancer.models.UpdateBackendDetails(
            weight=current.weight,
            backup=current.backup,
            offline=current.offline,
            drain=drain,
        )
        # Send the update.
        response = self._client.update_backend(
            details, self.lb_id, self.backend_set, backend
        )
        # OCI applies the change in the background. Wait for the work request.
        self._wait_for_work_request(response.headers["opc-work-request-id"], timeout_s)

    def backend_health(self, backend: str) -> str:
        """Return the health status of one backend."""
        # Ask OCI for the backend health.
        health = self._client.get_backend_health(
            self.lb_id, self.backend_set, backend
        ).data
        # The status is a string such as "OK" or "CRITICAL".
        return str(health.status)

    def _wait_for_work_request(self, work_request_id: str, timeout_s: int) -> None:
        """Poll a work request until it succeeds. Raise on failure or timeout."""
        # Stop waiting at this time.
        deadline: float = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            # Read the current state.
            wr = self._client.get_work_request(work_request_id).data
            # Done and good.
            if wr.lifecycle_state == "SUCCEEDED":
                return
            # Done and bad.
            if wr.lifecycle_state == "FAILED":
                raise RuntimeError(f"work request {work_request_id} failed: {wr.error_details}")
            # Not done yet. Wait a little.
            time.sleep(2)
        # Ran out of time.
        raise TimeoutError(f"work request {work_request_id} not done after {timeout_s}s")
