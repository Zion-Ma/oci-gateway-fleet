# OCI Gateway Fleet Project Plan

Nov 7, 2026 · @Chen-En

## Goal

In 4 days, build a small private network on Oracle Cloud (OCI) with Terraform, run a tiny app on a fleet of servers inside it, and practice changing it safely, breaking it on purpose, and fixing it. The project fills two gaps for the Oracle Virtual Networking Gateways role: no hands-on Terraform, and no hands-on virtual networking.

What you should be able to say honestly at the end:

1. I built an OCI network with public and private subnets, an Internet Gateway, a NAT Gateway, and a Service Gateway, all in Terraform.
2. I wrote Python tools that block risky network changes and update the fleet one server at a time with zero failed requests.
3. I broke the network on purpose, detected it with tests and an alarm, and fixed it with a runbook I wrote.

Rules for the whole project:

- Keep the app tiny. The network and the operations are the point.
- Run `terraform destroy` at the end of every day.
- Write down every number you measure, the moment you measure it. You will need them for the resume.

## Architecture

Users reach only the load balancer. The fleet servers sit in a private subnet with no public IP. They go out to the internet through the NAT Gateway and reach Object Storage through the Service Gateway.

&#91;embedded content: project network · 2 subnets, 3 gateways\]

Arrows point the way a connection can start. Only the Internet Gateway allows connections in both directions.

### Address plan

| Part | CIDR | Usable range | Who lives there |
| --- | --- | --- | --- |
| VCN | `10.0.0.0/16` | `10.0.0.0` to `10.0.255.255` | Everything |
| Public subnet (regional) | `10.0.1.0/24` | `10.0.1.2` to `10.0.1.254` | Load balancer, bastion |
| Private subnet (regional) | `10.0.2.0/24` | `10.0.2.2` to `10.0.2.254` | 2 to 3 fleet servers |
| Unused | `10.0.3.0` and up |  | Room to grow |

OCI reserves 3 addresses in every subnet: `.0` (network), `.1` (subnet router), `.255` (last).

### Route tables

Traffic inside the VCN is routed automatically. These rules are only for traffic leaving the VCN. The most specific rule wins.

| Route table | Destination | Target |
| --- | --- | --- |
| Public | `0.0.0.0/0` | Internet Gateway |
| Private | All Oracle services in the region | Service Gateway |
| Private | `0.0.0.0/0` | NAT Gateway |

### Security rules (NSGs, all stateful)

| NSG | Direction | Port | Who | Why |
| --- | --- | --- | --- | --- |
| Load balancer | Ingress | TCP 80 | `0.0.0.0/0` | Users visit the app |
| Load balancer | Egress | TCP 8000 | Fleet NSG | Forward requests and health checks |
| Bastion | Ingress | TCP 22 | Your home IP `/32` | Only you can log in |
| Bastion | Egress | TCP 22 | Fleet NSG | Jump to fleet servers |
| Fleet | Ingress | TCP 8000 | Load balancer NSG | App traffic |
| Fleet | Ingress | TCP 22 | Bastion NSG | Admin login |
| Fleet | Egress | TCP 443, 80 | `0.0.0.0/0` | Updates (NAT), Object Storage (Service Gateway) |

Also remove the rule in OCI's default security list that allows SSH from `0.0.0.0/0`.

### The four checks for any packet

1. Sender's egress rule allows it.
2. A route exists (only when leaving the VCN).
3. The gateway exists and is not blocked (only when leaving the VCN).
4. Receiver's ingress rule allows it.

If any check fails, the trip fails. Use this list every time something breaks.

## Before Day 1 (about 2 hours)

Set up the account and tools first, so Day 1 is only Terraform.

- [ ] Sign up for OCI. Pick **US East (Ashburn)** as the home region. You cannot change it later, and free resources live only there.
- [ ] Create a budget alert (for example, email at $10). Billing > Budgets.
- [ ] Open Governance > Limits, Quotas and Usage. Confirm NAT Gateway and Service Gateway limits are above 0.
- [ ] Create one compartment named `gateway-lab`. A compartment is a folder for cloud resources. Put everything in it.
- [ ] On your Mac, install: Terraform, the OCI CLI, Python 3.11 or newer, `tflint`. (Homebrew works for all of them.)
- [ ] Run `oci setup config`. It creates an API key so Terraform and Python can act as you. Upload the public key in the console under your user profile.
- [ ] Make an SSH key pair for the servers: `ssh-keygen -t ed25519 -f ~/.ssh/gateway_lab`.
- [ ] Find your home IP (search "what is my IP"). It goes into the bastion rule.
- [ ] Create an empty GitHub repo, for example `oci-gateway-fleet`. Add a `.gitignore` for `*.tfstate*`, `.terraform/`, and `*.tfvars` so secrets never get pushed.

