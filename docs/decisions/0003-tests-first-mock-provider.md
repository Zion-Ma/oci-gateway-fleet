# 0003: Tests first, with a mock provider
Date: 2026-11-08 | Day: 1 | Status: Accepted

## Context
Real applies cost time and can fail for reasons that have nothing to do with my code.

## Decision
- I write the `terraform test` file first and watch it fail. Then I write the code.
- Each test file uses `mock_provider "oci"`.
- I use `command = plan` by default.
- I use `command = apply` only when a value is unknown until apply. In the network tests this is the case for route tables, NSG rules and the default security list, because they compare IDs that the cloud creates. In the fleet tests one run uses it to read the bastion's tags.

## Why
The tests run offline and in seconds. They catch wrong wiring early.

## Trade-offs
Mock tests prove that my code says what I meant. They do not prove that OCI accepts it. Shape limits, hardware rules and capacity only showed up on a real apply. See [the service limit error](../incidents/2026-11-12-e2-micro-limit-exceeded.md) and [the rejected resize](../incidents/2026-11-12-in-place-resize-rejected.md).
