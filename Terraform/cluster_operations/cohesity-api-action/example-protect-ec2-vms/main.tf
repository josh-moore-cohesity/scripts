# End-to-end example: add one or more AWS EC2 instances to a Cohesity
# Protection Group, or create the group if it doesn't exist yet --
# mirroring
# https://github.com/bseltz-cohesity/scripts/blob/master/powershell/protectEC2VMs/protectEC2VMs.ps1
# (and its cohesity-api.ps1 helper), which is where every field name and
# endpoint below comes from. Sibling of ../example-protect-vm (Azure) and
# built the same way; the differences from that example are:
#
#   - environment is kAWS / awsParams, not kAzure / azureParams
#   - takes a LIST of VMs (vm_names and/or vm_list_file), not just one --
#     one read-only search per VM, via for_each on the lookup module
#   - protection type is selectable (kNative / kAgent / kSnapshotManager),
#     as in the PowerShell script's -protectionType
#   - a new group takes start_time / time_zone / SLAs / qos_policy / paused
#     (the script's -startTime -timeZone -incrementalSlaMinutes
#     -fullSlaMinutes -qosPolicy -paused), and the script's standard
#     file-indexing exclusion list
#   - an existing group is only PUT if it has VMs to add; otherwise
#     nothing fires (see apply_job below)
#
# Lives under cohesity-api-action/, not cohesity-api-module/, because its
# final step (§6 below) is a mutating POST/PUT: the read-only lookups
# (steps 1-4) go through ../../cohesity-api-module (safe to re-run every
# plan/apply, since GET has no side effects), but the actual create/update
# goes through cohesity-api-action (this module's sibling, "../"), which
# fires once and is tracked in state. See ../README.md for why.
#
# Authenticated via a Helios-issued API key fetched from Azure Key Vault
# at runtime, matching ../example-protect-vm; see
# ../../cohesity-api-module/README.md ("Keeping the API key out of
# plaintext") for why.
#
# NOT YET TESTED against a live cluster -- unlike example-protect-vm, which
# is confirmed working. Endpoints and body fields are taken from the
# reference script, but the v2 object-search response for EC2 (§2) is
# assumed to look like Azure's (objectProtectionInfos[0].objectId). Run with
# apply_changes = false first and check vm_lookup_raw before turning it on.

terraform {
  required_version = ">= 1.5" # check {} blocks; cohesity-api-action itself needs >= 1.4
}

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

variable "aws_source_name" {
  description = "Name of the registered AWS protection source in Cohesity (Helios/cluster UI > Protection > Sources), used to scope the VM search -- this is the registered source's name, not an instance's. Same as the script's -sourceName."
  type        = string
}

variable "vm_names" {
  description = "EC2 instance names to protect, exactly as they appear under that AWS source in Cohesity (matched case-insensitively, like the script). Same as the script's -vmName. Combine with vm_list_file if you like; duplicates are removed."
  type        = list(string)
  default     = []
}

variable "vm_list_file" {
  description = "Optional path to a text file with one instance name per line (blank lines ignored). Same as the script's -vmList. Relative paths resolve against the directory you run terraform from."
  type        = string
  default     = ""
}

variable "job_name" {
  description = "Name of the Protection Group. If a group with this name already exists (kAWS), the VMs are merged into its existing object list (PUT) -- it must use the same registered source and keeps its own policy, schedule and protection type. If not, a new group is created (POST), which requires policy_name (and storage_domain_name unless the policy is CloudArchiveDirect). Same as the script's -jobName."
  type        = string
}

# --- New-group-only settings (ignored when job_name already exists) --------

variable "policy_name" {
  description = "Name of an existing Protection Policy. Only required if job_name doesn't match an existing group (i.e. you're creating a new one). Same as the script's -policyName."
  type        = string
  default     = ""
}

variable "storage_domain_name" {
  description = "Name of an existing Storage Domain (View Box). Only used for a NEW group. If the cluster has exactly one storage domain it is used regardless of this value (like the script). Ignored for a CloudArchiveDirect policy or when ngce = true. Same as the script's -storageDomainName."
  type        = string
  default     = "DefaultStorageDomain"
}