Never commit API keys, private SSH keys, or state files. State files can contain secrets.

## Repo structure

Modules are reusable building blocks. Environments are the places that use them with different settings.

```
oci-gateway-fleet/
  terraform/
    modules/
      network/          VCN, subnets, gateways, route tables, NSGs
        tests/          network.tftest.hcl (mock provider, offline)
      fleet/            bastion, fleet servers, load balancer
        tests/          fleet.tftest.hcl (mock provider, offline)
    envs/
      dev/              main.tf, variables.tf, dev.tfvars
      prod/             same files, different values
  app/
    app.py              the tiny FastAPI app (about 50 lines)
    cloud-init.yaml     installs and starts the app when a server boots
    docker-compose.yml  2 app copies behind nginx, for local runs
    nginx.conf
  tools/
    lb_client.py        small interface over the OCI load balancer API
    plan_checker.py     blocks risky network changes
    rolling_update.py   updates servers one at a time
    load_probe.py       sends requests and counts failures
  tests/
    fixtures/           saved plan files: safe, deletes a gateway, opens SSH
    fakes/              fake load balancer client for offline tests
    unit/               pytest for the app and tools (offline)
    integration/        pytest that checks real cloud behavior
  runbooks/
    lost-egress.md
    rollback-network-change.md
  .github/workflows/ci.yml
  README.md
```

Start with only `terraform/modules/network` and `terraform/envs/dev`. Add the rest on the day it is needed.

## How we work: tests first, local first

Write the test, watch it fail, then write the code that makes it pass. Do everything you can on your Mac, and use the cloud only for what needs it.

| Part | Where it is built and tested | Test written first |
| --- | --- | --- |
| Terraform logic | Offline, `terraform test` with a mock provider | Yes |
| App | Mac, Docker Compose with 2 copies behind nginx | Yes, pytest |
| Plan checker | Mac, saved plan files as input | Yes, pytest |
| Rolling update logic | Mac, fake load balancer client | Yes, pytest |
| Network behavior (gateways, routes, NSGs) | Real OCI only | Yes, integration tests written before the build |

The red-green loop:

1. Write one test for one behavior.
2. Run it and see it fail (red). This proves the test can catch the problem.
3. Write the smallest code that makes it pass (green).
4. Clean up the code while the tests stay green.
5. Move to the next behavior.

One limit: mock tests prove your code says what you meant, not that OCI accepts it. Wrong shape names, missing permissions, and capacity errors only appear on a real `apply`. Don't polish offline tests for long. Reach the first real `apply` by the end of Day 1.

## Day 1: Tests first, offline, then the first real apply

By the end of Day 1, the network module and the app both pass tests you wrote first, offline, and one real `apply` has built the network in OCI.

### Terraform in 5 ideas

1. **Provider.** The plugin that talks to a cloud. You use the `oci` provider.
2. **Resource.** One thing to create, like a VCN. You describe what you want, not the steps to make it.
3. **Variable and output.** Inputs you can change (CIDRs, your IP) and values printed after a build (IDs, IPs).
4. **State.** A file where Terraform remembers what it built. It compares state with your code to decide what to change.
5. **The loop.** `terraform init` (once), `terraform plan` (preview the changes), `terraform apply` (make them), `terraform destroy` (delete everything).

### Tasks

