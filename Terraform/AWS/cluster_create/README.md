# Cohesity Cloud Edition Cluster Create on AWS Using Terraform

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

This Terraform module deploys the EC2 instances and EBS data volumes for a Cohesity Cloud Edition cluster in AWS and then creates (or expands) the cluster. Cluster creation is performed through **AWS Systems Manager (SSM)**: the AWS provider creates an SSM Command document and a State Manager association that runs the `iris_cli cluster cloud-create` script on the first VM. No SSH, passwords, `sshpass`, `local-exec`, `null_resource`, AWS CLI or network path from Terraform to the VMs is required, which makes the module suitable for Terraform Cloud (TFC) runners and for private subnets with no public IPs.

Related AWS documentation: [AWS Systems Manager State Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-state.html).

## Requirements

* Terraform 1.3 or later (the `ssm` custom endpoint uses an optional object attribute)
* Providers: `hashicorp/aws` (`~> 6.0`) and `hashicorp/random` (`~> 3.5`)
* An existing subnet (`subnet_id`) and security group(s) (`security_group_ids`) for the cluster nodes
* A Cohesity Cloud Edition AMI ID (`image_id`) for the desired software version
* An IAM instance profile (`instance_profile_name`) that includes the `AmazonSSMManagedInstanceCore` managed policy (required when `issue_cluster_create_cmd = true`)
* Network path from the VMs to the SSM endpoints (internet/NAT gateway, or VPC endpoints for `ssm`, `ssmmessages` and `ec2messages`)
* Permissions for the identity running Terraform, in addition to normal EC2/EBS permissions:
  * `ssm:CreateDocument`, `ssm:DeleteDocument`, `ssm:DescribeDocument`, `ssm:AddTagsToResource`
  * `ssm:CreateAssociation`, `ssm:DescribeAssociation`, `ssm:DeleteAssociation`

## Components

* `main.tf` - provider config, EC2 instances, EBS volumes/attachments, SSM document and association
* `variables.tf` - input variables
* `outputs.tf` - instance IP information and the `cluster_command` output
* `example_terraform.tfvars` - fully commented example variable file; copy to `terraform.tfvars` and edit
* `configs.json` - predefined VM sizing configurations selected with `config_id` (Entry, Core, Archive, Performance)
* `rules.json` - reference list of the security group rules (ports/protocols) a cluster needs; it is not read by the module, use it to build your security group

## How Cluster Creation Works

1. Terraform creates the instances and attaches the SSD and HDD tier EBS volumes.
2. An `aws_ssm_document` holds a script that is written to the first VM and run as the `cohesity` user (SSM itself runs as root).
3. An `aws_ssm_association` targets the first VM's instance ID, runs the document once and waits for it to succeed (post-boot wait plus one hour).
4. On the VM the script waits `post_boot_wait` seconds, polls `iris_cli cluster status` until the node reports `is not part of a cluster`, checks `cluster cloud-create help show-hidden` for `disk-identifiers` support, and runs the matching `cloud-create` command (with or without the disk mapping, so older images still work).
5. A marker file is written on the VM after a successful run so State Manager can never re-issue the create (for example after a reboot).

## Usage

### Create a New Cluster

Copy `example_terraform.tfvars` to `terraform.tfvars` and edit it (every option is documented in the file), or start from this minimal example:

```
region                = "us-east-1"
subnet_id             = "subnet-0123456789abcdef0"
security_group_ids    = ["sg-0123456789abcdef0"]
image_id              = "ami-0123456789abcdef0"
instance_profile_name = "my-ssm-instance-profile"
tags                  = ["owner:myname", "env:test"]

resource_name_prefix  = "cohesity-ce"
num_instances         = 3
config_id             = "2"

cluster_name          = "mycluster"
dns_server_ips        = "10.0.0.2"
ntp_servers           = "169.254.169.123"
domain_names          = "mydomain.net"
```

Then:

```
terraform init
terraform plan
terraform apply
```

### Create the Cluster Manually

Set `issue_cluster_create_cmd = false` to skip the SSM resources. The command to run on any one of the new VMs is printed in the `cluster_command` output:

```
terraform output -raw cluster_command
```

### Add Nodes to an Existing Cluster

Update `image_id` to the AMI matching your current cluster version, increase `num_instances` to the desired total and apply. Existing instances are protected from replacement (`ignore_changes` on `ami`), only the new nodes are created, the SSM create step is skipped, and the `cluster_command` output contains the `iris_cli cluster cloud-join` command to run on an existing cluster node (replace `REPLACE_WITH_IRIS_PASSWORD` with the Iris password).

