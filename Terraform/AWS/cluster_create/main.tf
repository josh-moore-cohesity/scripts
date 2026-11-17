################################################################################
# Provider Configuration
################################################################################

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "aws" {
  region = var.region

  # Older AWS provider builds may reject eusc-de-east-1 before custom endpoints
  # apply; skip validation only when aws_custom_endpoints is set (EUSC).
  skip_region_validation = var.aws_custom_endpoints != null

  dynamic "endpoints" {
    for_each = var.aws_custom_endpoints != null ? [var.aws_custom_endpoints] : []
    content {
      ec2 = endpoints.value.ec2
      sts = endpoints.value.sts
      iam = endpoints.value.iam
      s3  = endpoints.value.s3
      ssm = endpoints.value.ssm
    }
  }

  # Conditionally assume role if iam_role_arn is not empty
  dynamic "assume_role" {
    for_each = var.iam_role_arn != "" ? [1] : []
    content {
      role_arn = var.iam_role_arn
    }
  }
}

################################################################################
# Data Sources
################################################################################

# Fetch details of the existing subnet
data "aws_subnet" "subnet" {
  id = var.subnet_id
}

################################################################################
# Random String for Resource Name Prefix
################################################################################

# Generate an 8-character alphanumeric random string for resource names
resource "random_string" "random_prefix" {
  length  = 8
  special = false
  upper   = false
}

################################################################################
# Local Variables
################################################################################

