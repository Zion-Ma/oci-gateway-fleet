# In-place resize from E2 Micro to E5.Flex was rejected
Date: 2026-11-12 | Day: 2

## Symptom
The plan said `fleet[0]` would be updated in place. The apply failed with `400-InvalidParameter`: the new shape belongs to a hardware series that is not compatible with the current shape.

## How I found the cause
The error came from the `UpdateInstance` API call (see the request target in the error), not from Terraform's plan. The provider allows a shape update, but the API refuses to move between hardware series.

## Fix
I planned again with `-replace` on `fleet[0]`. The plan became delete and create, and that worked.

## Lesson
A clean plan does not prove that the API accepts the change. When the hardware changes, plan a replacement.