- [ ] Morning, offline. In `modules/network/tests`, write `network.tftest.hcl` with a `mock_provider "oci"` block and these checks first: the VCN uses the CIDR from a variable, the private subnet sets `prohibit_public_ip_on_vnic = true`, the private route table has no Internet Gateway rule, and no NSG rule allows TCP 22 from `0.0.0.0/0`. Run `terraform test` and see them fail.
- [ ] Write the network module until every check passes: the VCN (`oci_core_vcn`), the three gateways (`oci_core_internet_gateway`, `oci_core_nat_gateway`, `oci_core_service_gateway`, which needs the `oci_core_services` data source), two route tables, two regional subnets, three NSGs and their rules, and `oci_core_default_security_list` without the open SSH rule. Add outputs for the IDs.
- [ ] App, test first. Write pytest cases for `/health`, `/whoami`, and `/egress` with FastAPI's test client. Then write `app.py`. Keep the Object Storage call behind one small function, so tests can swap in a fake.
- [ ] Run 2 app copies behind nginx with Docker Compose. Confirm `/whoami` alternates between them.
- [ ] Evening, cloud. In `envs/dev`, add the `oci` provider with your API key config. Run `plan`, read every line, then `apply`. Check the result in the console. Then `destroy`.

### Done when

- `terraform test` passes offline, and every check failed once before its code existed.
- The app tests pass, and the local Docker Compose setup answers from both copies.
- `terraform apply` builds the network from zero with no console clicks, and `terraform plan` right after says "No changes."
- You can explain every resource in plain words.

### Measure

- Time for `apply` from zero, and the number of resources it creates.

## Day 2: Servers, app, and load balancer

By the end of Day 2, a user can open the load balancer's address in a browser and get an answer from one of the fleet servers.

### New ideas

1. **Instance.** A virtual server (`oci_core_instance`). Use a small shape such as `VM.Standard.E2.1.Micro` with Oracle Linux. The login user is `opc`.
2. **cloud-init.** A script a server runs on first boot. It installs Python and your app, then starts it. You pass it to the instance as `user_data`.
3. **Load balancer.** One public address in front of many servers. It sends each request to a healthy server and stops sending to a server whose health check fails.
4. **Instance principal.** A way for a server to prove who it is to OCI, so the app can write to Object Storage without storing a password. It needs a dynamic group ("all instances in `gateway-lab`") and a policy ("this group may manage objects in this bucket").
5. **Jump host.** You reach a private server by going through the bastion: `ssh -J opc@<bastion-ip> opc@10.0.2.x`.

### The app (about 50 lines of FastAPI)

| Endpoint | Returns | What it tests |
| --- | --- | --- |
| `GET /health` | `{"status": "ok", "version": "v1"}` | Load balancer health checks |
| `GET /whoami` | The server's hostname | Load balancing across servers |
| `POST /notes` | Saves a small text file to Object Storage | Service Gateway path |
| `GET /egress` | Tries to reach a public website, returns ok or fail | NAT Gateway path |

You already built and tested this app on Day 1. Today you only deploy it. The version comes from an environment variable, so Day 4 can roll out `v2`.

### Tasks

- [ ] Before building anything, write the integration tests (Day 3, section 4) in `tests/integration`. Run them against the Day 1 network. They should all fail.
- [ ] In `modules/fleet`, create the bastion in the public subnet with a public IP and the Bastion NSG.
- [ ] Create 2 to 3 fleet servers in the private subnet with the Fleet NSG and the cloud-init script. Use `count` so the number is one variable.
- [ ] Create an Object Storage bucket (`oci_objectstorage_bucket`).
- [ ] Create the dynamic group and the policy. If the Terraform resource for dynamic groups gives trouble with identity domains, create it once in the console and write that down in the README.
- [ ] Create the load balancer (`oci_load_balancer_load_balancer`, flexible shape, 10 Mbps) in the public subnet with the Load balancer NSG.
- [ ] Add a backend set with an HTTP health check on port 8000, path `/health`. Add each fleet server as a backend. Add a listener on port 80.
- [ ] Output the load balancer's public IP and the bastion's public IP.
- [ ] Rerun the integration tests after each piece. Stop when all are green.

### Done when

- `curl http://<lb-ip>/whoami` several times shows different hostnames.
- `POST /notes` creates a file you can see in the bucket.
- `GET /egress` returns ok.
- You can SSH to a fleet server only through the bastion.

### Measure

- Time from `apply` to all backends healthy.

## Day 3: Safety checker, rolling update logic, fault drills

By the end of Day 3, you can prove the network works, block a bad change before it happens, and show what each part does by breaking it.

### 1. Keep the offline tests green

- [ ] `terraform fmt -check`, `terraform validate`, `tflint`, and `terraform test` all pass.
- [ ] Add `fleet.tftest.hcl` for the fleet module, test first: fleet servers get no public IP, and the health check uses port 8000 and `/health`.