locals {
  random_prefix = random_string.random_prefix.result

  # Define resource name prefix based on user input
  resource_name_prefix = var.add_random_prefix == false ? var.resource_name_prefix : "${var.resource_name_prefix}-${local.random_prefix}"

  # Extract subnet mask
  subnet_mask = cidrnetmask(data.aws_subnet.subnet.cidr_block)
  # First usable IP is the subnet gateway
  subnet_gateway = cidrhost(data.aws_subnet.subnet.cidr_block, 1)

  # Parse user-provided tags into a key-value map
  parsed_tags = { for tag in var.tags : split(":", tag)[0] => split(":", tag)[1] }

  # Collect private IPs of the created instances
  private_ips = [
    for instance in aws_instance.vm :
    instance.private_ip
  ]

  # Collect public IPs of the created instances (if any)
  public_ips = var.attach_public_ip ? [
    for instance in aws_instance.vm :
    instance.public_ip
  ] : []

  # The instance to which the cluster create command is issued via SSM Run Command.
  instance_id = aws_instance.vm[0].id

  # Convert the list of private IPs into a comma-separated string
  private_ips_string = join(",", local.private_ips)

  # Convert the list of public IPs into a comma-separated string (if applicable)
  public_ips_string = join(",", local.public_ips)

  # Load VM configurations from the specified JSON file
  configurations = jsondecode(file(var.config_file)).Configurations

  # Select the configuration using the `config_id` variable
  selected_config = lookup(
    { for config in local.configurations : config.Id => config },
    var.config_id,
    null
  )

  # Fallback to `custom_config` if provided; otherwise, use the selected configuration
  config = var.custom_config != null ? var.custom_config : local.selected_config

  # Create a HDD disk map with a stable composite key
  hdd_disks = flatten([
    for vm_index in range(var.num_instances) : [
      for disk_index in range(local.config.HDDTierNumDisks) : {
        key        = "hdd-tier-${vm_index}-${disk_index}" # composite key: VM index and disk index
        vm_index   = vm_index
        disk_index = disk_index
      }
    ]
  ])
  hdd_disk_map = { for d in local.hdd_disks : d.key => d }

  # Create a SSD disk map with a stable composite key
  ssd_disks = flatten([
    for vm_index in range(var.num_instances) : [
      for disk_index in range(local.config.SSDTierNumDisks) : {
        key        = "ssd-tier-${vm_index}-${disk_index}" # composite key: VM index and disk index
        vm_index   = vm_index
        disk_index = disk_index
      }
    ]
  ])
  ssd_disk_map = { for d in local.ssd_disks : d.key => d }

  # Device name suffixes for SSD tier disks
  # Supports up to 20 disks: f-o (10), then aa-aj (10)
  # Note: We skip p-z to avoid conflicts with HDD which uses that range
  ssd_device_suffixes = concat(
    ["f", "g", "h", "i", "j", "k", "l", "m", "n", "o"], # 0-9
    ["aa", "ab", "ac", "ad", "ae", "af", "ag", "ah", "ai", "aj"] # 10-19
  )

  # Device name suffixes for HDD tier disks
  # Starts at 'p' to avoid conflicts with SSD (which uses f-o, then skips to aa+)
  # Supports up to 20 disks: p-y (10), then z, then ca-ci (9)
  hdd_device_suffixes = concat(
    ["p", "q", "r", "s", "t", "u", "v", "w", "x", "y"], # 0-9
    ["z", "ca", "cb", "cc", "cd", "ce", "cf", "cg", "ch", "ci"] # 10-19
  )

  # Determine fault tolerance level based on the number of instances
  metadata_fault_tolerance = var.num_instances > 1 ? 1 : 0

  # Build the per-node disk-identifier -> tier mapping passed to iris_cli
  per_node_disk_identifiers = join(",", concat(
    [for i in range(local.config.SSDTierNumDisks) : aws_volume_attachment.attach_ssd["ssd-tier-0-${i}"].device_name],
    [for i in range(local.config.HDDTierNumDisks) : aws_volume_attachment.attach_hdd["hdd-tier-0-${i}"].device_name]
  ))

  per_node_disk_tiers = join(",", concat(
    [for i in range(local.config.SSDTierNumDisks) : "PCIeSSD"],
    [for i in range(local.config.HDDTierNumDisks) : "SATA-HDD"]
  ))

  # Construct iris_cli command prefixes
  iris_cli_cmd_prefix = join(" ", [
    "iris_cli",
    "--v=10",
    "--username=admin",
    "--password=admin",
    "--skip_password_prompt=true",
    "--skip_force_password_change=true"
  ])

  # Construct cluster create command
  cluster_create_cmd = join(" ", [
    local.iris_cli_cmd_prefix,
    "cluster cloud-create cluster-size=${var.cluster_size} enable-software-encryption=true",
    "name=${var.cluster_name}",
    "node-ips=${local.private_ips_string}",
    "hostname=${local.private_ips[0]}",
    "subnet-gateway=${local.subnet_gateway}",
    "subnet-mask=${local.subnet_mask}",
    "dns-server-ips=${var.dns_server_ips}",
    "ntp-servers=${var.ntp_servers}",
    "domain-names=${var.domain_names}",
    "metadata-fault-tolerance=${local.metadata_fault_tolerance}",
    "apps-subnet=${var.apps_subnet}",
    "apps-subnet-mask=${var.apps_subnet_mask}",
  ])
  cluster_create_cmd_with_disk_mapping = join(" ", [
    local.cluster_create_cmd,
    "disk-identifiers=${local.per_node_disk_identifiers}",
    "disk-tiers=${local.per_node_disk_tiers}",
  ])

  # Nodes created while num_instances has this value are tagged with it.
  # The tag is ignored on update, so earlier nodes keep their own value.
  # Nodes created before this tag existed have none and count as existing.
  deploy_id = "deploy-${var.num_instances}"
  new_node_ips = [
    for instance in aws_instance.vm :
    instance.private_ip if try(instance.tags["cohesity-internal-deploy-id"], "") == local.deploy_id
  ]
  existing_node_ips = [
    for instance in aws_instance.vm :
    instance.private_ip if try(instance.tags["cohesity-internal-deploy-id"], "") != local.deploy_id
  ]
  is_create    = length(local.existing_node_ips) == 0
  is_expansion = !local.is_create && length(local.new_node_ips) > 0

  cluster_join_cmd = join(" ", [
    "iris_cli",
    "--v=10",
    "--username=admin",
    "--password=REPLACE_WITH_IRIS_PASSWORD",
    "--skip_password_prompt=true",
    "--skip_force_password_change=true",
    "cluster cloud-join",
    "node-ips=${join(",", local.new_node_ips)}",
  ])
  cluster_join_cmd_with_disk_mapping = join(" ", [
    local.cluster_join_cmd,
    "disk-identifiers=${local.per_node_disk_identifiers}",
    "disk-tiers=${local.per_node_disk_tiers}",
  ])

  # Construct the cloud-create help command for the target image.
  cluster_cloud_create_help_cmd = join(" ", [
    local.iris_cli_cmd_prefix,
    "cluster cloud-create help show-hidden",
  ])

  # Construct cluster status command
  cluster_status_cmd = join(" ", [
    local.iris_cli_cmd_prefix,
    "cluster status"
  ])

  ##############################################################################
  # Cluster create via SSM State Manager (no local-exec / AWS CLI required)
  ##############################################################################

  # Only create the SSM resources when requested and when this is a fresh cluster.
  run_cluster_create = var.issue_cluster_create_cmd && local.is_create

  # Marker written on the VM after a successful run, so that State Manager
  # re-applying the association (e.g. after a reboot) never re-issues the create.
  ssm_marker_file = "/var/lib/cohesity-tf-cluster-create.done"
  ssm_tmp_script  = "/tmp/tf_cohesity_cluster_create.sh"

  # Script executed on the first VM: wait for services, pick the right
  # cloud-create variant, and run it. Replaces the former SSH/sshpass flow.
  ssm_cluster_create_script = <<-EOT
    #!/bin/bash
    echo "Waiting for a few minutes for VM to be ready..."
    sleep ${var.post_boot_wait}

    while true; do
      output=$(${local.cluster_status_cmd} 2>&1)

      echo "Command Output: $output"

      if echo "$output" | grep -q "is not part of a cluster"; then
        echo "VM services are ready"
        break
      fi

      echo "VM services are not ready yet. Retrying in 10 seconds..."
      sleep 10
    done

    help_cmd_output=$(${local.cluster_cloud_create_help_cmd} 2>&1)

    if echo "$help_cmd_output" | grep -q "disk-identifiers"; then
      ${local.cluster_create_cmd_with_disk_mapping}
    else
      ${local.cluster_create_cmd}
    fi
  EOT

  # SSM Command document. SSM runs as root, so the script is written to a temp
  # file (base64 avoids any quoting issues) and run as the "cohesity" user,
  # matching how iris_cli was previously invoked over SSH.
  ssm_document_content = jsonencode({
    schemaVersion = "2.2"
    description   = "Create the Cohesity cluster from the first node"
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "createCluster"
      inputs = {
        timeoutSeconds = tostring(tonumber(var.post_boot_wait) + 3600)
        runCommand = [
          "if [ -f ${local.ssm_marker_file} ]; then echo 'Cluster create already ran on this VM; skipping.'; exit 0; fi",
          "echo ${base64encode(replace(local.ssm_cluster_create_script, "\r", ""))} | base64 -d > ${local.ssm_tmp_script}",
          "chmod 755 ${local.ssm_tmp_script}",
          "su - cohesity -c ${local.ssm_tmp_script}",
          "rc=$?",
          "rm -f ${local.ssm_tmp_script}",
          "if [ $rc -eq 0 ]; then touch ${local.ssm_marker_file}; fi",
          "exit $rc",
        ]
      }
    }]
  })

  # Text surfaced through the "cluster_command" output (replaces the former
  # null_resource/local-exec echo).
  cluster_command_message = (
    local.is_expansion ?
    join("\n", [
      "If cluster version is 7.5 or later, run the following command on any existing cluster node. Replace REPLACE_WITH_IRIS_PASSWORD with the Iris password:",
      local.cluster_join_cmd_with_disk_mapping,
      "Else, run the following command:",
      local.cluster_join_cmd,
    ]) :
    local.is_create ?
    join("\n", [
      "If cluster version is 7.5 or later, run the following command on any one of the VMs created:",
      local.cluster_create_cmd_with_disk_mapping,
      "Else, run the following command:",
      local.cluster_create_cmd,
    ]) :
    "No new nodes were created, so there is no cluster command to run."
  )
}

