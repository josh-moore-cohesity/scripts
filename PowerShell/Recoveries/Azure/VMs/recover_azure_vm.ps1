<#
.SYNOPSIS
    Recover one or more Azure VMs using the /v2/data-protect/recoveries (createRecovery) API with azureParams.
    https://developers.cohesity.com/v1-cluster-7.3.2/reference/createrecovery

.NOTES
    Body shape verified against the cohesity_sdk model docs (RecoverAzureParams / RecoverAzureVmParams /
    AzureTargetParamsForRecoverVm / RecoverAzureVmNewSourceConfig):
      { name, snapshotEnvironment, azureParams: { recoveryAction, objects, recoverVmParams: { targetEnvironment,
        azureTargetParams: { continueOnError, powerOnVms, recoveryTargetConfig, renameRecoveredVmsParams } } } }

    -newSource recoveries need several target objects as numeric Cohesity object ids
    (RecoveryObjectIdentifier.id - not raw Azure resource IDs): resource group, virtual network, subnet,
    subscription, region, and compute size (VM SKU, e.g. Standard_A2) are all required by the cluster even
    though the API schema marks most of them optional - omitting any of them causes a generic KInternalError
    instead of a clean validation message. newSourceConfig also always needs a networkResourceGroup (undocumented;
    defaults to the primary resource group) and a dataTransferInfo block. The public-endpoint dataTransferInfo
    shape was verified end-to-end by capturing the actual request the Cohesity UI sends; the -privateEndpoint
    form (DataTransferInfo.privateNetworkInfoList: region/vpn/subnet) is only confirmed to pass API validation
    (no KInternalError) - actual private-network transfer completion hasn't been confirmed. Pass the *Name params (-resourceGroupName,
    -virtualNetworkName, -subnetName, -subscriptionName, -regionName, -computeOptionName, etc.) and the script
    resolves the ids itself by walking the cluster's protectionSources tree for the registered Azure source -
    or pass the matching *Id param directly to skip the lookup. -storageResourceGroupName/-storageAccountName/
    -storageContainerName stay optional (the UI only sends these when an explicit storage account is picked).
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

    # VMs to recover
    [Parameter()][string[]]$vmName,
    [Parameter()][string]$vmList = '',  # text file of VM names
    [Parameter()][string]$recoverDate,  # e.g. '2026-08-30 14:00:00' - latest snapshot at or before this time. Omit for the latest snapshot.
    [Parameter()][string]$recoveryName,  # defaults to Recover-Azure-VM-<date>
    [Parameter()][switch]$powerOn,
    [Parameter()][switch]$continueOnError,
    [Parameter()][switch]$preview,  # print the recovery request JSON instead of submitting it
    [Parameter()][string]$renamePrefix,  # prepended to recovered VM name(s)
    [Parameter()][string]$renameSuffix,  # appended to recovered VM name(s)

    # recovery target (defaults to the original Azure source/resource group).
    # For each pair below, either the *Id or the *Name is required with -newSource. If a name is given, the
    # script looks up its numeric id automatically; the id (if you already know it) skips the lookup.
    [Parameter()][switch]$newSource,
    [Parameter()][Int64]$sourceId,
    [Parameter()][string]$sourceName,                # Azure source/subscription registration name (only needed if more than one is registered)
    [Parameter()][Int64]$resourceGroupId,
    [Parameter()][string]$resourceGroupName,
    [Parameter()][Int64]$virtualNetworkId,
    [Parameter()][string]$virtualNetworkName,
    [Parameter()][Int64]$subnetId,
    [Parameter()][string]$subnetName,
    [Parameter()][Int64]$networkResourceGroupId,
    [Parameter()][string]$networkResourceGroupName,
    [Parameter()][Int64]$availabilitySetId,
    [Parameter()][string]$availabilitySetName,
    [Parameter()][Int64]$subscriptionId,
    [Parameter()][string]$subscriptionName,
    [Parameter()][Int64]$regionId,
    [Parameter()][string]$regionName,                # Azure region slug, e.g. eastus2
    [Parameter()][Int64]$computeOptionId,
    [Parameter()][string]$computeOptionName,          # Azure VM size, e.g. Standard_A2
    [Parameter()][Int64]$storageResourceGroupId,
    [Parameter()][string]$storageResourceGroupName,
    [Parameter()][Int64]$storageAccountId,
    [Parameter()][string]$storageAccountName,         # optional
    [Parameter()][Int64]$storageContainerId,
    [Parameter()][string]$storageContainerName,       # optional

    # Azure SAS URL type for the disk transfer (defaults to public endpoint). -privateEndpoint switches to a
    # private endpoint; its region/virtual network/subnet default to the main -region/-virtualNetwork/-subnet
    # above if not given separately. UNVERIFIED - unlike the public-endpoint path, this hasn't been confirmed
    # against a live cluster; capture the UI's actual request (see .NOTES) if it doesn't work as-is.
    [Parameter()][switch]$privateEndpoint,
    [Parameter()][Int64]$dataTransferRegionId,
    [Parameter()][string]$dataTransferRegionName,
    [Parameter()][Int64]$dataTransferVirtualNetworkId,
    [Parameter()][string]$dataTransferVirtualNetworkName,
    [Parameter()][Int64]$dataTransferSubnetId,
    [Parameter()][string]$dataTransferSubnetName
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

