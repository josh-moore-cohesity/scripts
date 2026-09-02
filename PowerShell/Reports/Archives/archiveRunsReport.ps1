### process commandline arguments
[CmdletBinding()]
param (
    [Parameter()][string]$vip='helios.cohesity.com',
    [Parameter()][string]$username = 'helios',
    [Parameter()][string]$domain = 'local',
    [Parameter()][string]$tenant,
    [Parameter()][switch]$useApiKey,
    [Parameter()][string]$password,
    [Parameter()][switch]$noPrompt,
    [Parameter()][switch]$mcm,
    [Parameter()][string]$mfaCode,
    [Parameter()][switch]$emailMfaCode,
    [Parameter()][string]$clusterName,
   [Parameter()][string]$jobName,          # filter on job names
   [Parameter()][string]$jobList = '',    # filter on job names from text file
   [Parameter()][switch]$cancelOutdated,  # cancel if archive is already due to expire
   [Parameter()][switch]$cancelQueued,    # cancel if archive hasn't transferred any data yet
   [Parameter()][switch]$cancelAll,       # cancel all archives
   [Parameter()][switch]$quickScan,       # break scan if a completion is found or if no copyRuns are detected
   [Parameter()][switch]$showFinished,    # show completed archives
   [Parameter()][int]$numRuns = 1000,
   [Parameter()][ValidateSet('MiB','GiB','TiB')][string]$unit = 'MiB',
   [Parameter()][int]$statsDays = 7,      # days of write-bandwidth history to pull per external target
   [Parameter()][string]$reportPath,      # where to save the html summary report (defaults next to this script)
   [Parameter()][switch]$noBrowser,       # save the html report but don't open it
   [Parameter()][array]$excludeVaults # vault names to skip (e.g. NGCE's storage-domain-backed pseudo target, which is really the backup run, not a true archive)
)

# gather list of jobs
$jobNames = @()
if($jobName){
    $jobNames = @($jobNames + $jobName)
}
if ('' -ne $jobList){
    if(Test-Path -Path $jobList -PathType Leaf){
        $jobs = Get-Content $jobList
        foreach($j in $jobs){
            $jobNames += [string]$j
        }
    }else{
        Write-Host "Job list $jobList not found!" -ForegroundColor Yellow
        exit
    }
}

### source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)
if($cohesity_api.api_version -lt '2025.01.10'){
    Write-Host "This script requires cohesity-api.ps1 version 2025.01.10 or later" -foregroundColor Yellow
    Write-Host "Please download it from https://github.com/cohesity/community-automation-samples/tree/main/powershell/cohesity-api" -ForegroundColor Yellow
    exit
}


$conversion = @{'MiB' = 1024 * 1024; 'GiB' = 1024 * 1024 * 1024; 'TiB' = 1024 * 1024 * 1024 * 1024}
function toUnits($val){
    return "{0:n2}" -f ($val/($conversion[$unit]))
}

# convert bytes to a human readable unit (for the write-bandwidth report tile)
function humanBytes($bytes){
    if($null -eq $bytes){ return 'N/A' }
    $units2 = 'B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'
    $i = 0
    $val = [double]$bytes
    while([math]::Abs($val) -ge 1024 -and $i -lt ($units2.Count - 1)){
        $val = $val / 1024
        $i++
    }
    return "{0:n1} {1}" -f $val, $units2[$i]
}
function humanRate($bytesPerSec){
    if($null -eq $bytesPerSec){ return 'N/A' }
    return "$(humanBytes $bytesPerSec)/s"
}

# authentication =============================================
# demand clusterName for Helios/MCM
if(($vip -eq 'helios.cohesity.com' -or $mcm) -and ! $clusterName){
    Write-Host "-clusterName required when connecting to Helios/MCM" -ForegroundColor Yellow
    exit 1
}

# authenticate
apiauth -vip $vip -username $username -domain $domain -passwd $password -apiKeyAuthentication $useApiKey -mfaCode $mfaCode -sendMfaCode $emailMfaCode -heliosAuthentication $mcm -regionid $region -tenant $tenant -noPromptForPassword $noPrompt

# exit on failed authentication
if(!$cohesity_api.authorized){
    Write-Host "Not authenticated" -ForegroundColor Yellow
    exit 1
}

# select helios/mcm managed cluster
if($USING_HELIOS){
    $thisCluster = heliosCluster $clusterName
    if(! $thisCluster){
        exit 1
    }
}
# end authentication =========================================

$finishedStates = @('kCanceled', 'kCanceling')