################################################################################
# Resource Definitions
################################################################################

# Create Public IPs if attach_public_ip is true
resource "aws_eip" "public_ip" {
  count    = var.attach_public_ip ? var.num_instances : 0
  instance = aws_instance.vm[count.index].id

  tags = merge(local.parsed_tags, {
    Name = "${local.resource_name_prefix}-eip-${count.index}"
  })
}

# Create Instances
resource "aws_instance" "vm" {
  count                       = var.num_instances
  ami                         = var.image_id
  instance_type               = local.config.InstanceType
  subnet_id                   = var.subnet_id
  associate_public_ip_address = var.attach_public_ip
  vpc_security_group_ids      = var.security_group_ids
  iam_instance_profile        = var.instance_profile_name != "" ? var.instance_profile_name : null

  root_block_device {
    volume_type = "gp3"
    encrypted   = var.encrypt_ebs_volumes
    kms_key_id  = var.encrypt_ebs_volumes ? (var.kms_key_id != "" ? var.kms_key_id : null) : null
    tags = merge(local.parsed_tags, {
      Name = "${local.resource_name_prefix}-vm-${count.index}-os-disk"
    })
  }

  metadata_options {
    http_tokens   = var.enforce_imdsv2 ? "required" : "optional"
    http_endpoint = "enabled"
  }

  tags = merge(local.parsed_tags, {
    Name                          = "${local.resource_name_prefix}-vm-${count.index}"
    "cohesity-internal-deploy-id" = local.deploy_id
  })

  lifecycle {
    # Prevent replacement of existing cluster nodes when AMI changes.
    # This enables add-node scenarios where new nodes use a different AMI
    # (matching the upgraded cluster version) while existing nodes remain untouched.
    # When adding nodes to an upgraded cluster, update image_id to match
    # the current cluster version before increasing num_instances.
    # cohesity-internal-deploy-id must keep the value from the apply that created the VM.
    ignore_changes = [ami, tags["cohesity-internal-deploy-id"]]
  }
}

