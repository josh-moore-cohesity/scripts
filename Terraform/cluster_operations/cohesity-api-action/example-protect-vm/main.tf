# End-to-end example: add an Azure VM to an existing Cohesity Protection
# Group, or create a new one if it doesn't exist yet -- mirroring
# https://github.com/bseltz-cohesity/scripts/blob/master/powershell/protectAzureVM/protectAzureVM.ps1
# (and its cohesity-api.ps1 helper), which is where every field name and
# endpoint below comes from. Earlier versions of this example guessed at
# Azure's schema; this one is built against that verified reference
# instead, which is why it looks substantially different.
#
# Lives under cohesity-api-action/, not cohesity-api-module/, because its
# final step (§6 below) is a mutating POST/PUT: the five read-only
# lookups (steps 1-4) still go through ../../cohesity-api-module (safe to
# re-run every plan/apply, since GET has no side effects), but the actual
# create/update goes through cohesity-api-action (this module's sibling,
# "../"), which fires exactly once and is tracked in state instead of
# re-sent on every apply. See ../README.md for why.
#
# Authenticated via a Helios-issued API key fetched from Azure Key Vault
# at runtime, matching ../../cohesity-api-module/example-helios/main.tf;
# see ../../cohesity-api-module/README.md ("Keeping the API key out of
# plaintext") for why.

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
  description = "Name of an existing Storage Domain (View Box). Only required if job_name doesn't match an existing group (i.e. you're creating a new one) AND policy_name is not a CloudArchiveDirect policy -- a CloudArchiveDirect policy's primary backup target is itself an archival target, so the cluster rejects a storageDomainId on the job and this value is ignored."
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

    Once set true, the actual create/update goes through
    cohesity-api-action (step 6 below), which only fires on the first
    apply (or when the resulting request body actually changes) --
    unlike the old cohesity-api-module-based version of this example,
    there's no need to flip this back to false after creating a new
    group to avoid a duplicate POST. Leaving it true permanently is safe.
  EOT
  type        = bool
  default     = false
}

# --- 1. Look up the registered Azure source's ID -------------------------
# v1 endpoint -- registrationInfo isn't part of the v2 API.
module "find_azure_source" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_endpoint          = "protectionSources/registrationInfo?environments=kAzure"
}

output "azure_source_lookup_raw" {
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output azure_source_lookup_raw`."
  value       = module.find_azure_source.response
  sensitive   = true
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
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/search/objects?environments=kAzure&azureObjectTypes=kVirtualMachine&sourceIds=${local.azure_source_id != null ? local.azure_source_id : ""}&searchString=${var.vm_name}"
}

output "vm_lookup_raw" {
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output vm_lookup_raw`."
  value       = module.find_vm.response
  sensitive   = true
}

locals {
  matched_vm   = one([for o in module.find_vm.response.objects : o if o.name == var.vm_name])
  vm_object_id = try(local.matched_vm.objectProtectionInfos[0].objectId, null)
}

# --- 3. Look up the protection group (job) by name ------------------------
# v2 endpoint. Fetches all groups and filters client-side, same as the
# reference script -- there's no per-name filter query param used here.
module "find_job" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/protection-groups"
}

output "job_lookup_raw" {
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output job_lookup_raw`."
  value       = module.find_job.response
  sensitive   = true
}

locals {
  existing_job = one([for j in module.find_job.response.protectionGroups : j if j.name == var.job_name])
  job_exists   = local.existing_job != null
}

# --- 4. Only needed when creating a NEW group: policy + storage domain ---
module "find_policy" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/policies"
}

output "policy_lookup_raw" {
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output policy_lookup_raw`."
  value       = module.find_policy.response
  sensitive   = true
}

module "find_viewbox" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_endpoint          = "viewBoxes" # still v1 -- confirmed unchanged in the reference script
}