### 2. The plan checker

It reads Terraform's planned changes and refuses risky ones. Build it test-first: save three small plan files in `tests/fixtures` (one safe change, one that deletes the NAT Gateway, one that opens SSH to `0.0.0.0/0`), write pytest cases for all three, see them fail, then write the script.

1. `terraform plan -out plan.bin`, then `terraform show -json plan.bin > plan.json`.
2. The script reads `resource_changes` in `plan.json`. Each entry has a resource type and its actions (create, update, delete).
3. It fails (exit code 1) when a gateway, route table, or subnet would be deleted or replaced, or when a new rule opens port 22 to `0.0.0.0/0`.
4. An `--allow-destroy` flag overrides the first rule, on purpose, when you mean it.

### 3. Rolling update logic, offline

Put every load balancer call (drain, undrain, read backend health) behind a small `lb_client.py` interface. In tests, use a fake client you control. Day 4 runs the same logic against the real load balancer.

- [ ] Test first: all servers healthy, so every server is updated in order.
- [ ] Test first: server 2 never becomes healthy, so the script stops, rolls server 2 back, never touches server 3, and exits with an error.
- [ ] Test first: a load balancer call times out twice, then works, so the script retries with backoff and continues.
- [ ] Write `rolling_update.py` until all three pass.

### 4. Integration tests (written on Day 2, run after `apply`)

Read the IPs from `terraform output -json`, then check real behavior with pytest:

- [ ] Load balancer `/health` returns 200.
- [ ] `/whoami` shows every fleet server across many requests.
- [ ] `/egress` returns ok (NAT path works).
- [ ] `/notes` saves a file (Service Gateway path works).
- [ ] A fleet server's private IP cannot be reached from your laptop.
- [ ] No fleet server has a public IP (check with the OCI Python SDK).

### 5. Fault drills

For each drill: write your prediction first using the four checks, make the change, run the tests, record what failed and how long it took to notice, then undo it and record the recovery time. Make the NAT and Service Gateway drills variables (`block_traffic`), so the break and the fix are both one Terraform change.

| Drill | Change | Expected result |
| --- | --- | --- |
| NAT blocked | `block_traffic = true` on the NAT Gateway | `/egress` fails, `/whoami` still works |
| Service path lost | Remove the Oracle services route rule | `/notes` fails, everything else works |
| App port closed | Remove Fleet ingress TCP 8000 | Health checks fail, load balancer returns errors |
| One server down | Stop one fleet server | Load balancer stops sending to it, app stays up |

If a result does not match your prediction, that is the most valuable finding of the day. Write down why.

### Done when

- All offline and integration tests pass on a fresh `apply`.
- The plan checker blocks the saved gateway-deletion plan.
- The rolling update tests pass with the fake client.
- The drill table is filled with your real results and times.

## Day 4: Rolling update, alarm, pipeline, runbooks

By the end of Day 4, you can release a new app version with zero failed requests, get an email when something breaks, and hand a stranger a runbook to fix it.

### 1. Rolling update (`rolling_update.py`)

Update one server at a time, so users always have a healthy server. The logic was tested offline on Day 3. Today it runs against the real load balancer.

1. Tell the load balancer to drain server 1. Draining means it stops sending new requests to that server but lets current ones finish.
2. Wait a short time, then switch the server to `v2` and restart the app (SSH through the bastion).
3. Poll its `/health` until it reports `v2`. Use a timeout and retries with backoff.
4. Undrain it, and wait until the load balancer marks it healthy.
5. Repeat for the next server.
6. If any server fails its health check before the timeout, stop. Put that server back on `v1`, undrain it, and exit with an error.

While it runs, `load_probe.py` sends a request to the load balancer every 100 ms and counts failures and timeouts.

- [ ] Roll `v1` to `v2` with the probe running. Record total requests and failures.
- [ ] Roll out a broken `v3` (health check always fails). Confirm the script stops after the first server and the app stays up.

### 2. Alarm

- [ ] Create a Notifications topic with your email (`oci_ons_notification_topic`, `oci_ons_subscription`).
- [ ] Create a Monitoring alarm (`oci_monitoring_alarm`) that fires when the load balancer reports any unhealthy backend for 1 minute. Find the exact metric name in the console's Metrics Explorer under the load balancer namespace.
- [ ] Rerun the "App port closed" drill and record how long the email takes.

