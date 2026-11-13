# Engineering log

This is the engineering log for the OCI gateway fleet project. Each entry is one file. This page is the index.

Dates are the date of the git commit that holds the change. Rows and files marked `TODO` are not in the repo or my notes yet.

## Decisions

- [0001: Address plan](decisions/0001-address-plan.md): VCN `10.0.0.0/16`, two `/24` subnets, the rest free.
- [0002: Separate network and fleet modules, one provider block](decisions/0002-separate-modules-one-provider.md): only `envs/dev` sets the login and region.
- [0003: Tests first, with a mock provider](decisions/0003-tests-first-mock-provider.md): `apply` only when a value is unknown until apply.
- [0004: Find the Service Gateway service by filter, not by OCID](decisions/0004-service-gateway-lookup.md): the ID differs per region.
- [0005: NSGs with role-based rules](decisions/0005-role-based-nsgs.md): rules point at other NSGs, and only the load balancer is open to the internet.
- [0006: Empty the default security list](decisions/0006-empty-default-security-list.md): NSGs are the only rules, at the cost of the ICMP rule.
- [0007: Stateless app, outside pieces passed in](decisions/0007-stateless-testable-app.md): easy to test and replace. SIGTERM handling is still a TODO.
- [0008: Bastion on the free shape, fleet on a paid flexible shape](decisions/0008-bastion-free-fleet-paid-shape.md): E2.1.Micro and E5.Flex.
- [0009: Storage access limited to fleet servers by a tag](decisions/0009-tag-scoped-storage-access.md): dynamic group on a tag, policy on one bucket.
- [0010: Ship the app with cloud-init](decisions/0010-ship-app-with-cloud-init.md): esbuild bundle, npm install at boot, systemd service.
- [0011: Object Storage accepts note writes only through the Service Gateway](decisions/0011-notes-only-via-service-gateway.md): a network source and a policy condition. Removing the route now makes `/notes` fail.

## Incidents

- [2026-11-09: OCI CLI returned NotAuthenticated](incidents/2026-11-09-cli-not-authenticated.md): `user=` held a compartment OCID.
- [2026-11-09: Provider block inside the network module](incidents/2026-11-09-provider-in-module.md): moved to `envs/dev`.
- [2026-11-09: POST /notes hung for 10 seconds on my laptop](incidents/2026-11-09-notes-hang-locally.md): instance principal login only works inside OCI.
- [2026-11-10: A "must not" test passed on an empty route table](incidents/2026-11-10-empty-route-table-test-passed.md): added "must" checks.
- [2026-11-10: AI-suggested NSG test was too weak](incidents/2026-11-10-weak-nsg-test.md): replaced with who-can-reach-whom checks.
- [2026-11-12: Bastion could not reach the internet](incidents/2026-11-12-bastion-no-internet.md): by design.
- [2026-11-12: SSH to the first fleet server hung](incidents/2026-11-12-ssh-hang-1gb-server.md): a 1 GB server was overloaded. Added swap.
- [2026-11-12: A1.Flex had no host capacity](incidents/2026-11-12-a1-flex-no-capacity.md): moved to x86 shapes.
- [2026-11-12: LimitExceeded on standard-e2-micro-core-count](incidents/2026-11-12-e2-micro-limit-exceeded.md): fleet moved to E5.Flex.
- [2026-11-12: In-place resize from E2 Micro to E5.Flex was rejected](incidents/2026-11-12-in-place-resize-rejected.md): used `-replace`.
- [2026-11-13: Drill 1, NAT Gateway blocked](incidents/2026-11-13-drill-nat-blocked.md): only egress failed. The plan checker did not block it.
- [2026-11-13: Drill 2, Oracle services route removed](incidents/2026-11-13-drill-service-route-removed.md): nothing failed, because the NAT Gateway carried the traffic. After decision 0011, the rerun failed `/notes` as wanted.
- [2026-11-13: Drill 3, fleet ingress on 8000 removed](incidents/2026-11-13-drill-fleet-ingress-removed.md): the whole app failed. The plan checker did not block it.
- [2026-11-13: Drill 4, one server stopped](incidents/2026-11-13-drill-one-server-stopped.md): the app stayed up through the other server.

## Measurements

- [measurements.md](measurements.md): one table, one row per measurement, newest last.

## How to add an entry

1. Copy the template. Use `decisions/_template.md` for a decision. Use `incidents/_template.md` for an incident.
2. Name the new file.
   - Decision: the next number and a short kebab-case slug, for example `0011-my-choice.md`.
   - Incident: today's date and a slug, for example `2026-11-13-my-problem.md`.
3. Fill in every section. Write short sentences. Write `TODO` for anything I do not know yet. Do not guess numbers or dates.
4. Add one line to the matching group above. Put it at the bottom of that group.
5. For a measurement, add one row at the bottom of `measurements.md` instead.
