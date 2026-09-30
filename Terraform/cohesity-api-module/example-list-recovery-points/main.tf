# Lists available recovery points (snapshots) for a specific Azure VM --
# read-only end to end, so this stays on cohesity-api-module (GET calls,
# safe to repeat on every plan/apply) rather than cohesity-api-action.
#
# Endpoints and field names verified against a local, live-cluster-tested
# script (recover_azure_vm.ps1), not guessed or carried over from the
# VMware-oriented community scripts used elsewhere in this repo:
#   1. GET -v2 "data-protect/search/protected-objects?searchString=<vm>&environments=kAzure"
#      -> { objects: [ { name, id, ... } ] }
#   2. GET -v2 "data-protect/objects/<id>/snapshots"
#      -> { snapshots: [ { id, runStartTimeUsecs, expiryTimeUsecs,
#           protectionGroupName, runType, snapshotTargetType, ... } ] }
# No protectionGroupIds filter needed on step 2 for this -- that's an
# optional narrowing param seen in other (VMware) reference scripts, not
# a requirement.
#
# Confirmed working against a real cluster (24+ recovery points listed
# for an Azure VM, spanning local and archival targets).

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
  description = "Name of the Azure VM to list recovery points for, exactly as it appears in Cohesity."
  type        = string
}

# --- 1. Find the protected object's Cohesity object ID -------------------
module "find_vm" {
  source = "../"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/search/protected-objects?searchString=${var.vm_name}&environments=kAzure"
}

output "vm_lookup_raw" {
  description = "Full raw response from the protected-object search. sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output vm_lookup_raw`."
  value       = module.find_vm.response
  sensitive   = true
}

locals {
  matched_object = one([for o in module.find_vm.response.objects : o if o.name == var.vm_name])
  object_id      = try(local.matched_object.id, null)
}

# --- 2. List that object's available recovery points ---------------------
# object_id falls back to 0 (a harmless placeholder, never a real id) when
# the VM wasn't found above -- avoids interpolating null into the URL,
# same pattern used elsewhere in this repo (e.g. example-protect-vm).
module "list_snapshots" {
  source = "../"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/objects/${local.object_id != null ? local.object_id : 0}/snapshots"
}

output "recovery_points_raw" {
  description = "Full raw response from the snapshots list call. sensitive = true purely to keep this out of the plan/apply diff (it's not secret) -- retrieve it explicitly with `terraform output recovery_points_raw`."
  value       = module.list_snapshots.response
  sensitive   = true
}

output "recovery_points" {
  description = "Object name, protection group, and snapshot date/time (UTC) for each available recovery point."
  value = try(
    [for s in module.list_snapshots.response.snapshots : {
      objectName          = s.objectName
      protectionGroupName = s.protectionGroupName
      # runStartTimeUsecs is microseconds since epoch (Cohesity's usual
      # timestamp unit) -- Terraform has no direct epoch-to-date
      # function, so convert via timeadd() from the Unix epoch, then
      # format. floor() first: dividing usecs by 1e6 isn't exact, and
      # timeadd's duration string needs a whole number of seconds.
      snapshotTime = formatdate(
        "YYYY-MM-DD hh:mm:ss 'UTC'",
        timeadd("1970-01-01T00:00:00Z", "${floor(s.runStartTimeUsecs / 1000000)}s")
      )
    }],
    []
  )
}
