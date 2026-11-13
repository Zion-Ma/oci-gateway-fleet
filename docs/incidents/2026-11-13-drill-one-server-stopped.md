# Drill 4: One fleet server stopped
Date: 2026-11-13 | Day: 3

## Symptom
This was a planned drill. I stopped the first fleet server with the OCI API, outside Terraform. All times are UTC.

Prediction, written before the drill: a short window of errors until the health check marks the server `CRITICAL`. After that, the app stays up through the other server. `test_whoami_covers_all_servers` fails, because it expects both servers to answer.

Result: the prediction was right. The server reached `STOPPED` at 03:45:15. In the round that started at 03:45:23, `test_whoami_covers_all_servers` and `test_egress_ok` failed. From the round at 03:45:54 on, only `test_whoami_covers_all_servers` failed. `test_health_ok` and `test_notes_saved` passed in every round.

## How I found the cause
I ran the same test loop. The one-time `test_egress_ok` failure fits the short window before the health check removed the stopped server. I think a request went to the stopped server in that window. I did not confirm this.

## Fix
I started the server again. It reached `RUNNING` at 03:46:57. The last failing round started at 03:47:45, and the first round with all tests passing started at 03:47:58, about 61 seconds after `RUNNING`. The app starts by itself on boot, so I did nothing else.

## Lesson
With two servers, the app survives one failure. There was one short window with a failed request, so users can see an error. `test_whoami_covers_all_servers` fails on purpose when one server is down. It is a good alarm for a lost server. This fault is not a Terraform change, so the plan checker has nothing to check.