$cluster = api get cluster
$dateString = (get-date).ToString('yyyy-MM-dd')
$outfileName = "ArchiveQueue-$($cluster.name)-$dateString.tsv"
"Job ID`tJob Name`tRun Date`tLogical $unit`tPhysical $unit`tStatus`tTarget`tStart Time`tEnd Time`tExpiry Time" | Out-File -FilePath $outfileName

$nowUsecs = dateToUsecs (get-date)
$thenUsecs = [int64]($nowUsecs + ($daysTilExpire * 24 * 60 * 60 * 1000000))

$runningTasks = 0
$queuedCount = 0
$runningCount = 0
$reportRows = @()
$vaultIds = @{} # vault name -> vault id, gathered from active archive tasks encountered below

foreach($job in (api get protectionJobs | Where-Object {$_.isDeleted -ne $True} | Sort-Object -Property name)){

    $jobId = $job.id
    $jobName = $job.name

    if($jobNames.Length -eq 0 -or $jobName -in $jobNames){
        "$jobName ($jobId)"
        $endUsecs = dateToUsecs (Get-Date)
        $archiveTasksFound = $false
        $breakOut = $false
        # Get-Runs -includeRunning issues one extra (doomed) pagination call once it reaches a run
        # that's still in progress (e.g. a job on its first backup) - endTimeUsecs comes back empty
        # for that call and the cluster rejects it. Silence that specific noise locally.
        $cohesity_api.reportApiErrors = $false
        Get-Runs -jobId $jobId -numRuns $numRuns -includeRunning | Foreach-Object {
            $run = $_
            if($breakOut){
                break
            }
            $runStartTimeUsecs = $run.backupRun.stats.startTimeUsecs
            foreach($copyRun in ($run.copyRun | Where-Object {$_.target.type -eq 'kArchival' -and $_.target.archivalTarget.vaultName -notin $excludeVaults})){
                $archiveTasksFound = $True
                $target = $copyRun.target.archivalTarget.vaultName
                $status = $copyRun.status
                $startTimeUsecs = $copyRun.stats.startTimeUsecs
                $endTimeUsecs = $copyRun.stats.endTimeUsecs
                $noLongerNeeded = ''
                $cancelling = ''
                $cancel = $false
                $expiryTimeUsecs = $copyRun.expiryTimeUsecs
                if($copyRun.stats.logicalBytesTransferred){
                    $transferred = $copyRun.stats.logicalBytesTransferred
                }else{
                    $transferred = 0
                }
                if($copyRun.stats.physicalBytesTransferred){
                    $physicalTransferred = $copyRun.stats.physicalBytesTransferred
                }else{
                    $physicalTransferred = 0
                }
                if($copyRun.stats.isIncremental -eq $False){
                    $referenceFull = '(Reference Full)'
                }else{
                    $referenceFull = ''
                }

                if($copyRun.status -notin $finishedStates){
                    # only kAccepted/kRunning copy runs are eligible for cancellation - kSuccess/kWarning
                    # are reported here too (since $finishedStates no longer includes them) but must never be cancelled
                    $cancelEligible = $status -in @('kAccepted', 'kRunning')

                    # cancel outdated
                    if($cancelEligible -and $cancelOutdated){
                        $thisrun = api get "/backupjobruns?allUnderHierarchy=true&exactMatchStartTimeUsecs=$($runStartTimeUsecs)&id=$($jobId)"
                        foreach($task in $thisrun.backupJobRuns.protectionRuns[0].copyRun.activeTasks){
                            if($task.snapshotTarget.type -eq 3){
                                $daysToKeep = $task.retentionPolicy.numDaysToKeep - $daysTilExpire
                                $usecsToKeep = $daysToKeep * 1000000 * 86400
                                $timePassed = $nowUsecs - $runStartTimeUsecs
                                if($timePassed -gt $usecsToKeep){
                                    $noLongerNeeded = "(NO LONGER NEEDED)"
                                    if($cancelOutdated -or $cancelAll){
                                        $cancel = $True
                                        $cancelling = '(Cancelling)'
                                    }
                                }
                            }
                        }
                    }

                    if($cancelEligible -and $transferred -eq 0 -and ($cancelQueued -or $cancelAll)){
                        $cancel = $True
                        $cancelling = '(Cancelling)'
                    }

                    "        {0,25}:    ({1} $unit)    {2}  {3}  {4}" -f (usecsToDate $runStartTimeUsecs), (toUnits $transferred), $referenceFull, $noLongerNeeded, $cancelling
                    "{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}`t`t{8}" -f $jobId, $jobName, (usecsToDate $runStartTimeUsecs), (toUnits $transferred), (toUnits $physicalTransferred), $status, $target, (usecsToDate $startTimeUsecs), (usecsToDate $expiryTimeUsecs) | Out-File -FilePath $outfileName -Append
                    $runningTasks += 1
                    if($status -eq 'kAccepted'){
                        $queuedCount += 1
                    }elseif($status -eq 'kRunning'){
                        $runningCount += 1
                    }
                    $targetId = $copyRun.target.archivalTarget.vaultId
                    if($target -and !$vaultIds.ContainsKey($target)){
                        $vaultIds[$target] = $targetId
                    }
                    $reportRows += [pscustomobject]@{
                        Job         = $jobName
                        RunDate     = (usecsToDate $runStartTimeUsecs)
                        Status      = $status
                        Vault       = $target
                        Transferred = "$(toUnits $transferred) $unit"
                        Retention   = $(if($expiryTimeUsecs){usecsToDate $expiryTimeUsecs}else{'N/A'})
                        Flag        = $noLongerNeeded
                        Action      = $cancelling
                    }
                    # cancel archive task
                    if($cancel -eq $True){
                        $cancelTaskParams = @{
                            "jobId"       = $jobId;
                            "copyTaskUid" = $copyRun.taskUid
                        }
                        $null = api post "protectionRuns/cancel/$($jobId)" $cancelTaskParams 
                    }
                }else{
                    if($showFinished -and $expiryTimeUsecs -gt $nowUsecs){
                        "        {0,25}:    ({1} $unit)    {2}  {3}" -f (usecsToDate $runStartTimeUsecs), (toUnits $transferred), $status, $referenceFull
                        "{0}`t{1}`t{2}`t{3}`t{4}`t{5}`t{6}`t{7}`t{8}`t{9}" -f $jobId, $jobName, (usecsToDate $runStartTimeUsecs), (toUnits $transferred), (toUnits $physicalTransferred), $status, $target, (usecsToDate $startTimeUsecs), (usecsToDate $endTimeUsecs), (usecsToDate $expiryTimeUsecs) | Out-File -FilePath $outfileName -Append
                    }else{
                        if($quickScan){
                            $breakOut = $True
                            break
                        }
                    }
                }
            }
            if($breakOut){
                break
            }
            if($quickScan -and $archiveTasksFound -eq $false){
                $breakOut = $True
                break
            }
        }
        $cohesity_api.reportApiErrors = $true
    }
}

