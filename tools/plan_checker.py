"""Check a `terraform show -json` plan and block unsafe changes."""
import json
import sys

# Resource types that must not be deleted or replaced without --allow-destroy.
PROTECTED_TYPES: set[str] = {
    "oci_core_nat_gateway",
    "oci_core_subnet",
    "oci_core_vcn",
    "oci_core_internet_gateway",
}
# NSG rule type that controls network access.
RULE_TYPE: str = "oci_core_network_security_group_security_rule"
# Source that means "the whole internet".
WORLD: str = "0.0.0.0/0"


def _open_ports(after: dict) -> tuple[int, int] | None:
    """Return the (min, max) port range a world-open ingress rule exposes, else None."""
    # Only ingress rules from the whole internet matter.
    if after.get("direction") != "INGRESS" or after.get("source") != WORLD:
        return None
    # Protocol "all" opens every port.
    if after.get("protocol") == "all":
        return (1, 65535)
    # Only TCP (protocol "6") is checked beyond this point.
    if after.get("protocol") != "6":
        return None
    # Pull the destination port range out of tcp_options.
    tcp: list[dict] = after.get("tcp_options") or []
    ranges: list[dict] = (tcp[0].get("destination_port_range") or []) if tcp else []
    # No port range on a TCP rule means all ports.
    if not ranges:
        return (1, 65535)
    # Return the declared range.
    return (ranges[0]["min"], ranges[0]["max"])


def check_plan(plan: dict, allow_destroy: bool = False) -> list[str]:
    """Return a list of violations. Empty list means safe."""
    # Collect one message per problem.
    violations: list[str] = []
    # Walk every planned resource change.
    for rc in plan.get("resource_changes", []):
        # Shorthand for the fields we use.
        address: str = rc.get("address", "?")
        change: dict = rc.get("change", {})
        actions: list[str] = change.get("actions", [])
        # A delete (or replace) of a protected resource needs the flag.
        if rc.get("type") in PROTECTED_TYPES and "delete" in actions and not allow_destroy:
            violations.append(f"{address}: would be destroyed ({'+'.join(actions)})")
        # Open ports are always blocked, flag or not.
        if rc.get("type") == RULE_TYPE and "create" in actions:
            ports: tuple[int, int] | None = _open_ports(change.get("after") or {})
            # SSH, or the whole range, exposed to the internet.
            if ports and ports[0] <= 22 <= ports[1]:
                violations.append(
                    f"{address}: opens ports {ports[0]}-{ports[1]} to {WORLD}"
                )
    # Hand back everything found.
    return violations


def main(argv: list[str]) -> int:
    """Command line entry point. Return the exit code: 0 safe, 1 blocked."""
    # Need a plan file path.
    if len(argv) < 2:
        print("usage: plan_checker.py plan.json [--allow-destroy]", file=sys.stderr)
        return 2
    # Load the plan JSON.
    with open(argv[1]) as f:
        plan: dict = json.load(f)
    # Run the check.
    violations: list[str] = check_plan(plan, allow_destroy="--allow-destroy" in argv)
    # Print each violation.
    for v in violations:
        print(f"BLOCKED: {v}")
    # Exit 1 if anything was found.
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
