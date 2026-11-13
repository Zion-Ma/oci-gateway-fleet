# OCI CLI returned NotAuthenticated
Date: 2026-11-09 | Day: 1

## Symptom
The OCI CLI answered every call with `NotAuthenticated`.

## How I found the cause
The cause was in `~/.oci/config`. The `user=` line held a compartment OCID, not a user OCID.

## Fix
I put my user OCID on the `user=` line. The `tenancy=` line is a separate value.

## Lesson
Check the type of each OCID, not only that it is present. The prefix tells you what it is (`ocid1.user`, `ocid1.compartment`, `ocid1.tenancy`).
