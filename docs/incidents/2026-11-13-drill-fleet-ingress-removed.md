# Drill 3: Fleet ingress on port 8000 removed
Date: 2026-11-13 | Day: 3

## Symptom
This was a planned drill. I removed the `fleet_ingress_app` rule from the fleet NSG. That rule lets the load balancer reach the app on port 8000. All times are UTC.

Prediction, written before the drill: the health checks fail after about 30 seconds. Then the load balancer returns errors, so health, whoami, egress and notes all fail. The plan checker passes the plan.

Result: the apply ended at 03:41:23. In the round that started at 03:41:35, four tests failed: `test_health_ok`, `test_whoami_covers_all_servers`, `test_egress_ok` and `test_notes_saved`. This was faster than my 30 second guess. One round at 03:41:20 ran while the rule was being removed, and only `test_egress_ok` failed in it. The plan checker exited with 0.

## How I found the cause
I ran the same test loop. The plan said "1 to destroy". The rules are one `for_each` resource, so removing a rule destroys that rule resource. It is not an in-place update. The checker still passed it, because security rules are not on its protected list. The only rule it blocks is an open SSH or all-ports rule that is being created.

## Fix
I undid the change and applied it. The undo ended at 03:43:06. The last failing round started at 03:43:42. The first round with all tests passing started at 03:43:52. The load balancer needs several good health checks before it sends traffic again.

## Lesson
This fault takes down the whole app, and the plan checker passes it. This is a known gap. Removing a rule is as dangerous as deleting a gateway. The checker should look at which rules disappear, not only at which resources are on the protected list.
