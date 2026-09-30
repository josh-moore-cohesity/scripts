# cohesity-api-module

A minimal Terraform module that authenticates to a Cohesity cluster (or via
Helios) and issues one GET, POST, or PUT call against Cohesity's public API
(v1 or v2) -- the Terraform equivalent of `iris_cli`'s `api get/post/put
cluster`. It's meant as a base to build on, not a finished product.

## Why this shape, instead of the `cohesity/cohesity` provider?

The official [`cohesity/cohesity`](https://registry.terraform.io/providers/cohesity/cohesity/latest/docs)
Terraform provider is resource-oriented (cluster creation, VMware protection
sources/jobs, etc.) -- it doesn't expose a generic "call any API endpoint"
resource or data source. To get a flexible `api get <endpoint>`-style
building block, this module instead wraps the auth + call sequence in a
shell script and drives it through Terraform's built-in
[`external` data source](https://registry.terraform.io/providers/hashicorp/external/latest/docs/data-sources/external).
That keeps everything in native Terraform (no extra provider plugin to
install), and any endpoint you can hit with `GET /irisservices/api/v1/public/...`
(or `/v2/...` -- see "API versions" below) becomes a one-line change
(`api_endpoint = "..."`).

## Requirements

- Terraform >= 1.0
- `bash`, `curl`, `jq` available on the machine running `terraform plan/apply`
- Network reachability to whichever endpoint you're calling (cluster VIP,
  or helios.cohesity.com) over HTTPS (443)

## Files

```
cohesity-api-module/
├── variables.tf              # auth_method + all auth inputs, api_endpoint, api_version, http_method, request_body, insecure
├── main.tf                   # external data source wiring
├── outputs.tf                # raw_response (string) and response (decoded object)
├── scripts/
│   └── cohesity_api.sh       # does the actual auth + GET/POST/PUT call, branches on auth_method
├── example/
│   ├── main.tf                     # username/password against a cluster directly
│   └── terraform.tfvars.example
├── example-helios/
│   └── main.tf                     # Helios API key, proxied to a specific cluster
├── example-protect-vm/
│   ├── main.tf                     # add an Azure VM to an existing protection group (PUT) or create one (POST); v2 API, Helios API key
│   └── terraform.tfvars.example
└── example-list-recovery-points/
    ├── main.tf                     # list available recovery points/snapshots for an Azure VM; v2 API, Helios API key
    └── terraform.tfvars.example
```

## Auth methods

Set `auth_method` to one of:

| auth_method        | Talks to             | Needs                                   | Notes |
|---------------------|-----------------------|------------------------------------------|-------|
| `password` (default)| `cluster_vip` directly | `username`, `password`, `domain`         | POSTs `/accessTokens` first to get a session token |
| `cluster_api_key`    | `cluster_vip` directly | `api_key` (minted in that cluster's UI)  | No token exchange; `apiKey` header on every call |
| `helios_api_key`     | `helios_url` (Helios) | `api_key` (Helios-issued), `access_cluster_id` | No cluster VIP reachability needed; Helios proxies the call to the cluster identified by `access_cluster_id` via the `accessClusterId` header |

### Using an API key via Helios

```hcl
module "cohesity_cluster" {
  source = "./cohesity-api-module"

  auth_method       = "helios_api_key"
  api_key           = var.helios_api_key       # Helios-issued API key
  access_cluster_id = var.target_cluster_id    # clusterId Helios should proxy to
  api_endpoint      = "cluster"                # -> GET /irisservices/api/v1/public/cluster, proxied via Helios
}

