"""Unit tests for tools/ssh_deploy.py (written first, so they start red). No real SSH runs."""
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# Repo root, two levels above tests/unit.
ROOT: Path = Path(__file__).resolve().parents[2]
# Make tools/ importable without a package.
sys.path.insert(0, str(ROOT / "tools"))

from ssh_deploy import build_script, make_update_server, ssh_command  # noqa: E402


def test_build_script_v2() -> None:
    """A normal release sets the version and has no ExecStart override."""
    # Build the script for v2.
    script: str = build_script("v2")
    # It strict-fails, sets the version, and reloads and restarts the service.
    assert "set -euo pipefail" in script
    assert "Environment=APP_VERSION=v2" in script
    assert "/etc/systemd/system/fleet-app.service.d/version.conf" in script
    assert "daemon-reload" in script
    assert "restart fleet-app" in script
    # A normal release must not touch ExecStart.
    assert "ExecStart" not in script


def test_build_script_crash() -> None:
    """A crash release clears ExecStart and points it at a file that does not exist."""
    # Build the script for v3 with the crash switch on.
    script: str = build_script("v3", simulate_crash=True)
    # The version is still set.
    assert "Environment=APP_VERSION=v3" in script
    # An empty ExecStart= resets the old command, then the bad one replaces it.
    assert "ExecStart=\n" in script
    assert "ExecStart=/usr/bin/node /opt/fleet-app/missing.js" in script


def test_build_script_waits_for_new_version() -> None:
    """The script checks the app itself reports the new version, and fails if it does not."""
    # Build the script for v2.
    script: str = build_script("v2")
    # It polls the local health endpoint for the new version.
    assert "127.0.0.1:8000/health" in script
    assert '"version":"v2"' in script
    # And it exits non-zero when the version never shows up.
    assert "exit 1" in script


@pytest.mark.parametrize("bad", ["v2; rm -rf /", "2", "v", "V2", "v2\n", "v2 ", "$(id)", ""])
def test_build_script_rejects_bad_version(bad: str) -> None:
    """Anything that is not v<digits> is refused, so nothing can reach the shell."""
    # Each bad value must raise before any script exists.
    with pytest.raises(ValueError):
        build_script(bad)


def test_ssh_command() -> None:
    """The ssh command jumps through the bastion and runs bash from stdin as root."""
    # Build the command for one bastion and one server.
    cmd: list[str] = ssh_command("1.2.3.4", "10.0.2.204")
    # Jump host, target, and the remote command at the end.
    assert "-J" in cmd and cmd[cmd.index("-J") + 1] == "opc@1.2.3.4"
    assert "opc@10.0.2.204" in cmd
    assert cmd[-1] == "sudo bash -s"
    # Safe, non-interactive options.
    assert "BatchMode=yes" in cmd
    assert "StrictHostKeyChecking=accept-new" in cmd
    assert "ConnectTimeout=10" in cmd


class FakeRun:
    """Stand-in for subprocess.run that records calls and returns a set result."""

    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        """Choose the exit code and stderr the fake ssh will give back."""
        # What each call returns.
        self.returncode: int = returncode
        self.stderr: str = stderr
        # Every call: (command, keyword arguments).
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        """Record the call and return a finished process."""
        # Remember what was asked.
        self.calls.append((cmd, kwargs))
        # Return the fixed result.
        return subprocess.CompletedProcess(cmd, self.returncode, "", self.stderr)


def test_update_server_sends_script_to_the_right_ip() -> None:
    """update_server strips :8000, sends the script on stdin, and sets a 60 s timeout."""
    # A fake run that succeeds.
    fake: FakeRun = FakeRun()
    update = make_update_server("1.2.3.4", run=fake)
    # Update one backend.
    update("10.0.2.204:8000", "v2")
    # One ssh call, to the bare IP.
    cmd, kwargs = fake.calls[0]
    assert "opc@10.0.2.204" in cmd
    assert "opc@10.0.2.204:8000" not in cmd
    # The script goes on stdin, with a timeout.
    assert "Environment=APP_VERSION=v2" in kwargs["input"]
    assert kwargs["timeout"] == 60


def test_update_server_crash_versions() -> None:
    """A version listed in crash_versions gets the crash script; others do not."""
    # v3 is a crash version.
    fake: FakeRun = FakeRun()
    update = make_update_server("1.2.3.4", crash_versions=frozenset({"v3"}), run=fake)
    # v3 crashes, v2 does not.
    update("10.0.2.204:8000", "v3")
    update("10.0.2.204:8000", "v2")
    assert "missing.js" in fake.calls[0][1]["input"]
    assert "missing.js" not in fake.calls[1][1]["input"]


def test_update_server_raises_with_stderr() -> None:
    """A non-zero exit raises RuntimeError that includes the ssh error text."""
    # A fake run that fails.
    update = make_update_server("1.2.3.4", run=FakeRun(returncode=255, stderr="Permission denied"))
    # The error carries stderr.
    with pytest.raises(RuntimeError, match="Permission denied"):
        update("10.0.2.204:8000", "v2")


def test_build_script_clears_a_failed_state_before_restart() -> None:
    """A crash-looping unit hits systemd's start limit; reset-failed lets the rollback restart it."""
    # Build the script for a normal rollback to v2.
    script: str = build_script("v2")
    # reset-failed comes before the restart, and cannot stop the script if there is nothing to reset.
    assert "systemctl reset-failed fleet-app || true" in script
    assert script.index("reset-failed") < script.index("restart fleet-app")


def test_error_message_is_short_and_readable() -> None:
    """The error drops ssh warnings and repeated lines, and keeps the real cause."""
    # stderr as seen live: warnings twice, the same curl error many times, then the cause.
    stderr: str = (
        "** WARNING: connection is not using a post-quantum key exchange algorithm.\n"
        "** This session may be vulnerable to \"store now, decrypt later\" attacks.\n"
        "** The server may need to be upgraded. See https://openssh.com/pq.html\n"
        + "curl: (7) Failed to connect to 127.0.0.1 port 8000: Connection refused\n" * 30
        + "app did not report v3 within 30 s\n"
    )
    # A fake run that fails with that stderr.
    update = make_update_server("1.2.3.4", run=FakeRun(returncode=1, stderr=stderr))
    # Catch the error and read its text.
    with pytest.raises(RuntimeError) as info:
        update("10.0.2.204:8000", "v3")
    message: str = str(info.value)
    # The cause is there, once; the warnings are gone; the curl line appears once.
    assert "app did not report v3 within 30 s" in message
    assert "post-quantum" not in message
    assert message.count("Connection refused") == 1
