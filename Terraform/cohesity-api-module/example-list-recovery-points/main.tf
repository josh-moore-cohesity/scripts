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
#      -> { snapshots: [ { id, runStartTimeUsecs, ... } ] }
# No protectionGroupIds filter needed on step 2 for this -- that's an
# optional narrowing param seen in other (VMware) reference scripts, not
# a requirement.

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
  description = "Full raw response from the protected-object search."
  value       = module.find_vm.response
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
  description = "Full raw response from the snapshots list call."
  value       = module.list_snapshots.response
}

output "recovery_points" {
  description = "Simplified list: each recovery point's id and run start time (microseconds since epoch -- Cohesity's usual timestamp unit; convert with e.g. `date -d @$(($usecs/1000000))` on the VM if you need a readable date)."
  value = try(
    [for s in module.list_snapshots.response.snapshots : {
      id                = s.id
      runStartTimeUsecs = s.runStartTimeUsecs
    }],
    []
  )
}
