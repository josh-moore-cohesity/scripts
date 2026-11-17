# Cohesity Cluster Operations Using Terraform

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

This folder contains Terraform building blocks for operating an existing Cohesity cluster through its public REST API, directly or through Helios. Unlike the official [`cohesity/cohesity`](https://registry.terraform.io/providers/cohesity/cohesity/latest/docs) provider, which is resource-oriented, these modules expose a generic "call any API endpoint" pattern (the Terraform equivalent of `iris_cli`'s `api get/post/put`), so a new operation is usually a one-line change to `api_endpoint` rather than new provider code.

To deploy a new Cohesity Cloud Edition cluster in AWS, see [`../AWS/cluster_create`](../AWS/cluster_create) instead.

## Requirements

* Terraform 1.0 or later (1.4 or later for `cohesity-api-action`, which uses `terraform_data`)
* `bash`, `curl` and `jq` on the machine running `terraform plan/apply`
* HTTPS (443) reachability to the cluster VIP, or to `helios.cohesity.com` when using Helios
* An authentication method: username/password, a cluster API key, or a Helios API key (see the module README)
* For the runbook scenario: an Azure VM with a managed identity and an Azure Key Vault holding the Helios API key

## Components

* `cohesity-api-module` - issues a GET, POST or PUT call against the public API (v1 or v2) through an `external` data source. It re-runs on every `plan`/`apply`, so use it for reads (GET) and idempotent PUTs. Includes examples for direct cluster access, Helios, and listing Azure VM recovery points.
* `cohesity-api-action` - issues a POST or PUT call **exactly once**, tracked in Terraform state through `terraform_data`. Use it for genuine one-time creates, where a repeated POST would make a duplicate object. Includes examples for protecting an Azure VM, recovering an Azure VM and registering an Azure source.
* `RUNBOOK.md` - end-to-end runbook for running these modules from an Azure runner VM, with the Helios API key kept in Azure Key Vault so it never lands in Terraform variables or state.

## Choosing a Module

| You want to... | Use |
| --- | --- |
| Read cluster data (GET), or make an idempotent PUT | `cohesity-api-module` |
| Create something once (POST), such as protecting a VM or registering a source | `cohesity-api-action` |
| Recover a VM to a new location | `cohesity-api-action` |
| Set up the runner VM and Key Vault | `RUNBOOK.md` |

## Authentication Methods

Both modules authenticate with one of the following (set through `auth_method`):

| auth_method | Talks to | Needs |
| --- | --- | --- |
| `password` (default) | Cluster VIP directly | `username`, `password`, `domain` |
| `cluster_api_key` | Cluster VIP directly | `api_key` created in that cluster's UI |
| `helios_api_key` | Helios (proxied to the cluster) | Helios `api_key` and `access_cluster_id` |

## Usage

### Query a Cluster Through Helios

```
module "cohesity_cluster" {
  source = "./cohesity-api-module"

  auth_method       = "helios_api_key"
  api_key           = var.helios_api_key
  access_cluster_id = var.target_cluster_id
  api_endpoint      = "cluster"
}

output "cluster_name" {
  value = module.cohesity_cluster.response.name
}
```

### Run an Example

Each module has `example*` folders with a `terraform.tfvars.example`. Copy it to `terraform.tfvars`, edit it, then:

```
cd cohesity-api-module/example-helios
terraform init
terraform plan
terraform apply
```

The `cohesity-api-action` examples reference `cohesity-api-module` through relative paths (`../../cohesity-api-module`), so keep the two module folders side by side.

## Notes

* `cohesity-api-module` calls the API on every `plan` and `apply`. Do not use it for a POST that creates an object, or each refresh can create a duplicate. Use `cohesity-api-action` for that.
* The Helios API key is fetched at apply time by the shell script (for example from Azure Key Vault, per the runbook) and is not stored in Terraform variables or state.
* The scripts must be executable on the machine running Terraform (`chmod +x scripts/*.sh`).
* `RUNBOOK.md` marks which scenarios were confirmed working and which have not yet been exercised, so check it before relying on an example.
* These modules are a base to build on, not a finished product.

## Folder Layout

```
cluster_operations/
├── README.md
├── RUNBOOK.md
├── cohesity-api-module/
└── cohesity-api-action/
```
