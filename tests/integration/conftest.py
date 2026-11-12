import json
import subprocess
from typing import Any

import pytest


@pytest.fixture(scope="session")
def tf() -> dict[str, Any]:
    """Read every Terraform output from the dev environment into a dict."""
    # Ask Terraform for all outputs as JSON (run from the repo root).
    raw: bytes = subprocess.check_output(
        ["terraform", "-chdir=terraform/envs/dev", "output", "-json"]
    )
    # Terraform wraps each output as {"value": ..., "type": ...}; keep only the value.
    return {name: out["value"] for name, out in json.loads(raw).items()}


@pytest.fixture(scope="session")
def lb_url(tf: dict[str, Any]) -> str:
    """Base URL of the load balancer, e.g. http://203.0.113.5."""
    return f"http://{tf['lb_public_ip']}"
