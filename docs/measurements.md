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
| 2026-11-13 | 3 | Drill 1, NAT blocked: apply end to first failing round, and undo end to all tests passing | 11 s and 11 s | A loop that ran `pytest tests/integration` about every 12 s and logged the start time in UTC. Each time is accurate to about 12 s. The loop script is not kept in the repo. |
| 2026-11-13 | 3 | Drill 2, Oracle services route removed: time with no failing test | 2 min 14 s, none failed | Same loop |
| 2026-11-13 | 3 | Drill 3, fleet ingress removed: apply end to 4 failing tests, and undo end to all tests passing | 12 s and 46 s | Same loop |
| 2026-11-13 | 3 | Drill 4, one server stopped: `STOPPED` to first failing round, and `RUNNING` to all tests passing | 8 s and 61 s | Same loop, with the OCI API for the stop and start |
| 2026-11-13 | 3 | Plan checker on the three Terraform drill plans | 0 of 3 blocked | `tools/plan_checker.py` on `terraform show -json` of each plan |
| 2026-11-13 | 3 | Drill 2 rerun after decision 0011: `test_notes_saved` | failed with 502 in both rounds on record (06:08:18 and 06:08:38 UTC); the other 5 tests passed | The same kind of loop, one round about every 20 s. The apply and undo times were not recorded. |
| 2026-11-13 | 3 | Plan checker on the drill 2 rerun plan | 1 of 1 blocked | `tools/plan_checker.py` on `terraform show -json` of the plan |
| 2026-11-13 | 3 | Unit tests after the new checker rules | 17 of 17 passing | `pytest tests/unit` |
