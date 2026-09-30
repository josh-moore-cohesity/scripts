# cohesity-api-action

A Terraform module that fires a POST or PUT call against the Cohesity API
**exactly once**, with a real resource lifecycle -- unlike
[`cohesity-api-module`](../cohesity-api-module), whose `data "external"`
source re-runs the call on every `plan`/`apply` with no tracking and no
diff to review. Use this one whenever a mutating call is a genuine
one-time "create" (a POST that would make a duplicate object if it fired
twice), not a repeatable "set this to this state" PUT.

## Why this exists

`cohesity-api-module`'s README has a whole section on this tradeoff: it
drives calls through a `data` source specifically to stay out of
Terraform's resource graph, which is fine for GET (and fine for PUT
against an idempotent endpoint), but risky for POST against a create
endpoint -- every `plan`/`apply` refresh is a real API call, with no
lifecycle stopping it from firing again.

This module fixes that by wrapping the call in `terraform_data` (built
into Terraform since 1.4) with a `local-exec` provisioner:

- **Unchanged config on a later `apply`** → no diff, the call does **not**
  refire. Same as any other resource that already exists.
- **Changed `api_endpoint`/`http_method`/`request_body`/auth target**
  (anything in `triggers_replace`) → shows up as a real `-/+ replace` in
  `terraform plan`, and only refires then.
- **Failed call** → the resource is left tainted; the next `apply` retries
  the create instead of silently doing nothing (or, worse, silently
  succeeding at nothing while the rest of your plan proceeds).

## The catch: capturing the response

`local-exec` provisioners can't return a value into the resource's own
attributes the way a real provider's create call would. To get the API
response back into Terraform outputs, the provisioner redirects the
script's stdout to a local file, and a companion `data "local_file"`
reads it back (`main.tf`/`outputs.tf`). That file lives under
`.terraform-cohesity-action/` in the **root** module's directory
(`path.root`, not `path.module`) -- add that path to `.gitignore`.

## Requirements

- **Terraform >= 1.4** (`terraform_data` doesn't exist before that --
  check with `terraform version` before pointing this at an older
  install; `cohesity-api-module` itself still only needs >= 1.0)
- `bash`, `curl`, `jq` (same as `cohesity-api-module`, whose
  `scripts/cohesity_api.sh` this module calls directly via a relative
  path -- keep this module as a sibling of `cohesity-api-module`, not
  moved independently)
- The `hashicorp/local` provider (for reading the response file back)

## Usage

```hcl
module "create_protection_group" {
  source = "../cohesity-api-action"

  name = "protect-vm-example01" # unique label -- becomes the response file's name

  auth_method            = "helios_api_key"
  key_vault_name         = "my-keyvault"
  key_vault_secret_name  = "helios-api-key"
  access_cluster_id      = var.target_cluster_id

  api_version  = "v2"
  api_endpoint = "data-protect/protection-groups"
  http_method  = "POST"
  request_body = jsonencode({
    name        = "example01"
    environment = "kAzure"
    # ...rest of the job body -- see ../cohesity-api-module/example-protect-vm/main.tf
  })
}

output "created_job" {
  value = module.create_protection_group.response
}
```

Run `terraform plan` first and read it: the **first** apply will show
`terraform_data.action` as `+ create` (this is when the call actually
fires). Every apply after that, with the same inputs, shows **no
changes** -- confirming the call really did only run once. If you need
to force a retry without changing anything else (e.g. after fixing an
unrelated cluster-side problem), bump `replace_trigger` to any new value.

### Endpoints outside `/public/` (v1 only)

Most v1 endpoints live under `/irisservices/api/v1/public/...`, but a
few (e.g. `/backupsources`, used to register a new protection source)
live outside `/public/` entirely. Give `api_endpoint` a leading slash to
reach one of those (e.g. `api_endpoint = "/backupsources"`); without a
leading slash it goes through `/public/` as usual. This mirrors the
community `cohesity-api.ps1` helper's own `api()` function, which
applies the same rule.

## Examples

- **`example/`** -- creates an Azure protection group (`data-protect/protection-groups`, v2), combining a `cohesity-api-module` lookup for the policy/storage-domain IDs with the one-time create here.
- **`example-register-azure-source/`** -- registers an Azure subscription as a Cohesity protection source (`POST /backupsources`, v1, outside `/public/`) -- every field verified against [`registerAzureSource.ps1`](https://github.com/bseltz-cohesity/scripts/blob/master/powershell/registerAzureSource/registerAzureSource.ps1) rather than guessed. Requires an Azure AD App Registration with a client secret already set up -- see the comments in that example's `main.tf`.
- **`example-recover-azure-vm/`** -- recovers an Azure VM to its original location, from either its latest snapshot or (via `restore_before`, an RFC3339 cutoff) the latest snapshot at or before a given point in time (`POST data-protect/recoveries`, v2), with optional renaming (`rename_prefix`/`rename_suffix`) to avoid colliding with the original VM if it still exists. Field names verified against a local, live-cluster-tested script -- recovering to a *new* location (different resource group/VNet/subscription/region/VM size) is a meaningfully more complex path from that same script, not attempted here. Requires Terraform >= 1.6 (`timecmp()`), stricter than this module's own >= 1.4 floor. Guarded by an `apply_changes` variable on top of this module's own tracking, since submitting a recovery has real cost/side effects. **Confirmed working** against a real cluster, including the `restore_before` point-in-time path.

## What this does NOT do

- **No automatic delete-on-destroy call.** `terraform destroy` removes
  the resource from state and deletes the local response file, but does
  **not** issue a DELETE against the cluster -- this module only supports
  POST/PUT (see `variables.tf`). The real-world object this created stays
  protected/created until you remove it yourself, same limitation
  `cohesity-api-module` has today.
- **State still records the request in plaintext**, same caveat as
  `cohesity-api-module` -- `triggers_replace` includes `password`/`api_key`
  if you passed them directly. Prefer the Key Vault path for `api_key`
  (see `cohesity-api-module`'s README).
- This is still a thin wrapper around a shell script, not a real
  provider -- if you outgrow this pattern (need real read/update/delete,
  or many resources of the same kind), a proper Terraform provider is
  the next step up, not another layer on top of this.
