"""A fake load balancer that tests control."""


class FakeLoadBalancer:
    """Plain Python stand-in for LoadBalancerClient."""

    def __init__(self, health: dict[str, list[str]]) -> None:
        """health: per backend, consumed in order, e.g. {"b2": ["CRITICAL", "CRITICAL"]}."""
        # Health answers per backend. The last one repeats forever.
        self.health: dict[str, list[str]] = health
        # Every call, in order, for asserts.
        self.calls: list[tuple] = []
        # Backends that are currently drained.
        self.drained: set[str] = set()

    def set_drain(self, backend: str, drain: bool) -> None:
        """Record the call and update the drained set."""
        # Remember the call.
        self.calls.append(("set_drain", backend, drain))
        # Add or remove the backend.
        (self.drained.add if drain else self.drained.discard)(backend)

    def backend_health(self, backend: str) -> str:
        """Record the call and return the next health answer."""
        # Remember the call.
        self.calls.append(("health", backend))
        # Backends not listed are always OK.
        queue: list[str] = self.health.get(backend, ["OK"])
        # Use up answers in order, but keep the last one.
        return queue.pop(0) if len(queue) > 1 else queue[0]
