# **recover_azure_vm.ps1**

   Recover one or more Azure VMs from a Cohesity snapshot, either back to their original resource group or to a new subscription, resource group, and network. Target resource group/network/subscription/region/VM size can be given by name - the script resolves the underlying Cohesity object ids itself. <br />
   [cohesity-api.ps1](https://github.com/bseltz-cohesity/scripts/tree/master/powershell/cohesity-api) is required

## **Examples**

    .\recover_azure_vm.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmName vm1 -powerOn

    .\recover_azure_vm.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmList vms.txt -recoverDate '2026-08-30 14:00:00' -powerOn

    .\recover_azure_vm.ps1 -vip helios.cohesity.com -useApiKey -clusterName mycluster -vmName vm1 -newSource `
        -resourceGroupName rg-dr -virtualNetworkName vnet-dr -subnetName subnet-dr `
        -subscriptionName 00000000-0000-0000-0000-000000000000 -regionName eastus2 -computeOptionName Standard_B2s -powerOn

## **Download**
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/PowerShell/Recoveries/Azure/VMs/recover_azure_vm.ps1
