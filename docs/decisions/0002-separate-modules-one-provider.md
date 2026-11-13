# 0002: Separate network and fleet modules, one provider block
Date: 2026-11-09 | Day: 1 | Status: Accepted

## Context
I wanted the network and the servers to change on their own schedule. I also needed to decide where the login and region settings live.

## Decision
- `modules/network` builds the VCN, subnets, gateways, route tables and NSGs.
- `modules/fleet` builds the bastion, fleet servers, load balancer and storage.
- Only `envs/dev/versions.tf` has a `provider "oci"` block (profile and region).
- Each module only declares `required_providers`.

## Why
A module without its own login can be used by any environment. The login and region are set in one place. It also lets the tests use a mock provider.

## Trade-offs
A module cannot run on its own. The environment must pass in every ID, such as subnet and NSG IDs. That makes `envs/dev/main.tf` longer.

See also: [provider in the network module](../incidents/2026-11-09-provider-in-module.md).
