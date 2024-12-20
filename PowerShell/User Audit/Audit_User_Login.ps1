#Source API Helper
### source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)

#connect to helios with api key
apiauth -apiKeyAuthentication 1

#Set output file
$outfile = $(Join-Path -Path $PSScriptRoot -ChildPath "user_audit.csv")

#Get All Helios Users
$users = api -mcm get users

#Get Clusters
$clusters = api get -mcmv2 cluster-mgmt/info
$clusters = $clusters.cohesityClusters

#Get Audit Log
$auditlog = api -mcmv2 get audit-logs?actions=login`&count=5000
$auditlog = $auditlog.auditLogs

#Report Oldest Record From Audit Log
$oldestrecord = $auditlog | select -Last 1
$oldestdatestamp = usecsToDate $oldestrecord.timestampUsecs
Write-Host "Oldest record is $oldestdatestamp`n" -ForegroundColor Green
Start-Sleep 5

#Create or Clear Output File
"Username,Domain,Last Login,Role,Total Clusters,Accessible Clusters" | Out-File $outfile


#Find Last Login for Each User and their cluster access
foreach($user in $users |sort username){

$username = $user.username
$role = $user.roles
$domain = $user.domain
$lastlogin = $auditlog | Where-Object {$_.username -eq $username -and $_.sourceType -eq "helios" } |select -First 1
$logintime = $lastlogin.timestampUsecs
$totalclusters = $user.clusterIdentifiers.count
$allclusters = $clusters.count
if($user.clusterIdentifiers.clusterId -eq "-1"){
$totalclusters = $allclusters
}

$clusternames = foreach($cluster in $user.clusterIdentifiers){
if($cluster.clusterId -eq "-1"){

$clusters.clustername

}

else{
$clusters |Where-Object {$_.clusterid -eq $cluster.clusterId} | select clusterName

}
}

if($clusternames.count -eq $clusters.count){
$clusternames = $clusternames -join ","
}

else{
$clusternames = $clusternames.clustername -join ","
}

#Login Audit Found
if($logintime.count -gt 0){
$logintime = usecsToDate $logintime
Write-Host "$username,$domain,$logintime,$role" -ForegroundColor Green
"$username,$domain,$logintime,$role,$allclusters,$totalclusters,$clusternames" | Out-File $outfile -Append
}

#Login Audit Not Found
else{

Write-Host "$username,$domain,NA,$role" -ForegroundColor Yellow
"$username,$domain,NA,$role,$allclusters,$totalclusters,$clusternames" | Out-File $outfile -Append
}


}

Write-Host "`nOutput Saved to user_audit.csv`n"
