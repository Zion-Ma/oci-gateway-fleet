# A "must not" test passed on an empty route table
Date: 2026-11-10 | Day: 1

## Symptom
My test said the private route table must not route through the Internet Gateway. It passed even when the route table had no rules at all.

## How I found the cause
A "must not" check is true for an empty table. The test could not tell a good table from a missing one.

## Fix
In commit `3619a81` I added "must" checks to the test:
- `0.0.0.0/0` must go to the NAT Gateway.
- The Oracle services range must go to the Service Gateway.
- The private subnet must use this route table.

## Lesson
Pair every "must not" with a "must".
