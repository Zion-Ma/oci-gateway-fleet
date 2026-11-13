# 0004: Find the Service Gateway service by filter, not by OCID
Date: 2026-11-09 | Day: 1 | Status: Accepted

## Context
The private subnet needs a route to Object Storage. The Service Gateway needs the ID of the Oracle services entry. That ID is different in each region.

## Decision
I use the `oci_core_services` data source. I filter it by name with the pattern `All .* Services In Oracle Services Network`. I take the service ID and the `cidr_block` from the result. The private route table sends that `cidr_block` to the Service Gateway.

## Why
No OCID is written in the code, so it works in any region.

## Trade-offs
The code depends on the text of Oracle's service name. It also uses the first match (`services[0]`).
