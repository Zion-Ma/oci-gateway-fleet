# 0005: NSGs with role-based rules
Date: 2026-11-10 | Day: 1 | Status: Accepted

## Context
Servers get new IP addresses when I replace them. Rules based on IP ranges would break.

## Decision
I use three NSGs: load balancer, bastion and fleet. Rules point at other NSGs, not at IP ranges.
- Load balancer: accepts TCP 80 from `0.0.0.0/0`. Sends TCP 8000 to the fleet NSG.
- Fleet: accepts TCP 8000 from the load balancer NSG. Accepts TCP 22 from the bastion NSG. Sends TCP 80 and 443 out.
- Bastion: accepts TCP 22 only from `bastion_allowed_cidr`. Sends TCP 22 to the fleet NSG.

`bastion_allowed_cidr` has no default and must be a single `/32` address.

## Why
Only the load balancer accepts traffic from the open internet. The bastion accepts SSH only from my own address. The rules stay correct when instances are replaced.

## Trade-offs
The fleet can send TCP 80 and 443 to any address. It needs this for package installs through the NAT Gateway. A test checks that exactly one ingress rule is open to `0.0.0.0/0`.

See also: [the weak NSG test](../incidents/2026-11-10-weak-nsg-test.md).
