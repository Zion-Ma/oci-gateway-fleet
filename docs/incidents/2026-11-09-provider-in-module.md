# Provider block inside the network module
Date: 2026-11-09 | Day: 1

## Symptom
I had put the `oci` provider configuration (login and region) inside the network module.

## How I found the cause
TODO: write down how I noticed this.

## Fix
The `provider "oci"` block now lives only in `terraform/envs/dev/versions.tf`. The modules only declare `required_providers`. See [decision 0002](../decisions/0002-separate-modules-one-provider.md).

## Lesson
Modules describe what to build. The environment decides who logs in and where.
