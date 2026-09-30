# Registers an Azure subscription as a Cohesity protection source --
# fired exactly once via cohesity-api-action, since re-registering an
# already-registered subscription on every apply is exactly the kind of
# thing that module exists to prevent.
#
# Every field name and the endpoint itself (POST /backupsources -- a v1
# endpoint that lives OUTSIDE /public/, hence the leading slash below;
# see ../variables.tf's api_endpoint description) come from
# https://github.com/bseltz-cohesity/scripts/blob/master/powershell/registerAzureSource/registerAzureSource.ps1
# rather than guessed.
#
# Prerequisite this module does NOT set up: an Azure AD App Registration
# (service principal) with a client secret, granted appropriate access
# to the target subscription (at minimum Reader, plus whatever role
# Cohesity's backup/restore operations need -- check current Cohesity
# docs for the exact role, since that's a Cohesity requirement, not a
# Terraform one). application_id/tenant_id/application_key below are
# that app's identity, NOT the Terraform runner VM's managed identity or
# the Helios API key used to authenticate this call.

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

variable "subscription_id" {
  description = "Azure subscription ID to register as a protection source."
  type        = string
}

variable "application_id" {
  description = "Application (client) ID of the Azure AD App Registration Cohesity will use to access this subscription."
  type        = string
}

variable "tenant_id" {
  description = "Azure AD tenant (directory) ID that App Registration belongs to."
  type        = string
}

variable "application_key" {
  description = "Client secret for that App Registration. Prefer TF_VAR_application_key over a checked-in tfvars file -- there's no Key Vault fetch path for this one (unlike the Helios API key above); it's recorded in this resource's triggers_replace in plaintext regardless of the sensitive flag, same caveat as cohesity-api-module's api_key/password."
  type        = string
  sensitive   = true
}

module "register_azure_subscription" {
  source = "../"

  name = "register-azure-source-${var.subscription_id}"

  auth_method           = "helios_api_key"
  key_vault_name        = var.key_vault_name
  key_vault_secret_name = var.key_vault_secret_name
  access_cluster_id     = var.target_cluster_id

  api_endpoint = "/backupsources" # v1, outside /public/
  http_method  = "POST"

  request_body = jsonencode({
    entity = {
      type = 8
      azureEntity = {
        type = 0
        name = var.subscription_id
        id   = "/subscriptions/${var.subscription_id}"
      }
    }
    entityInfo = {
      type = 8
      credentials = {
        cloudCredentials = {
          azureCredentials = {
            subscriptionType = 1
            subscriptionId   = var.subscription_id
            applicationId    = var.application_id
            tenantId         = var.tenant_id
            applicationKey   = var.application_key
          }
        }
      }
    }
    registeredEntityParams = {
      isSpaceThresholdEnabled = false
      throttlingPolicy = {
        isThrottlingEnabled             = false
        isDatastoreStreamsConfigEnabled = false
        datastoreStreamsConfig          = {}
      }
      vmwareParams = {}
    }
  })
}

output "registered_source" {
  description = "Cluster's response to the /backupsources create call."
  value       = module.register_azure_subscription.response
}
