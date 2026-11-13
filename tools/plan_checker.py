"""Check a `terraform show -json` plan and block unsafe changes.

Blocked unless --allow-destroy: deleting or replacing a protected resource
(NAT and internet gateways, subnets, the VCN, security rules),
removing a route rule, and turning on block_traffic on a NAT or Service Gateway.
Always blocked: ingress from 0.0.0.0/0 that includes port 22.
"""
import json
import sys

# Resource types that must not be deleted or replaced without --allow-destroy.
PROTECTED_TYPES: set[str] = {
    "oci_core_nat_gateway",
    "oci_core_subnet",
    "oci_core_vcn",
    "oci_core_internet_gateway",
    # A removed security rule can cut all traffic (drill 3), so it needs the flag too.
    "oci_core_network_security_group_security_rule",
}
# Gateways that carry traffic. Setting block_traffic on them cuts that traffic.
GATEWAY_TYPES: set[str] = {"oci_core_nat_gateway", "oci_core_service_gateway"}
# Route table type, whose rules decide where traffic goes.
ROUTE_TABLE_TYPE: str = "oci_core_route_table"
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


def _route_keys(rules: list[dict] | None) -> set[tuple]:
    """Identify each route rule by where it sends traffic.

    Computed fields (such as cidr_block) can be unset in the plan's after value,
    so only the fields that define the route are compared.
    """
    # A missing list means no rules.
    return {
        (r.get("destination"), r.get("destination_type"), r.get("network_entity_id"))
        for r in (rules or [])
    }


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
        # An update that removes a route rule cuts a path, so it needs the flag.
        if rc.get("type") == ROUTE_TABLE_TYPE and "update" in actions and not allow_destroy:
            # Rules that were there before and are gone after.
            gone: set[tuple] = _route_keys((change.get("before") or {}).get("route_rules")) - _route_keys(
                (change.get("after") or {}).get("route_rules")
            )
            for dest, _dtype, _entity in sorted(gone, key=str):
                violations.append(f"{address}: route rule to {dest} would be removed")
        # An update that turns block_traffic on cuts a gateway, so it needs the flag.
        if rc.get("type") in GATEWAY_TYPES and "update" in actions and not allow_destroy:
            # Blocked now, and not blocked before.
            if (change.get("after") or {}).get("block_traffic") is True and not (
                (change.get("before") or {}).get("block_traffic")
            ):
                violations.append(f"{address}: block_traffic would be turned on")
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