output "cluster_name" {
  value = module.cohesity_cluster.response.name
}
```

Two things worth knowing:
- `access_cluster_id` is the cluster's **clusterId** (visible in the Helios
  UI or via `GET .../mcm/clusters/info`), not its VIP/IP -- Helios doesn't
  expose or need the VIP at all for this path.
- A Helios API key will **not** authenticate directly against a cluster VIP
  -- it only works through `helios_url`. If you want to hit a cluster
  directly with an API key, mint a cluster-local key and use
  `auth_method = "cluster_api_key"` instead.

### Keeping the API key out of plaintext

`sensitive = true` on `api_key` only suppresses it from CLI output/diffs --
it does **not** stop the value from being written into `terraform.tfstate`
in plaintext, since it's recorded as an input the `external` data source
received. Two ways to actually avoid plaintext exposure:

1. **Don't persist it anywhere -- pass it via an interactively-entered env
   var** for that one `apply`:

   ```powershell
   # PowerShell
   $secure = Read-Host -Prompt "Helios API key" -AsSecureString
   $env:TF_VAR_api_key = [System.Net.NetworkCredential]::new("", $secure).Password
   ```

   ```bash
   # bash (e.g. on the VM)
   read -s -p "Helios API key: " TF_VAR_api_key; export TF_VAR_api_key; echo
   ```

   This keeps it out of `.tfvars` files and shell history, but it will
   still land in state -- see the state notes below.

2. **Keep it out of Terraform entirely -- fetch it from Azure Key Vault
   inside the script instead.** Leave `api_key` unset and set
   `key_vault_name` + `key_vault_secret_name`; `scripts/cohesity_api.sh`
   will call `az keyvault secret show` at run time and use the result only
   in memory for that process. Terraform never sees the value, so it never
   ends up in state:

   ```hcl
   module "cohesity_cluster" {
     source = "./cohesity-api-module"

     auth_method            = "helios_api_key"
     key_vault_name          = "my-keyvault"
     key_vault_secret_name   = "helios-api-key"
     access_cluster_id       = var.target_cluster_id
   }
   ```

   Requires the Azure CLI to be logged in wherever `terraform apply` runs.
   On the Azure VM, the clean way to do that without a human typing
   credentials is a managed identity: assign the VM a system-assigned
   identity, grant it the **Key Vault Secrets User** role on the vault,
   then `az login --identity` once per session before running Terraform.

Run it:

```bash
cd example-helios
export TF_VAR_helios_api_key="..."
export TF_VAR_target_cluster_id="1234567890123456"
terraform init
terraform apply
```

### Using username/password directly against a cluster (original base)

```bash
cd example
export TF_VAR_cluster_vip="10.2.45.143"
export TF_VAR_cluster_username="myuser"
export TF_VAR_cluster_password="mypassword"
terraform init
terraform apply
```

`terraform apply` will print the cluster name and software version pulled
straight from the API, confirming auth + connectivity end to end -- for
whichever auth path you chose.

## API versions (v1 vs v2)

By default `api_endpoint` is resolved against the classic v1 public API:
`/irisservices/api/v1/public/<api_endpoint>`. Some newer functionality
(e.g. `data-protect/protection-groups`, `data-protect/policies`,
`data-protect/search/objects` -- what `example-protect-vm/` uses to
manage Azure VM protection) only exists in Cohesity's **v2** API, which
lives at a genuinely different base path: `/v2/<api_endpoint>` -- no
`/irisservices/api` prefix, no `/public/` segment. Set `api_version = "v2"`
to switch:

```hcl
module "list_protection_groups" {
  source       = "./cohesity-api-module"
  auth_method  = "helios_api_key"
  api_key      = var.helios_api_key
  access_cluster_id = var.target_cluster_id
  api_version  = "v2"
  api_endpoint = "data-protect/protection-groups"
}
```

For `auth_method = "helios_api_key"`, the module sends both `apiKey` +
`accessClusterId` **and** `clusterId` headers (the latter added
specifically for v2 support) -- this matches the behavior of the
community [`cohesity-api.ps1`](https://github.com/bseltz-cohesity/scripts/blob/master/powershell/cohesity-api/cohesity-api.ps1)
helper's `heliosCluster` function, which sets both together whenever it
selects a Helios-managed cluster, for every call regardless of version.

**A handful of v1 endpoints live outside `/public/` entirely** (e.g.
`/backupsources`, used to register a new protection source -- see
`cohesity-api-action/example-register-azure-source`). Give `api_endpoint`
a leading slash to reach one of those (`api_endpoint = "/backupsources"`);
without one it goes through `/public/` as usual. This mirrors
`cohesity-api.ps1`'s own `api()` function, which applies the exact same
rule based on whether the given uri starts with `/`.

## GET, POST, and PUT calls

Set `http_method` (default `"GET"`) and, for POST/PUT, `request_body` (a
JSON string -- use `jsonencode({...})`):

```hcl
module "cohesity_view_update" {
  source = "./cohesity-api-module"

