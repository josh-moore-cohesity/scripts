variable "name" {
  description = "Short, unique-within-this-config label for this action (e.g. \"protect-vm-jmoore-restored\"). Used to name the local file the API response is captured into -- must be unique per call if you use this module more than once in the same root config, or the response files will collide."
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9._-]+$", var.name))
    error_message = "name must contain only letters, digits, '.', '_', or '-' -- it's interpolated into a shell command as a file path."
  }
}

variable "auth_method" {
  description = <<-EOT
    How to authenticate:
      "password"         - username/password exchanged for a session token, called directly against cluster_vip.
      "cluster_api_key"   - an API key minted in the cluster's own UI, called directly against cluster_vip.
      "helios_api_key"    - a Helios-issued API key, called against helios_url and proxied to a
                            specific cluster via the access_cluster_id / clusterId headers. No cluster VIP
                            reachability or per-cluster credential needed.
  EOT
  type        = string
  default     = "password"

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
  description = "API key, if you're passing it in directly. Required for auth_method = cluster_api_key or helios_api_key -- UNLESS key_vault_name + key_vault_secret_name are set, in which case leave this empty and the underlying script fetches the key from Key Vault at runtime instead. Fetching from Key Vault is preferred: this variable's value gets recorded in triggers_replace (see below) in plaintext regardless of the sensitive flag."
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
    Sent as the accessClusterId + clusterId headers so Helios knows which
    registered cluster to proxy the call to.
  EOT
  type        = string
  default     = ""
}

variable "api_endpoint" {
  description = "API endpoint to call, relative to the base path selected by api_version (see cohesity-api-module's README for v1 vs v2)."
  type        = string
}

variable "api_version" {
  description = "\"v1\" (default, /irisservices/api/v1/public/...) or \"v2\" (/v2/..., e.g. data-protect/protection-groups)."
  type        = string
  default     = "v1"

  validation {
    condition     = contains(["v1", "v2"], var.api_version)
    error_message = "api_version must be one of: v1, v2."
  }
}

variable "http_method" {
  description = <<-EOT
    HTTP method for the call this resource performs exactly once: POST or
    PUT. GET isn't accepted here -- there's nothing to "create once" for a
    read, so use cohesity-api-module's data source for that instead.
  EOT
  type        = string
  default     = "POST"

  validation {
    condition     = contains(["POST", "PUT"], upper(var.http_method))
    error_message = "http_method must be POST or PUT (use cohesity-api-module for GET)."
  }
}

variable "request_body" {
  description = "JSON string sent as the request body (e.g. jsonencode({ name = \"...\" }))."
  type        = string
}

variable "insecure" {
  description = "Skip TLS certificate verification (curl -k). Relevant only for direct cluster calls (password/cluster_api_key) against self-signed certs; Helios presents a valid public cert, so this has no effect for auth_method = helios_api_key."
  type        = bool
  default     = true
}

variable "replace_trigger" {
  description = "Optional extra value folded into triggers_replace. The call already re-fires automatically if api_endpoint/http_method/request_body/auth target change; set this to any new value (e.g. a timestamp) to force a one-off re-run without changing those -- e.g. to retry after fixing an unrelated problem on the cluster."
  type        = string
  default     = ""
}