# external target write-bandwidth stats (advanced diagnostics -> external target stats) ===
$vaultStats = @{}
if($vaultIds.Count -gt 0){
    "`nGathering write bandwidth for active external targets..."
    $vaultStatEntities = api get "statistics/entities?maxEntities=1000&schemaName=kIceboxVaultStats"
    $vaultStatEntityIds = @($vaultStatEntities.entityId.entityId.data.int64Value)
    $statsEndMsecs = [int64][math]::Round((dateToUsecs (Get-Date -Hour 0 -Minute 0)) / 1000) + 86400000
    $statsStartMsecs = $statsEndMsecs - (86400000 * $statsDays)

    foreach($vaultName in $vaultIds.Keys){
        $vaultId = $vaultIds[$vaultName]
        if($vaultId -and $vaultId -in $vaultStatEntityIds){
            $entityNameParam = "External Target: $vaultName"
            $vaultTimeSeries = api get "statistics/timeSeriesStats?endTimeMsecs=$statsEndMsecs&entityId=$vaultId&entityName=$entityNameParam&metricName=kNumBytesWritten&metricUnitType=0&range=week&schemaName=kIceboxVaultStats&startTimeMsecs=$statsStartMsecs"
            $bandwidthPoints = @($vaultTimeSeries.dataPointVec | Sort-Object timestampMsecs)

            $currentRate = $null
            $peakRate = $null
            $avgRate = $null
            $totalWritten = $null

            if($bandwidthPoints.Count -gt 0){
                $totalWritten = ($bandwidthPoints | ForEach-Object { $_.data.int64Value } | Measure-Object -Sum).Sum
                $rates = @()
                for($i = 1; $i -lt $bandwidthPoints.Count; $i++){
                    $intervalSecs = ($bandwidthPoints[$i].timestampMsecs - $bandwidthPoints[$i - 1].timestampMsecs) / 1000
                    if($intervalSecs -gt 0){
                        $rates += ($bandwidthPoints[$i].data.int64Value / $intervalSecs)
                    }
                }
                if($rates.Count -gt 0){
                    $currentRate = $rates[-1]
                    $peakRate = ($rates | Measure-Object -Maximum).Maximum
                    $avgRate = ($rates | Measure-Object -Average).Average
                }
            }
            $vaultStats[$vaultName] = [pscustomobject]@{
                Current = $currentRate
                Peak    = $peakRate
                Avg     = $avgRate
                Total   = $totalWritten
            }
            "$($vaultName): Current $(humanRate $currentRate), Peak $(humanRate $peakRate), Avg $(humanRate $avgRate), Total written ($statsDays d) $(humanBytes $totalWritten)"
        }else{
            Write-Host "No write-bandwidth stats found for external target $vaultName" -ForegroundColor Gray
        }
    }
}

