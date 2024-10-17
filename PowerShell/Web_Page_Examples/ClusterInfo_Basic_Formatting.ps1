#Source API Helper
### source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)


#connect to helios with api key
apiauth -apiKeyAuthentication  1 

#get clusters connected in Helios
$clusters = api get -mcmv2 cluster-mgmt/info

$clusters = $clusters.cohesityClusters

$clusters = $clusters |Where-Object {$_.isConnectedToHelios -eq $true}

$clusterinfo = $clusters | select clusterName,clusterId,currentVersion,usedCapacity,totalCapacity,numberofNodes,type

Add-Type -AssemblyName System.Web
$date = Get-Date

$outputfile = $(Join-Path -Path $PSScriptRoot -ChildPath "ClusterInfo.html")

#set css table styles
$a = "<style>"
$a = $a + "BODY{background-color:White;}"
$a = $a + "TABLE{border-width: 1px;border-style: solid;border-color: black;border-collapse: collapse;}"
$a = $a + "TH{border-width: 1px;padding: 10px;border-style: solid;border-color: black;background-color: #66ff33;font-size: 18pt;}"
$a = $a + "TR:Nth-Child(Even) {Background-Color: #E0E0E0;font-size: 16pt;}"
$a = $a + "TD{border-width: 1px;padding: 0px;border-style: solid;border-color: black;font-size: 16pt;}"
$a = $a + "</style>"



$clusterinfo | sort clusterName | ConvertTo-Html -head $a -PreContent "<b>Last Updated $date</b>" -PostContent "<p></p>" | Out-File $outputfile

invoke-item $outputfile
