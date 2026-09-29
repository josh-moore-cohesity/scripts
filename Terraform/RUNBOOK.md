# Runbook: Cohesity Cluster Query via Helios + Terraform + Azure Key Vault

**Purpose:** Authenticate to a Cohesity cluster through Helios (API key,
proxied via `accessClusterId`) and run a call against the public API (`GET
/irisservices/api/v1/public/cluster` by default — the Terraform equivalent of
`iris_cli`'s `api get cluster` — or a POST/PUT against another endpoint), with
the API key stored in Azure Key Vault rather than in Terraform variables or
state.

---

## 1. Architecture summary

```
Terraform (on runner VM)
  └─ module "cohesity_cluster"  (source: cohesity-api-module)
       └─ data "external"  →  scripts/cohesity_api.sh
              1. az login --identity            (VM's managed identity)
              2. az keyvault secret show        (fetch Helios API key)
              3. curl -X <http_method> -H "apiKey: ..."
                      -H "accessClusterId: <clusterId>" -H "clusterId: <clusterId>"
                      [-d '<request_body>']
                      https://helios.cohesity.com/<v1 or v2 base path>/<api_endpoint>
              4. Helios proxies the call to the target cluster and returns its response
```

`http_method` defaults to `GET`; set it to `POST` or `PUT` (plus
`request_body`) to make a mutating call instead. See §6. `api_version`
defaults to `"v1"` (`/irisservices/api/v1/public/<api_endpoint>`); set it
to `"v2"` for endpoints that only exist there (`/v2/<api_endpoint>`, e.g.
`data-protect/protection-groups` -- see §9).

The API key never becomes a Terraform variable value or gets written to
`terraform.tfstate` — it's fetched fresh, in-memory, by the shell script at
apply time.

---

## 2. Environment reference (fill in for your setup)

| Item | Value |
|---|---|
| Azure subscription ID | `<SUBSCRIPTION_ID>` |
| Azure tenant ID | `<TENANT_ID>` |
| Resource group | `<RESOURCE_GROUP>` |
| Region | `<REGION>` |
| Key Vault name | `<VAULT_NAME>` |
| Secret name | `<SECRET_NAME>` (e.g. `helios-api-key`) |
| Terraform runner VM hostname | `<VM_HOSTNAME>` |
| Terraform runner VM public IP/FQDN | `<VM_ADDRESS>` |
| Terraform runner VM (Azure resource name) | `<VM_NAME>` — confirm with `az vm list -g <RESOURCE_GROUP> -o table` if unsure |
| SSH user on the VM | `<SSH_USER>` |
| Module path on VM | `<MODULE_PATH>` (e.g. `~/cohesity-api-module`) |
| Target cluster name | `<CLUSTER_NAME>` |
| Target cluster ID (`accessClusterId`) | `<CLUSTER_ID>` — from Helios UI or `GET .../mcm/clusters/info` |

Keep this table filled in and up to date for whichever environment you're
running against.

---

## 3. One-time setup: Azure Key Vault

Run these from PowerShell (or the VM — `az` works the same either way) with
an account that has Owner/Contributor on the subscription or resource
group.

### 3.1 Create the vault (RBAC authorization model)

```powershell
az keyvault create `
  --name <VAULT_NAME> `
  --resource-group <RESOURCE_GROUP> `
  --location <REGION> `
  --enable-rbac-authorization true
```

### 3.2 Give yourself write access to manage secrets

Vault RBAC is separate from subscription/RG RBAC — creating the vault does
**not** grant you secret read/write. Grant your own account the
**Key Vault Secrets Officer** role, scoped to just this vault:

```powershell
$VAULT_ID = az keyvault show --name <VAULT_NAME> --resource-group <RESOURCE_GROUP> --query id -o tsv

az role assignment create `
  --assignee <your-object-id-or-upn> `
  --role "Key Vault Secrets Officer" `
  --scope $VAULT_ID
```

> Wait 1-2 minutes for the role assignment to propagate before the next
> step, or you'll see:
> `Error: Caller is not authorized to perform action ... Action: 'Microsoft.KeyVault/vaults/secrets/setSecret/action'`

### 3.3 Store the Helios API key

Avoid typing the raw key on a command line (shell history, process list):

```powershell
$secure = Read-Host -Prompt "Helios API key" -AsSecureString
$plain = [System.Net.NetworkCredential]::new("", $secure).Password
az keyvault secret set --vault-name <VAULT_NAME> --name <SECRET_NAME> --value $plain
```

### 3.4 Give the VM a managed identity

```powershell
az vm identity assign --name <VM_NAME> --resource-group <RESOURCE_GROUP>
$PRINCIPAL_ID = az vm show --name <VM_NAME> --resource-group <RESOURCE_GROUP> --query identity.principalId -o tsv
```

### 3.5 Grant the VM's identity read-only access to the vault

Read-only is intentional: the VM only ever needs `secret show`, never
`secret set`.

```powershell
az role assignment create `
  --assignee $PRINCIPAL_ID `
  --role "Key Vault Secrets User" `
  --scope $VAULT_ID
```

### 3.6 Verify from the VM itself

```bash
ssh <SSH_USER>@<VM_ADDRESS>
az login --identity
az keyvault secret show --vault-name <VAULT_NAME> --name <SECRET_NAME> --query value -o tsv
```

Should print the key. If it errors with `Forbidden`, re-check step 3.5 and
give the role assignment another minute or two to propagate.

**Rotating the key later:** repeat step 3.3 with the new value under the
same secret name. Nothing else needs to change — Terraform fetches it fresh
on every `apply`.

---

## 4. One-time setup: the Terraform runner VM

### 4.1 Install prerequisites

```bash
sudo apt-get update && sudo apt-get install -y jq
which curl jq az terraform
```

All four must resolve. `curl`/`jq` are required for every run; `az` only
for the Key Vault path used here.

> If this VM isn't Debian/Ubuntu-based, use `sudo yum install -y jq` or
> `sudo dnf install -y jq` instead — check with `cat /etc/os-release` if
> unsure.

### 4.2 Get the module files onto the VM

From your local machine, in the directory containing `cohesity-api-module`:

```powershell
scp -r cohesity-api-module <SSH_USER>@<VM_ADDRESS>:<MODULE_PATH>
```

Confirm the structure landed intact (subfolders matter — a flat copy will
break the module):

```bash
find <MODULE_PATH> -type f
```

Expected:

```
cohesity-api-module/README.md
cohesity-api-module/main.tf
cohesity-api-module/outputs.tf
cohesity-api-module/variables.tf
cohesity-api-module/scripts/cohesity_api.sh
cohesity-api-module/example/main.tf
cohesity-api-module/example/terraform.tfvars.example
cohesity-api-module/example-helios/main.tf
cohesity-api-module/example-protect-vm/main.tf
cohesity-api-module/example-protect-vm/terraform.tfvars.example
```

### 4.3 Fix script permissions

`scp` from Windows doesn't preserve the Unix executable bit:

```bash
chmod +x <MODULE_PATH>/scripts/cohesity_api.sh
```

---

## 5. Every time: run Terraform

```bash
ssh <SSH_USER>@<VM_ADDRESS>
az login --identity

cd <MODULE_PATH>/example-helios

export TF_VAR_key_vault_name="<VAULT_NAME>"
export TF_VAR_key_vault_secret_name="<SECRET_NAME>"
export TF_VAR_target_cluster_id="<CLUSTER_ID>"

terraform init      # first time only, or after provider changes
terraform plan
terraform apply
```

### Expected successful output

```
Changes to Outputs:
  + cluster_name             = "<CLUSTER_NAME>"
  + cluster_software_version = "<SOFTWARE_VERSION>"
```

`terraform apply` (confirm with `yes`) writes these to state.

**If you've set `http_method` to `POST` or `PUT`:** read the plan output
carefully before typing `yes`. This module still runs the call through
`data "external"`, which Terraform refreshes on *every* `plan`/`apply` —
there's no create/read/update/delete lifecycle and no tracking of whether
the call already ran against this cluster. A `PUT` against an idempotent
endpoint (same body → same end state) is safe to re-run; a `POST` against a
"create" endpoint is not — each `apply` on this VM (including ones run by a
scheduled/automated job) will fire it again and can create duplicate
objects on the cluster.

---

## 6. Extending this base

**Different endpoint (still GET):** change one line in
`example-helios/main.tf`:

```hcl
api_endpoint = "nodes"      # or "vaults", "alerts", etc.
```

**POST/PUT calls:** set `http_method` and `request_body` in
`example-helios/main.tf`:

```hcl
api_endpoint = "views/myView"
http_method  = "PUT"
request_body = jsonencode({
  qos = { principalName = "TestHigh" }
})
```

Re-run `terraform plan`/`apply` — no other changes needed. See the
idempotency caution in §5 before running this against a real cluster,
especially on a VM with any scheduled/automated `apply`.

---

## 7. Troubleshooting log

| Symptom | Cause | Fix |
|---|---|---|
| `Caller is not authorized to perform action ... setSecret/action` | Vault uses RBAC auth; your account has no data-plane role on the vault yet | Grant yourself **Key Vault Secrets Officer** on the vault (§3.2), wait 1-2 min for propagation |
| `jq: command not found` (exit status 127) | `jq` not installed on the VM | `sudo apt-get install -y jq` (§4.1) |
| `Error: Failed to fetch secret ... from Key Vault` | Not logged in via `az login --identity`, or VM identity lacks **Key Vault Secrets User** role | Run `az login --identity`; re-check §3.5 role assignment |
| `program is not found` / script not found error from Terraform | `scripts/` subfolder missing or flattened during file transfer (e.g. multi-file zip download flattened paths) | Re-copy the module preserving directory structure; verify with `find <MODULE_PATH> -type f` (§4.2) |
| Script fails silently with no useful curl error | `-k`/insecure TLS not needed for Helios (valid public cert) — if you see TLS errors here, check `helios_url` is exactly `https://helios.cohesity.com` and not a cluster VIP | N/A — Helios API keys don't work against a cluster VIP directly |
| `Value for undeclared variable` on `terraform apply -var=... <planfile>` | `-var` combined with a saved plan file doesn't override anything — the plan already froze variable values at `plan` time, and this specific combination produces a misleading "not declared" error instead of a clearer one | Either bake the value in at plan time (`terraform plan -var="..." -out plan.out` then `terraform apply plan.out`, no `-var` on the apply step), or skip the saved-plan file and just run `terraform apply -var="..."` directly |
| `Error: Inconsistent conditional result types` pointing at a `jsonencode(cond ? a : b)` expression | Terraform's `?:` operator requires both branches to have the same *shape* before evaluating either one — two differently-shaped objects (e.g. a real API response vs. a hand-built literal) fail this check regardless of which branch would actually be selected | `jsonencode()` each branch separately (`cond ? jsonencode(a) : jsonencode(b)`) so the ternary only ever compares two strings, which always unify — see `example-protect-vm/main.tf` §9 |
| `data "external"` crashes even though the resource/module that would use the bad value has `count = 0` | `count = 0` stops a resource/module from being *created*, but does not stop Terraform from evaluating that block's own argument expressions — a common wrong assumption | Guard the value itself with `try(..., null)` (or similar), not just a `count` gate — don't rely on `count = 0` to skip evaluation |

---

## 8. Reference: variables used in `example-helios/main.tf`

| Variable | Source | Notes |
|---|---|---|
| `auth_method` | hardcoded `"helios_api_key"` in the example | |
| `api_key` | left unset | fetched from Key Vault instead |
| `key_vault_name` | `TF_VAR_key_vault_name` | |
| `key_vault_secret_name` | `TF_VAR_key_vault_secret_name` | |
| `access_cluster_id` | `TF_VAR_target_cluster_id` | this is the cluster's **clusterId**, not its VIP |
| `api_endpoint` | hardcoded `"cluster"` in the example | change to pull other endpoints |
| `http_method` | defaults to `"GET"` in the module | set to `"POST"` or `"PUT"` for a mutating call (§6) |
| `request_body` | defaults to `""` (unset) in the module | JSON string, required for POST/PUT; use `jsonencode({...})` |

---

## 9. Protecting an Azure VM (`example-protect-vm/`) -- confirmed working

Adds an Azure VM to an existing Cohesity Protection Group (PUT), or
creates a new one if `job_name` doesn't match one (POST). Every endpoint
and field name it uses was taken from the community
[`protectAzureVM.ps1`](https://github.com/bseltz-cohesity/scripts/blob/master/powershell/protectAzureVM/protectAzureVM.ps1)
script rather than guessed, because Azure protection groups/policies/object
search live in Cohesity's **v2** API (`api_version = "v2"`, §1), not v1.

```bash
ssh <SSH_USER>@<VM_ADDRESS>
az login --identity

cd <MODULE_PATH>/example-protect-vm

export TF_VAR_key_vault_name="<VAULT_NAME>"
export TF_VAR_key_vault_secret_name="<SECRET_NAME>"
export TF_VAR_target_cluster_id="<CLUSTER_ID>"

terraform init      # first time only

# Step 1: lookups only (apply_changes defaults to false) -- you'll be
# prompted for azure_source_name, job_name, vm_name if not exported.
terraform apply
```

Then check the lookup outputs before changing anything:

```bash
terraform output azure_source_lookup_raw
terraform output vm_lookup_raw
terraform output job_lookup_raw
```

Confirm: `vm_lookup_raw.objects` contains an entry named for your target
VM, and `job_lookup_raw.protectionGroups` contains an entry named for
your target group (if adding to an existing one).

**Note on `azure_source_name`:** this is the registered Azure *source's*
name in Cohesity (Protection > Sources), not the VM's -- and in practice
it may be a GUID-looking string (e.g. the Azure subscription ID) rather
than a friendly name, depending on how the source was registered. Check
`azure_source_lookup_raw` if unsure what to pass.

Once the lookups confirm the right source/VM/group, apply for real:

```bash
terraform plan -var="apply_changes=true" -out protectvm.out
# review the plan carefully, then:
terraform apply protectvm.out
```

Adding to an **existing** group (PUT) is idempotent -- safe to leave
`apply_changes = true` set afterward. Creating a **new** group (POST) is
not -- flip `apply_changes` back to `false` after the one apply that
creates it (same as §5's POST/PUT caution, generally).

---

## 10. Reference: variables used in `example-protect-vm/main.tf`

| Variable | Source | Notes |
|---|---|---|
| `auth_method` | hardcoded `"helios_api_key"` in the example | |
| `key_vault_name` | `TF_VAR_key_vault_name` | |
| `key_vault_secret_name` | `TF_VAR_key_vault_secret_name` | |
| `access_cluster_id` | `TF_VAR_target_cluster_id` | this is the cluster's **clusterId**, not its VIP |
| `azure_source_name` | `TF_VAR_azure_source_name` | the registered Azure *source's* name -- may be a GUID, see §9 |
| `vm_name` | `TF_VAR_vm_name` | exactly as it appears under that Azure source |
| `job_name` | `TF_VAR_job_name` | existing group to add the VM to, or a new group's name |
| `policy_name` | `TF_VAR_policy_name` (optional, default `""`) | only required when creating a **new** group |
| `storage_domain_name` | `TF_VAR_storage_domain_name` (optional, default `""`) | only required when creating a **new** group |
| `apply_changes` | defaults to `false` in the example | set `true` (via `-var`, not on a saved-plan `apply` -- see §7) to actually PUT/POST |
