# process commandline arguments
[CmdletBinding()]
param (

[Parameter()][array]$objectnames, # list of objects to include in audit
[Parameter()][string]$objectlist = '',  # text file of object names
[Parameter()][switch]$showsnaps  # Report Snapshot Info

)

# gather list of objects to audit
$objects = @()
foreach($o in $objectnames){
    $objects += $o
}
if ('' -ne $objectlist){
    if(Test-Path -Path $objectlist -PathType Leaf){
        $servers = Get-Content $objectlist
        foreach($server in $servers){
            $objects += [string]$server
        }
    }else{
        Write-Host "Object list $objectlist not found!" -ForegroundColor Yellow
        exit
    }
}
if($objects.Count -eq 0){
    Write-Host "No objects to audit" -ForegroundColor Yellow
    exit
}

# source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)

#Source API Helper
. .\cohesity-api.ps1

#connect to helios with api key
apiauth -apiKeyAuthentication 1

#capture date
$dateString = (get-date).ToString("yyyy-MM-dd")

#get clusters connected in Helios
$clusters = api get -mcmv2 cluster-mgmt/info

$clusters = $clusters.cohesityClusters

$clusters = $clusters |Where-Object {$_.isConnectedToHelios -eq $true}

#Set output file
if($objectlist){
$outfile = $(Join-Path -Path $PSScriptRoot -ChildPath "$objectlist.csv")
}
else{
$outfile = $(Join-Path -Path $PSScriptRoot -ChildPath "audit-protection-$dateString.csv")
}


#Create or Clear Output File and add header row
if($showsnaps){

"Object,Cluster,Protection Group,Backup Type,Policy,Retention,Total Snapshots,Oldest Snapshot, Newest Snapshot" | Out-File $outfile

}
else{
"Object,Cluster,Protection Group,Backup Type,Policy,Retention" | Out-File $outfile
}

#Get Stats and Info for each object
foreach($object in $objects){

Write-Host "Getting Details for $object" -ForegroundColor Green

#Find Object
$stats = api -v2 get data-protect/search/objects?searchString=$object`&includeTenants=true`&count=5
$stats = $stats.objects

#Find Object Primary Cluster
$primarybackup = $stats |Where-Object {$_.objectProtectionInfos.protectionGroups -ne $null}
$primarybackupinfo = $primarybackup.objectProtectionInfos |Where-Object {$_.protectionGroups -ne $null}

if($primarybackupinfo -eq $null){

Write-Host "No Backups found for $object" -ForegroundColor Yellow
"$object,No Backup Found" | Out-File $outfile -Append
continue

}
#Get Backup Type (vmware, physical, etc)
$environment = $primarybackup.environment.Substring(1)

foreach($record in $primarybackupinfo){ 
#Find Object ID
$objectid = $record.objectid

#Get Details on Primary Cluster
$cluster = $clusters |where-object {$_.clusterId -eq $primarybackupinfo.clusterId[0]}
$clustername = $cluster.clusterName
$clusterid = $cluster.clusterId

#Connect to Object Primary Cluster
heliosCluster $clustername


#Get Snapshots For Object
$snapshots = api get -v2 data-protect/objects/$objectid/snapshots?runTypes=kRegular`&orrunTypes=kFull
$snapshots = $snapshots.snapshots
$snapcount = $snapshots.Count
$latestsnap = usecsToDate $snapshots.runStartTimeUsecs[-1]
$oldestsnap = usecsToDate $snapshots.runStartTimeUsecs[0]

#Get Protectiong Group Info
if($primarybackupinfo.protectionGroups.count -gt 1){
$pg = $primarybackup.objectProtectionInfos.protectionGroups[0]
}
else{
$pg = $primarybackup.objectProtectionInfos.protectionGroups
}
$pgname = $pg.name

#Get Policy Info
$policyname = $pg.policyName


$policy = api get -v2 data-protect/policies?policyNames=$policyname
$policy = $policy.policies
$retention = $policy.backuppolicy.regular.retention | select duration,unit
$retention = "{0} {1}" -f $retention.duration, $retention.unit

#Display Info On Screen
if($showsnaps){

Write-Host $object,$clustername,$pgname,$environment,$policyname,$retention,$snapcount,$oldestsnap,$latestsnap

}
else{

Write-Host $object,$clustername,$pgname,$environment,$policyname,$retention

}

#Write Info to CSV
if($showsnaps){

"$object,$clustername,$pgname,$environment,$policyname,$retention,$snapcount,$oldestsnap,$latestsnap" | Out-File $outfile -Append

}
else{

"$object,$clustername,$pgname,$environment,$policyname,$retention" | Out-File $outfile -Append

}

#Disconnect from Object Primary Cluster
heliosCluster -

}


}

$date = Get-Date
"`n`nThis report (audit_protection.ps1) was run $date" | Out-File $outfile -Append

Write-Host "`nOutput saved to $outfile`n" -ForegroundColor Green
