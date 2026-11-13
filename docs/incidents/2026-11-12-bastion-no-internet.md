# Bastion could not reach the internet
Date: 2026-11-12 | Day: 2

## Symptom
From the bastion, requests to the internet did not work.

## How I found the cause
I walked the four checks for a packet: the sender's egress rule, a route, the gateway, and the receiver's ingress rule. The first check failed. The bastion NSG allows only SSH out, and only to the fleet NSG.

## Fix
No fix. This is by design. The bastion is a jump host and needs nothing else. See [decision 0005](../decisions/0005-role-based-nsgs.md).

## Lesson
Use the four checks every time. An error can be the design working.
