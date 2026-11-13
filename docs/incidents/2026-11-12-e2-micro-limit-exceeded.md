# LimitExceeded on standard-e2-micro-core-count
Date: 2026-11-12 | Day: 2

## Symptom
`terraform apply` failed on `fleet[1]` with `400-LimitExceeded` for `standard-e2-micro-core-count`.

## How I found the cause
The free tier allows 2 `VM.Standard.E2.1.Micro` instances. The bastion and `fleet[0]` already used both. One `shape` variable served both kinds of server.

## Fix
I split it into `bastion_shape` (free micro) and `fleet_shape` (`VM.Standard.E5.Flex`, 1 OCPU, 4 GB). See [decision 0008](../decisions/0008-bastion-free-fleet-paid-shape.md).

## Lesson
Check service limits before choosing a shape for a whole fleet.
