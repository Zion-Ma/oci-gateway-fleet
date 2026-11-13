# 0011: Object Storage accepts note writes only through the Service Gateway
Date: 2026-11-13 | Day: 3 | Status: Accepted

## Context
Drill 2 showed a gap. I removed the Oracle services route from the private route table. `/notes` kept working, because the NAT Gateway carried the traffic over the public internet. The Service Gateway route was not enforced by anything.

## Decision
I made a network source in the tenancy root, named `gateway-lab-fleet-vcn`. It lists the VCN and only the private subnet range. The `notes_writer` policy now needs both conditions inside one `all { ... }` block: the bucket name and `request.networkSource.name`. The verbs and the dynamic group are the same as before.

## Why
Object Storage sees the VCN only when a request arrives through the Service Gateway. A request that falls back to NAT comes from a public address. It does not match the network source, so it is refused. Removing the route now makes `/notes` fail with an error. It no longer falls back without a sign.

I did not use `request.vcn.id`. Oracle documents it as deprecated for Object Storage. A network source with `request.networkSource.name` is the supported way.

## Trade-offs
- Network sources live in the tenancy root, outside the project compartment.
- The policy and the route now depend on each other. If the route breaks, `/notes` stops. That is the goal, but it is also a new way to fail.
- The network source lists the private subnet range. If that range changes, the network source must change with it. Both now take the range from the same variable.
- I applied it, and the 6 integration tests passed. I did not try the identity-domain fallback (a source made by hand in the console), because it was not needed.
