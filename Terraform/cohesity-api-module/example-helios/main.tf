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

module "cohesity_cluster" {
  source = "../"

  auth_method            = "helios_api_key"
  # api_key intentionally left unset -- fetched from Key Vault at runtime instead,
  # so the value never touches a Terraform variable or state file.
  key_vault_name          = var.key_vault_name
  key_vault_secret_name   = var.key_vault_secret_name
  access_cluster_id       = var.target_cluster_id
  api_endpoint            = "cluster" # equivalent of `heliosCluster <name>` + `api get cluster`
}

output "cluster_name" {
  value = module.cohesity_cluster.response.name
}

output "cluster_software_version" {
  value = module.cohesity_cluster.response.clusterSoftwareVersion
}