### Use a Role, Custom Endpoints or Sovereign Cloud

Assume a role for all AWS API calls:

```
iam_role_arn = "arn:aws:iam::123456789012:role/my-terraform-role"
```

Use custom service endpoints (for example EUSC). Include `ssm` because cluster creation runs through SSM:

```
aws_custom_endpoints = {
  ec2 = "https://ec2.example.com"
  sts = "https://sts.example.com"
  iam = "https://iam.example.com"
  s3  = "https://s3.example.com"
  ssm = "https://ssm.example.com"
}
```

## Parameters

### Authentication

| Variable | Description |
| --- | --- |
| region | (Required) AWS region to deploy to |
| iam_role_arn | (Optional) IAM role ARN to assume for AWS API calls |
| aws_custom_endpoints | (Optional) Custom `ec2`, `sts`, `iam`, `s3` and optional `ssm` endpoints for sovereign clouds |

### Deployment

| Variable | Description |
| --- | --- |
| subnet_id | (Required) ID of the existing subnet |
| security_group_ids | (Optional) List of security group IDs to attach to the instances |
| image_id | (Required) AMI ID for the VMs; when adding nodes, set to the AMI matching the current cluster version |
| tags | (Required) List of tags in `key:value` format |
| num_instances | (Optional) Number of VMs, default 1 |
| resource_name_prefix | (Required) Prefix for all resource names, 1-30 chars, lowercase letters, numbers and hyphens |
| add_random_prefix | (Optional) Append an 8 character random string to the prefix, default false |
| attach_public_ip | (Optional) Attach an Elastic IP to each VM, default false |
| instance_profile_name | (Optional) Name (not ARN) of the instance profile for the VMs; required when `issue_cluster_create_cmd` is true |
| enforce_imdsv2 | (Optional) Require IMDSv2, default false |
| encrypt_ebs_volumes | (Optional) Encrypt EBS volumes, default true |
| kms_key_id | (Optional) KMS key ARN for EBS encryption; AWS default key is used if blank |

### VM Sizing

| Variable | Description |
| --- | --- |
| config_id | (Optional) ID of the configuration in `configs.json`, default `2` |
| config_file | (Optional) Path to the configuration JSON file, default `./configs.json` |
| custom_config | (Optional) Object that overrides the configuration selected by `config_id` |

### Cluster Create

| Variable | Description |
| --- | --- |
| cluster_name | (Required) Name of the Cohesity cluster |
| dns_server_ips | (Required) Comma separated DNS server IPs |
| ntp_servers | (Required) Comma separated NTP servers |
| domain_names | (Required) Domain name |
| cluster_size | (Optional) `nextGen` (default) or legacy cluster type |
| apps_subnet / apps_subnet_mask | (Optional) Internal overlay network for the apps infrastructure, default `192.168.0.0` / `255.255.0.0` |
| issue_cluster_create_cmd | (Optional) Create the cluster automatically through SSM, default true |
| post_boot_wait | (Optional) Seconds to wait after boot before checking services, default 600 |
| ssm_output_s3_bucket_name | (Optional) S3 bucket for the SSM run output; the instance profile must be able to write to it |

## Outputs

| Output | Description |
| --- | --- |
| instance_info | Map of instance ID to private (and public, if attached) IP |
| cluster_command | The `iris_cli` create or join command, for manual use or reference |

## Notes

* Terraform does not stream the `iris_cli` output into its own log. Review it in the SSM console (association execution history), or set `ssm_output_s3_bucket_name`.
* The cluster create command uses the default `admin` Iris credentials, and the command text is visible in SSM command history and CloudTrail. Change the password after the cluster is created.
* `resource_name_prefix` is used in the SSM document name, which must be unique per region. Two deployments with the same prefix in one region (and `add_random_prefix = false`) will collide.
* The `ssm_output_s3_bucket_name` and instance profile S3 permissions are only needed if you want the run output stored in S3.
* The script runs `iris_cli` through `su - cohesity`; this assumes the SSM agent is present and running on the Cohesity AMI and `iris_cli` is on the `cohesity` user's login `PATH`.
* This module has not been tested end to end against every image version. Validate in a non-production account first.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Terraform/AWS/cluster_create/main.tf
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Terraform/AWS/cluster_create/variables.tf
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Terraform/AWS/cluster_create/outputs.tf
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Terraform/AWS/cluster_create/example_terraform.tfvars
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Terraform/AWS/cluster_create/configs.json
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Terraform/AWS/cluster_create/rules.json
```
