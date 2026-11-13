# 0009: Storage access limited to fleet servers by a tag
Date: 2026-11-12 | Day: 2 | Status: Accepted

## Context
The fleet servers write notes to Object Storage. The bastion must not be able to write.

## Decision
- A tag namespace `gateway-lab` has a tag `role`. Only the fleet instances get `role = fleet`.
- A dynamic group `gateway-lab-fleet` matches `tag.gateway-lab.role.value='fleet'`. This tenancy uses identity domains, so I use `oci_identity_domains_dynamic_resource_group` in the `Default` domain.
- One policy statement: the dynamic group (written as `'Default'/'gateway-lab-fleet'`) may manage objects in the gateway-lab compartment, only where `target.bucket.name='gateway-lab-notes'`.
- The bucket is `NoPublicAccess`.
- The policy lives in the gateway-lab compartment, not in the root. It only grants access inside that compartment, so the root is not needed.

## Why
A rule on the compartment would include the bastion. A rule on instance OCIDs would break when I replace servers, and I replaced both on 2026-11-12. The tag follows the role.

## Trade-offs
The tag must exist before an instance launches with it. On the first apply, OCI did not see the new tag namespace yet and both launches failed. A second apply worked. A policy can also take a minute or two to start working.
