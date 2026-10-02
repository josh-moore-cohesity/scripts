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
# Recovers the latest available snapshot by default, or the latest
# snapshot at or before restore_before if given (point-in-time
# recovery). Renaming the recovered VM (rename_prefix/rename_suffix
# below) is also supported -- needed since recovering to the original
# location with the original name while that VM still exists would
# otherwise collide with it.
#
# Endpoint/body verified against a local, live-cluster-tested script
# (recover_azure_vm.ps1) -- same source used for
# ../../cohesity-api-module/example-list-recovery-points, whose lookup
# steps this reuses.

terraform {
  # Stricter than cohesity-api-action's own >= 1.4 floor: restore_before
  # filtering below uses timecmp(), added in Terraform 1.6.
  required_version = ">= 1.6"
}

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
  description = "Name of the Azure VM to recover, exactly as it appears in Cohesity."
  type        = string
}

variable "restore_before" {
  description = <<-EOT
    Recover the latest snapshot taken at or before this time, instead
    of the overall latest snapshot (point-in-time recovery). Must be
    RFC3339 (e.g. "2026-08-30T14:00:00Z") -- Terraform's date functions
    only understand RFC3339, unlike the reference script's more
    flexible date parsing (e.g. "2026-08-30 14:00:00"), so reformat
    accordingly. Leave empty (default) to just use the latest snapshot.
  EOT
  type        = string
  default     = ""
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
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output vm_lookup_raw`."
  value       = module.find_vm.response
  sensitive   = true
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
  description = "sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output snapshot_lookup_raw`."
  value       = module.list_snapshots.response
  sensitive   = true
}

locals {
  snapshots = try(module.list_snapshots.response.snapshots, [])

  # If restore_before is set, narrow to snapshots at or before that
  # time before picking the latest -- gives point-in-time recovery.
  # Each snapshot's runStartTimeUsecs is converted to RFC3339 the same
  # way example-list-recovery-points converts it for display
  # (timeadd() from the Unix epoch), then compared with timecmp() --
  # hence this file's own required_version >= 1.6 above (stricter than
  # cohesity-api-action's >= 1.4 floor for terraform_data).
  # Verified this filtering logic against sample data (three cases:
  # no cutoff, cutoff mid-range, cutoff before every snapshot) via
  # `terraform apply` before wiring it in here.
  eligible_snapshots = var.restore_before != "" ? [
    for s in local.snapshots : s
    if timecmp(
      timeadd("1970-01-01T00:00:00Z", "${floor(s.runStartTimeUsecs / 1000000)}s"),
      var.restore_before
    ) <= 0
  ] : local.snapshots

  latest_run_time = length(local.eligible_snapshots) > 0 ? max([for s in local.eligible_snapshots : s.runStartTimeUsecs]...) : null
  latest_snapshot = local.latest_run_time != null ? one([for s in local.eligible_snapshots : s if s.runStartTimeUsecs == local.latest_run_time]) : null
  snapshot_id     = try(local.latest_snapshot.id, null)

  chosen_snapshot_time = local.latest_run_time != null ? formatdate(
    "YYYY-MM-DD hh:mm:ss 'UTC'",
    timeadd("1970-01-01T00:00:00Z", "${floor(local.latest_run_time / 1000000)}s")
  ) : null

  # The reference script omits renameRecoveredVmsParams entirely when
  # neither prefix nor suffix is given, rather than sending it empty.
  # Sending `null` here instead of omitting the key is NOT explicitly
  # verified against a live cluster the way the rest of this body is --
  # flag it if the API rejects a literal null instead of just ignoring
  # it. Don't take this on faith: ../example-protect-vm's new_job_body
  # used to set storageDomainId = null on this same assumption (explicit
  # null treated the same as absent), and a real cluster proved that
  # wrong for a CloudArchiveDirect-policy job -- it rejected the key
  # being present at all, null value or not. That field now omits the
  # key outright instead of relying on null; this one hasn't been
  # confirmed either way yet.
  rename_params = merge(
    var.rename_prefix != "" ? { prefix = var.rename_prefix } : {},
    var.rename_suffix != "" ? { suffix = var.rename_suffix } : {}
  )
}

output "chosen_snapshot" {
  description = "The snapshot that will actually be recovered -- its id and a readable UTC date/time. Null if no snapshot matched (VM not found, or restore_before is earlier than every available snapshot). Check this before setting apply_changes = true, especially when restore_before is set."
  value = {
    id   = local.snapshot_id
    time = local.chosen_snapshot_time
  }
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
