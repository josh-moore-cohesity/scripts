# Demonstrates the intended pattern: read-only lookups still go through
# cohesity-api-module (safe to re-run on every plan/apply, since GET has
# no side effects), and only the actual mutating create goes through
# cohesity-api-action -- so it fires exactly once instead of on every
# apply. This mirrors ../../cohesity-api-module/example-protect-vm's
# create-a-new-group path, but with the create step made safe.

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

variable "job_name" {
  description = "Name for the new Protection Group."
  type        = string
}

variable "policy_name" {
  description = "Name of an existing Protection Policy to assign."
  type        = string
}

variable "storage_domain_name" {
  description = "Name of an existing Storage Domain (View Box)."
  type        = string
}

variable "vm_object_id" {
  description = "The Azure VM's object ID to protect (from cohesity-api-module's v2 object search -- see ../../cohesity-api-module/example-protect-vm's find_vm module for how to look this up)."
  type        = number
}

# --- Read-only lookups: safe to re-run every plan/apply (GET) -----------
module "find_policy" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_version           = "v2"
  api_endpoint          = "data-protect/policies"
}

module "find_viewbox" {
  source = "../../cohesity-api-module"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id
  api_endpoint          = "viewBoxes" # v1 -- see cohesity-api-module's README
}

locals {
  policy_id  = one([for p in module.find_policy.response.policies : p.id if p.name == var.policy_name])
  viewbox_id = one([for v in module.find_viewbox.response : v.id if v.name == var.storage_domain_name])
}

# --- The actual create: fires exactly once, tracked in state -------------
module "create_protection_group" {
  source = "../"

  name = "protect-vm-${var.job_name}"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id

  api_version  = "v2"
  api_endpoint = "data-protect/protection-groups"
  http_method  = "POST"

  # Field names verified against
  # github.com/bseltz-cohesity/scripts/blob/master/powershell/protectAzureVM/protectAzureVM.ps1
  # -- same body shape as cohesity-api-module/example-protect-vm's
  # new_job_body, just built directly here since there's no existing-job
  # merge path in this simpler example.
  request_body = jsonencode({
    name            = var.job_name
    environment     = "kAzure"
    isPaused        = false
    policyId        = local.policy_id
    priority        = "kMedium"
    storageDomainId = local.viewbox_id
    description     = ""
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
        objects          = [{ id = var.vm_object_id }]
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
  })
}

output "created_job" {
  value = module.create_protection_group.response
}
