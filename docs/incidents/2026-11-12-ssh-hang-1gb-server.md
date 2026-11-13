# SSH to the first fleet server hung
Date: 2026-11-12 | Day: 2

## Symptom
SSH to the first fleet server hung. TCP port 22 was open, but no SSH banner came back.

## How I found the cause
An open port with no banner means the network works and the server does not answer. The 1 GB micro server was overloaded by `dnf` during cloud-init.

## Fix
cloud-init now creates a 2 GB swap file in `bootcmd`. The fleet also moved to a 4 GB shape. See [decision 0008](../decisions/0008-bastion-free-fleet-paid-shape.md).

## Lesson
An open port does not mean a healthy server. Small servers need swap while packages install.