variable "ngce" {
  description = "Create the new group with no storage domain (the script's -ngce switch). A CloudArchiveDirect policy is detected automatically and treated the same way, so this is only needed to force it."
  type        = bool
  default     = false
}

variable "protection_type" {
  description = "kNative, kAgent or kSnapshotManager. Only used for a NEW group -- an existing group keeps its own. Same as the script's -protectionType."
  type        = string
  default     = "kNative"

  validation {
    condition     = contains(["kAgent", "kNative", "kSnapshotManager"], var.protection_type)
    error_message = "protection_type must be one of: kAgent, kNative, kSnapshotManager."
  }
}

variable "start_time" {
  description = "Daily start time, 24h HH:MM. Same as the script's -startTime."
  type        = string
  default     = "20:00"

  validation {
    condition     = can(regex("^([01]?[0-9]|2[0-3]):[0-5][0-9]$", var.start_time))
    error_message = "start_time must be HH:MM in 24-hour time, e.g. \"20:00\"."
  }
}

variable "time_zone" {
  description = "Time zone for start_time. Same as the script's -timeZone."
  type        = string
  default     = "America/New_York"
}

variable "full_sla_minutes" {
  description = "Full backup SLA in minutes. Same as the script's -fullSlaMinutes."
  type        = number
  default     = 120
}

variable "incremental_sla_minutes" {
  description = "Incremental backup SLA in minutes. Same as the script's -incrementalSlaMinutes."
  type        = number
  default     = 60
}

variable "qos_policy" {
  description = "kBackupHDD or kBackupSSD. Same as the script's -qosPolicy."
  type        = string
  default     = "kBackupHDD"

  validation {
    condition     = contains(["kBackupHDD", "kBackupSSD"], var.qos_policy)
    error_message = "qos_policy must be kBackupHDD or kBackupSSD."
  }
}

variable "paused" {
  description = "Create the new group paused. Same as the script's -paused switch."
  type        = bool
  default     = false
}

variable "apply_changes" {
  description = <<-EOT
    Set to true to actually create/update the protection group. Defaults
    to false so a first `terraform apply` only does the read-only lookups
    below -- check `vm_lookup_raw`, `aws_source_lookup_raw` and
    `job_lookup_raw` (and `planned_action`, `resolved_vms`,
    `vms_not_found`) first to confirm the right source/VMs/group were
    found.

    Once true, the create/update fires only when there is something to do:
    a new group, or an existing group missing at least one of the VMs.
    After that apply the group already contains them, so the next plan
    has nothing to add and does nothing -- leaving this true permanently
    is safe. (The cost: apply_job_response goes back to null on that next
    apply, since the tracked call is removed from state; no API call is
    made for that.)
  EOT
  type        = bool
  default     = false
}

# --- 1. Look up the registered AWS source's ID ---------------------------
# v1 endpoint -- registrationInfo isn't part of the v2 API.
module "find_aws_source" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_endpoint          = "protectionSources/registrationInfo?environments=kAWS"
}

output "aws_source_lookup_raw" {
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output aws_source_lookup_raw`."
  value       = module.find_aws_source.response
  sensitive   = true
}

locals {
  aws_source_id = one([
    for n in try(module.find_aws_source.response.rootNodes, []) : n.rootNode.id
    if lower(n.rootNode.name) == lower(var.aws_source_name)
  ])
}

# --- 2. Look up each VM's object ID under that source ---------------------
# v2 global object search, one call per VM. sourceIds scopes it to the AWS
# source found above; searchString is a substring match, so the exact
# (case-insensitive) name match happens client-side below. If
# aws_source_id came back null (name mismatch) the call still runs with an
# empty sourceIds filter -- check aws_source_lookup_raw first if this errors.
locals {
  vm_names_from_file = var.vm_list_file != "" ? [for l in split("\n", file(var.vm_list_file)) : trimspace(l)] : []
  vm_names           = distinct(compact(concat([for n in var.vm_names : trimspace(n)], local.vm_names_from_file)))
}

module "find_vm" {
  for_each = toset(local.vm_names)
  source   = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/search/objects?environments=kAWS&sourceIds=${local.aws_source_id != null ? local.aws_source_id : ""}&searchString=${urlencode(each.key)}"
}

output "vm_lookup_raw" {
  description = "Raw search response per requested VM name. sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output vm_lookup_raw`."
  value       = { for n, m in module.find_vm : n => m.response }
  sensitive   = true
}

