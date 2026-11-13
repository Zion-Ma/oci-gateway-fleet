# Drill 1: NAT Gateway blocked
Date: 2026-11-13 | Day: 3

## Symptom
This was a planned drill. I set `block_traffic = true` on the NAT Gateway. All times are UTC.

Prediction, written before the drill: only `test_egress_ok` fails. The plan checker passes the plan, because it is an in-place update and not a delete.

Result: the prediction was right. The apply ended at 03:35:05. The first failing round started at 03:35:16, and only `test_egress_ok` failed. `/health`, `/whoami` and `/notes` kept working.

## How I found the cause
There was nothing to find. I made the fault. I ran `pytest tests/integration` in a loop, about every 12 seconds, and logged which tests failed. I ran `tools/plan_checker.py` on the plan first. It exited with 0, so it did not block the change.

## Fix
I undid the change and applied it. The undo ended at 03:35:56. The first round with all tests passing started at 03:36:07, 11 seconds later.

## Lesson
Blocking the NAT Gateway breaks only outbound internet from the fleet. The plan checker does not see this fault. It watches deletes and open ports, and this change is neither. This is a known gap in the checker.

## Follow up: plan checker
The checker now blocks an update that turns `block_traffic` on for a NAT or Service Gateway, unless `--allow-destroy` is set. I tested this with fixtures and unit tests. I did not rerun this drill, so I have not run the checker on the real drill 1 plan.