# build a Cohesity RecoveryObjectIdentifier ({id}), or $null if no id was given
function roi($id){
    if($id){
        return @{'id' = $id}
    }
    return $null
}

# find the first protectionSources tree node of $type named $name, at or below $node
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

# reformat ConvertTo-Json's output - Windows PowerShell pads every "key":  value with two spaces
# and aligns brackets oddly; this collapses it to normal, tightly-indented JSON
function Format-Json([string]$json){
    $indent = 0
    ($json -split '\r?\n' | ForEach-Object {
        if($_ -match '[\}\]]\s*,?\s*$'){
            $indent = [Math]::Max($indent - 1, 0)
        }
        $line = ('  ' * $indent) + ($_.TrimStart() -replace '":\s+(["{[])', '": $1' -replace ':\s+', ': ')
        if($_ -match '[\{\[]\s*$'){
            $indent++
        }
        $line
    }) -join "`n"
}

# get list of clusters from command line params and/or file
$clusterNames = @(gatherList -Param $clusterName -FilePath $clusterList -Name 'clusters' -Required $false)

# get list of VMs to recover
$vmNames = @(gatherList -Param $vmName -FilePath $vmList -Name 'VMs' -Required $true)

# validate new-source recovery target params (each pair needs an id or a name to resolve one).
# -sourceId/-sourceName is not required here - if omitted, the script auto-selects the only registered
# Azure source once connected to a cluster (and errors per-cluster if there's more than one).
if($newSource){
    if(! $resourceGroupId -and ! $resourceGroupName){
        Write-Host "-resourceGroupId or -resourceGroupName is required when -newSource is specified" -ForegroundColor Yellow
        exit 1
    }
    if(! $virtualNetworkId -and ! $virtualNetworkName){
        Write-Host "-virtualNetworkId or -virtualNetworkName is required when -newSource is specified" -ForegroundColor Yellow
        exit 1
    }
    if(! $subnetId -and ! $subnetName){
        Write-Host "-subnetId or -subnetName is required when -newSource is specified" -ForegroundColor Yellow
        exit 1
    }
    if(! $subscriptionId -and ! $subscriptionName){
        Write-Host "-subscriptionId or -subscriptionName is required when -newSource is specified" -ForegroundColor Yellow
        exit 1
    }
    if(! $regionId -and ! $regionName){
        Write-Host "-regionId or -regionName is required when -newSource is specified" -ForegroundColor Yellow
        exit 1
    }
    if(! $computeOptionId -and ! $computeOptionName){
        Write-Host "-computeOptionId or -computeOptionName (Azure VM size) is required when -newSource is specified" -ForegroundColor Yellow
        exit 1
    }
}

# date and time
$now = Get-Date
$dateTimeString = $now.ToString('MM/dd/yyyy hh:mm tt')
$dateString = $now.ToString('yyyy-MM-dd')

$recoverAtUsecs = $null
if($recoverDate){
    $recoverAtUsecs = dateToUsecs $recoverDate
}

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