  auth_method  = "cluster_api_key"
  cluster_vip  = var.cluster_vip
  api_key      = var.cluster_api_key
  api_endpoint = "views/myView"
  http_method  = "PUT"
  request_body = jsonencode({
    qos = { principalName = "TestHigh" }
  })
}
```

**Read this before pointing a POST/PUT at anything real:** this module
drives the call through `data "external"`, which Terraform refreshes on
every `plan`/`apply` -- there's no create/read/update/delete lifecycle, no
tracking of whether the call already ran, and no diff to review beforehand.
That's harmless for GET, and fine for PUT against an endpoint whose body is
idempotent (re-sending the same update is a no-op). It's risky for POST
against a "create" endpoint, since each refresh can create another
duplicate object.

For real create-once semantics, use the sibling
[`cohesity-api-action`](../cohesity-api-action) module instead for that
specific call -- it wraps the same underlying script in a `terraform_data`
resource with a `local-exec` provisioner, so Terraform tracks it in state
and only fires the call once, showing a real `+ create` / `-/+ replace`
in `terraform plan` instead of silently re-running on every refresh. Keep
using this module (`cohesity-api-module`) for GET lookups and idempotent
PUTs; reach for `cohesity-api-action` specifically for one-time POSTs.

### Worked example: protecting an Azure VM

`example-protect-vm/` adds an Azure VM to an existing Cohesity Protection
Group (PUT), or creates a new one if it doesn't exist yet (POST) --
guarded behind an `apply_changes` variable so a first `apply` only runs
the read-only lookups. Like `example-helios/`, it authenticates with a
Helios-issued API key fetched from Azure Key Vault at runtime.

Unlike the VMware path (which has a dedicated, well-documented v1 lookup
endpoint), every endpoint and field name this example uses for Azure was
taken directly from the community
[`protectAzureVM.ps1`](https://github.com/bseltz-cohesity/scripts/blob/master/powershell/protectAzureVM/protectAzureVM.ps1)
script (and its `cohesity-api.ps1` helper) rather than guessed -- it's
what led to adding `api_version = "v2"` support (see above), since Azure
protection groups, policies, and object search all live in the v2 API.

```bash
cd example-protect-vm
export TF_VAR_target_cluster_id="1234567890123456"
terraform init
terraform apply     # apply_changes defaults to false -- lookups only

# Inspect azure_source_lookup_raw / vm_lookup_raw / job_lookup_raw
# (and policy_lookup_raw / viewbox_lookup_raw, if creating a new group)
# to confirm the right source/VM/group were found, then:
terraform apply -var="apply_changes=true"
```

Adding to an **existing** group is a PUT (idempotent -- safe to leave
`apply_changes = true` permanently). Creating a **new** group is a POST
(not idempotent -- flip `apply_changes` back to `false` after the one
apply that creates it, same caution as everywhere else in this module).

**Confirmed working** against a real cluster: adding an Azure VM to an
existing protection group via this example's PUT path. The create-new-group
(POST) path uses the same verified field names but hasn't been exercised
against a real cluster yet.

If you hit `Error: Inconsistent conditional result types` from
`request_body`, that's a reminder the module's own copy is stale --
`jsonencode()` needs to wrap each branch of that ternary separately (the
real existing-job object and the hand-built new-job object have different
shapes, so encoding the raw ternary first fails Terraform's type
unification check). Pull the latest `example-protect-vm/main.tf`.

### Worked example: listing recovery points for an Azure VM

`example-list-recovery-points/` looks up a specific Azure VM's Cohesity
object ID (`data-protect/search/protected-objects`, v2), then lists its
available snapshots (`data-protect/objects/<id>/snapshots`, v2) -- purely
read-only, so unlike `example-protect-vm/` there's no guard variable
needed; both calls are safe GETs on every `plan`/`apply`.

```bash
cd example-list-recovery-points
export TF_VAR_target_cluster_id="1234567890123456"
export TF_VAR_vm_name="my-vm-01"
terraform init
terraform apply

terraform output recovery_points        # simplified: [{id, runStartTimeUsecs}, ...]
terraform output recovery_points_raw    # full response, if you need more fields
```

Endpoints and field names came from a live-cluster-verified local
script, not the community repo used elsewhere in this README -- notably,
listing snapshots needs no `protectionGroupIds` filter or similar; a
plain `GET .../objects/<id>/snapshots` returns everything available for
that object.

## Extending this base

- **Different endpoint**: change `api_endpoint` (e.g. `"nodes"`, `"vaults"`,
  `"alerts"`) -- no code changes needed for any endpoint/method combination
  the script already supports.
- **Other HTTP methods** (DELETE, PATCH, ...): add them to the `validation`
  block on `http_method` in `variables.tf` and to the `case` statement in
  `scripts/cohesity_api.sh`.
- **Real TLS**: set `insecure = false` once the cluster presents a cert your
  CA trust store recognizes (Helios always presents a valid public cert,
  so `insecure` is a no-op for `auth_method = helios_api_key`).

## Security notes

- `password` and `api_key` are marked `sensitive` in `variables.tf`, but they
  still pass through the `external` data source's stdin and will appear in
  Terraform's state as part of the query object whenever they're set
  directly (Terraform sensitive-marks the value in CLI output, but state is
  plaintext by default). Prefer the Key Vault path above for `api_key` to
  avoid this entirely; for `password`, there's no equivalent built into this
  module yet, so at minimum use a remote backend with encryption at rest
  (e.g. Azure Storage backend, which encrypts by default) and restrict who
  can read the state file/blob.
- Prefer environment variables (`TF_VAR_...`) or a secrets manager data
  source over checked-in `.tfvars` files.
- This module is a starting point for internal tooling/automation, not a
  vetted, production-hardened artifact -- review it the way you'd review
  any other internal script before pointing it at a production cluster.