locals {
  # Exact name matches per requested VM (the script's getObjectId is a
  # case-insensitive -eq on the name). Normally 0 or 1; >1 is ambiguous and
  # is refused rather than guessing which one was meant.
  vm_matches = {
    for n in local.vm_names : n => [
      for o in try(module.find_vm[n].response.objects, []) : o if lower(o.name) == lower(n)
    ]
  }

  vm_ids       = { for n, m in local.vm_matches : n => try(m[0].objectProtectionInfos[0].objectId, null) if length(m) == 1 }
  resolved_vms = { for n, id in local.vm_ids : n => id if id != null }

  vms_not_found = [for n in local.vm_names : n if !contains(keys(local.resolved_vms), n) && length(local.vm_matches[n]) == 0]
  vms_ambiguous = [for n in local.vm_names : n if length(local.vm_matches[n]) > 1]
}

output "resolved_vms" {
  description = "VM name -> Cohesity object ID, for every requested VM that was found."
  value       = local.resolved_vms
}

output "vms_not_found" {
  description = "Requested VMs that were not found under the AWS source (the script prints these as warnings and carries on without them)."
  value       = local.vms_not_found
}

check "vms_found" {
  assert {
    condition     = length(local.vms_not_found) == 0
    error_message = "VM(s) not found under AWS source '${var.aws_source_name}': ${join(", ", local.vms_not_found)}. They will be skipped."
  }
}

# --- 3. Look up the protection group (job) by name ------------------------
# v2 endpoint, scoped to kAWS like the script. Fetches all kAWS groups and
# filters by name client-side, same as the script.
module "find_job" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/protection-groups?environments=kAWS"
}

output "job_lookup_raw" {
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output job_lookup_raw`."
  value       = module.find_job.response
  sensitive   = true
}

locals {
  existing_job = one([for j in try(module.find_job.response.protectionGroups, []) : j if lower(j.name) == lower(var.job_name)])
  job_exists   = local.existing_job != null
}

# --- 4. Policy + storage domain (needed to create a NEW group) -----------
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
  api_endpoint          = "viewBoxes" # still v1 -- same as the script
}

output "viewbox_lookup_raw" {
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output viewbox_lookup_raw`."
  value       = module.find_viewbox.response
  sensitive   = true
}

locals {
  policies = try(module.find_policy.response.policies, [])

  # The policy that actually governs this job: for an update, whatever
  # policyId the existing group already has; for a new group, the one
  # looked up by name.
  governing_policy = local.job_exists ? one([
    for p in local.policies : p if p.id == local.existing_job.policyId
    ]) : one([
    for p in local.policies : p if p.name == var.policy_name
  ])

  policy_id = local.job_exists ? try(local.existing_job.policyId, null) : try(local.governing_policy.id, null)

  # A CloudArchiveDirect policy's primary backup target IS an archival
  # target (no local snapshot), so the cluster rejects a storageDomainId on
  # the job. Detected the same way as example-protect-vm (confirmed against
  # a real policy there); var.ngce just forces the same behaviour, like the
  # script's -ngce switch.
  is_cloud_archive_direct = try(local.governing_policy.backupPolicy.regular.primaryBackupTarget.targetType, "") == "Archival"
  skip_storage_domain     = var.ngce || local.is_cloud_archive_direct

  # Like the script: if the cluster has exactly one storage domain, use it
  # regardless of name; otherwise match storage_domain_name
  # case-insensitively.
  viewboxes = module.find_viewbox.response
  viewbox_id = local.skip_storage_domain ? null : (
    length(local.viewboxes) == 1 ? local.viewboxes[0].id :
    one([for v in local.viewboxes : v.id if lower(v.name) == lower(var.storage_domain_name)])
  )
}

# --- 5. Build the request body for whichever path applies -----------------

