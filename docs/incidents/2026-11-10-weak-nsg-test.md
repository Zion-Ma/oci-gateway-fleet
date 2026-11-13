# AI-suggested NSG test was too weak
Date: 2026-11-10 | Day: 1

## Symptom
An AI assistant suggested a test for the NSG rules. It caught only a rule that opened exactly port 22 to the world. Its `try()` call could also make the check pass when something was wrong.

## How I found the cause
The test checked one exact port. A rule that opened a different port, or a range, would not fail it. The `try()` could hide an error and let the check pass.

## Fix
In commit `3619a81` I replaced it with `nsg_rules_follow_least_privilege`. It checks who can reach whom:
- Exactly one ingress rule is open to `0.0.0.0/0`, and it is the load balancer on TCP 80.
- Fleet port 8000 is reachable only from the load balancer NSG.
- Fleet SSH is reachable only from the bastion NSG.
- The fleet accepts ingress only on ports 22 and 8000.
- The bastion accepts traffic only from `bastion_allowed_cidr`.

I also broke the rules by hand to see each check fail. These manual breaks are not saved in the repo. TODO: turn them into tests.

## Lesson
A test that cannot fail is not a test. Test who can reach whom, not one port number.
