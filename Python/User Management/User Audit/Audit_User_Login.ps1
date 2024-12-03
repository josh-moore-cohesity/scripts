#Source API Helper
### source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)


#connect to helios with api key
apiauth -apiKeyAuthentication 1

#Get All Helios Users
$users = api -mcm get users

#Get Audit Log
$auditlog = api -mcmv2 get audit-logs?actions=login`&count=5000
$auditlog = $auditlog.auditLogs

#Report Oldest Record From Audit Log
$oldestrecord = $auditlog | select -Last 1
$oldestdatestamp = usecsToDate $oldestrecord.timestampUsecs
Write-Host "Oldest record is $oldestdatestamp`n" -ForegroundColor Green
Start-Sleep 5

#Create or Clear Output File
"Username,Domain,Last Login,Role" | Out-File user_audit.csv

#Find Last Login for Each User
foreach($user in $users){

$username = $user.username
$role = $user.roles
$domain = $user.domain
$lastlogin = $auditlog | Where-Object {$_.username -eq $username -and $_.sourceType -eq "helios" } |select -First 1
$logintime = $lastlogin.timestampUsecs

#Login Audit Found
if($logintime.count -gt 0){
$logintime = usecsToDate $logintime
Write-Host "$username,$domain,$logintime,$role" -ForegroundColor Green
"$username,$domain,$logintime,$role" | Out-File user_audit.csv -Append
}

#Login Audit Not Found
else{

Write-Host "$username,$domain,NA,$role" -ForegroundColor Yellow
"$username,$domain,NA,$role" | Out-File user_audit.csv -Append
}


}

Write-Host "`nOutput Saved to user_audit.csv`n"
