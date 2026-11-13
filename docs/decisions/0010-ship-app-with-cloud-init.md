# 0010: Ship the app with cloud-init
Date: 2026-11-12 | Day: 2 | Status: Accepted

## Context
Instance `user_data` is limited to about 32 KB. I needed a simple way to put the app on a server.

## Decision
- `esbuild` bundles only my code into `app/deploy/server.js` (`--packages=external`). A small `deploy/package.json` lists the dependencies.
- The cloud-init template embeds both files as base64, plus a systemd unit.
- On first boot, cloud-init installs Node.js 20 with `dnf`, runs `npm install --omit=dev` through the NAT Gateway, and starts the app as a systemd service under the system user `fleetapp`.
- The unit sets `APP_VERSION` and `NOTES_BUCKET`.
- cloud-init also opens TCP 8000 in `firewalld`. The server has its own firewall, so the NSG alone is not enough.
- A 2 GB swap file is created in `bootcmd`.

## Why
The bundle is small, so it fits in `user_data` with room left. Dependencies come from the registry, so they do not count against the limit. No image build or registry is needed.

## Trade-offs
Any change to `user_data` or to `server.js` replaces the servers. On 2026-11-12 this replaced both fleet servers at the same time. First boot takes a few minutes because the install runs at boot. A server needs the NAT Gateway and the npm registry to start.

See also: [the SSH hang on a 1 GB server](../incidents/2026-11-12-ssh-hang-1gb-server.md).
