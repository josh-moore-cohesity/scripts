# process commandline arguments
[CmdletBinding()]
param (

[Parameter()][array]$usernames, # list of users to update
[Parameter()][string]$userlist = '',  # text file of users to update
[Parameter()][array]$clusternames, # list of clusters to add/remove from user access
[Parameter()][string]$clusterlist = '',  # text file of clusters to add/remove from user access
[Parameter(Mandatory=$true)][ValidateSet('Add', 'Remove','Query')][string]$action = ''  # Set to Add or Remove Cluster(s) for users access
)

# gather list of Users to Update
$users = @()
foreach($u in $usernames){
    $users += $u
}
if ('' -ne $userlist){
    if(Test-Path -Path $userlist -PathType Leaf){
        $usernamelist = Get-Content $userlist
        foreach($user in $usernamelist){
            $users += [string]$user
        }
    }else{
        Write-Host "User list $userlist not found!" -ForegroundColor Yellow
        exit
    }
}
if($users.Count -eq 0){
    Write-Host "No Users Specified" -ForegroundColor Yellow
    exit
}


# gather list of Clusters to add/remove
$clusters = @()
foreach($c in $clusternames){
    $clusters += $c
}
if ('' -ne $clusterlist){
    if(Test-Path -Path $clusterlist -PathType Leaf){
        $clusternamelist = Get-Content $clusterlist
        foreach($cluster in $clusternamelist){
            $clusters += [string]$cluster
        }
    }else{
        Write-Host "Cluster list $clusterlist not found!" -ForegroundColor Yellow
        exit
    }
}

if($clusters.Count -eq 0 -and $action -ne "Query"){
    Write-Host "No Clusters provided to $action" -ForegroundColor Yellow
    exit
}

#Exit if all clusters and action is to remove
if($clusters -eq "all" -and $action -eq "remove"){

Write-Host "Cannot Remove All Clusters from a user" -ForegroundColor Yellow
Exit

}

# source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)

#Source API Helper
. .\cohesity-api.ps1

#connect to helios with api key
apiauth -apiKeyAuthentication 1

#Get IDP(SSO) Users
$idpusers = api get idps/principals -mcmv2
$idpusers = $idpusers.principals

#Add/Remove Clusters for each user
foreach($username in $users){

$user = $idpusers | Where-Object {$_.name -eq "$username"}

if($user -eq $null){

Write-Host "$username not found" -ForegroundColor Yellow
continue

}

#Query Cluster Access
if($action -eq "Query"){

if("-1:-1" -in $user.clusters){

Write-Host "$username has all cluster access" -ForegroundColor Green
continue

}

else{

Write-Host "$username has access to:" -ForegroundColor Green

$userclusters = $user.clusters

foreach($usercluster in $userclusters){


$clusterid = ($usercluster).split(":")[0]

$clustername = heliosclusters | Where-Object {$_.clusterId -eq "$clusterid"} | select name

Write-Host $clustername.name

}
continue
}

}

#Skip if adding "all" clusters and user already has "all" cluster access
if("-1:-1" -in $user.clusters -and $action -eq "add"){
Write-Host "$username already has all cluster access" -ForegroundColor Yellow
continue
}

#Set user sid
$usersid = $user.sid

#Add all to user if clusters = all
if($clusters -eq "all" -and $action -eq "add"){

Write-Host "Adding all clusters for $usernameS" -ForegroundColor Green

$userclusters = "{`"clusters`":[`"-1:-1`"]}" | ConvertFrom-Json
$userclusters = $userclusters.clusters
$user.clusters = $userclusters

}

#Add/Remove individual clusters to/from user
else{

#capture cluster details
foreach($clustername in $clusters){

$cluster = heliosClusters | Where-Object {$_.name -eq $clustername}

if($cluster -eq $null){

Write-Host "Cluster $clustername not found" -ForegroundColor Yellow
continue 



}

$clusterid = $cluster.clusterid
$clusterincid = $cluster.clusterIncarnationId

#Add Cluster(s) to User
if($action -eq "Add" -and $user.clusters -notcontains "$clusterid`:$clusterincid"){

Write-Host "Adding $clustername for $usernameS" -ForegroundColor Green
$user.clusters += "$clusterid`:$clusterincid"

}

#skip is user already access to cluster
elseif($action -eq "Add" -and $user.clusters -contains "$clusterid`:$clusterincid"){

Write-Host "$username already has access to $clustername" -ForegroundColor Yellow


}

#Remove Cluster from User
if($action -eq "Remove"){

Write-Host "Removing $clustername from $username" -ForegroundColor Yellow

#If going from "all" clusters to specific cliusters
if("-1:-1" -in $user.clusters){

$newclusters = heliosClusters | Where-Object {$_.name -ne $clustername}

foreach($newcluster in $newclusters){

$newclusterid = $newcluster.clusterid
$newclusterincid = $newcluster.clusterIncarnationId

$user.clusters += "$newclusterid`:$newclusterincid"

$updatedclusters = $user.clusters | Where-Object {$_ -notcontains "-1:-1"}

}

}

#Remove Cluster from access
else{

$updatedclusters = $user.clusters | where-object {$_ -notcontains "$clusterid`:$clusterincid"}

}

#Handle object type (make an object, not string) if only 1 cluster will be in access list
if($updatedclusters.count -eq "1"){

$splitcluster = ($updatedclusters).split(":")
$newid = $splitcluster[0]
$newincid = $splitcluster[1]
$userclusters = "{`"clusters`":[`"$newid`:$newincid`"]}" | ConvertFrom-Json
$userclusters = $userclusters.clusters
$user.clusters = $userclusters

}
else{

$user.clusters = $updatedclusters

}

}

}

}

#API Call to update User
$null = api put idps/principals/$usersid $user -mcmv2

}
