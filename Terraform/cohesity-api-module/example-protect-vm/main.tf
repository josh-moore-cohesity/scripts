# End-to-end example: add an Azure VM to an existing Cohesity Protection
# Group, or create a new one if it doesn't exist yet -- mirroring
# https://github.com/bseltz-cohesity/scripts/blob/master/powershell/protectAzureVM/protectAzureVM.ps1
# (and its cohesity-api.ps1 helper), which is where every field name and
# endpoint below comes from. Earlier versions of this example guessed at
# Azure's schema; this one is built against that verified reference
# instead, which is why it looks substantially different.
#
# Authenticated via a Helios-issued API key fetched from Azure Key Vault
# at runtime, matching ../example-helios/main.tf; see ../README.md
# ("Keeping the API key out of plaintext") for why.
#
# See ../README.md ("GET, POST, and PUT calls") for background on why the
# mutating step at the bottom is guarded behind a variable instead of
# running unconditionally -- this module drives every call through a
# `data "external"` source, which Terraform re-evaluates on every
# plan/apply, and POST is not idempotent (PUT-ing the same membership list
# repeatedly is fine).

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

variable "azure_source_name" {
  description = "Name of the registered Azure protection source in Cohesity (Helios/cluster UI > Protection > Sources), used to scope the VM search -- this is the registered source's name, not the VM's."
  type        = string
}

variable "vm_name" {
  description = "Name of the Azure VM to protect, exactly as it appears under that Azure source in Cohesity."
  type        = string
}

variable "job_name" {
  description = "Name of the Protection Group to add the VM to. If a group with this name already exists, the VM is merged into its existing object list (PUT). If not, a new group is created with just this VM (POST) -- which requires policy_name and storage_domain_name to also be set."
  type        = string
}

variable "policy_name" {
  description = "Name of an existing Protection Policy. Only required if job_name doesn't match an existing group (i.e. you're creating a new one)."
  type        = string
  default     = ""
}

variable "storage_domain_name" {
  description = "Name of an existing Storage Domain (View Box). Only required if job_name doesn't match an existing group (i.e. you're creating a new one)."
  type        = string
  default     = ""
}

variable "apply_changes" {
  description = <<-EOT
    Set to true to actually create/update the protection group. Defaults
    to false so a first `terraform apply` only does the read-only lookups
    below -- check `azure_source_lookup_raw`, `vm_lookup_raw`, and
    `job_lookup_raw` first to confirm the right source/VM/group were
    found (and, for a new group, `policy_lookup_raw`/`viewbox_lookup_raw`).

    Adding to an EXISTING group is a PUT, which is idempotent -- safe to
    leave this true permanently once confirmed, since re-applying with
    the same VM already in the list is a no-op. Creating a NEW group is a
    POST, which is NOT idempotent -- flip this to true, apply once, then
    flip it back to false, or you'll get a duplicate-group error (or a
    second group) on the next apply.
  EOT
  type    = bool
  default = false
}

# --- 1. Look up the registered Azure source's ID -------------------------
# v1 endpoint -- registrationInfo isn't part of the v2 API.
module "find_azure_source" {
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_endpoint           = "protectionSources/registrationInfo?environments=kAzure"
}

output "azure_source_lookup_raw" {
  value = module.find_azure_source.response
}

locals {
  azure_source_id = one([
    for n in module.find_azure_source.response.rootNodes : n.rootNode.id
    if n.rootNode.name == var.azure_source_name
  ])
}

# --- 2. Look up the VM's object ID under that source ----------------------
# v2 global object search. sourceIds scopes the search to the Azure source
# found above -- if azure_source_id came back null (name mismatch), this
# call still runs with an empty sourceIds filter, which the cluster may
# reject; check azure_source_lookup_raw first if this errors.
module "find_vm" {
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_version            = "v2"
  api_endpoint           = "data-protect/search/objects?environments=kAzure&azureObjectTypes=kVirtualMachine&sourceIds=${local.azure_source_id != null ? local.azure_source_id : ""}&searchString=${var.vm_name}"
}

output "vm_lookup_raw" {
  value = module.find_vm.response
}

locals {
  matched_vm   = one([for o in module.find_vm.response.objects : o if o.name == var.vm_name])
  vm_object_id = try(local.matched_vm.objectProtectionInfos[0].objectId, null)
}

# --- 3. Look up the protection group (job) by name ------------------------
# v2 endpoint. Fetches all groups and filters client-side, same as the
# reference script -- there's no per-name filter query param used here.
module "find_job" {
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_version            = "v2"
  api_endpoint           = "data-protect/protection-groups"
}

