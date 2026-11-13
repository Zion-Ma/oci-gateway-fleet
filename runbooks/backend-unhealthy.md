# Runbook: backend unhealthy

Use this when the alarm `gateway-lab-unhealthy-backend` fires. The alarm watches the metric `UnHealthyBackendServers` on the load balancer `fleet-lb`.

Run all commands from the repo root. Set these once:

```
source .venv/bin/activate
LB=$(terraform -chdir=terraform/envs/dev output -raw lb_id)
```

The virtual environment has the `oci` package that the integration tests need.

## Symptoms

- You got the alarm email.
- `test_whoami_covers_all_servers` fails. The other tests may still pass.
- If every server is down, `/health` through the load balancer fails too.

## Impact

The alarm value is the number of unhealthy servers. This fleet has 2 servers.

- Value 1: one server is down. The load balancer stops sending traffic to it after 3 failed health checks, 10 seconds apart. That is about 30 seconds. Users may see a few errors in that window. After that the app works on one server. Fix it soon, because there is no spare.
- Value 2: no server can answer. This is a full outage. Fix it first, before anything else.

## Checks

Do them in this order. Stop at the first check that finds the cause.

1. Find the unhealthy server. The names are in the lists as `IP:8000`.

   ```
   oci lb backend-set-health get --load-balancer-id "$LB" --backend-set-name fleet
   ```

   `status` is `OK` when all servers are healthy. Look at `critical-state-backend-names` and `warning-state-backend-names`. Match the IP to a server. The first IP is `fleet-1` and the second is `fleet-2`:

   ```
   terraform -chdir=terraform/envs/dev output fleet_private_ips
   ```

   For the detail of one server, use its name from the list:

   ```
   oci lb backend-health get --load-balancer-id "$LB" --backend-set-name fleet --backend-name 10.0.2.204:8000 --query 'data.status'
   ```

2. Log in through the bastion. Load the key into your agent first. The jump hop needs it.

   ```
   ssh-add ~/.ssh/gateway_lab
   BASTION=$(terraform -chdir=terraform/envs/dev output -raw bastion_public_ip)
   ssh -J opc@$BASTION opc@10.0.2.204
   ```

   If you cannot log in at all, the server may be stopped. Check its state. The ids are in the same order as the IPs. The state must be `RUNNING`:

   ```
   oci compute instance get --instance-id <id> --query 'data."lifecycle-state"'
   ```

   Get the ids with `terraform -chdir=terraform/envs/dev output fleet_instance_ids`.

3. On the server, check the service:

   ```
   systemctl status fleet-app --no-pager
   ```

   You want `active (running)`.

4. Read the last log lines:

   ```
   sudo journalctl -u fleet-app -n 50 --no-pager
   ```

   A healthy start ends with `app v6 listening on 8000`. The version number can differ.

5. Ask the app on the same server:

   ```
   curl -s --max-time 5 localhost:8000/health
   ```

   You want `{"status":"ok","version":"v6"}`. If this works, the app is fine and the problem is the path from the load balancer. Go to check 6.

6. Check the firewall on the server. It must list `8000/tcp`:

   ```
   sudo firewall-cmd --list-ports
   ```

7. Leave the server. Check that the fleet NSG allows port 8000 from the load balancer NSG. These two values must match: the `source` of the port 8000 rule, and `$LB_NSG`.

   ```
   FLEET_NSG=$(terraform -chdir=terraform/envs/dev state show -no-color module.network.oci_core_network_security_group.fleet | awk '$1=="id" {gsub(/"/,"",$3); print $3}')
   LB_NSG=$(terraform -chdir=terraform/envs/dev state show -no-color module.network.oci_core_network_security_group.lb | awk '$1=="id" {gsub(/"/,"",$3); print $3}')
   oci network nsg rules list --nsg-id "$FLEET_NSG" --direction INGRESS --all --query 'data[].{source:source,port:"tcp-options"."destination-port-range".min}'
   echo "$LB_NSG"
   ```

   If the port 8000 rule is missing, this is the same fault as drill 3. Both servers go unhealthy together.

## Fix

- Service stopped or crashed (checks 3 and 4): on the server, run `sudo systemctl restart fleet-app`. Then run check 5.
- Firewall rule missing (check 6): on the server, run `sudo firewall-cmd --permanent --add-port=8000/tcp` and then `sudo firewall-cmd --reload`. These are the same commands cloud-init runs.
- NSG rule missing (check 7): restore it in Terraform. Never fix a rule by clicking in the console. That creates drift, and the next apply will undo your change.
  1. Find the commit that removed the rule: `git log --oneline -n 10 -- terraform`.
  2. Revert it: `git revert <commit>`.
  3. Follow `runbooks/rollback-network-change.md` from the plan step. It covers the plan, the plan checker and the apply.
- Server stopped: start it with `oci compute instance action --action START --instance-id <id>`. The app starts by itself on boot.

## Verify

1. The set is healthy. `status` must be `OK` and both name lists must be empty:

   ```
   oci lb backend-set-health get --load-balancer-id "$LB" --backend-set-name fleet
   ```

2. Run the integration tests. All 6 must pass. `test_notes_saved` writes one small note.

   ```
   pytest tests/integration
   ```

3. Wait for the alarm to clear. In the drills the tests passed again 46 to 61 seconds after the fix, because the load balancer needs several good health checks first. The alarm uses 1 minute windows, so it can take a few more minutes to clear.

## Rollback

- A service restart has nothing to undo.
- If you applied a revert and it made things worse, revert the revert: `git revert <revert commit>`. Then plan, check and apply as in `runbooks/rollback-network-change.md`.
