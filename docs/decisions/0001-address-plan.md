# 0001: Address plan
Date: 2026-11-09 | Day: 1 | Status: Accepted

## Context
I needed IP ranges before I wrote any Terraform. Two networks with overlapping ranges cannot be joined later.

## Decision
- VCN: `10.0.0.0/16`
- Public subnet: `10.0.1.0/24` (load balancer, bastion)
- Private subnet: `10.0.2.0/24` (fleet servers)
- The rest of the `/16` stays free.

## Why
Each `/24` has 256 addresses. That is far more than 2 or 3 servers need. Two subnets let me give each one its own route table. The free space lets me add subnets later without renumbering.

## Trade-offs
The `/16` is much larger than I use today. The ranges are defaults in `modules/network/variables.tf`. In `envs/dev/main.tf` I pass only the VCN range, as a literal. The two subnet variables in `envs/dev/variables.tf` are not passed to the module, so the module defaults apply.
