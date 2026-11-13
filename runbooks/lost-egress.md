# Runbook: lost egress

Use this when fleet servers cannot reach the internet. Egress means traffic that leaves the fleet. It goes out through the NAT Gateway.

Run all commands from the repo root. Run `source .venv/bin/activate` first. The tests need the `oci` package in it.

## Symptoms

- `GET /egress` through the load balancer answers HTTP 200 with `{"egress":"fail", ...}`. It does not answer 503. The app always answers 200 here, and the body says ok or fail. A 503 comes from the load balancer when no server is healthy. That is a different problem. Use `runbooks/backend-unhealthy.md`.
- `test_egress_ok` fails. The other tests pass.
- New servers stay stuck in cloud-init at `npm install`. The server cannot download packages.

## Impact

Users are still served. `/health`, `/whoami` and `/notes` keep working, as drill 1 showed. The alarm does not fire.

The danger is silent. Scaling the fleet or replacing a server fails, because a new server cannot finish cloud-init. You may find out only when you need the new server. An old server keeps working until you replace it.

## Checks

Do all four. The fault can be in more than one place.

1. The fleet NSG allows egress on ports 443 and 80. You want two rules with destination `0.0.0.0/0`, one for 443 and one for 80.

   ```
   FLEET_NSG=$(terraform -chdir=terraform/envs/dev state show -no-color module.network.oci_core_network_security_group.fleet | awk '$1=="id" {gsub(/"/,"",$3); print $3}')
   oci network nsg rules list --nsg-id "$FLEET_NSG" --direction EGRESS --all --query 'data[].{dest:destination,min:"tcp-options"."destination-port-range".min,max:"tcp-options"."destination-port-range".max}'
   ```

   Terraform view of one rule (use `fleet_egress_http` for port 80):

   ```
   terraform -chdir=terraform/envs/dev state show -no-color 'module.network.oci_core_network_security_group_security_rule.nsg_rules["fleet_egress_https"]'
   ```

2. The private route table sends `0.0.0.0/0` to the NAT Gateway. You also want the Oracle services rule to the Service Gateway.

   ```
   RT=$(terraform -chdir=terraform/envs/dev state show -no-color module.network.oci_core_route_table.private | awk '$1=="id" {gsub(/"/,"",$3); print $3}')
   oci network route-table get --rt-id "$RT" --query 'data."route-rules"[].{dest:destination,target:"network-entity-id"}'
   ```

   The target of `0.0.0.0/0` must start with `ocid1.natgateway`.

3. The NAT Gateway exists, its state is `AVAILABLE`, and `block_traffic` is false.

   ```
   NAT=$(terraform -chdir=terraform/envs/dev state show -no-color module.network.oci_core_nat_gateway.main | awk '$1=="id" {gsub(/"/,"",$3); print $3}')
   oci network nat-gateway get --nat-gateway-id "$NAT" --query 'data.{state:"lifecycle-state",block:"block-traffic"}'
   ```

   Terraform view: `terraform -chdir=terraform/envs/dev state show -no-color module.network.oci_core_nat_gateway.main | grep block_traffic`. If this command says the resource does not exist, the gateway was deleted.

4. Test from a fleet server. Load the key, then log in through the bastion:

   ```
   ssh-add ~/.ssh/gateway_lab
   BASTION=$(terraform -chdir=terraform/envs/dev output -raw bastion_public_ip)
   ssh -J opc@$BASTION opc@10.0.2.204 'curl --max-time 5 -s -o /dev/null -w "%{http_code}\n" https://www.oracle.com'
   ```

   You want `200`. A timeout means the path is broken. A timeout with checks 1 to 3 all correct points to something not listed here. Look at `git log --oneline -n 10 -- terraform`.

## Fix

Find the Terraform change that broke the path, and revert it. Never fix it in the console. That creates drift.

1. `git log --oneline -n 10 -- terraform`, then `git revert <commit>`.
2. Follow `runbooks/rollback-network-change.md` from the plan step.

Check 3 with `block_traffic` true is the simplest case. Drill 1 set it by Terraform, and the fix was one Terraform change.

Note on drill 2: the first run removed the Service Gateway route and nothing failed. Traffic to Object Storage fell back to the NAT Gateway. That was a gap. Decision 0011 closed it. Now Object Storage refuses requests that do not come through the Service Gateway. So if the Service Gateway route is removed, `/notes` fails with HTTP 502, and `/egress` still works. If you see `/notes` fail and `/egress` pass, check the Oracle services rule in check 2 first.

## Verify

1. The server test in check 4 prints `200`.
2. `pytest tests/integration` passes all 6 tests. `test_notes_saved` writes one small note.
3. If a server was stuck in cloud-init, it may need a replacement. Read the plan before you replace anything. See `runbooks/rollback-network-change.md`.

In drill 1, the tests passed again 11 seconds after the undo apply.

## Rollback

The fix is a revert commit. To undo it, run `git revert` on the revert commit. Then plan, check and apply as in `runbooks/rollback-network-change.md`.