# build html summary report =================================================
$reportDate = Get-Date
if(!$reportPath){
    $reportPath = Join-Path -Path $PSScriptRoot -ChildPath "$($cluster.name)-$($reportDate.ToString('yyyy-MM-dd_HHmmss'))-archiveRunsReport.html"
}

$statusColors = @{
    'kAccepted' = '#c78a00'
    'kRunning'  = '#1b7f3a'
}

$rowsHtml = ($reportRows | ForEach-Object {
    $color = $statusColors[$_.Status]
    if(!$color){ $color = '#333333' }
    "<tr><td>$($_.Job)</td><td>$($_.RunDate)</td><td style='color:$color;font-weight:600;'>$($_.Status)</td><td>$($_.Vault)</td><td>$($_.Transferred)</td><td>$($_.Retention)</td><td>$($_.Flag)</td><td>$($_.Action)</td></tr>"
}) -join "`n"

$throughputTilesHtml = if($vaultStats.Count -gt 0){
    ($vaultStats.Keys | ForEach-Object {
        $v = $vaultStats[$_]
        @"
  <div class='tile'>
    <h2>External Target Throughput &mdash; $_</h2>
    <div class='metric-row'><span>Current Write Bandwidth</span><span class='value'>$(humanRate $v.Current)</span></div>
    <div class='metric-row'><span>Peak ($statsDays d)</span><span class='value'>$(humanRate $v.Peak)</span></div>
    <div class='metric-row'><span>Average ($statsDays d)</span><span class='value'>$(humanRate $v.Avg)</span></div>
    <div class='metric-row'><span>Total Written ($statsDays d)</span><span class='value'>$(humanBytes $v.Total)</span></div>
  </div>
"@
    }) -join "`n"
}else{
    "<div class='tile'><h2>External Target Throughput</h2><div class='metric-row'><span>No active archive tasks found</span></div></div>"
}

$html = @"
<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<title>Archive Runs Report - $($cluster.name)</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#f4f5f7;color:#222;margin:0;padding:24px;}
h1{font-size:20px;margin:0 0 4px 0;}
.subtitle{color:#666;font-size:13px;margin:0 0 24px 0;}
.tiles{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px;}
.tile{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.15);padding:18px 24px;min-width:220px;flex:1;}
.tile h2{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#666;margin:0 0 12px 0;}
.metric-row{display:flex;justify-content:space-between;margin:6px 0;font-size:14px;}
.metric-row .value{font-weight:700;font-size:16px;}
table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.15);border-radius:8px;overflow:hidden;}
th,td{padding:8px 12px;border-bottom:1px solid #eee;text-align:left;font-size:13px;}
th{background:#eef0f3;text-transform:uppercase;font-size:11px;letter-spacing:.05em;color:#555;}
tr:last-child td{border-bottom:none;}
</style>
</head>
<body>
<h1>Archive Runs Report &mdash; $($cluster.name)</h1>
<p class='subtitle'>Generated $($reportDate.ToString('yyyy-MM-dd HH:mm'))</p>
<div class='tiles'>
  <div class='tile'>
    <h2>Archive Migration Queue (cluster-wide)</h2>
    <div class='metric-row'><span>Queued</span><span class='value'>$queuedCount</span></div>
    <div class='metric-row'><span>Running</span><span class='value'>$runningCount</span></div>
  </div>
$throughputTilesHtml
</div>
<table>
<tr><th>Job</th><th>Run Date</th><th>Status</th><th>Vault</th><th>Transferred</th><th>Retention</th><th>Flag</th><th>Action</th></tr>
$rowsHtml
</table>
</body>
</html>
"@

$html | Out-File -FilePath $reportPath -Encoding utf8
Write-Host "`nReport saved to $reportPath" -ForegroundColor Cyan
if(!$noBrowser){
    Invoke-Item $reportPath
}

if($runningTasks -eq 0){
    "`nNo active archive tasks found"
    exit 0
}else{
    "`nOutput saved to $outfilename"
    exit 1
}