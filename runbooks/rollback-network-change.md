# Runbook: roll back a network change

Use this after a `terraform apply` changed the network, and you want to undo it. Other runbooks send you here for the plan, check and apply steps.

Run all commands from the repo root. Run `source .venv/bin/activate` first. The tests need the `oci` package in it. Terraform reads `dev.tfvars` from `terraform/envs/dev`.

## Symptoms

- Integration tests fail right after an apply, or
- the alarm `gateway-lab-unhealthy-backend` fires right after an apply.

## Impact

Depends on the change. Drills on this fleet showed:

- NAT Gateway blocked: only `/egress` fails.
- Oracle services route removed: `/notes` fails with HTTP 502.
- Fleet NSG rule for port 8000 removed: the whole app fails.

## Checks

1. Find the change. List the last commits that touched Terraform:

   ```
   git log --oneline -n 10 -- terraform
   git show --stat <commit>
   ```

   The commit that matches the time of the apply is the likely one.

2. Read what the last plan was. Check the file date first. `plan.bin` is not in git. It can be an old plan from a drill, and it is not proof of the last apply.

   ```
   ls -l terraform/envs/dev/plan.bin
   terraform -chdir=terraform/envs/dev show -no-color plan.bin
   ```

   If the date does not match the apply, ignore the file. The new plan in the Fix section shows the facts you need.

3. Confirm the cause with the other runbooks: `runbooks/backend-unhealthy.md` or `runbooks/lost-egress.md`.

## Fix

1. Revert the bad commit. This makes a new commit and keeps the history:

   ```
   git revert <commit>
   ```

2. Make a plan file:

   ```
   terraform -chdir=terraform/envs/dev plan -var-file=dev.tfvars -out=plan.bin
   ```

   Read the summary. It must show only what the bad commit changed, turned back. If it shows other changes, stop and find out why.

3. Check the plan with the plan checker:

   ```
   terraform -chdir=terraform/envs/dev show -json plan.bin > terraform/envs/dev/plan.json
   python3 tools/plan_checker.py terraform/envs/dev/plan.json
   ```

   Exit code 0 means safe. Exit code 1 prints `BLOCKED:` lines.

4. If the checker blocks the plan, decide about `--allow-destroy`. During a rollback this can be correct, because the revert may delete what the bad change created. It is acceptable only when every `BLOCKED:` line names a resource that the bad commit added or changed. Check each line against `git show <commit>`. Do not use the flag if a line names something that existed before the bad commit. Then run:

   ```
   python3 tools/plan_checker.py terraform/envs/dev/plan.json --allow-destroy
   ```

   The flag never allows opening port 22 to `0.0.0.0/0`. That is always blocked.

5. Apply the plan file, not a new plan:

   ```
   terraform -chdir=terraform/envs/dev apply plan.bin
   ```

6. Run the integration tests. All 6 must pass:

   ```
   pytest tests/integration
   ```

   `test_notes_saved` writes one small note.

## Verify

- The 6 integration tests pass.
- `oci lb backend-set-health get --load-balancer-id "$(terraform -chdir=terraform/envs/dev output -raw lb_id)" --backend-set-name fleet` shows `status` `OK`.
- Wait for the alarm to clear. In the drills, tests passed again 11 to 46 seconds after the undo apply.

## Rollback

This runbook is itself a rollback. If the revert made things worse, revert the revert commit and go through the same steps again.

What a revert cannot undo:

- A replaced server. If the bad plan said `must be replaced`, the server was destroyed and a new one was made. The new server has a new ID and a new private IP. It loses its disk. The old ID and IP do not return, even if you revert. This is fine here because the app keeps no data on the server. Notes are in Object Storage. The load balancer backend follows the new IP.
- The app version on a replaced server. A rolling release sets the version in a file on the server. A new server starts with `app_version` from Terraform, which is `v1` unless set. After a replacement, check the version with `curl localhost:8000/health` on the server. Then run `tools/rolling_update.py --version <current version>` to bring it to the current version.
- Time. Users saw errors while the fault lasted. A revert does not change that.

The plan checker does not block a replaced server. It guards gateways, subnets, the VCN, security rules and route rules. Always read the plan summary for `replaced` before you apply.