### 3. Pipeline (GitHub Actions)

On every pull request, with no cloud credentials needed:

- [ ] `terraform fmt -check`, `terraform validate`, `tflint`.
- [ ] `terraform test` using a mock provider, so it runs without an OCI account.
- [ ] pytest unit tests for the tools.

Stretch: run `terraform plan` plus the plan checker in CI, with the OCI key stored as a GitHub secret.

### 4. Runbooks

Write two, each about one page, using the same sections:

1. **Symptoms.** What the alarm or the user sees.
2. **Impact.** What still works and what does not.
3. **Checks.** The four checks, in order, with the exact command or console page for each.
4. **Fix.** The smallest safe change.
5. **Verify.** Which tests to run.
6. **Rollback.** How to undo the fix if it makes things worse.

- [ ] `lost-egress.md`: private servers cannot reach the internet.
- [ ] `rollback-network-change.md`: undo a bad Terraform change safely.

### Done when

- The rollout to `v2` has a recorded failure count, ideally 0.
- The broken `v3` rollout stopped by itself.
- The alarm email arrived during a drill.
- CI is green on a pull request.
- Then: `terraform destroy`.

## Measurements and resume bullets

Fill this table as you go. Only numbers you actually measured go on the resume.

| Measurement | Day | Your result |
| --- | --- | --- |
| Resources created by one `apply` | 1 |  |
| Time to build the network from zero | 1 |  |
| Time until all backends are healthy | 2 |  |
| Number of unit and integration tests | 3 |  |
| Risky changes the plan checker blocked | 3 |  |
| Time to detect each drill | 3 |  |
| Time to recover from each drill | 3 |  |
| Requests and failures during the `v2` rollout | 4 |  |
| Servers updated before the broken `v3` was stopped | 4 |  |
| Minutes from fault to alarm email | 4 |  |

Bullet templates (what you did, how, and the measured result). Replace every `[ ]` with a real number, or drop the bullet.

- Provisioned an OCI network with public and private subnets, Internet, NAT, and Service Gateways, and a load-balanced fleet using Terraform modules, rebuilding \[ \] resources from zero in \[ \] minutes.
- Developed a Python rolling-update tool using load balancer draining and health checks, releasing a new version with \[ \] failed requests out of \[ \].
- Developed a Python plan checker that blocks gateway or route deletions and open SSH rules before `terraform apply`, verified with \[ \] pytest cases.
- Validated network design through fault-injection drills on NAT, Service Gateway, and security rules, detecting each failure within \[ \] and documenting recovery in runbooks.

## Troubleshooting and glossary

### When something breaks

1. Read the exact error message first. Copy it before you change anything.
2. Walk the four checks: sender egress, route, gateway, receiver ingress.
3. Run `terraform plan`. If it shows changes you did not expect, someone (maybe you, in the console) changed things by hand.
4. Change one thing at a time, then test again.
5. Stuck for more than 30 minutes? Bring the error and what you tried back to Claude.

Common first-time problems:

- **Out of capacity** when creating a small server: try another availability domain or shape.
- **Authorization failed:** the API key or policy is missing, or the resource is in the wrong compartment.
- **App never becomes healthy:** SSH in through the bastion and run `curl localhost:8000/health`. If that works, the problem is a security rule. If not, check the cloud-init log in `/var/log/cloud-init-output.log`.
- **Server cannot install packages:** check Fleet egress rules and the NAT route.

### Glossary

| Term | Plain meaning |
| --- | --- |
| VCN | Your private network in OCI |
| CIDR | A short way to write an address range, like `10.0.0.0/16` |
| Subnet | A smaller slice of the VCN's range |
| Route table | Rules for where traffic leaving a subnet goes |
| Internet Gateway | Two-way door to the internet, needs a public IP |
| NAT Gateway | One-way door out to the internet for private servers |
| Service Gateway | Private door to Oracle services like Object Storage |
| NSG | Firewall rules attached to specific servers, can refer to other NSGs |
| Stateful | Replies are allowed back automatically |
| Bastion | The one server you log in through |
| Load balancer | One public address that spreads requests across healthy servers |
| Drain | Stop sending new requests to a server so it can be updated |
| Terraform state | Terraform's record of what it built |
| Runbook | Step-by-step fix for a known problem |
