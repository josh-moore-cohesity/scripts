# Fires a POST/PUT call against the Cohesity API exactly once -- unlike
# cohesity-api-module's data "external" source, which Terraform re-runs
# on every plan/apply with no lifecycle and no diff to review. This
# module instead wraps the call in a real resource (terraform_data, with
# a local-exec provisioner), so Terraform tracks it in state and only
# calls "create" once, the same as any other resource:
#   - unchanged config on a later apply -> no diff, the call does NOT refire
#   - changed api_endpoint/http_method/request_body/auth target (anything
#     in triggers_replace) -> Terraform shows this as a replace in the
#     plan, and refires only then
#   - failed call -> the resource is left tainted, so the next apply
#     retries the create rather than silently doing nothing
#
# Reuses ../cohesity-api-module/scripts/cohesity_api.sh rather than a
# copy -- this module is meant to live as a sibling of that one.
#
# Tradeoff vs. cohesity-api-module: local-exec provisioners can't return
# values directly into a resource's attributes, so the API response is
# captured by redirecting the script's stdout to a local file, then read
# back with a companion `data "local_file"` (see outputs.tf). That file
# lives under .terraform-cohesity-action/ in the ROOT module's directory
# (path.root, not path.module) -- gitignore that path.

terraform {
  required_version = ">= 1.4" # terraform_data was introduced in 1.4

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

locals {
  script_input = {
    auth_method           = var.auth_method
    cluster_vip           = var.cluster_vip
    username              = var.username
    password              = var.password
    domain                = var.domain
    api_key               = var.api_key
    key_vault_name        = var.key_vault_name
    key_vault_secret_name = var.key_vault_secret_name
    helios_url            = var.helios_url
    access_cluster_id     = var.access_cluster_id
    endpoint              = var.api_endpoint
    method                = upper(var.http_method)
    body                  = var.request_body
    api_version           = var.api_version
    insecure              = tostring(var.insecure)
  }

  response_dir  = "${path.root}/.terraform-cohesity-action"
  response_file = "${local.response_dir}/${var.name}.json"
}

resource "terraform_data" "action" {
  # input's only purpose is to make the response file's path available
  # to the destroy-time provisioner below via self.output -- Terraform
  # restricts destroy-time provisioners to referencing `self` only (not
  # local.*/var.*), so local.response_file can't be used there directly.
  input = local.response_file

  # Anything in here changing (including replace_trigger, which only
  # exists to be bumped manually) causes Terraform to show a replace in
  # the plan and re-run the call -- otherwise it never refires.
  triggers_replace = merge(local.script_input, {
    replace_trigger = var.replace_trigger
  })

  provisioner "local-exec" {
    when        = create
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      mkdir -p '${local.response_dir}'
      echo "$COHESITY_ACTION_INPUT" | bash '${path.module}/../cohesity-api-module/scripts/cohesity_api.sh' > '${local.response_file}'
    EOT

    # Passed as a real environment variable, not interpolated into the
    # command string -- avoids shell-escaping the request body/secrets.
    environment = {
      COHESITY_ACTION_INPUT = jsonencode(local.script_input)
    }
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["bash", "-c"]
    command     = "rm -f '${self.output}'"
  }
}

# Reads the file the provisioner just wrote. depends_on is required here
# because nothing in this data source's own arguments references
# terraform_data.action's attributes -- without it, Terraform has no way
# to know this must run after the provisioner, not before.
data "local_file" "action_response" {
  filename   = local.response_file
  depends_on = [terraform_data.action]
}
