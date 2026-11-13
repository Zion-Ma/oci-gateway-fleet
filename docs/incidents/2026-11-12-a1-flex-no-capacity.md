# A1.Flex had no host capacity
Date: 2026-11-12 | Day: 2

## Symptom
Creating a `VM.Standard.A1.Flex` (Ampere) server failed with "Out of host capacity" in AD-1.

## How I found the cause
The error says the availability domain has no free hardware for this shape. It is not a problem in my code.

## Fix
The dev environment now uses x86 shapes. An older comment in `envs/dev/variables.tf` said a fixed shape avoids Ampere capacity errors. Today the modules use the first availability domain (`availability_domains[0]`). I have **not** made the availability domain a variable. TODO: decide whether to do that.

## Lesson
Capacity errors only appear on a real apply. Mock tests cannot find them.
