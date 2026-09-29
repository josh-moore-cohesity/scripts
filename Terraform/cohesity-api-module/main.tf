terraform {
  required_version = ">= 1.0"

  required_providers {
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }
}

# Authenticates (password, cluster-issued API key, or Helios-issued API key)
# and then issues the requested GET call, all inside one script invocation.
# Using the `external` data source keeps this read-only in Terraform's eyes
# -- no resource is created/tracked in state -- while still giving you a
# real API round trip each plan/apply.
data "external" "cohesity_api_call" {
  program = ["bash", "${path.module}/scripts/cohesity_api.sh"]

  query = {
    auth_method       = var.auth_method
    cluster_vip       = var.cluster_vip
    username          = var.username
    password          = var.password
    domain            = var.domain
    api_key                = var.api_key
    key_vault_name         = var.key_vault_name
    key_vault_secret_name  = var.key_vault_secret_name
    helios_url        = var.helios_url
    access_cluster_id = var.access_cluster_id
    endpoint          = var.api_endpoint
    insecure          = tostring(var.insecure)
  }
}