locals {
  # awsParams' nested key depends on the group's protectionType (the
  # script's $awsParamName table). An existing group keeps its own type;
  # a new group uses var.protection_type.
  aws_param_names = {
    kAgent           = "agentProtectionTypeParams"
    kNative          = "nativeProtectionTypeParams"
    kSnapshotManager = "snapshotManagerProtectionTypeParams"
  }
  protection_type = local.job_exists ? try(local.existing_job.awsParams.protectionType, var.protection_type) : var.protection_type
  aws_param_name  = local.aws_param_names[local.protection_type]

  existing_objects_raw = try(local.existing_job.awsParams[local.aws_param_name].objects, null)
  existing_objects     = local.existing_objects_raw == null ? [] : local.existing_objects_raw
  existing_object_ids  = [for o in local.existing_objects : tostring(o.id)]

  # The script refuses to touch a group that uses a different AWS source.
  existing_job_source_id = try(local.existing_job.awsParams[local.aws_param_name].sourceId, null)

  # Only the VMs not already in the group (the script's $existingObject check).
  vms_to_add = { for n, id in local.resolved_vms : n => id if !contains(local.existing_object_ids, tostring(id)) }
  vms_already_protected = [for n, id in local.resolved_vms : n if contains(local.existing_object_ids, tostring(id))]

  # Nothing to do for an existing group that already has every VM -- that's
  # what makes apply_changes = true safe to leave on (see its description).
  has_changes = local.job_exists ? length(local.vms_to_add) > 0 : true

  # Path A: group exists -- merge the new VMs into its current object list.
  # merge() is shallow in Terraform, so the nested objects are merged
  # explicitly at each level. The try() here is NOT extra insurance:
  # merged_job_base is evaluated every time regardless of job_exists, and
  # when the group doesn't exist local.existing_job is null and the
  # attribute accesses error immediately (same trap as example-protect-vm).
  merged_objects = concat(
    local.existing_objects,
    [for n, id in local.vms_to_add : { id = id, name = n }]
  )

  merged_job_base = try(merge(
    local.existing_job,
    {
      awsParams = merge(
        local.existing_job.awsParams,
        {
          (local.aws_param_name) = merge(
            local.existing_job.awsParams[local.aws_param_name],
            { objects = local.merged_objects }
          )
        }
      )
    }
  ), null)

  # The existing group (from the GET) can still carry a storageDomainId
  # after its policy became CloudArchiveDirect, and merge() can only
  # override a key, not delete it -- so drop it with a filtered for-expr.
  updated_job_body = try(local.job_exists ? {
    for k, v in local.merged_job_base : k => v
    if !(local.skip_storage_domain && k == "storageDomainId")
  } : null, null)

  # Path B: group doesn't exist -- build a fresh one, following the script's
  # $job hashtable field-for-field.
  new_job_body = merge(
    {
      name        = var.job_name
      policyId    = local.policy_id
      priority    = "kMedium"
      description = ""
      startTime = {
        hour     = tonumber(split(":", var.start_time)[0])
        minute   = tonumber(split(":", var.start_time)[1])
        timeZone = var.time_zone
      }
      alertPolicy = {
        backupRunStatus = ["kFailure"]
        alertTargets    = []
      }
      sla = [
        { backupRunType = "kFull", slaMinutes = var.full_sla_minutes },
        { backupRunType = "kIncremental", slaMinutes = var.incremental_sla_minutes },
      ]
      qosPolicy        = var.qos_policy
      abortInBlackouts = false
      isActive         = true
      isPaused         = var.paused
      environment      = "kAWS"
      permissions      = []
      missingEntities  = null
      awsParams = {
        protectionType = var.protection_type
        (local.aws_param_name) = {
          objects          = [for n, id in local.resolved_vms : { id = id, name = n }]
          excludeObjectIds = null
          vmTagIds         = null
          excludeVmTagIds  = null
          sourceId         = local.aws_source_id
          sourceName       = var.aws_source_name
          indexingPolicy = {
            enableIndexing = true
            includePaths   = ["/"]
            excludePaths = [
              "/$Recycle.Bin",
              "/Windows",
              "/Program Files",
              "/Program Files (x86)",
              "/ProgramData",
              "/System Volume Information",
              "/Users/*/AppData",
              "/Recovery",
              "/var",
              "/usr",
              "/sys",
              "/proc",
              "/lib",
              "/grub",
              "/grub2",
              "/opt",
              "/splunk",
            ]
          }
        }
      }
    },
    # storageDomainId is omitted entirely (not set to null) when there's no
    # storage domain -- the cluster rejects the key being present at all
    # (confirmed for CloudArchiveDirect in example-protect-vm). Unlike the
    # script, which sends an explicit null for -ngce.
    local.skip_storage_domain ? {} : { storageDomainId = local.viewbox_id }
  )
}

