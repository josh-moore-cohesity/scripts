# Protect AWS EC2 Instances Using Terraform

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

This example adds one or more AWS EC2 instances to a Cohesity protection group, or creates the protection group if it does not exist yet. It uses the Cohesity v2 `data-protect/protection-groups` API, through [`cohesity-api-module`](../../cohesity-api-module) for the read-only lookups and [`cohesity-api-action`](..) for the single create/update call, so the call is tracked in Terraform state instead of being re-sent on every apply.

This is a Terraform port of [protectEC2VMs.ps1](https://github.com/bseltz-cohesity/scripts/blob/master/powershell/protectEC2VMs/protectEC2VMs.ps1). Every endpoint and body field comes from that script. It is the AWS counterpart of [`example-protect-vm`](../example-protect-vm), which does the same for a single Azure VM.

Beyond the script, it can also **auto-protect by tag and exclude by tag**, with or without named instances. The script only protects by name (it sends `vmTagIds` and `excludeVmTagIds` as null), so the tag logic follows the VMware equivalent, [protectVMsByTag.ps1](https://github.com/bseltz-cohesity/scripts/blob/master/powershell/protectVMsByTag/protectVMsByTag.ps1).

**Status: not yet tested against a live cluster.** `example-protect-vm` is confirmed working; this example follows the same structure but has not been run. See [Notes](#notes) before using it.

## Requirements

* Terraform 1.5 or later (for the `check` block; `cohesity-api-action` itself needs 1.4 or later)
* `bash`, `curl` and `jq` on the machine running `terraform plan/apply`
* A Helios API key stored in an Azure Key Vault, with the Azure CLI logged in on the runner (see [`cohesity-api-module`'s README](../../cohesity-api-module/README.md) and the [runbook](../../RUNBOOK.md))
* The AWS account already registered as a protection source in Cohesity
* For a new protection group: an existing protection policy and storage domain

## Components

* `main.tf` - variables, the read-only lookups, the request-body logic, pre-flight checks and the one-time create/update call
* `terraform.tfvars.example` - example input values; copy to `terraform.tfvars` and edit
* `../` (`cohesity-api-action`) and `../../cohesity-api-module` - sibling modules this example calls by relative path. Keep the folder structure intact.

## How It Works

1. Looks up the registered AWS source ID (`protectionSources/registrationInfo?environments=kAWS`).
2. Searches for each requested instance under that source (`data-protect/search/objects`, one call per instance) and matches the name exactly, ignoring case.
3. If any tags are requested (or `list_tags = true`), reads the AWS source's tree (`protectionSources?environments=kAWS`) and resolves each tag name to its Cohesity tag ID.
4. Looks up the protection group by name (`data-protect/protection-groups?environments=kAWS`), plus the policies and storage domains.
5. Builds the request body for whichever path applies:
   * **Group exists** - the instances and tag groups not already in the group are merged into it and the group is updated (PUT). The group keeps its own policy, schedule and protection type, and must use the same AWS source.
   * **Group does not exist** - a new group is created (POST) with the settings below.
6. Sends the one create/update call through `cohesity-api-action`.

## Usage

### First pass: lookups only

`apply_changes` defaults to `false`, so the first apply only runs the read-only lookups:

```bash
cp terraform.tfvars.example terraform.tfvars   # then edit
terraform init
terraform apply
terraform output planned_action
terraform output resolved_vms
terraform output vms_not_found
terraform output vm_lookup_raw
```

Check that the right source, instances and group were found.

### Create or update the protection group

```bash
terraform apply -var apply_changes=true
```

The call fires only if there is something to do: a new group, or an existing group missing at least one of the instances. After that apply the group already contains them, so later applies do nothing. Leaving `apply_changes = true` permanently is safe.

### Instance list from a file

```hcl
vm_list_file = "./vms.txt"   # one instance name per line
```

`vm_names` and `vm_list_file` can be combined; duplicates are removed.

### Auto-protect a tag and exclude another

The common case: protect everything tagged `tag1` except anything tagged `tag2`. New instances that get `tag1` are picked up by the cluster automatically.

```hcl
include_tags = ["tag1"]
exclude_tags = ["tag2"]
```

Tag names must match what Cohesity shows under the AWS source. If you are not sure of the format, run once with `list_tags = true` and read `terraform output available_tags`, which maps each tag node name to its ID. A numeric tag ID can be used in place of a name.

### Tags with AND/OR logic

`include_tags` and `exclude_tags` treat each entry as an alternative (OR). For the full shape use the `*_tag_groups` variables: a tag group matches an instance only if it has **all** the tags in the group (AND), and an instance is included (or excluded) if it matches **any** group (OR).

```hcl
# (env:prod AND app:web) OR backup:true
include_tag_groups = [["env:prod", "app:web"], ["backup:true"]]

# ...but not anything that has both dr:true AND test:true
exclude_tag_groups = [["dr:true", "test:true"]]
```

Tags can be combined with `vm_names`, and the `*_tags` and `*_tag_groups` variables can be used together.

### Create a new group with custom settings

```hcl
job_name                = "AWS-EC2-Daily"
policy_name             = "Gold"
storage_domain_name     = "DefaultStorageDomain"
protection_type         = "kNative"
start_time              = "22:30"
time_zone               = "America/Chicago"
full_sla_minutes        = 240
incremental_sla_minutes = 120
qos_policy              = "kBackupSSD"
paused                  = true
```

## Parameters

### Authentication and target

| Variable | Description |
| --- | --- |
| `target_cluster_id` | Required. The `clusterId` of the registered cluster Helios should proxy calls to (not the cluster VIP) |
| `key_vault_name` | Required. Azure Key Vault holding the Helios API key |
| `key_vault_secret_name` | Optional. Secret name in that vault (default `helios-api-key`) |

### What to protect

| Variable | Script parameter | Description |
| --- | --- | --- |
| `aws_source_name` | `-sourceName` | Required. Name of the registered AWS protection source |
| `job_name` | `-jobName` | Required. Protection group to update, or the name of the new group |
| `vm_names` | `-vmName` | Optional. List of instance names |
| `vm_list_file` | `-vmList` | Optional. Text file with one instance name per line |
| `include_tags` | - | Optional. Auto-protect instances with **any** of these tags (OR) |
| `include_tag_groups` | - | Optional. List of tag lists: an instance matches a list if it has **all** its tags (AND); lists are OR'd. Added to `include_tags` |
| `exclude_tags` | - | Optional. Exclude instances with **any** of these tags (OR) |
| `exclude_tag_groups` | - | Optional. Same shape as `include_tag_groups`, for exclusions |
| `list_tags` | - | Optional. Populate `available_tags` even when no tag is requested |

At least one of `vm_names`, `vm_list_file` or the include tag variables is needed to create a group. The tag variables are not part of the PowerShell script.

### New protection group only

These are ignored when `job_name` already exists.

| Variable | Script parameter | Description |
| --- | --- | --- |
| `policy_name` | `-policyName` | Required to create a group. Name of an existing protection policy |
| `storage_domain_name` | `-storageDomainName` | Optional. Default `DefaultStorageDomain`. Used as-is if the cluster has only one storage domain |
| `ngce` | `-ngce` | Optional. Create the group with no storage domain. A CloudArchiveDirect policy is detected automatically |
| `protection_type` | `-protectionType` | Optional. `kNative` (default), `kAgent` or `kSnapshotManager` |
| `start_time` | `-startTime` | Optional. Daily start time, 24-hour `HH:MM` (default `20:00`) |
| `time_zone` | `-timeZone` | Optional. Default `America/New_York` |
| `full_sla_minutes` | `-fullSlaMinutes` | Optional. Default 120 |
| `incremental_sla_minutes` | `-incrementalSlaMinutes` | Optional. Default 60 |
| `qos_policy` | `-qosPolicy` | Optional. `kBackupHDD` (default) or `kBackupSSD` |
| `paused` | `-paused` | Optional. Create the group paused |

### Control

| Variable | Description |
| --- | --- |
| `apply_changes` | Optional. Default `false` (lookups only). Set `true` to create or update the group |

## Outputs

| Output | Description |
| --- | --- |
| `planned_action` | What `apply_changes = true` would do right now |
| `resolved_vms` | Instance name to Cohesity object ID, for every instance found |
| `vms_not_found` | Requested instances not found under the AWS source |
| `available_tags` | Tag node name to tag ID(s) found under the AWS source. Only populated when tags are requested or `list_tags = true` |
| `resolved_tag_ids` | Requested tag to Cohesity tag ID (null if not found or ambiguous) |
| `vms_already_protected` | Requested instances already in the existing group (skipped) |
| `apply_job_response` | The cluster's response to the create/update call. Null until `apply_changes = true`, and again once the group already contains every instance |
| `*_lookup_raw` | Raw API responses for the lookups. Marked sensitive only to keep them out of the plan diff; read them with `terraform output <name>` |

## Notes

* **Not yet tested against a live cluster.** The one assumption to verify is the EC2 search response (`data-protect/search/objects`): the example reads each instance's ID from `objectProtectionInfos[0].objectId`, as the confirmed-working Azure example does, and assumes that equals the ID the PowerShell script reads from the `protectionSources` tree. Run the lookups-only pass first and check `vm_lookup_raw`.
* **Tag support is less verified than the by-name path.** The `vmTagIds` / `excludeVmTagIds` shape (a list of lists of tag IDs, AND inside, OR across) comes from the VMware script. How an AWS tag appears in the `protectionSources` tree is assumed: the example looks for nodes whose `awsProtectionSource.type` is `kTag` and matches the requested tag against the node's `name`. Check `available_tags` first; if your tags do not appear or are named differently, pass the numeric tag ID instead.
* A tag that is not found, or matches more than one node, is a hard error (not a warning like a missing VM), because a missing exclude tag would protect more than intended.
* The tree is flattened to 7 levels because Terraform cannot recurse; tags nested deeper are not seen. It is only fetched when a tag is requested or `list_tags = true`.
* On an existing group, tag groups are merged into the ones already there and compared as sets of IDs. Removing a tag from a group is not supported.
* The search is scoped to the AWS source and filtered by exact name on the client side. It does not filter on object type, so if two objects under the source share a name the example stops with an "ambiguous" error instead of guessing.
* Pre-flight checks mirror the script's `exit` conditions and run only when `apply_changes = true`: nothing to protect, tag not found or ambiguous, source not found, existing group uses a different source, `policy_name` missing or not found, storage domain not found, or (for a new group) none of the instances found. Instances that are not found are only a warning, as in the script, as long as at least one is found.
* Unlike the script, which sends an explicit `null` for `storageDomainId` with `-ngce`, this example omits the key. The cluster rejects the key being present for a CloudArchiveDirect policy.
* Removing an instance from the group is not supported; the script does not do it either.
* `terraform destroy` removes the call from state but does not delete the protection group on the cluster. See the [`cohesity-api-action` README](../README.md).
* The API response is saved under `.terraform-cohesity-action/` in the directory you run Terraform from. Add that path to `.gitignore`.

## Download

```bash
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Terraform/cluster_operations/cohesity-api-action/example-protect-ec2-vms/main.tf
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Terraform/cluster_operations/cohesity-api-action/example-protect-ec2-vms/terraform.tfvars.example
```

The example calls its sibling modules by relative path, so clone the repository (or keep the `cohesity-api-action` and `cohesity-api-module` folders together) rather than downloading `main.tf` on its own.
