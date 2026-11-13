# OCI Gateway Fleet

A small private network on Oracle Cloud (OCI), built with Terraform. A tiny app runs on a fleet of servers inside it. The point of the project is the network and the operations around it: changing it safely, breaking it on purpose, and fixing it with runbooks.

## What it builds

```
Internet
   |
   v
Load balancer (public subnet 10.0.1.0/24, port 80)
   |  port 8000
   v
Fleet servers x2 (private subnet 10.0.2.0/24, no public IP)
   |-- NAT Gateway ------> internet (updates, npm install)
   '-- Service Gateway --> Object Storage (notes bucket)

Bastion (public subnet, SSH only from one admin IP) --> fleet servers (port 22)
```

- VCN `10.0.0.0/16` with a public and a private subnet.
- Internet, NAT and Service Gateways. The private route table sends Oracle services to the Service Gateway and everything else to the NAT Gateway.
- Role-based NSGs (load balancer, bastion, fleet). Rules point at other NSGs, and only the load balancer is open to the internet.
- A flexible load balancer that health-checks `/health` on port 8000. A server is removed after 3 failed checks, 10 seconds apart.
- An Object Storage bucket for notes. A policy lets fleet servers write only through the Service Gateway, using a network source (decision 0011).
- An alarm, `gateway-lab-unhealthy-backend`, that sends email when the load balancer reports an unhealthy backend. The email links to a runbook.

## The app

A small Express app in TypeScript (`app/src`). It is stateless on purpose.

| Endpoint | What it does | Path it proves |
|---|---|---|
| `GET /health` | `{"status":"ok","version":"vN"}` | Load balancer health check |
| `GET /whoami` | Hostname of the server that answered | Load balancing |
| `GET /egress` | Calls a public site. Always HTTP 200. Body is `{"egress":"ok"}` or `{"egress":"fail"}` | NAT Gateway |
| `POST /notes` | Saves a note to Object Storage. 201 on success, 502 on failure | Service Gateway |

cloud-init ships the app: it installs Node 20, runs `npm install`, and starts the `fleet-app` systemd service.

## Repo layout

```
terraform/
  modules/network/   VCN, subnets, gateways, route tables, NSGs (+ offline tests)
  modules/fleet/     bastion, fleet servers, load balancer, storage, alarm (+ offline tests)
  envs/dev/          the one environment: providers, variables, outputs
app/                 the Express app, Jest tests, Dockerfile, docker-compose + nginx
tools/               Python tools (see below)
tests/unit/          offline tests for the tools
tests/integration/   tests against the live cloud
tests/fixtures/      saved plan files used by the plan checker tests
runbooks/            what to do when something breaks
.github/workflows/   CI
```

## Tools

| Tool | Purpose |
|---|---|
| `tools/plan_checker.py` | Reads `terraform show -json` output and blocks risky changes: deleting or replacing gateways, subnets, the VCN or security rules; removing a route rule; turning on `block_traffic`; opening port 22 to `0.0.0.0/0` (always blocked). `--allow-destroy` lifts all but the last. Exit code 0 is safe, 1 is blocked. |
| `tools/rolling_update.py` | Moves the fleet to a new app version one server at a time: drain, update over SSH, wait for health, undrain. |
| `tools/load_probe.py` | Calls `/health` every 100 ms and counts failures. Used to show a rolling update drops no requests. |
| `tools/lb_client.py`, `tools/ssh_deploy.py` | Helpers for the load balancer API and for SSH through the bastion. |

Known gap: the plan checker does not block a replaced server. Read the plan summary before you apply.

## Getting started

You need: Terraform 1.7 or newer, the OCI CLI (`oci setup config` done), Python 3.11, Node 20, and an SSH key pair at `~/.ssh/gateway_lab`.

1. Make `terraform/envs/dev/dev.tfvars`. It is git-ignored. Set these:

   ```
   compartment_id       = "<OCID of the gateway-lab compartment>"
   tenancy_ocid         = "<tenancy OCID>"
   bastion_allowed_cidr = "<your public IP>/32"
   alarm_email          = "<email for alerts>"
   fleet_size           = 2
   ```

2. Build the app bundle that cloud-init ships:

   ```
   cd app && npm ci && npm run bundle && npm run deploy-pkg && cd ..
   ```

3. Python environment:

   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

4. Plan, check, apply:

   ```
   terraform -chdir=terraform/envs/dev init
   terraform -chdir=terraform/envs/dev plan -var-file=dev.tfvars -out=plan.bin
   terraform -chdir=terraform/envs/dev show -json plan.bin > terraform/envs/dev/plan.json
   python3 tools/plan_checker.py terraform/envs/dev/plan.json
   terraform -chdir=terraform/envs/dev apply plan.bin
   ```

5. Confirm the email subscription. OCI sends a confirmation email, and the alarm stays silent until you click the link.

6. Try it: `curl http://$(terraform -chdir=terraform/envs/dev output -raw lb_public_ip)/health`

Servers cost money. Run `terraform -chdir=terraform/envs/dev destroy -var-file=dev.tfvars` when you are done for the day.

## Testing

| What | Command | Needs the cloud |
|---|---|---|
| Terraform modules (mock provider) | `cd terraform/modules/network && terraform init -backend=false && terraform test` (same for `fleet`) | No |
| App | `cd app && npm test` | No |
| Python tools | `pytest tests/unit` | No |
| Live checks (6 tests) | `source .venv/bin/activate && pytest tests/integration` | Yes |

The integration tests check health, that load balancing reaches every server, egress, saving a note, that the fleet is unreachable from outside, and that no fleet server has a public IP. `test_notes_saved` writes one small note.

To run the app locally: `cd app && docker compose up`. It starts 2 copies behind nginx.

## CI

CI runs on every pull request and on pushes to main. It needs no cloud credentials. Jobs: Terraform fmt, validate and mock tests for each module; app tests and build; Python unit tests. The integration tests never run in CI.

## Operations

Runbooks are one page each, with the same sections: Symptoms, Impact, Checks, Fix, Verify, Rollback.

- [Backend unhealthy](runbooks/backend-unhealthy.md): the alarm fired.
- [Lost egress](runbooks/lost-egress.md): `/egress` reports `fail`, or new servers hang in cloud-init.
- [Roll back a network change](runbooks/rollback-network-change.md): tests fail or the alarm fires right after an apply.

Rule for all fixes: change Terraform, never the console. A console edit creates drift, and the next apply undoes it.

## Fault drills

Planned breaks, with times from an integration-test loop that ran about every 12 seconds:

| Drill | What failed | Time to recover after the undo apply |
|---|---|---|
| NAT Gateway blocked | Only `test_egress_ok` | 11 s |
| Oracle services route removed | Nothing at first, because NAT carried the traffic. After decision 0011, `/notes` fails with 502 | Not recorded |
| Fleet NSG rule for port 8000 removed | The whole app | 46 s |
| One server stopped | `test_whoami_covers_all_servers` only; the other server kept serving | 61 s after the server was running |

Drills 1 to 3 showed gaps in the plan checker, and some are now closed. The engineering log (decisions and incident notes) is kept locally in `docs/`, which is git-ignored.

## Safety notes

- Never commit `*.tfvars`, API keys, private SSH keys or state files. `.gitignore` covers them.
- SSH reaches fleet servers only through the bastion, and the bastion accepts SSH only from `bastion_allowed_cidr`.
- Fleet servers have no public IP. An integration test checks this.
