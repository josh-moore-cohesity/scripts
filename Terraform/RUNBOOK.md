# Runbook: Cohesity Cluster Query via Helios + Terraform + Azure Key Vault

**Purpose:** Authenticate to a Cohesity cluster through Helios (API key,
proxied via `accessClusterId`) and run a basic read call (`GET
/irisservices/api/v1/public/cluster` — the Terraform equivalent of `iris_cli`'s
`api get cluster`), with the API key stored in Azure Key Vault rather than
in Terraform variables or state.

---

## 1. Architecture summary

```
Terraform (on runner VM)
  └─ module "cohesity_cluster"  (source: cohesity-api-module)
       └─ data "external"  →  scripts/cohesity_api.sh
              1. az login --identity            (VM's managed identity)
              2. az keyvault secret show        (fetch Helios API key)
              3. curl -H "apiKey: ..."
                      -H "accessClusterId: <clusterId>"
                      https://helios.cohesity.com/irisservices/api/v1/public/cluster
              4. Helios proxies the call to the target cluster and returns its response
```

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

---

## 6. Extending this base

To pull a different read-only endpoint, change one line in
`example-helios/main.tf`:

```hcl
api_endpoint = "nodes"      # or "vaults", "alerts", etc.
```

No other changes needed — re-run `terraform plan`/`apply`.

---

## 7. Troubleshooting log

| Symptom | Cause | Fix |
|---|---|---|
| `Caller is not authorized to perform action ... setSecret/action` | Vault uses RBAC auth; your account has no data-plane role on the vault yet | Grant yourself **Key Vault Secrets Officer** on the vault (§3.2), wait 1-2 min for propagation |
| `jq: command not found` (exit status 127) | `jq` not installed on the VM | `sudo apt-get install -y jq` (§4.1) |
| `Error: Failed to fetch secret ... from Key Vault` | Not logged in via `az login --identity`, or VM identity lacks **Key Vault Secrets User** role | Run `az login --identity`; re-check §3.5 role assignment |
| `program is not found` / script not found error from Terraform | `scripts/` subfolder missing or flattened during file transfer (e.g. multi-file zip download flattened paths) | Re-copy the module preserving directory structure; verify with `find <MODULE_PATH> -type f` (§4.2) |
| Script fails silently with no useful curl error | `-k`/insecure TLS not needed for Helios (valid public cert) — if you see TLS errors here, check `helios_url` is exactly `https://helios.cohesity.com` and not a cluster VIP | N/A — Helios API keys don't work against a cluster VIP directly |

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
