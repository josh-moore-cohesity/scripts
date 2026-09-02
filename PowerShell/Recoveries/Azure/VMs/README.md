# Recover an Azure VM Using PowerShell

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`recover_azure_vm.ps1` recovers one or more Azure VMs from a Cohesity snapshot, either back to their original subscription/resource group/network or to a new one, via the `/v2/data-protect/recoveries` (`createRecovery`) API. See the [API reference](https://developers.cohesity.com/v1-cluster-7.3.2/reference/createrecovery).

## Requirements

* Windows PowerShell 5.1+ or PowerShell 7+ (`pwsh`)
* [`cohesity-api.ps1`](https://github.com/bseltz-cohesity/scripts/tree/master/powershell/cohesity-api) in the same directory as `recover_azure_vm.ps1`

## Components

* `recover_azure_vm.ps1` - the main script
* `cohesity-api.ps1` - the Cohesity REST API helper module

## Recovery Target

By default, VMs are recovered back to their original subscription, resource group and network. Pass `-newSource` to recover to a different target instead - a new resource group, virtual network, subnet, subscription, region and VM size are then all required.

For each new-source target object, pass either its `*Name` (the script looks up the matching numeric Cohesity object id for you by walking the registered Azure source's protection-sources tree) or its `*Id` directly if you already know it, to skip that lookup.

### Recover to the original location

```
.\recover_azure_vm.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmName vm1 -powerOn
```

### Recover multiple VMs from a list, from a point-in-time snapshot

```
.\recover_azure_vm.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmList vms.txt -recoverDate '2026-08-30 14:00:00' -powerOn
```

### Recover to a new subscription/resource group/network, by name

```
.\recover_azure_vm.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmName vm1 -newSource `
    -resourceGroupName rg-dr -virtualNetworkName vnet-dr -subnetName subnet-dr `
    -subscriptionName 00000000-0000-0000-0000-000000000000 -regionName eastus2 -computeOptionName Standard_B2s -powerOn
```

### Recover to a new source using known object ids (skips the name lookup)

```
.\recover_azure_vm.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmName vm1 -newSource `
    -resourceGroupId 12345 -virtualNetworkId 12346 -subnetId 12347 -subscriptionId 12348 -regionId 12349 -computeOptionId 12350 -powerOn
```

### Recover to a new source over a private-endpoint data transfer

```
.\recover_azure_vm.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmName vm1 -newSource `
    -resourceGroupName rg-dr -virtualNetworkName vnet-dr -subnetName subnet-dr `
    -subscriptionName 00000000-0000-0000-0000-000000000000 -regionName eastus2 -computeOptionName Standard_B2s `
    -privateEndpoint -dataTransferSubnetName subnet-transfer
```

### Rename recovered VMs and continue past per-VM errors

```
.\recover_azure_vm.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmList vms.txt -continueOnError -renamePrefix 'dr-'
```

## Authentication Parameters

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

## Cluster/VM Selection Parameters

| Flag | Description |
|---|---|
| `-clusterName` | (optional) one or more cluster names to run against; repeat the flag for multiple. Defaults to all Helios-connected clusters |
| `-clusterList` | (optional) text file of cluster names (one per line) |
| `-vmName` | (required unless `-vmList`) one or more VM names to recover; repeat the flag for multiple |
| `-vmList` | (required unless `-vmName`) text file of VM names (one per line) |
| `-recoverDate` | (optional) recover the latest snapshot at or before this date/time, e.g. `'2026-08-30 14:00:00'`. Defaults to the latest snapshot |
| `-recoveryName` | (optional) name for the recovery task (defaults to `Recover-Azure-VM-<date>`) |
| `-powerOn` | (optional) power on the recovered VM(s) |
| `-continueOnError` | (optional) continue recovering remaining VMs if one fails |
| `-renamePrefix` | (optional) prepended to recovered VM name(s) |
| `-renameSuffix` | (optional) appended to recovered VM name(s) |

## New-Source Recovery Target Parameters

Only used with `-newSource`. For each pair, either the `*Id` or the `*Name` is required unless noted otherwise; if a name is given, the script resolves it to a numeric Cohesity object id automatically.

| Flag | Description |
|---|---|
| `-sourceId` / `-sourceName` | (optional) target Azure source/subscription registration. Only needed if more than one Azure source is registered on the cluster - the script auto-selects the sole registered source otherwise |
| `-resourceGroupId` / `-resourceGroupName` | (required) target resource group |
| `-virtualNetworkId` / `-virtualNetworkName` | (required) target virtual network |
| `-subnetId` / `-subnetName` | (required) target subnet |
| `-subscriptionId` / `-subscriptionName` | (required) target subscription |
| `-regionId` / `-regionName` | (required) target Azure region, e.g. `eastus2` |
| `-computeOptionId` / `-computeOptionName` | (required) target VM size, e.g. `Standard_B2s` |
| `-networkResourceGroupId` / `-networkResourceGroupName` | (optional) resource group for the network config, if different from `-resourceGroupName`. Defaults to the primary resource group |
| `-availabilitySetId` / `-availabilitySetName` | (optional) target availability set |
| `-storageResourceGroupId` / `-storageResourceGroupName` | (optional) resource group for an explicit storage account |
| `-storageAccountId` / `-storageAccountName` | (optional) explicit storage account for the disk transfer |
| `-storageContainerId` / `-storageContainerName` | (optional) explicit storage container for the disk transfer |

## Data Transfer Parameters

Controls how disks are transferred to Azure during a `-newSource` recovery. Defaults to a public-endpoint SAS URL transfer.

| Flag | Description |
|---|---|
| `-privateEndpoint` | (optional) use a private endpoint for the disk transfer instead of a public SAS URL |
| `-dataTransferRegionId` / `-dataTransferRegionName` | (optional) region for the private-endpoint transfer network. Defaults to the main `-region` above |
| `-dataTransferVirtualNetworkId` / `-dataTransferVirtualNetworkName` | (optional) virtual network for the private-endpoint transfer. Defaults to the main `-virtualNetwork` above |
| `-dataTransferSubnetId` / `-dataTransferSubnetName` | (optional) subnet for the private-endpoint transfer. Defaults to the main `-subnet` above |

## Notes

* `-newSource` recoveries need several target objects as **numeric Cohesity object ids** (resource group, virtual network, subnet, subscription, region, and VM size) even though most are marked optional in the API schema - omitting one produces a generic internal error instead of a clean validation message. Pass the `*Name` params and let the script resolve the ids, or pass the matching `*Id` directly if you already know it.
* The public-endpoint disk transfer (the default) has been verified end-to-end against a live cluster. The `-privateEndpoint` form is only confirmed to pass API validation - actual private-network transfer completion has not been confirmed.
* `-outputPath` is reserved and currently unused.

## Download
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/PowerShell/Recoveries/Azure/VMs/recover_azure_vm.ps1
