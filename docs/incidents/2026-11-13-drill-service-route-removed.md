# Drill 2: Oracle services route removed
Date: 2026-11-13 | Day: 3

## Symptom
This was a planned drill. I removed the Oracle services route from the private route table. That left only the route to the NAT Gateway. All times are UTC.

The project plan said only `/notes` should fail. My prediction, written before the drill, was different. The app uses the public Object Storage address. I thought the route through the NAT Gateway would carry that traffic. So I predicted that no test would fail. The plan checker should pass the plan, because it is an in-place update.

Result: my prediction was right. The apply ended at 03:37:32. No test failed in any round until I undid the change at 03:39:54. That is about 2 minutes 14 seconds. The plan checker exited with 0.

## How I found the cause
I ran the same test loop as in drill 1. Every round passed, including `test_notes_saved`. I did not check which path the Object Storage calls took. The app might also have reused open connections. So I know that `/notes` kept working, but I do not know for certain that it used the NAT Gateway.

## Fix
I undid the change and applied it. The undo ended at 03:39:57, and the tests were still passing.

## Lesson
The Service Gateway route is not what makes `/notes` work in this design. The NAT Gateway is a fallback for the same traffic. The Service Gateway keeps Object Storage traffic off the internet path. It does not decide whether the call works. To make `/notes` fail, I would need to remove the service route and block the NAT Gateway together. I did not run that. The plan checker does not see this fault either.

## Follow up: rerun after the fix
I fixed the gap in [decision 0011](../decisions/0011-notes-only-via-service-gateway.md). Then I made the same break again. All times are UTC.

- The plan checker now has a rule for removed route rules. It printed `BLOCKED: module.network.oci_core_route_table.private: route rule to all-iad-services-in-oracle-services-network would be removed` and exited with 1.
- After I applied the break, `test_notes_saved` failed with `assert 502 == 201`. The other 5 tests passed. I have two rounds on record, at 06:08:18 and 06:08:38. I did not keep the apply time or the rest of the rounds.
- I undid the break and all 6 tests passed. I did not record the time of the undo.

The first result was that `/notes` kept working. Now it fails with an error when the route is gone. The gap is closed. This was only one run, and I did not check the cause of the 502 on the servers.