foreach($cluster in $clusterNames){
    heliosCluster $cluster
    Write-Host $cluster

    if($cohesity_api.last_api_error -ne 'OK'){
        continue
    }

    # resolve the new-source recovery target ids (by name) for this cluster
    if($newSource){
        $azureSourceId = $sourceId
        if(! $azureSourceId){
            $azureRoots = @(api get "protectionSources?environments=kAzure")
            if($sourceName){
                $azureRoot = $azureRoots | Where-Object {$_.protectionSource.name -eq $sourceName} | Select-Object -First 1
            }elseif($azureRoots.Count -eq 1){
                $azureRoot = $azureRoots[0]
            }else{
                Write-Host "  Multiple Azure sources are registered on $cluster - specify -sourceName or -sourceId" -ForegroundColor Yellow
                continue
            }
            if(! $azureRoot){
                Write-Host "  Azure source '$sourceName' not found on $cluster" -ForegroundColor Yellow
                continue
            }
            $azureSourceId = $azureRoot.protectionSource.id
        }

        $azureTree = api get "protectionSources?id=$azureSourceId&environments=kAzure"

        $azureResourceGroupId = $resourceGroupId
        if(! $azureResourceGroupId){
            $azureResourceGroupId = (findAzureNode $azureTree 'kResourceGroup' $resourceGroupName).protectionSource.id
            if(! $azureResourceGroupId){
                Write-Host "  Resource group '$resourceGroupName' not found on $cluster" -ForegroundColor Yellow
                continue
            }
        }

        $azureVnetNode = $null
        $azureVirtualNetworkId = $virtualNetworkId
        if(! $azureVirtualNetworkId){
            $azureVnetNode = findAzureNode $azureTree 'kVirtualNetwork' $virtualNetworkName
            if(! $azureVnetNode){
                Write-Host "  Virtual network '$virtualNetworkName' not found on $cluster" -ForegroundColor Yellow
                continue
            }
            $azureVirtualNetworkId = $azureVnetNode.protectionSource.id
        }

        $azureSubnetId = $subnetId
        if(! $azureSubnetId){
            $searchNode = $(if($azureVnetNode){$azureVnetNode}else{$azureTree})
            $azureSubnetId = (findAzureNode $searchNode 'kSubnet' $subnetName).protectionSource.id
            if(! $azureSubnetId){
                Write-Host "  Subnet '$subnetName' not found on $cluster" -ForegroundColor Yellow
                continue
            }
        }

        # networkResourceGroup is undocumented-required (the UI always sends it) - default to the primary
        # resource group when not given explicitly
        $azureNetworkResourceGroupId = $networkResourceGroupId
        if(! $azureNetworkResourceGroupId -and $networkResourceGroupName){
            $azureNetworkResourceGroupId = (findAzureNode $azureTree 'kResourceGroup' $networkResourceGroupName).protectionSource.id
        }
        if(! $azureNetworkResourceGroupId){
            $azureNetworkResourceGroupId = $azureResourceGroupId
        }

        $azureAvailabilitySetId = $availabilitySetId
        if(! $azureAvailabilitySetId -and $availabilitySetName){
            $azureAvailabilitySetId = (findAzureNode $azureTree 'kAvailabilitySet' $availabilitySetName).protectionSource.id
        }

        $azureSubscriptionId = $subscriptionId
        if(! $azureSubscriptionId){
            $azureSubscriptionId = (findAzureNode $azureTree 'kSubscription' $subscriptionName).protectionSource.id
            if(! $azureSubscriptionId){
                Write-Host "  Subscription '$subscriptionName' not found on $cluster" -ForegroundColor Yellow
                continue
            }
        }

        $azureRegionId = $regionId
        if(! $azureRegionId){
            $azureRegionId = (findAzureNode $azureTree 'kRegion' $regionName).protectionSource.id
            if(! $azureRegionId){
                Write-Host "  Region '$regionName' not found on $cluster" -ForegroundColor Yellow
                continue
            }
        }

        $azureComputeOptionId = $computeOptionId
        if(! $azureComputeOptionId){
            $azureComputeOptionId = (findAzureNode $azureTree 'kComputeOptions' $computeOptionName).protectionSource.id
            if(! $azureComputeOptionId){
                Write-Host "  VM size '$computeOptionName' not found on $cluster" -ForegroundColor Yellow
                continue
            }
        }

        $azureStorageResourceGroupId = $storageResourceGroupId
        if(! $azureStorageResourceGroupId -and $storageResourceGroupName){
            $azureStorageResourceGroupId = (findAzureNode $azureTree 'kResourceGroup' $storageResourceGroupName).protectionSource.id
        }

        $azureStorageAccountId = $storageAccountId
        if(! $azureStorageAccountId -and $storageAccountName){
            $azureStorageAccountId = (findAzureNode $azureTree 'kStorageAccount' $storageAccountName).protectionSource.id
        }

        $azureStorageContainerId = $storageContainerId
        if(! $azureStorageContainerId -and $storageContainerName){
            $azureStorageContainerId = (findAzureNode $azureTree 'kStorageContainer' $storageContainerName).protectionSource.id
        }

        # private-endpoint SAS transfer network - defaults to the main region/virtualNetwork/subnet above
        if($privateEndpoint){
            $azureDataTransferRegionId = $dataTransferRegionId
            if(! $azureDataTransferRegionId -and $dataTransferRegionName){
                $azureDataTransferRegionId = (findAzureNode $azureTree 'kRegion' $dataTransferRegionName).protectionSource.id
            }
            if(! $azureDataTransferRegionId){ $azureDataTransferRegionId = $azureRegionId }

            $azureDataTransferVirtualNetworkId = $dataTransferVirtualNetworkId
            if(! $azureDataTransferVirtualNetworkId -and $dataTransferVirtualNetworkName){
                $azureDataTransferVirtualNetworkId = (findAzureNode $azureTree 'kVirtualNetwork' $dataTransferVirtualNetworkName).protectionSource.id
            }
            if(! $azureDataTransferVirtualNetworkId){ $azureDataTransferVirtualNetworkId = $azureVirtualNetworkId }

            $azureDataTransferSubnetId = $dataTransferSubnetId
            if(! $azureDataTransferSubnetId -and $dataTransferSubnetName){
                $azureDataTransferSubnetId = (findAzureNode $azureTree 'kSubnet' $dataTransferSubnetName).protectionSource.id
            }
            if(! $azureDataTransferSubnetId){ $azureDataTransferSubnetId = $azureSubnetId }
        }
    }

    # find each VM's latest (or point-in-time) snapshot
    $recoveryObjects = @()
    foreach($vm in $vmNames){
        Write-Host "  Searching for VM $vm..."
        $searchResult = api get "data-protect/search/protected-objects?searchString=$vm&environments=kAzure" -v2
        $object = $searchResult.objects | Where-Object {$_.name -eq $vm} | Select-Object -First 1
        if(! $object){
            Write-Host "    VM $vm not found" -ForegroundColor Yellow
            continue
        }

        $snapshots = (api get "data-protect/objects/$($object.id)/snapshots" -v2).snapshots
        if($recoverAtUsecs){
            $snapshotInfo = $snapshots | Where-Object {$_.runStartTimeUsecs -le $recoverAtUsecs} | Sort-Object -Property runStartTimeUsecs -Descending | Select-Object -First 1
            if(! $snapshotInfo){
                Write-Host "    No snapshot found for $vm at or before $recoverDate" -ForegroundColor Yellow
                continue
            }
        }else{
            $snapshotInfo = $snapshots | Sort-Object -Property runStartTimeUsecs -Descending | Select-Object -First 1
            if(! $snapshotInfo){
                Write-Host "    No snapshot found for $vm" -ForegroundColor Yellow
                continue
            }
        }
        $snapshotId = $snapshotInfo.id

        Write-Host "    Using snapshot $snapshotId"
        $recoveryObjects += @{'snapshotId' = $snapshotId}
    }

    if($recoveryObjects.Count -eq 0){
        Write-Host "  No VMs to recover on $cluster" -ForegroundColor Yellow
        continue
    }

    # build the recovery target config
    $recoveryTargetConfig = @{'recoverToNewSource' = [bool]$newSource}
    if($newSource){
        $networkConfig = @{
            'virtualNetwork' = (roi $azureVirtualNetworkId)
            'subnet' = (roi $azureSubnetId)
        }
        if($azureNetworkResourceGroupId){ $networkConfig['networkResourceGroup'] = (roi $azureNetworkResourceGroupId) }

        $newSourceConfig = @{
            'source' = (roi $azureSourceId)
            'resourceGroup' = (roi $azureResourceGroupId)
            'networkConfig' = $networkConfig
            'subscription' = (roi $azureSubscriptionId)
            'region' = (roi $azureRegionId)
            'computeOption' = (roi $azureComputeOptionId)
        }
        if($privateEndpoint){
            # UNVERIFIED - field names come from the cohesity_sdk schema (DataTransferInfo/PrivateNetworkInfo),
            # not from a captured working request like the public-endpoint form below
            $newSourceConfig['dataTransferInfo'] = @{
                'isPrivateNetwork' = $true
                'useProtectionJobInfo' = $false
                'privateNetworkInfoList' = @(
                    @{
                        'region' = (roi $azureDataTransferRegionId)
                        'vpn' = (roi $azureDataTransferVirtualNetworkId)
                        'subnet' = (roi $azureDataTransferSubnetId)
                    }
                )
            }
        }else{
            # matches the request the Cohesity UI actually sends (public-endpoint SAS transfer) - verified
            # against a live cluster
            $newSourceConfig['dataTransferInfo'] = @{
                'isPrivateNetwork' = $false
                'useProtectionJobInfo' = $false
                'privateNetworkInfoList' = $null
            }
        }
        if($azureAvailabilitySetId){ $newSourceConfig['availabilitySet'] = (roi $azureAvailabilitySetId) }
        if($azureStorageResourceGroupId){ $newSourceConfig['storageResourceGroup'] = (roi $azureStorageResourceGroupId) }
        if($azureStorageAccountId){ $newSourceConfig['storageAccount'] = (roi $azureStorageAccountId) }
        if($azureStorageContainerId){ $newSourceConfig['storageContainer'] = (roi $azureStorageContainerId) }

        $recoveryTargetConfig['newSourceConfig'] = $newSourceConfig
    }

    # build azureTargetParams
    $azureTargetParams = @{
        'continueOnError' = [bool]$continueOnError
        'powerOnVms' = [bool]$powerOn
        'recoveryTargetConfig' = $recoveryTargetConfig
    }
    if($renamePrefix -or $renameSuffix){
        $renameParams = @{}
        if($renamePrefix){ $renameParams['prefix'] = $renamePrefix }
        if($renameSuffix){ $renameParams['suffix'] = $renameSuffix }
        $azureTargetParams['renameRecoveredVmsParams'] = $renameParams
    }

    $thisRecoveryName = $recoveryName
    if(! $thisRecoveryName){ $thisRecoveryName = "Recover-Azure-VM-$dateString" }

    $recoveryParams = @{
        'name' = $thisRecoveryName
        'snapshotEnvironment' = 'kAzure'
        'azureParams' = @{
            'recoveryAction' = 'RecoverVMs'
            'objects' = $recoveryObjects
            'recoverVmParams' = @{
                'targetEnvironment' = 'kAzure'
                'azureTargetParams' = $azureTargetParams
            }
        }
    }

    if($preview){
        Write-Host "  Preview of recovery '$thisRecoveryName' for $($recoveryObjects.Count) VM(s) on ${cluster}:"
        Format-Json ($recoveryParams | ConvertTo-Json -Depth 10)
        continue
    }

    Write-Host "  Creating recovery '$thisRecoveryName' for $($recoveryObjects.Count) VM(s) on $cluster..."
    $result = api post "data-protect/recoveries" $recoveryParams -v2

    if($cohesity_api.last_api_error -eq 'OK' -and $result){
        Write-Host "  Recovery task created (id: $($result.id))" -ForegroundColor Green
    }else{
        Write-Host "  Recovery request failed: $($cohesity_api.last_api_error)" -ForegroundColor Yellow
    }
}
