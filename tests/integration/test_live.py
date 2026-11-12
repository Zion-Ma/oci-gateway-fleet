import socket
from typing import Any

import oci
import pytest
import requests


def test_health_ok(lb_url: str) -> None:
    """The load balancer's /health answers 200 with status ok."""
    # Call the health endpoint through the load balancer.
    res: requests.Response = requests.get(f"{lb_url}/health", timeout=5)
    # A healthy fleet returns HTTP 200 and {"status": "ok", ...}.
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_whoami_covers_all_servers(lb_url: str, tf: dict[str, Any]) -> None:
    """Many requests reach every fleet server, so load balancing works."""
    # How many servers Terraform says exist.
    expected: int = len(tf["fleet_private_ips"])
    # Collect the distinct hostnames seen across 20 requests.
    seen: set[str] = {
        requests.get(f"{lb_url}/whoami", timeout=5).json()["hostname"]
        for _ in range(20)
    }
    # Every server must have answered at least once.
    assert len(seen) == expected, f"saw {seen}, expected {expected} servers"


def test_egress_ok(lb_url: str) -> None:
    """A fleet server can reach the internet (NAT Gateway path)."""
    # Longer timeout: the server makes its own outbound call first.
    res: requests.Response = requests.get(f"{lb_url}/egress", timeout=15)
    # The app always answers 200; the body says ok or fail.
    assert res.json()["egress"] == "ok"


def test_notes_saved(lb_url: str) -> None:
    """A fleet server can write to Object Storage (Service Gateway path)."""
    # Post a small note through the load balancer.
    res: requests.Response = requests.post(
        f"{lb_url}/notes", json={"text": "integration test"}, timeout=20
    )
    # Success means HTTP 201 (Created) and the saved file name in the body.
    assert res.status_code == 201
    assert "saved" in res.json()


def test_fleet_unreachable_from_laptop(tf: dict[str, Any]) -> None:
    """Fleet servers sit in a private subnet, so the laptop cannot open a connection."""
    # Try every fleet server's private IP on the app port.
    for ip in tf["fleet_private_ips"]:
        # Connecting must fail (refused, timed out or no route); success is a leak.
        with pytest.raises(OSError):
            socket.create_connection((ip, 8000), timeout=3).close()


def test_fleet_has_no_public_ip(tf: dict[str, Any]) -> None:
    """No fleet server Terraform built has a public IP on any network card."""
    # Build OCI clients from ~/.oci/config.
    cfg: dict[str, Any] = oci.config.from_file()
    compute: oci.core.ComputeClient = oci.core.ComputeClient(cfg)
    network: oci.core.VirtualNetworkClient = oci.core.VirtualNetworkClient(cfg)

    # Exact instance OCIDs from Terraform, so no name prefix or stale server is involved.
    ids: list[str] = tf["fleet_instance_ids"]
    # An empty list would make this test pass for the wrong reason.
    assert ids, "no fleet instances in Terraform outputs"

    for inst_id in ids:
        # Look up the instance to get its name and compartment.
        inst: Any = compute.get_instance(inst_id).data
        # List the network cards (VNICs) attached to this instance.
        attachments: list[Any] = compute.list_vnic_attachments(
            inst.compartment_id, instance_id=inst_id
        ).data
        for attachment in attachments:
            # Skip cards that are detaching or detached.
            if attachment.lifecycle_state != "ATTACHED":
                continue
            # A private-subnet server must have no public IP.
            public_ip: str | None = network.get_vnic(attachment.vnic_id).data.public_ip
            assert public_ip is None, f"{inst.display_name} has public IP {public_ip}"
