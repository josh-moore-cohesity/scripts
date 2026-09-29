# End-to-end example: look up a VM's protection source object, an existing
# protection policy, and a storage domain, then create a Cohesity
# protection job that protects it -- authenticated via a Helios-issued API
# key, proxied to the target cluster via access_cluster_id, matching
# ../example-helios/main.tf. Leave api_key unset and use Key Vault (as
# here) so the raw key never touches a Terraform variable or state file;
# see ../README.md ("Keeping the API key out of plaintext") for why.
#
# See ../README.md ("GET, POST, and PUT calls") for background on why the
# create step below is guarded behind a variable instead of running
# unconditionally -- this module drives every call through a
# `data "external"` source, which Terraform re-evaluates on every
# plan/apply, and POST is not idempotent.

variable "target_cluster_id" {
  description = "clusterId of the registered cluster you want Helios to proxy calls to (from Helios UI or GET .../mcm/clusters/info)."
  type        = string
}

variable "key_vault_name" {
  description = "Azure Key Vault holding the Helios API key."
  type        = string
}

variable "key_vault_secret_name" {
  description = "Secret name in that vault."
  type        = string
  default     = "helios-api-key"
}

variable "vm_name" {
  description = "Name of the VM to protect, exactly as it appears in vCenter/the cluster's source tree."
  type        = string
}

variable "policy_name" {
  description = "Name of an existing Protection Policy to assign to the new job."
  type        = string
}

variable "storage_domain_name" {
  description = "Name of an existing Storage Domain (View Box) for the job to write backups to."
  type        = string
}

variable "create_job" {
  description = <<-EOT
    Set to true to actually create the protection job. Defaults to false
    so a first `terraform apply` only does the read-only lookups below --
    check `vm_lookup_raw`, `policy_lookup_raw`, and `viewbox_lookup_raw`
    first to confirm the right VM/policy/storage domain were found.

    The create call is a POST, which is NOT idempotent: re-running
    `terraform apply` with this left at true would create a duplicate job
    every time, since the external data source refreshes on every
    plan/apply. Flip this to true, apply once, then flip it back to false.
  EOT
  type    = bool
  default = false
}

# --- 1. Look up the VM's source object ------------------------------------
module "find_vm" {
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_endpoint           = "protectionSources/virtualMachines?vmName=${var.vm_name}"
}

output "vm_lookup_raw" {
  description = "Full raw response from the VM lookup. The response shape (VmDocument layout) varies a bit by cluster software version -- inspect this before trusting local.vm_entity's field path below on an unfamiliar cluster."
  value       = module.find_vm.response
}

# --- 2. Look up the protection policy and storage domain ------------------
module "find_policy" {
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_endpoint           = "protectionPolicies"
}

output "policy_lookup_raw" {
  value = module.find_policy.response
}

module "find_viewbox" {
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_endpoint           = "viewBoxes"
}

output "viewbox_lookup_raw" {
  value = module.find_viewbox.response
}

# --- 3. Pull the IDs out of those responses --------------------------------
#
# find_policy/find_viewbox responses are simple lists of {id, name, ...} --
# safe to filter directly. `one(...)` deliberately errors out if the name
# doesn't match exactly one policy/storage domain, instead of silently
# protecting the VM with the wrong one.
locals {
  vm_entity  = module.find_vm.response[0].vmDocument.objectId.entity
  policy_id  = one([for p in module.find_policy.response : p.id if p.name == var.policy_name])
  viewbox_id = one([for v in module.find_viewbox.response : v.id if v.name == var.storage_domain_name])
}

# --- 4. Create the protection job (guarded by create_job) ------------------
module "protect_vm" {
  count  = var.create_job ? 1 : 0
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_endpoint           = "protectionJobs"
  http_method            = "POST"
  request_body = jsonencode({
    name           = "Protect-${var.vm_name}"
    environment    = "kVMware"
    policyId       = local.policy_id
    viewBoxId      = local.viewbox_id
    parentSourceId = local.vm_entity.parentId
    sourceIds      = [local.vm_entity.id]
  })
}

output "protect_job_response" {
  description = "Cluster's response to the protectionJobs create call. Null until create_job = true."
  value       = try(module.protect_vm[0].response, null)
}
