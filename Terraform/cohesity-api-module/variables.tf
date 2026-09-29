variable "auth_method" {
  description = <<-EOT
    How to authenticate:
      "password"         - username/password exchanged for a session token, called directly against cluster_vip.
      "cluster_api_key"   - an API key minted in the cluster's own UI, called directly against cluster_vip.
      "helios_api_key"    - a Helios-issued API key, called against helios_url and proxied to a
                            specific cluster via the access_cluster_id header. No cluster VIP
                            reachability or per-cluster credential needed.
  EOT
  type    = string
  default = "password"

  validation {
    condition     = contains(["password", "cluster_api_key", "helios_api_key"], var.auth_method)
    error_message = "auth_method must be one of: password, cluster_api_key, helios_api_key."
  }
}

variable "cluster_vip" {
  description = "IP address or hostname (VIP) of the Cohesity cluster. Required for auth_method = password or cluster_api_key. Not used for helios_api_key."
  type        = string
  default     = ""
}

variable "username" {
  description = "Cohesity cluster username. Required for auth_method = password."
  type        = string
  default     = ""
}

variable "password" {
  description = "Cohesity cluster password. Required for auth_method = password. Prefer TF_VAR_password over a checked-in tfvars file."
  type        = string
  sensitive   = true
  default     = ""
}

variable "domain" {
  description = "Authentication domain for username/password auth (e.g. LOCAL, or an AD domain)."
  type        = string
  default     = "LOCAL"
}

variable "api_key" {
  description = "API key, if you're passing it in directly. Required for auth_method = cluster_api_key or helios_api_key -- UNLESS key_vault_name + key_vault_secret_name are set, in which case leave this empty and the script fetches the key from Key Vault at runtime instead. Fetching from Key Vault is preferred: this variable's value gets written to Terraform state in plaintext regardless of the sensitive flag, since it's recorded as an input to the external data source."
  type        = string
  sensitive   = true
  default     = ""
}

variable "key_vault_name" {
  description = "Azure Key Vault name to fetch api_key from at runtime (az keyvault secret show), instead of passing api_key directly. Requires the Azure CLI to be logged in on the machine running terraform apply (e.g. via the VM's managed identity: `az login --identity`)."
  type        = string
  default     = ""
}

variable "key_vault_secret_name" {
  description = "Secret name in key_vault_name holding the API key. Used together with key_vault_name."
  type        = string
  default     = ""
}

variable "helios_url" {
  description = "Base URL for Helios. Used when auth_method = helios_api_key."
  type        = string
  default     = "https://helios.cohesity.com"
}

variable "access_cluster_id" {
  description = <<-EOT
    Required when auth_method = helios_api_key. The target cluster's clusterId
    (as shown in Helios / GET .../mcm/clusters/info) -- NOT the cluster VIP.
    Sent as the accessClusterId header so Helios knows which registered
    cluster to proxy the call to.
  EOT
  type    = string
  default = ""
}

variable "api_endpoint" {
  description = "Public API v1 GET endpoint to call, relative to /irisservices/api/v1/public/ (e.g. 'cluster', 'nodes', 'vaults')."
  type        = string
  default     = "cluster"
}

variable "insecure" {
  description = "Skip TLS certificate verification (curl -k). Relevant only for direct cluster calls (password/cluster_api_key) against self-signed certs; Helios presents a valid public cert, so this has no effect for auth_method = helios_api_key."
  type        = bool
  default     = true
}
