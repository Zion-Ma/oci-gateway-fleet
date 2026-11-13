# POST /notes hung for 10 seconds on my laptop
Date: 2026-11-09 | Day: 1

## Symptom
Running the app locally, `POST /notes` hung for about 10 seconds before it failed.

## How I found the cause
Instance principal login asks a special metadata address for a token. That address exists only inside OCI. On my laptop nothing answers, so the call waits until it times out.

## Fix
- The app reads the bucket name from `NOTES_BUCKET`. This variable is in the first commit with the app (2026-11-09).
- On 2026-11-12 I added a fail-fast check in `app/src/notes.ts`. If `NOTES_BUCKET` is unset, saving fails at once, with no OCI call.
- On the same day, a failed save returns `502 {"error": "could not save note"}`. The real error goes to the log with `console.error`. A test checks that the response never contains the internal error text.

## Lesson
Check the settings before any network call. Never send internal error text to the caller.
