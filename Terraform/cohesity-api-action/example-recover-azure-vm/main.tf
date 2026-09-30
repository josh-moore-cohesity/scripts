# Recovers an Azure VM to its ORIGINAL location (resource group/VNet/
# subnet unchanged) from its latest snapshot -- a one-time "create a
# recovery task" POST, so the actual recovery call goes through
# cohesity-api-action (fires once, tracked in state) rather than
# cohesity-api-module. Recovering to a NEW location (different resource
# group/VNet/subscription/region/VM size) is a separate, meaningfully
# more complex path -- it requires walking the Azure protectionSources
# tree to resolve several IDs by name, and the private-endpoint data
# transfer variant is explicitly unverified even in the reference below.
# Not attempted here; ask for it separately if needed.
#
# Point-in-time recovery is out of scope for this first pass -- this
# always recovers the latest available snapshot. Renaming the recovered
# VM (rename_prefix/rename_suffix below) IS supported -- needed since
# recovering to the original location with the original name while that
# VM still exists would otherwise collide with it.
#
# Endpoint/body verified against a local, live-cluster-tested script
# (recover_azure_vm.ps1) -- same source used for
# ../../cohesity-api-module/example-list-recovery-points, whose lookup
# steps this reuses.

variable "target_cluster_id" {
  description = "clusterId of the registered cluster you want Helios to proxy calls to."
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
  description = "Name of the Azure VM to recover, exactly as it appears in Cohesity. Always recovers from the latest available snapshot."
  type        = string
}

variable "recovery_name" {
  description = <<-EOT
    Name for the recovery task. Required, with no default -- deliberately:
    a default built from timestamp() would change on every plan/apply,
    which would make cohesity-api-action's triggers_replace see a
    "changed" input and refire the recovery every time. Pick a stable
    name yourself instead.
  EOT
  type        = string
}

variable "power_on" {
  description = "Power on the recovered VM automatically. Defaults to false, matching the reference script's default (off)."
  type        = bool
  default     = false
}

variable "continue_on_error" {
  description = "Continue recovering remaining objects if one fails (only relevant if you extend this to recover more than one VM)."
  type        = bool
  default     = false
}

variable "rename_prefix" {
  description = "Prepended to the recovered VM's name (e.g. \"restored-\"). Leave both this and rename_suffix empty to keep the original name -- only sensible when recovering to a new location; recovering to the original location with the original name while that VM still exists will otherwise collide with it."
  type        = string
  default     = ""
}

variable "rename_suffix" {
  description = "Appended to the recovered VM's name (e.g. \"-restored\"). See rename_prefix."
  type        = string
  default     = ""
}

variable "apply_changes" {
  description = <<-EOT
    Set to true to actually submit the recovery. Defaults to false so a
    first `terraform apply` only runs the read-only lookups below --
    check `vm_lookup_raw` and `snapshot_lookup_raw` to confirm the right
    VM and snapshot were found before recovering anything.

    cohesity-api-action's own tracking already stops this from refiring
    on a later apply with the same inputs -- this variable is an extra,
    explicit confirmation step on top of that, since submitting a
    recovery has real cost/side effects (a new VM gets created) and
    shouldn't happen just because someone ran `terraform apply` to check
    the lookups.
  EOT
  type        = bool
  default     = false
}

# --- 1. Find the VM's Cohesity object ID (read-only, safe to repeat) -----
module "find_vm" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/search/protected-objects?searchString=${var.vm_name}&environments=kAzure"
}

output "vm_lookup_raw" {
  value = module.find_vm.response
}

locals {
  matched_object = one([for o in module.find_vm.response.objects : o if o.name == var.vm_name])
  object_id      = try(local.matched_object.id, null)
}

# --- 2. List its snapshots and pick the latest one ------------------------
module "list_snapshots" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/objects/${local.object_id != null ? local.object_id : 0}/snapshots"
}

output "snapshot_lookup_raw" {
  value = module.list_snapshots.response
}

locals {
  snapshots       = try(module.list_snapshots.response.snapshots, [])
  latest_run_time = length(local.snapshots) > 0 ? max([for s in local.snapshots : s.runStartTimeUsecs]...) : null
  latest_snapshot = local.latest_run_time != null ? one([for s in local.snapshots : s if s.runStartTimeUsecs == local.latest_run_time]) : null
  snapshot_id     = try(local.latest_snapshot.id, null)

  # The reference script omits renameRecoveredVmsParams entirely when
  # neither prefix nor suffix is given, rather than sending it empty.
  # Sending `null` here instead of omitting the key is NOT explicitly
  # verified against a live cluster the way the rest of this body is --
  # it's a reasonable bet (most REST APIs treat an explicit null on an
  # optional field the same as absent, and this codebase already relies
  # on that elsewhere, e.g. storageDomainId in example-protect-vm's
  # new_job_body), but flag it if the API rejects a literal null instead
  # of just ignoring it.
  rename_params = merge(
    var.rename_prefix != "" ? { prefix = var.rename_prefix } : {},
    var.rename_suffix != "" ? { suffix = var.rename_suffix } : {}
  )
}

# --- 3. Submit the recovery (guarded by apply_changes) --------------------
module "recover_vm" {
  count  = var.apply_changes ? 1 : 0
  source = "../"

  name = "recover-azure-vm-${var.recovery_name}"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id

  api_version  = "v2"
  api_endpoint = "data-protect/recoveries"
  http_method  = "POST"

  request_body = jsonencode({
    name                = var.recovery_name
    snapshotEnvironment = "kAzure"
    azureParams = {
      recoveryAction = "RecoverVMs"
      objects        = [{ snapshotId = local.snapshot_id }]
      recoverVmParams = {
        targetEnvironment = "kAzure"
        azureTargetParams = {
          continueOnError = var.continue_on_error
          powerOnVms      = var.power_on
          recoveryTargetConfig = {
            recoverToNewSource = false
          }
          renameRecoveredVmsParams = length(local.rename_params) > 0 ? local.rename_params : null
        }
      }
    }
  })
}

output "recovery_task" {
  description = "Cluster's response to the recovery create call, including its task id. Null until apply_changes = true."
  value       = try(module.recover_vm[0].response, null)
}
