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
  description = "Name of the Azure VM to protect, exactly as it appears in the cluster's registered source tree (Helios/cluster UI > Protection > Sources)."
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
#
# `protectionSources/virtualMachines` (used in an earlier version of this
# example) is a VMware-only convenience endpoint -- it will not find an
# Azure-hosted VM. For Azure, the generic `protectionSources` endpoint
# (filtered to the Azure environment) is the right one: it returns the
# registered source tree (subscription -> resource group -> VM, roughly),
# which you then have to search for the VM by name yourself.
#
# I don't have verified confidence in the exact nested field names Azure
# entities use in this tree the way I do for VMware's dedicated endpoint --
# rather than guess and hand you a fabricated `local.vm_entity` extraction,
# this stops here at the raw response. Run `terraform apply` (create_job
# stays false), inspect `vm_lookup_raw` below for the node matching
# var.vm_name, and share its shape so step 3 can be filled in against your
# cluster's real output instead of a guess.
module "find_vm" {
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_endpoint           = "protectionSources?environments=kAzure"
}

output "vm_lookup_raw" {
  description = "Full raw registered-source tree for the Azure environment. Find the node for var.vm_name in here and use its shape to fill in local.vm_entity in step 3."
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
#
# vm_entity is left null for now -- see the comment on module.find_vm
# above. TODO: once you've inspected vm_lookup_raw and found the VM's
# node, replace this with the real extraction, e.g. something like:
#   one([for n in module.find_vm.response : n.protectionSource
#         if n.protectionSource.name == var.vm_name])
# possibly with recursion into `.nodes` if the VM sits under a resource
# group rather than directly under the subscription. Left as plain `null`
# rather than guessed so a lookups-only plan (create_job = false) still
# completes instead of crashing on a wrong field path.
locals {
  vm_entity  = null # TODO: fill in from vm_lookup_raw -- see above
  policy_id  = one([for p in module.find_policy.response : p.id if p.name == var.policy_name])
  viewbox_id = one([for v in module.find_viewbox.response : v.id if v.name == var.storage_domain_name])
}

# --- 4. Create the protection job (guarded by create_job) ------------------
#
# environment = "kAzure" follows the same enum pattern as kVMware, but --
# like local.vm_entity above -- I haven't verified this exact string
# against a real protectionJobs create call for Azure. Confirm it (and
# the required body fields) once you can see a successful example, e.g.
# from creating an equivalent job by hand in the UI and then
# `GET protectionJobs/<that job's id>` to see the real shape Cohesity
# expects/returns for an Azure job.
#
# parentSourceId/sourceIds are wrapped in try(...) rather than accessed
# directly: `count = 0` on this module call does NOT stop Terraform from
# evaluating its argument expressions (that's a resource-level behavior,
# not a module-call one) -- so a null local.vm_entity crashed every plan,
# even with create_job = false. try(..., null)/try(..., []) makes this
# safe while vm_entity is still the null placeholder; once you fill in the
# real extraction in step 3, these will carry real values whenever
# create_job = true actually creates the job.
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
    environment    = "kAzure"
    policyId       = local.policy_id
    viewBoxId      = local.viewbox_id
    parentSourceId = try(local.vm_entity.parentId, null)
    sourceIds      = try([local.vm_entity.id], [])
  })
}

output "protect_job_response" {
  description = "Cluster's response to the protectionJobs create call. Null until create_job = true."
  value       = try(module.protect_vm[0].response, null)
}
