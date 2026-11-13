"""Real update_server: switch a fleet server to a new app version over SSH."""
import argparse
import re
import subprocess
import sys
from typing import Any, Callable

# A version must be "v" and digits only, so nothing can slip into the shell.
VERSION_RE: re.Pattern[str] = re.compile(r"v\d+")
# Drop-in file that overrides the version in the systemd unit from cloud-init.
DROPIN: str = "/etc/systemd/system/fleet-app.service.d/version.conf"


def build_script(version: str, simulate_crash: bool = False) -> str:
    """Return the shell script that moves one server to `version`."""
    # fullmatch (not match) so a trailing newline is refused too.
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"version must look like v2, got {version!r}")
    # Lines of the systemd drop-in file.
    lines: list[str] = ["[Service]", f"Environment=APP_VERSION={version}"]
    if simulate_crash:
        # An empty ExecStart= resets the old command, then the bad one replaces it.
        lines += ["ExecStart=", "ExecStart=/usr/bin/node /opt/fleet-app/missing.js"]
    # Join the drop-in lines for the heredoc below.
    body: str = "\n".join(lines)
    # The script stops on the first error, writes the drop-in, restarts the app,
    # then waits up to 30 s for the app itself to report the new version.
    return f"""set -euo pipefail
mkdir -p /etc/systemd/system/fleet-app.service.d
cat > {DROPIN} <<'EOF'
{body}
EOF
systemctl daemon-reload
systemctl reset-failed fleet-app || true
systemctl restart fleet-app
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health | grep -q '"version":"{version}"'; then
    exit 0
  fi
  sleep 1
done
echo "app did not report {version} within 30 s" >&2
exit 1
"""


def summarize_stderr(stderr: str, keep: int = 3) -> str:
    """Shorten ssh stderr: drop ssh "** ..." warnings and repeated lines, keep the last few."""
    unique: list[str] = []
    for line in stderr.splitlines():
        line = line.strip()
        # ssh prints warnings that start with "**". They hide the real cause.
        if not line or line.startswith("**"):
            continue
        # The same line repeated (like 30 curl retries) is shown once.
        if line not in unique:
            unique.append(line)
    # The last lines hold the cause.
    return " | ".join(unique[-keep:])


def ssh_command(bastion_ip: str, server_ip: str) -> list[str]:
    """Return the ssh command that runs a script on a private server via the bastion."""
    return [
        "ssh",
        "-o", "BatchMode=yes",  # never ask for a password or passphrase
        "-o", "StrictHostKeyChecking=accept-new",  # trust a new host once, refuse a changed key
        "-o", "ConnectTimeout=10",
        "-J", f"opc@{bastion_ip}",  # jump through the bastion
        f"opc@{server_ip}",
        "sudo bash -s",  # run the script from stdin as root
    ]


def make_update_server(
    bastion_ip: str,
    crash_versions: frozenset[str] = frozenset(),
    run: Callable[..., Any] = subprocess.run,
) -> Callable[[str, str], None]:
    """Build update_server(backend, version) for rolling_update.

    `run` is subprocess.run in real use. Tests pass a fake.
    """

    def update_server(backend: str, version: str) -> None:
        """Move one backend ("<ip>:8000") to `version`. Raise RuntimeError on failure."""
        # The load balancer name is "<ip>:8000"; ssh needs only the IP.
        server_ip: str = backend.split(":")[0]
        # Versions listed in crash_versions get the broken release.
        script: str = build_script(version, simulate_crash=version in crash_versions)
        try:
            # Send the script on stdin.
            result = run(
                ssh_command(bastion_ip, server_ip),
                input=script, text=True, capture_output=True, timeout=60,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"ssh to {server_ip} timed out after 60 s") from e
        # Any non-zero exit means the server did not reach the new version.
        if result.returncode != 0:
            raise RuntimeError(
                f"update of {server_ip} to {version} failed (exit {result.returncode}): "
                f"{summarize_stderr(result.stderr)}"
            )

    return update_server


def main(argv: list[str]) -> int:
    """Command line: update one backend by hand. Return 0 on success, 1 on failure."""
    # Read the options.
    parser = argparse.ArgumentParser(description="Move one fleet server to an app version.")
    parser.add_argument("--bastion", required=True, help="bastion public IP")
    parser.add_argument("--backend", required=True, help='backend name, like "10.0.2.204:8000"')
    parser.add_argument("--version", required=True, help="version, like v2")
    parser.add_argument("--crash", action="store_true", help="make this release crash on purpose")
    args = parser.parse_args(argv)
    # Build the update function and run it once.
    update = make_update_server(
        args.bastion, crash_versions=frozenset({args.version}) if args.crash else frozenset()
    )
    try:
        update(args.backend, args.version)
    except (RuntimeError, ValueError) as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    print(f"{args.backend} is on {args.version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
