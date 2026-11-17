variable "cluster_vip" {
  type = string
}

variable "cluster_username" {
  type = string
}

variable "cluster_password" {
  type      = string
  sensitive = true
}

module "cohesity_cluster" {
  source = "../"

  cluster_vip  = var.cluster_vip
  username     = var.cluster_username
  password     = var.cluster_password
  domain       = "LOCAL"
  api_endpoint = "cluster" # equivalent of `iris_cli` / `api get cluster`
}

output "cluster_name" {
  value = module.cohesity_cluster.response.name
}

output "cluster_software_version" {
  value = module.cohesity_cluster.response.clusterSoftwareVersion
}

output "cluster_full_response" {
  value = module.cohesity_cluster.response
}