output "job_lookup_raw" {
  value = module.find_job.response
}

locals {
  existing_job = one([for j in module.find_job.response.protectionGroups : j if j.name == var.job_name])
  job_exists   = local.existing_job != null
}

# --- 4. Only needed when creating a NEW group: policy + storage domain ---
module "find_policy" {
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_version            = "v2"
  api_endpoint           = "data-protect/policies"
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
  api_endpoint           = "viewBoxes" # still v1 -- confirmed unchanged in the reference script
}

output "viewbox_lookup_raw" {
  value = module.find_viewbox.response
}

locals {
  policy_id  = one([for p in module.find_policy.response.policies : p.id if p.name == var.policy_name])
  viewbox_id = one([for v in module.find_viewbox.response : v.id if v.name == var.storage_domain_name])
}

# --- 5. Build the request body for whichever path applies -----------------
#
# Path A: group exists -- merge the VM into its current object list. The
# nested key under azureParams (nativeProtectionTypeParams vs
# snapshotManagerProtectionTypeParams) depends on the group's own
# protectionType; `merge()` is shallow in Terraform, so the nested objects
# have to be merged explicitly at each level, unlike the reference
# script's simpler in-place PowerShell hashtable mutation.
locals {
  protection_type  = try(local.existing_job.azureParams.protectionType, "kNative")
  azure_param_name = local.protection_type == "kNative" ? "nativeProtectionTypeParams" : "snapshotManagerProtectionTypeParams"
  existing_objects = try(local.existing_job.azureParams[local.azure_param_name].objects, [])

  merged_objects = concat(
    [for o in local.existing_objects : o if try(o.id, null) != local.vm_object_id],
    local.vm_object_id != null ? [{ id = local.vm_object_id }] : []
  )

  # try(...) here is extra insurance, not strictly required: a plain
  # ternary should already skip the merge(...) branch when job_exists is
  # false, but this codebase has been burned twice already by wrong
  # assumptions about what Terraform evaluates unconditionally (see the
  # git history on this file), so the cheap defensive wrap stays.
  updated_job_body = try(local.job_exists ? merge(
    local.existing_job,
    {
      azureParams = merge(
        local.existing_job.azureParams,
        {
          (local.azure_param_name) = merge(
            local.existing_job.azureParams[local.azure_param_name],
            { objects = local.merged_objects }
          )
        }
      )
    }
  ) : null, null)

  # Path B: group doesn't exist -- build a fresh one, following the
  # reference script's $job hashtable field-for-field (defaults for
  # startTime/sla/qosPolicy/indexingPolicy copied from there, not guessed).
  new_job_body = {
    name             = var.job_name
    environment      = "kAzure"
    isPaused         = false
    policyId         = local.policy_id
    priority         = "kMedium"
    storageDomainId  = local.viewbox_id
    description      = ""
    startTime = {
      hour     = 20
      minute   = 0
      timeZone = "America/New_York"
    }
    abortInBlackouts = false
    alertPolicy = {
      backupRunStatus = ["kFailure"]
      alertTargets    = []
    }
    sla = [
      { backupRunType = "kFull", slaMinutes = 120 },
      { backupRunType = "kIncremental", slaMinutes = 60 },
    ]
    qosPolicy = "kBackupHDD"
    azureParams = {
      protectionType = "kNative"
      nativeProtectionTypeParams = {
        objects          = local.vm_object_id != null ? [{ id = local.vm_object_id }] : []
        excludeObjectIds = []
        vmTagIds         = []
        excludeVmTagIds  = []
        indexingPolicy = {
          enableIndexing = true
          includePaths   = ["/"]
          excludePaths   = []
        }
      }
    }
  }
}

# --- 6. Apply: PUT to the existing group, or POST a new one --------------
module "apply_job" {
  count  = var.apply_changes ? 1 : 0
  source = "../"

  auth_method            = "helios_api_key"
  key_vault_name         = var.key_vault_name
  key_vault_secret_name  = var.key_vault_secret_name
  access_cluster_id      = var.target_cluster_id
  api_version            = "v2"
  api_endpoint           = local.job_exists ? "data-protect/protection-groups/${try(local.existing_job.id, "")}" : "data-protect/protection-groups"
  http_method            = local.job_exists ? "PUT" : "POST"
  request_body           = jsonencode(local.job_exists ? local.updated_job_body : local.new_job_body)
}

output "apply_job_response" {
  description = "Cluster's response to the create/update call. Null until apply_changes = true."
  value       = try(module.apply_job[0].response, null)
}
