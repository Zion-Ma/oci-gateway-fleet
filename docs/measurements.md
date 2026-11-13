# Measurements

One row per measurement. Newest last. `TODO` means the value is not in the repo or my notes yet.

| Date | Day | What | Result | How measured |
|---|---|---|---|---|
| TODO | 1 | Network apply | 20 resources, about 22 s | TODO (resource count matches the network module; time is from my notes) |
| TODO | 2 | Bastion create | about 1 min 12 s | TODO |
| TODO | 2 | First fleet server create | about 1.5 min | TODO |
| TODO | 2 | cloud-init on the 1 GB micro server | 10 to 20 min | TODO |
| 2026-11-12 | 2 | E5.Flex (4 GB) server, instance created to app listening | about 3 min 10 s | `time_created` of the instance (07:14:30 UTC) and the first app line in `journalctl -u fleet-app` (07:17:41 UTC) |
| TODO | 2 | Load balancer split in a 6-request check | 3 requests to each of 2 servers | TODO |
| 2026-11-12 | 2 | Integration tests | 6 of 6 passing | `pytest tests/integration` (stated in the Day 2 commit message) |
