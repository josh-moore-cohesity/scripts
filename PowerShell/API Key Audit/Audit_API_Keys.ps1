#Source API Helper
### source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)


#connect to helios with api key
apiauth -apiKeyAuthentication 1

#Set output file
$outfile = $(Join-Path -Path $PSScriptRoot -ChildPath "apikey_audit.csv")

#Create or Clear Output File
"Username,Action,Name,Type,Date" | Out-File $outfile

#Get Audit Log
$auditlog = api -mcmv2 get audit-logs?searchString=api%20key`&actions=create%2Cdelete`&count=5000
$apiaudit = $auditlog.auditLogs

#$apiaudit = $auditlog | Where-Object {$_.entityType -eq "ApiKey"} 

#Select data from each record and output to Screen and CSV
foreach($audit in $apiaudit){
$username = $audit.username
$action = $audit.action
$entityname = $audit.entityname
$entitytype = $audit.entityType
$timestamp = usecsToDate $audit.timestampUsecs

Write-Host "$username,$action,$entityname,$entitytype,$timestamp" -ForegroundColor Green
"$username,$action,$entityname,$entitytype,$timestamp" | Out-File $outfile -Append

}


Write-Host "`nOutput Saved to $outfile`n"
