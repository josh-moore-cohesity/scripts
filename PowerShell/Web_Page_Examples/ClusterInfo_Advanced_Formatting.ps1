#Source API Helper
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)


#connect to helios with api key
apiauth -apiKeyAuthentication  1 

#get clusters connected in Helios
$clusters = api get -mcmv2 cluster-mgmt/info

$clusters = $clusters.cohesityClusters

$clusters = $clusters |Where-Object {$_.isConnectedToHelios -eq $true}

$clusterinfo = $clusters | select clusterName,clusterId,currentVersion,usedCapacity,totalCapacity,numberofNodes,type

#Get Current Date
Add-Type -AssemblyName System.Web
$date = Get-Date

#set output file
$outputfile = $(Join-Path -Path $PSScriptRoot -ChildPath "ClusterInfo_advanced.html")


#set css table styles
$a = "<style>"
$a = $a + "BODY{background-color:White;}"
$a = $a + "TABLE{border-width: 1px;border-style: solid;border-color: black;border-collapse: collapse;white-space: nowrap}"
$a = $a + "TH{border-width: 1px;white-space: nowrap;padding: 0px;border-style: solid;border-color: black;background-color: #66ff33;font-size: 18pt;}"
$a = $a + "TR:Nth-Child(Even) {Background-Color: #E0E0E0;font-size: 16pt;}"
$a = $a + "TD{border-width: 1px;padding: 0px;border-style: solid;border-color: black;font-size: 16pt;}"
$a = $a + "</style>"

#format results
foreach($cluster in $clusterinfo){

$cluster.usedCapacity = [math]::Round($cluster.usedCapacity/1024/1024/1024,2)
$cluster.totalCapacity = [math]::Round($cluster.totalCapacity/1024/1024/1024,2)
$clusterpercentused = [math]::Round(($cluster.usedCapacity/$cluster.totalCapacity)*100,2)

# Rename the NoteProperty
$cluster| Add-Member -MemberType NoteProperty -Name 'Cluster Name' -Value $cluster.clusterName
$cluster.PSObject.Properties.Remove('clusterName')

$cluster| Add-Member -MemberType NoteProperty -Name 'Cluster ID' -Value $cluster.clusterId
$cluster.PSObject.Properties.Remove('clusterId')

$cluster| Add-Member -MemberType NoteProperty -Name 'Cluster Version' -Value $cluster.currentVersion
$cluster.PSObject.Properties.Remove('currentVersion')

$cluster| Add-Member -MemberType NoteProperty -Name 'Used Capacity (GB)' -Value $cluster.usedCapacity
$cluster.PSObject.Properties.Remove('usedCapacity')

$cluster| Add-Member -MemberType NoteProperty -Name 'Total Capacity (GB)' -Value $cluster.totalCapacity
$cluster.PSObject.Properties.Remove('totalCapacity')

$cluster| Add-Member -MemberType NoteProperty -Name '% Used' -Value $clusterpercentused

$cluster| Add-Member -MemberType NoteProperty -Name 'Node Count' -Value $cluster.numberOfNodes
$cluster.PSObject.Properties.Remove('numberOfNodes')

$cluster| Add-Member -MemberType NoteProperty -Name 'Cluster Type' -Value $cluster.type
$cluster.PSObject.Properties.Remove('type')


} 

#Output results to html file
$clusterinfo |sort 'Cluster Name' | ConvertTo-Html -head $a -PreContent "<b>Last Updated $date</b>" -PostContent "<p></p>" | Out-File $outputfile

#Open html file
invoke-item $outputfile