output "viewbox_lookup_raw" {
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output viewbox_lookup_raw`."
  value       = module.find_viewbox.response
  sensitive   = true
}

locals {
  # The policy that actually governs this job: for an update, that's
  # whatever policyId the existing group already has (policy_name is
  # optional once the group exists -- see its variable description);
  # for a new group, it's the one looked up by name.
  governing_policy = local.job_exists ? one([
    for p in module.find_policy.response.policies : p if p.id == local.existing_job.policyId
    ]) : one([
    for p in module.find_policy.response.policies : p if p.name == var.policy_name
  ])

  policy_id = local.job_exists ? try(local.existing_job.policyId, null) : try(local.governing_policy.id, null)

  # A CloudArchiveDirect policy's primary backup target IS an archival
  # target (no local snapshot), which is why the cluster rejects a
  # storageDomainId on the job: there's no storage domain in the path.
  # Confirmed against a real policy via `policy_lookup_raw` -- targetType
  # "Archival" on primaryBackupTarget is the tell. Derived from the job's
  # OWN policy, not just var.policy_name, because the GET for an existing
  # job keeps returning a stale storageDomainId even after its policy
  # became CloudArchiveDirect -- see VMs-Azure-PS-Sub's lookup.
  is_cloud_archive_direct = try(local.governing_policy.backupPolicy.regular.primaryBackupTarget.targetType, "") == "Archival"

  viewbox_id = local.is_cloud_archive_direct ? null : one([for v in module.find_viewbox.response : v.id if v.name == var.storage_domain_name])
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

  # try(...) here is NOT extra insurance: merged_job_base is its own
  # local, evaluated every time regardless of job_exists, so when the
  # group doesn't exist yet local.existing_job is null and the attribute
  # accesses below error immediately -- burned by this exact thing
  # before (see git history on this file), now a third time from
  # pulling this merge out of the try()-wrapped ternary it used to live
  # inside. try() here, plus the one around updated_job_body below
  # (which would otherwise error iterating `for ... in null`), are both
  # required, not redundant.
  merged_job_base = try(merge(
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
  ), null)

  # local.existing_job (from the GET) still carries storageDomainId even
  # once the group's policy is CloudArchiveDirect -- merge() can only
  # override a key, not delete it, so drop it with a filtered for-expr
  # instead of merging in a null that would still send the key.
  updated_job_body = try(local.job_exists ? {
    for k, v in local.merged_job_base : k => v
    if !(local.is_cloud_archive_direct && k == "storageDomainId")
  } : null, null)

  # Path B: group doesn't exist -- build a fresh one, following the
  # reference script's $job hashtable field-for-field (defaults for
  # startTime/sla/qosPolicy/indexingPolicy copied from there, not guessed).
  new_job_body = merge(
    {
      name        = var.job_name
      environment = "kAzure"
      isPaused    = false
      policyId    = local.policy_id
      priority    = "kMedium"
      description = ""
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
    },
    # storageDomainId is omitted entirely (not set to null) for a
    # CloudArchiveDirect policy -- the cluster rejects the key being
    # present at all, not just a non-null value.
    local.is_cloud_archive_direct ? {} : { storageDomainId = local.viewbox_id }
  )
}

# --- 6. Apply: PUT to the existing group, or POST a new one --------------
# Through cohesity-api-action (this module's own sibling dir), not the
# find_* modules' cohesity-api-module -- so this fires once and is
# tracked in state, instead of re-sent on every apply. name is fixed per
# job_name regardless of PUT vs POST, since which path runs can change
# between applies (e.g. someone deletes the group on the cluster) and
# the response file should still land in the same place either way.
module "apply_job" {
  count  = var.apply_changes ? 1 : 0
  source = "../"

  name = "protect-vm-${var.job_name}"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = local.job_exists ? "data-protect/protection-groups/${try(local.existing_job.id, "")}" : "data-protect/protection-groups"
  http_method           = local.job_exists ? "PUT" : "POST"
  # jsonencode() each branch separately, rather than
  # jsonencode(cond ? a : b): Terraform's conditional operator requires
  # both branches to have the same *shape*, and the real existing job
  # object (returned by the cluster, with fields like advancedConfigs we
  # didn't include) will never structurally match our hand-built
  # new_job_body literal. Encoding first makes both branches plain
  # strings, which always unify.
  request_body = local.job_exists ? jsonencode(local.updated_job_body) : jsonencode(local.new_job_body)
}

output "apply_job_response" {
  description = "Cluster's response to the create/update call. Null until apply_changes = true."
  value       = try(module.apply_job[0].response, null)
}
