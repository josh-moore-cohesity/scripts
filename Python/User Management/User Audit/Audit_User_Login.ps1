
#Source API Helper
### source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)

#connect to helios with api key
apiauth -apiKeyAuthentication 1

$users = api -mcm get users

$auditlog = api -mcmv2 get audit-logs?actions=login`&count=5000

$auditlog = $auditlog.auditLogs

$oldestrecord = $auditlog | select -Last 1
$oldestdatestamp = usecsToDate $oldestrecord.timestampUsecs

Write-Host "Oldest record is $oldestdatestamp`n" -ForegroundColor Green
Start-Sleep 5

foreach($user in $users){

$username = $user.username
$role = $user.roles
$domain = $user.domain
$lastlogin = $auditlog | Where-Object {$_.username -eq $username -and $_.sourceType -eq "helios" } |select -First 1
$logintime = $lastlogin.timestampUsecs

if($logintime.count -gt 0){
$logintime = usecsToDate $logintime
Write-Host "$username, $domain,$logintime, $role" -ForegroundColor Green
}
else{

Write-Host "$username, $domain,NA,$role" -ForegroundColor Yellow
}


}
