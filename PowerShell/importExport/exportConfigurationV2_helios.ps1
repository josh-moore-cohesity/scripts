# process commandline arguments
[CmdletBinding()]
param (
    [Parameter()][string]$vip='helios.cohesity.com', #the cluster to connect to (DNS name or IP)
    [Parameter()][string]$username = 'helios',
    [Parameter()][string]$domain = 'local', #local or AD domain
    [Parameter()][string]$tenant,
    [Parameter()][switch]$useApiKey,
    [Parameter()][string]$password = $null,
    [Parameter()][switch]$noPrompt,
    [Parameter()][string]$mfaCode = $null,
    [Parameter()][switch]$emailMfaCode,
    [Parameter()][switch]$mcm,
    [Parameter()][string[]]$clusterName,
    [Parameter()][string]$clusterList = '',  # text file of cluster names
    [Parameter()][string]$configFolder = './configExports'  # folder to store export files
)

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

$clusterNames = @(gatherList -Param $clusterName -FilePath $clusterList -Name 'clusternames' -Required $true)

# source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)

# authenticate
apiauth -vip $vip -username $username -domain $domain -passwd $password -apiKeyAuthentication $useApiKey -mfaCode $mfaCode -heliosAuthentication $mcm -tenant $tenant -noPromptForPassword $noPrompt

foreach($cluster in $clusterNames){
# select helios/mcm managed cluster
#if($USING_HELIOS -and !$region){
    #if($clusterName){
        $thisCluster = heliosCluster $cluster
    #}else{
        #write-host "Please provide -clusterName when connecting through helios" -ForegroundColor Yellow
        #exit 1
    #}
#}

if(!$cohesity_api.authorized){
    Write-Host "Not authenticated"
    exit 1
}

# get cluster info
$cluster = api get cluster

# create export folder
$configPath = Join-Path -Path $configFolder -ChildPath $cluster.name 
if(! (Test-Path -PathType Container -Path $configPath)){
    $null = New-Item -ItemType Directory -Path $configPath -Force
}

$summaryFile = Join-Path -Path $configPath -ChildPath 'clusterSummary.txt'

write-host "Exporting configuration information for $($cluster.name) to $configPath..."

# cluster configuration
$cluster | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'cluster.json')
"Cluster name: {0}" -f $cluster.name | Out-File -FilePath $summaryFile
"  Cluster id: {0}" -f $cluster.id | Out-File -FilePath $summaryFile -Append
"     Version: {0}" -f $cluster.clusterSoftwareVersion | Out-File -FilePath $summaryFile -Append
"  Node count: {0}" -f $cluster.nodeCount | Out-File -FilePath $summaryFile -Append
"Domain Names: {0}" -f ($cluster.domainNames -join ', ') | Out-File -FilePath $summaryFile -Append
" DNS Servers: {0}" -f ($cluster.dnsServerIps -join ', ') | Out-File -FilePath $summaryFile -Append

api get viewBoxes | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'storageDomains.json')
api get clusterPartitions | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'clusterPartitions.json')
api get /smtpServer | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'smtp.json')
api get /snmp/config | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'snmp.json') 

# networking
api get interfaceGroups | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'interfaceGroups.json')
api get vlans?skipPrimaryAndBondIface=true | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'vlans.json')
api get /nexus/cluster/get_hosts_file | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'hosts.json')

# access management
api get activeDirectory | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'activeDirectory.json') 
api get idps?allUnderHierarchy=true | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'idps.json') 
api get ldapProvider | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'ldapProvider.json') 
api get roles | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'roles.json') 
api get users | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'users.json') 
api get groups | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'groups.json') 

# copy targets
api get remoteClusters | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'remoteClusters.json')
api get vaults | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'vaults.json')

# data protection
api get protectionSources?allUnderHierarchy=true | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'sources.json')
api get -v2 data-protect/policies?allUnderHierarchy=true | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'policies.json')
api get -v2 data-protect/protection-groups?allUnderHierarchy=true | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'jobs.json')

# file services
api get views?allUnderHierarchy=true | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'views.json')
api get externalClientSubnets | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'globalWhitelist.json')
api get shares | ConvertTo-Json -Depth 99 | Out-File -FilePath (Join-Path -Path $configPath -ChildPath 'shares.json')
}
