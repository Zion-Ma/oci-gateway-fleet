# 0008: Bastion on the free shape, fleet on a paid flexible shape
Date: 2026-11-12 | Day: 2 | Status: Accepted

## Context
The free tier allows 2 `VM.Standard.E2.1.Micro` instances. The bastion and the first fleet server used both. The second fleet server failed with a limit error. See [the incident](../incidents/2026-11-12-e2-micro-limit-exceeded.md).

## Decision
I split the single `shape` variable in two.
- `bastion_shape` defaults to `VM.Standard.E2.1.Micro`.
- `fleet_shape` defaults to `VM.Standard.E5.Flex`, with `ocpus = 1` and `memory_in_gbs = 4`.

Both shapes are x86. One Oracle Linux 9 image lookup (filtered by `fleet_shape`) serves both.

## Why
The bastion does almost nothing, so the free shape is enough. The fleet needs more memory than 1 GB. The trial credits pay for it.

## Trade-offs
The fleet costs credits. If the two shapes ever need different images, I must add a second image lookup. Changing a server between hardware series needs a replacement, not an update. See [the rejected resize](../incidents/2026-11-12-in-place-resize-rejected.md).
