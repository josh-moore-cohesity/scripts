<#
.SYNOPSIS
    Report resource group, region/OS, and IP info for one or more Azure VMs, from their Cohesity
    Azure source registration (protectionSources tree).

.NOTES
    Cohesity's Azure protectionSources tree (AzureProtectionSource, azureType 'kVirtualMachine') does not
    store the VM's compute size/SKU, or any VM-to-virtualNetwork/subnet association - those fields simply
    don't exist on the model (verified against the cohesity_management_sdk / cohesity_sdk AzureProtectionSource
    definitions). The kVirtualNetwork/kSubnet/kComputeOptions nodes in the tree are just a catalog of what's
    available in the subscription for picking a *recovery* target, not a record of what the VM currently uses,
    so this script does not report ComputeType/VirtualNetwork/Subnet at all - getting those requires querying
    Azure directly (e.g. Get-AzVM / Get-AzNetworkInterface).
    Resource group and subscription are recovered by parsing the VM's ARM resourceId (authoritative) with a
    fallback to walking up the source tree to the nearest kResourceGroup/kSubscription ancestor. SourceId,
    ResourceGroupId, SubscriptionId, and RegionId are the numeric Cohesity object ids for those same nodes -
    these are things the VM actually sits under, so (unlike compute size/VNet/subnet) they can be resolved
    accurately, and can be passed directly to recover_azure_vm.ps1's -sourceId/-resourceGroupId/-subscriptionId/
    -regionId to recover the VM back to its original location by id instead of by name.
#>

# process commandline arguments
[CmdletBinding()]
param (
    [Parameter()][string]$vip = 'helios.cohesity.com',
    [Parameter()][string]$username = 'helios',
    [Parameter()][string]$domain = 'local',
    [Parameter()][string]$tenant,
    [Parameter()][switch]$useApiKey,
    [Parameter()][string]$password,
    [Parameter()][switch]$noPrompt,
    [Parameter()][switch]$mcm,
    [Parameter()][string]$mfaCode,
    [Parameter()][switch]$emailMfaCode,
    [Parameter()][string[]]$clusterName,
    [Parameter()][string]$clusterList = '',  # text file of cluster names
    [Parameter()][string]$outputPath = './Results',

    # VM(s) to look up (all Azure VMs found if neither is specified)
    [Parameter()][string[]]$vmName,
    [Parameter()][string]$vmList = ''  # text file of VM names
)

# source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)

# gather list from command line params and file
function gatherList($Param=$null, $FilePath=$null, $Required=$True, $Name='items'){
    $items = @()
    if($Param){
        $Param | ForEach-Object {$items += $_}
    }
    if($FilePath){
        if(Test-Path -Path $FilePath -PathType Leaf){
            Get-Content $FilePath | ForEach-Object {$items += [string]$_}
        }else{
            Write-Host "Text file $FilePath not found!" -ForegroundColor Yellow
            exit
        }
    }
    if($Required -eq $True -and $items.Count -eq 0){
        Write-Host "No $Name specified" -ForegroundColor Yellow
        exit
    }
    return ($items | Sort-Object -Unique)
}

# recursively find all kVirtualMachine nodes matching $names (all VM nodes if $names is empty), tracking
# each match's chain of ancestor nodes (root first) so the resource group/subscription can be resolved
function findAzureVMs($node, $names, $ancestors=@()){
    $matches = @()
    if($node.protectionSource.azureProtectionSource.type -eq 'kVirtualMachine'){
        if($names.Count -eq 0 -or $node.protectionSource.name -in $names){
            $matches += [PSCustomObject]@{'node' = $node; 'ancestors' = $ancestors}
        }
    }
    $childAncestors = $ancestors + $node
    foreach($child in $node.nodes){
        $matches += findAzureVMs $child $names $childAncestors
    }
    return $matches
}

# nearest ancestor (closest to the node, i.e. last in the list) of the given azureType -
# returns the ancestor's protectionSource (both .name and .id), or $null if none found
function nearestAncestor($ancestors, $type){
    for($i = $ancestors.Count - 1; $i -ge 0; $i--){
        if($ancestors[$i].protectionSource.azureProtectionSource.type -eq $type){
            return $ancestors[$i].protectionSource
        }
    }
    return $null
}

# find the first protectionSources tree node of $type named $name, at or below $node -
# used for catalog nodes (e.g. kRegion) that aren't ancestors of the VM node
function findAzureNode($node, $type, $name){
    if($node.protectionSource -and $node.protectionSource.azureProtectionSource.type -eq $type -and $node.protectionSource.name -eq $name){
        return $node
    }
    foreach($child in $node.nodes){
        $found = findAzureNode $child $type $name
        if($found){ return $found }
    }
    return $null
}

