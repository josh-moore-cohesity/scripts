#Source API Helper
### source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)


#connect to helios with api key
apiauth -apiKeyAuthentication 1

#Set output file
$outfile = $(Join-Path -Path $PSScriptRoot -ChildPath "local_user_audit.csv")

#Create or Clear Output File
"Cluster,Username,Email,Domain,Role" | Out-File $outfile

#get local cluster users
foreach($cluster in heliosClusters){

$clustername = $cluster.name

heliosCluster $clustername

$users = api get users

foreach($user in $users){
$username = $user.username
$role = $user.roles
$domain = $user.domain
$email = $user.emailAddress

Write-Host "$clustername,$username,$email,$domain,$role" -ForegroundColor Green
"$clustername,$username,$email,$domain,$role" | Out-File $outfile -Append

}


}
