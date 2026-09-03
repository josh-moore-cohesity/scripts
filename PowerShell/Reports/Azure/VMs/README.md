# Report Azure VM Info from Cohesity's Protection Source Tree

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`get-azure-object-info.ps1` reports resource group, subscription, region, OS, IP address, and managed-VM info for one or more Azure VMs, read from their Cohesity Azure source registration (the `protectionSources` tree) rather than from Azure itself. It also reports the numeric Cohesity object ids for the VM's source registration, resource group, subscription, and region - useful for feeding straight into [`recover_azure_vm.ps1`](../../../Recoveries/Azure/VMs)'s `-sourceId`/`-resourceGroupId`/`-subscriptionId`/`-regionId` params to recover a VM back to its original location by id instead of by name.

## Requirements

* Windows PowerShell 5.1+ or PowerShell 7+ (`pwsh`)
* [`cohesity-api.ps1`](https://github.com/bseltz-cohesity/scripts/tree/master/powershell/cohesity-api) in the same directory as `get-azure-object-info.ps1`

## Components

* `get-azure-object-info.ps1` - the main script
* `cohesity-api.ps1` - the Cohesity REST API helper module

### Report all Azure VMs across all Helios-connected clusters

```
.\get-azure-object-info.ps1 -vip helios.cohesity.com -useApiKey
```

### Report specific VMs by name

```
.\get-azure-object-info.ps1 -vip helios.cohesity.com -useApiKey -vmName vm1 -vmName vm2
```

### Report VMs from a list, on specific clusters

```
.\get-azure-object-info.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmList vms.txt
```

## Parameters

| Flag | Description |
|---|---|
| `-vip` | (optional) name or IP of Cohesity cluster (defaults to `helios.cohesity.com`) |
| `-username` | (optional) name of user to connect to Cohesity (defaults to `helios`) |
| `-domain` | (optional) your AD domain (defaults to `local`) |
| `-tenant` | (optional) organization to impersonate |
| `-useApiKey` | (optional) use an API key for authentication |
| `-password` | (optional) will use cached password/key or will be prompted |
| `-noPrompt` | (optional) do not prompt for password |
| `-mcm` | (optional) connect through Helios/MCM |
| `-mfaCode` | (optional) TOTP MFA code |
| `-emailMfaCode` | (optional) send MFA code via email |
| `-clusterName` | (optional) one or more cluster names to search; repeat the flag for multiple. Defaults to all Helios-connected clusters |
| `-clusterList` | (optional) text file of cluster names (one per line) |
| `-vmName` | (optional) one or more VM names to look up; repeat the flag for multiple. Defaults to all Azure VMs found |
| `-vmList` | (optional) text file of VM names (one per line) |
| `-outputPath` | (optional) folder for the output CSV (defaults to `./Results`) |

## Output

One row per matched VM, written to `<outputPath>/azure-object-info-<date>.csv` and printed to the console:

| Column | Description |
|---|---|
| `ClusterName` | Cohesity cluster the VM was found on |
| `AzureSource` | name of the registered Azure source containing the VM |
| `SourceId` | numeric Cohesity object id of that Azure source |
| `VMName` | the VM's name |
| `ResourceGroup` | the VM's resource group name |
| `ResourceGroupId` | numeric Cohesity object id of that resource group |
| `SubscriptionGuid` | the VM's Azure subscription id (GUID) |
| `SubscriptionId` | numeric Cohesity object id of that subscription |
| `Region` | Azure region slug, e.g. `eastus2` |
| `RegionId` | numeric Cohesity object id of that region |
| `OSType` | `Linux` or `Windows` |
| `IPAddresses` | comma-separated IP address(es) |
| `IsManagedVM` | whether the VM is an Azure managed disk VM |

## Notes

* Cohesity's Azure protection source tree does not store the VM's compute size/SKU, or any VM-to-virtualNetwork/subnet association - those fields simply don't exist on the model (verified against the `cohesity_management_sdk`/`cohesity_sdk` `AzureProtectionSource` definitions). The `kVirtualNetwork`/`kSubnet`/`kComputeOptions` nodes in the tree are just a catalog of what's available in the subscription for picking a *recovery* target, not a record of what the VM currently uses - this script does not report them at all. Getting the real values requires querying Azure directly (e.g. `Get-AzVM` / `Get-AzNetworkInterface`).
* `ResourceGroup`/`SubscriptionGuid` are recovered by parsing the VM's ARM resourceId (authoritative) with a fallback to walking up the source tree to the nearest `kResourceGroup`/`kSubscription` ancestor. `SourceId`/`ResourceGroupId`/`SubscriptionId`/`RegionId` are things the VM actually sits under (or, for region, a catalog node matched by name), so - unlike compute size/VNet/subnet - they can be resolved accurately from the tree alone.

## Download
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/PowerShell/Reports/Azure/VMs/get-azure-object-info.ps1