output "planned_action" {
  description = "What apply_changes = true would do right now."
  value = (
    !local.job_exists ? "create new protection group '${var.job_name}' with ${length(local.resolved_vms)} VM(s)" :
    length(local.vms_to_add) > 0 ? "update protection group '${var.job_name}': add ${join(", ", keys(local.vms_to_add))}" :
    "nothing -- protection group '${var.job_name}' already contains every VM that was found"
  )
}

output "vms_already_protected" {
  description = "Requested VMs that are already objects in the existing group (skipped, like the script)."
  value       = local.vms_already_protected
}

# --- 5b. Pre-flight: the script's hard "exit" conditions -----------------
# Only evaluated when apply_changes = true, so the lookup-only first pass
# can still finish and show you the *_lookup_raw outputs when something is
# wrong. apply_job depends on this, so a failed precondition stops the
# apply before any call is made.
resource "terraform_data" "preflight" {
  count = var.apply_changes ? 1 : 0

  lifecycle {
    precondition {
      condition     = length(local.vm_names) > 0
      error_message = "No VMs specified -- set vm_names and/or vm_list_file."
    }
    precondition {
      condition     = local.aws_source_id != null
      error_message = "AWS protection source '${var.aws_source_name}' not found. Check aws_source_lookup_raw."
    }
    precondition {
      condition     = length(local.vms_ambiguous) == 0
      error_message = "More than one object matched the name(s): ${join(", ", local.vms_ambiguous)}. Check vm_lookup_raw."
    }
    precondition {
      condition     = !local.job_exists || tostring(local.existing_job_source_id) == tostring(local.aws_source_id)
      error_message = "Protection job '${var.job_name}' uses a different registered AWS protection source."
    }
    precondition {
      condition     = local.job_exists || var.policy_name != ""
      error_message = "policy_name is required to create a new protection group."
    }
    precondition {
      condition     = local.job_exists || local.policy_id != null
      error_message = "Policy '${var.policy_name}' not found. Check policy_lookup_raw."
    }
    precondition {
      condition     = local.job_exists || local.skip_storage_domain || local.viewbox_id != null
      error_message = "Storage domain '${var.storage_domain_name}' not found. Check viewbox_lookup_raw."
    }
    precondition {
      condition     = local.job_exists || length(local.resolved_vms) > 0
      error_message = "None of the requested VMs were found, so there is nothing to put in a new protection group. Check vm_lookup_raw."
    }
  }
}

# --- 6. Apply: PUT to the existing group, or POST a new one --------------
# Through cohesity-api-action (this module's own sibling dir), not the
# find_* modules' cohesity-api-module -- so this fires once and is tracked
# in state, instead of re-sent on every apply. name is fixed per job_name
# regardless of PUT vs POST, since which path runs can change between
# applies (e.g. someone deletes the group on the cluster) and the response
# file should still land in the same place either way.
module "apply_job" {
  count  = var.apply_changes && local.has_changes ? 1 : 0
  source = "../"

  depends_on = [terraform_data.preflight]

  name = "protect-ec2-${var.job_name}"

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
  # object (returned by the cluster, with fields we didn't include) will
  # never structurally match our hand-built new_job_body literal. Encoding
  # first makes both branches plain strings, which always unify.
  request_body = local.job_exists ? jsonencode(local.updated_job_body) : jsonencode(local.new_job_body)
}

output "apply_job_response" {
  description = "Cluster's response to the create/update call. Null until apply_changes = true, and again once the group already contains every VM (see apply_changes)."
  value       = try(module.apply_job[0].response, null)
}
