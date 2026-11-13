# 0006: Empty the default security list
Date: 2026-11-09 | Day: 1 | Status: Accepted

## Context
OCI creates a default security list with every VCN. It includes an open SSH rule. Security lists and NSGs combine, so a packet passes if either one allows it.

## Decision
I manage the default security list with `oci_core_default_security_list` and give it no rules. That removes the open SSH rule and the allow-all egress rule. I named it `default-security-list-disabled`. A test checks that it has zero ingress and zero egress rules.

## Why
Then the NSGs are the only source of rules. I do not have to reason about two rule systems.

## Trade-offs
I lost the ICMP rule that allows path MTU discovery. If I see odd stalls on large packets, I should look here first.