# get list of clusters from command line params and/or file
$clusterNames = @(gatherList -Param $clusterName -FilePath $clusterList -Name 'clusters' -Required $false)

# get list of VMs to look up (all Azure VMs found if none specified)
$vmNames = @(gatherList -Param $vmName -FilePath $vmList -Name 'VMs' -Required $false)

# date and time
$now = Get-Date
$dateTimeString = $now.ToString('MM/dd/yyyy hh:mm tt')
$dateString = $now.ToString('yyyy-MM-dd')

if(! (Test-Path -Path $outputPath -PathType Container)){
    New-Item -Path $outputPath -ItemType Directory | Out-Null
}
$outfile = Join-Path -Path $outputPath -ChildPath "azure-object-info-$dateString.csv"
$results = @()

# authentication =============================================

# authenticate
apiauth -vip $vip -username $username -domain $domain -passwd $password -apiKeyAuthentication $useApiKey -mfaCode $mfaCode -sendMfaCode $emailMfaCode -heliosAuthentication $mcm -tenant $tenant -noPromptForPassword $noPrompt

# exit on failed authentication
if(!$cohesity_api.authorized){
    Write-Host "Not authenticated" -ForegroundColor Yellow
    exit 1
}

# end authentication =========================================

# get clusters (all Helios-connected clusters if none specified)
if($clusterNames.Count -eq 0){
    $clusters = (api get -mcmv2 cluster-mgmt/info).cohesityClusters | Where-Object {$_.isConnectedToHelios -eq $True}
    $clusterNames = $clusters.clusterName
}

$vmNamesRemaining = [System.Collections.Generic.List[string]]$vmNames

foreach($cluster in $clusterNames){
    heliosCluster $cluster
    Write-Host $cluster

    if($cohesity_api.last_api_error -ne 'OK'){
        continue
    }

    # walk each registered Azure source's tree looking for the requested VM(s)
    $azureRoots = @(api get "protectionSources?environments=kAzure")
    foreach($azureRoot in $azureRoots){
        $sourceName = $azureRoot.protectionSource.name
        $azureTree = api get "protectionSources?id=$($azureRoot.protectionSource.id)&environments=kAzure"

        $vmMatches = @(findAzureVMs $azureTree $vmNamesRemaining)
        foreach($match in $vmMatches){
            $vmSource = $match.node.protectionSource.azureProtectionSource
            $matchedVmName = $match.node.protectionSource.name

            # resource group / subscription: parse the authoritative ARM resourceId first, fall back to
            # the nearest matching ancestor in the source tree. Either way, that same ancestor node also
            # gives us the numeric Cohesity object id for the resource group/subscription - useful for
            # feeding straight into recover_azure_vm.ps1's -resourceGroupId/-subscriptionId
            $resourceGroupNode = nearestAncestor $match.ancestors 'kResourceGroup'
            $subscriptionNode = nearestAncestor $match.ancestors 'kSubscription'

            $resourceGroup = $null
            $subscriptionGuid = $vmSource.subscriptionId
            if($vmSource.resourceId -match '/subscriptions/([^/]+)/resourceGroups/([^/]+)/'){
                $subscriptionGuid = $Matches[1]
                $resourceGroup = $Matches[2]
            }
            if(! $resourceGroup){
                $resourceGroup = $resourceGroupNode.name
            }
            if(! $subscriptionGuid){
                $subscriptionGuid = $subscriptionNode.name
            }

            # region is a catalog node, not an ancestor of the VM - resolve its id by matching name
            $regionId = (findAzureNode $azureTree 'kRegion' $vmSource.location).protectionSource.id

            $osType = $vmSource.hostType -replace '^k', ''

            $results += [PSCustomObject]@{
                'ClusterName'     = $cluster
                'AzureSource'     = $sourceName
                'SourceId'        = $azureRoot.protectionSource.id
                'VMName'          = $matchedVmName
                'ResourceGroup'   = $resourceGroup
                'ResourceGroupId' = $resourceGroupNode.id
                'SubscriptionGuid'= $subscriptionGuid
                'SubscriptionId'  = $subscriptionNode.id
                'Region'          = $vmSource.location
                'RegionId'        = $regionId
                'OSType'          = $osType
                'IPAddresses'     = ($vmSource.ipAddresses -join ', ')
                'IsManagedVM'     = $vmSource.isManagedVm
            }

            $vmNamesRemaining.Remove($matchedVmName) | Out-Null
        }
    }
}

foreach($missingVm in $vmNamesRemaining){
    Write-Host "VM '$missingVm' not found on any specified cluster" -ForegroundColor Yellow
}

if($results.Count -gt 0){
    $results | Format-Table -AutoSize
    $results | Export-Csv -Path $outfile -NoTypeInformation
    Write-Host "`nOutput saved to $outfile"
}else{
    Write-Host "No matching VMs found" -ForegroundColor Yellow
}