# Create EBS Volumes (SSD Tier)
resource "aws_ebs_volume" "ssd_tier_data_disk" {
  for_each          = local.ssd_disk_map
  availability_zone = data.aws_subnet.subnet.availability_zone
  size              = local.config.SSDTierDiskSizeinGB
  type              = local.config.SSDTierDiskType
  iops              = local.config.SSDTierDiskIops
  throughput        = local.config.SSDTierDiskThroughputinMBps
  encrypted         = var.encrypt_ebs_volumes
  kms_key_id        = var.encrypt_ebs_volumes ? (var.kms_key_id != "" ? var.kms_key_id : null) : null

  tags = merge(local.parsed_tags, {
    Name = "${local.resource_name_prefix}-${each.key}"
  })
}

# Attach EBS Volumes (SSD Tier)
resource "aws_volume_attachment" "attach_ssd" {
  for_each    = local.ssd_disk_map
  instance_id = aws_instance.vm[each.value.vm_index].id
  volume_id   = aws_ebs_volume.ssd_tier_data_disk[each.key].id

  # Generate a unique device name for each SSD disk attached to the same instance
  device_name  = "/dev/sd${element(local.ssd_device_suffixes, each.value.disk_index)}"
  force_detach = true
}

# Create EBS Volumes (HDD Tier)
resource "aws_ebs_volume" "hdd_tier_data_disk" {
  for_each          = local.hdd_disk_map
  availability_zone = data.aws_subnet.subnet.availability_zone
  size              = local.config.HDDTierDiskSizeinGB
  type              = local.config.HDDTierDiskType
  iops              = local.config.HDDTierDiskIops
  throughput        = local.config.HDDTierDiskThroughputinMBps
  encrypted         = var.encrypt_ebs_volumes
  kms_key_id        = var.encrypt_ebs_volumes ? (var.kms_key_id != "" ? var.kms_key_id : null) : null

  tags = merge(local.parsed_tags, {
    Name = "${local.resource_name_prefix}-${each.key}"
  })
}

# Attach EBS Volumes (HDD Tier)
resource "aws_volume_attachment" "attach_hdd" {
  for_each    = local.hdd_disk_map
  instance_id = aws_instance.vm[each.value.vm_index].id
  volume_id   = aws_ebs_volume.hdd_tier_data_disk[each.key].id

  # Generate a unique device name for each HDD disk attached to the same instance
  device_name  = "/dev/sd${element(local.hdd_device_suffixes, each.value.disk_index)}"
  force_detach = true
}

################################################################################
# Commands Based on Cluster Creation
################################################################################

# Command document that holds the cluster create script
resource "aws_ssm_document" "cluster_create" {
  count           = local.run_cluster_create ? 1 : 0
  name            = "${local.resource_name_prefix}-cohesity-cluster-create"
  document_type   = "Command"
  document_format = "JSON"
  content         = local.ssm_document_content

  tags = local.parsed_tags
}

# State Manager association: runs the document once on the first VM and waits
# for it to succeed. Executed entirely through the AWS API by the AWS provider,
# so it needs no local-exec, AWS CLI, SSH, or network path to the VMs.
resource "aws_ssm_association" "cluster_create" {
  count            = local.run_cluster_create ? 1 : 0
  name             = aws_ssm_document.cluster_create[0].name
  association_name = "${local.resource_name_prefix}-cluster-create"

  targets {
    key    = "InstanceIds"
    values = [local.instance_id]
  }

  # Post-boot wait + readiness loop + cluster create, plus margin.
  wait_for_success_timeout_seconds = tonumber(var.post_boot_wait) + 3600

  dynamic "output_location" {
    for_each = var.ssm_output_s3_bucket_name != "" ? [1] : []
    content {
      s3_bucket_name = var.ssm_output_s3_bucket_name
      s3_key_prefix  = "${local.resource_name_prefix}-cluster-create"
    }
  }

  depends_on = [aws_volume_attachment.attach_ssd, aws_volume_attachment.attach_hdd]

  lifecycle {
    precondition {
      condition     = var.instance_profile_name != ""
      error_message = "issue_cluster_create_cmd uses AWS Systems Manager, so instance_profile_name must be set to an instance profile that includes AmazonSSMManagedInstanceCore. Otherwise set issue_cluster_create_cmd = false."
    }
  }
}
