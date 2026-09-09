<#
.SYNOPSIS
    Report archived objects (latest/oldest backup and archive dates, archive target, and expiry) across one or more clusters.
#>

# process commandline arguments
[CmdletBinding()]
param (
    [Parameter()][string]$vip = 'helios.cohesity.com',
    [Parameter()][string]$username = 'helios',
    [Parameter()][string]$domain = 'local',
    [Parameter()][string]$tenant,
    [Parameter()][switch]$useApiKey,
    [Parameter()][string]$password,
    [Parameter()][switch]$noPrompt,
    [Parameter()][switch]$mcm,
    [Parameter()][string]$mfaCode,
    [Parameter()][switch]$emailMfaCode,
    [Parameter()][string[]]$clusterName,
    [Parameter()][string]$clusterList = '',  # text file of cluster names
    [Parameter()][string]$outputPath = './Results',
    [Parameter()][ValidateSet('csv', 'html', 'pdf')][string[]]$format = @('csv')
)

# source the cohesity-api helper code
. $(Join-Path -Path $PSScriptRoot -ChildPath cohesity-api.ps1)

# gather list from command line params and file
function gatherList($Param=$null, $FilePath=$null, $Required=$True, $Name='items'){
    $items = @()
    if($Param){
        $Param | ForEach-Object {$items += $_}
    }
    if($FilePath){
        if(Test-Path -Path $FilePath -PathType Leaf){
            Get-Content $FilePath | ForEach-Object {$items += [string]$_}
        }else{
            Write-Host "Text file $FilePath not found!" -ForegroundColor Yellow
            exit
        }
    }
    if($Required -eq $True -and $items.Count -eq 0){
        Write-Host "No $Name specified" -ForegroundColor Yellow
        exit
    }
    return ($items | Sort-Object -Unique)
}

# find a Chromium based browser to render the html report to pdf
function findPdfBrowser(){
    $candidates = @(
        (Join-Path -Path $env:ProgramFiles -ChildPath 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path -Path ${env:ProgramFiles(x86)} -ChildPath 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path -Path $env:ProgramFiles -ChildPath 'Google\Chrome\Application\chrome.exe'),
        (Join-Path -Path ${env:ProgramFiles(x86)} -ChildPath 'Google\Chrome\Application\chrome.exe')
    )
    foreach($candidate in $candidates){
        if($candidate -and (Test-Path -Path $candidate -PathType Leaf)){
            return $candidate
        }
    }
    return $null
}

# resolve a per-archive-copy status: use the API's own status field if the endpoint provides
# one (tried under a few plausible field names), otherwise fall back to a derived Active/Expired
function resolveArchiveStatus($replica, $expiryUsecs, $nowUsecs){
    foreach($propName in @('status', 'replicationStatus', 'archivalStatus')){
        if($replica.PSObject.Properties[$propName] -and $replica.$propName){
            $rawStatus = $replica.$propName
            if($rawStatus -is [string]){
                return ($rawStatus -replace '^k', '')
            }
            return [string]$rawStatus
        }
    }
    if($expiryUsecs -and $expiryUsecs -gt 0){
        if($expiryUsecs -lt $nowUsecs){
            return 'Expired'
        }else{
            return 'Active'
        }
    }
    return ''
}

# render rows as a sortable, filterable html report
function toHtmlReport($rows, $title, [switch]$forPrint){
    $tableRows = ($rows | ForEach-Object {
        $expiryDateOnly = ''
        if($_.ArchiveExpiry){
            $expiryDateOnly = $_.ArchiveExpiry.Substring(0, 10)
        }
        "<tr data-job=""$($_.'Job Name')"" data-status=""$($_.Status)"" data-vault=""$($_.'Archive Target')"" data-expiry=""$expiryDateOnly"">" +
        "<td>$($_.'Cluster Name')</td><td>$($_.'Job Name')</td><td>$($_.'Job Type')</td><td>$($_.'Protected Object')</td>" +
        "<td>$($_.'Latest Backup Date')</td><td>$($_.'Oldest Backup Date')</td><td>$($_.'Latest Archive Date')</td><td>$($_.'Oldest Archive Date')</td>" +
        "<td>$($_.'Archive Count')</td><td>$($_.'Archive Target')</td><td>$($_.Status)</td><td>$($_.ArchiveExpiry)</td></tr>"
    }) -join "`n"

    $filtersBlock = ''
    if(! $forPrint){
        $jobOptions = (@($rows.'Job Name' | Where-Object {$_} | Sort-Object -Unique) | ForEach-Object {"<option value='$_'>$_</option>"}) -join "`n"
        $statusOptions = (@($rows.Status | Where-Object {$_} | Sort-Object -Unique) | ForEach-Object {"<option value='$_'>$_</option>"}) -join "`n"
        $vaultOptions = (@($rows.'Archive Target' | Where-Object {$_} | Sort-Object -Unique) | ForEach-Object {"<option value='$_'>$_</option>"}) -join "`n"
        $filtersBlock = @"
<div class='filters'>
  <label>Job<select id='jobFilter'><option value='all'>All</option>$jobOptions</select></label>
  <label>Status<select id='statusFilter'><option value='all'>All</option>$statusOptions</select></label>
  <label>Vault<select id='vaultFilter'><option value='all'>All</option>$vaultOptions</select></label>
  <label>Retention From<input type='date' id='expiryFrom'></label>
  <label>Retention To<input type='date' id='expiryTo'></label>
  <span id='rowCount' class='row-count'></span>
</div>
"@
    }

    return @"
<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<title>$title</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#f4f5f7;color:#222;margin:0;padding:24px;}
h1{font-size:20px;margin:0 0 4px 0;}
.subtitle{color:#666;font-size:13px;margin:0 0 20px 0;}
.filters{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:12px;font-size:13px;color:#444;}
.filters label{display:flex;flex-direction:column;gap:3px;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#666;}
.filters select,.filters input{padding:5px 8px;border-radius:4px;border:1px solid #ccc;font-size:13px;}
.row-count{color:#888;margin-left:auto;align-self:flex-end;}
table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.15);border-radius:8px;overflow:hidden;}
th,td{padding:8px 12px;border-bottom:1px solid #eee;text-align:left;font-size:13px;white-space:nowrap;}
th{background:#eef0f3;text-transform:uppercase;font-size:11px;letter-spacing:.05em;color:#555;cursor:pointer;user-select:none;}
th:hover{background:#e2e5ea;}
th.sort-asc::after{content:' \25B2';font-size:9px;}
th.sort-desc::after{content:' \25BC';font-size:9px;}
tr:last-child td{border-bottom:none;}
tr[hidden]{display:none;}
</style>
</head>
<body>
<h1>$title</h1>
<p class='subtitle'>Generated $((Get-Date).ToString('yyyy-MM-dd HH:mm'))</p>
$filtersBlock
<table id='reportTable'>
<thead>
<tr><th>Cluster Name</th><th>Job Name</th><th>Job Type</th><th>Protected Object</th><th>Latest Backup Date</th><th>Oldest Backup Date</th><th>Latest Archive Date</th><th>Oldest Archive Date</th><th>Archive Count</th><th>Archive Target</th><th>Status</th><th>ArchiveExpiry</th></tr>
</thead>
<tbody>
$tableRows
</tbody>
</table>
<script>
(function(){
    var table = document.getElementById('reportTable');
    if(!table){ return; }
    var tbody = table.tBodies[0];
    var ths = table.querySelectorAll('thead th');
    var sortCol = -1, sortAsc = true;

    function parseCell(text){
        text = text.trim();
        if(text === ''){ return {type:'empty', value:0, raw:text}; }
        var n = parseFloat(text.replace(/[^0-9.\-]/g, ''));
        if(!isNaN(n) && /^-?[0-9.,]+$/.test(text)){
            return {type:'num', value:n, raw:text};
        }
        var d = Date.parse(text.replace(' ', 'T'));
        if(!isNaN(d) && /^\d{4}-\d{2}-\d{2}/.test(text)){
            return {type:'num', value:d, raw:text};
        }
        return {type:'str', value:text.toLowerCase(), raw:text};
    }

    function compareCells(a, b){
        var pa = parseCell(a), pb = parseCell(b);
        if(pa.type === 'empty' && pb.type === 'empty'){ return 0; }
        if(pa.type === 'empty'){ return -1; }
        if(pb.type === 'empty'){ return 1; }
        if(pa.type === 'num' && pb.type === 'num'){ return pa.value - pb.value; }
        return pa.raw.toLowerCase().localeCompare(pb.raw.toLowerCase());
    }

    ths.forEach(function(th, idx){
        th.addEventListener('click', function(){
            sortAsc = (sortCol === idx) ? !sortAsc : true;
            sortCol = idx;
            var rows = Array.prototype.slice.call(tbody.rows);
            rows.sort(function(r1, r2){
                var cmp = compareCells(r1.cells[idx].textContent, r2.cells[idx].textContent);
                return sortAsc ? cmp : -cmp;
            });
            rows.forEach(function(r){ tbody.appendChild(r); });
            ths.forEach(function(h){ h.classList.remove('sort-asc', 'sort-desc'); });
            th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
        });
    });

    var jobFilter = document.getElementById('jobFilter');
    var statusFilter = document.getElementById('statusFilter');
    var vaultFilter = document.getElementById('vaultFilter');
    var expiryFrom = document.getElementById('expiryFrom');
    var expiryTo = document.getElementById('expiryTo');
    var rowCount = document.getElementById('rowCount');
    if(!jobFilter || !statusFilter || !vaultFilter || !expiryFrom || !expiryTo){ return; }

    function applyFilters(){
        var jobVal = jobFilter.value;
        var statusVal = statusFilter.value;
        var vaultVal = vaultFilter.value;
        var fromVal = expiryFrom.value;
        var toVal = expiryTo.value;
        var rows = tbody.rows;
        var visible = 0;
        for(var i = 0; i < rows.length; i++){
            var row = rows[i];
            var show = true;
            if(jobVal !== 'all' && row.getAttribute('data-job') !== jobVal){ show = false; }
            if(show && statusVal !== 'all' && row.getAttribute('data-status') !== statusVal){ show = false; }
            if(show && vaultVal !== 'all' && row.getAttribute('data-vault') !== vaultVal){ show = false; }
            if(show && (fromVal || toVal)){
                var expiry = row.getAttribute('data-expiry');
                if(!expiry){
                    show = false;
                }else{
                    if(fromVal && expiry < fromVal){ show = false; }
                    if(show && toVal && expiry > toVal){ show = false; }
                }
            }
            row.hidden = !show;
            if(show){ visible++; }
        }
        if(rowCount){ rowCount.textContent = visible + ' of ' + rows.length + ' rows'; }
    }

    [jobFilter, statusFilter, vaultFilter, expiryFrom, expiryTo].forEach(function(el){
        el.addEventListener('change', applyFilters);
    });
    applyFilters();
})();
</script>
</body>
</html>
"@
}

# get list of clusters from command line params and/or file
$clusterNames = @(gatherList -Param $clusterName -FilePath $clusterList -Name 'clusters' -Required $false)

# date and time
$now = Get-Date
$dateString = $now.ToString('yyyy-MM-dd')

if(! (Test-Path -Path $outputPath -PathType Container)){
    New-Item -Path $outputPath -ItemType Directory | Out-Null
}
$environments = @('Unknown', 'VMware', 'HyperV', 'SQL', 'View',
                  'RemoteAdapter', 'Physical', 'Pure', 'Azure', 'Netapp',
                  'Agent', 'GenericNas', 'Acropolis', 'PhysicalFiles',
                  'Isilon', 'KVM', 'AWS', 'Exchange', 'HyperVVSS',
                  'Oracle', 'GCP', 'FlashBlade', 'AWSNative', 'VCD',
                  'O365', 'O365Outlook', 'HyperFlex', 'GCPNative',
                  'AzureNative','AD', 'AWSSnapshotManager', 'Unknown',
                  'Unknown', 'Unknown', 'Unknown', 'Unknown')

# authentication =============================================

# authenticate
apiauth -vip $vip -username $username -domain $domain -passwd $password -apiKeyAuthentication $useApiKey -mfaCode $mfaCode -sendMfaCode $emailMfaCode -heliosAuthentication $mcm -tenant $tenant -noPromptForPassword $noPrompt

# exit on failed authentication
if(!$cohesity_api.authorized){
    Write-Host "Not authenticated" -ForegroundColor Yellow
    exit 1
}

# end authentication =========================================

# get clusters (all Helios-connected clusters if none specified)
if($clusterNames.Count -eq 0){
    $clusters = (api get -mcmv2 cluster-mgmt/info).cohesityClusters | Where-Object {$_.isConnectedToHelios -eq $True}
    $clusterNames = $clusters.clusterName
}

$results = @()
$nowUsecs = dateToUsecs (Get-Date)

foreach($cluster in $clusterNames){
    heliosCluster $cluster
    Write-Host $cluster

    if($cohesity_api.last_api_error -ne 'OK'){
        continue
    }

    # find recoverable objects
    $ro = api get /searchvms

    if($ro.count -gt 0){
        $ro.vms | Sort-Object -Property {$_.vmDocument.jobName}, {$_.vmDocument.objectName } | ForEach-Object {
            $doc = $_.vmDocument
            $jobName = $doc.jobName
            $objName = $doc.objectName
            $objType = $environments[$doc.registeredSource.type]
            $objAlias = ''
            if('objectAliases' -in $doc.PSobject.Properties.Name){
                $objAlias = $doc.objectAliases[0]
                if($objAlias -eq "$objName.vmx" -or $objType -eq 'VMware'){
                    $objAlias = ''
                }
            }
            if($objAlias -ne ''){
                $objName = "$objName on $objAlias"
            }
            $latestVersion = 0
            $oldestVersion = 0
            $vaultStats = @{}  # vault name -> latest/oldest archive time, expiry, and count for that vault
            $doc.versions | ForEach-Object {
                $version = $_
                $startTime = $version.instanceId.jobStartTimeUsecs
                if($latestVersion -eq 0){
                    $latestVersion = $startTime
                }
                $oldestVersion = $startTime
                $version.replicaInfo.replicaVec | ForEach-Object {
                    if($_.target.type -eq 3) {
                        $vName = $_.target.archivalTarget.name
                        if(! $vaultStats.ContainsKey($vName)){
                            $vaultStats[$vName] = @{'latest' = 0; 'oldest' = 0; 'expiry' = 0; 'count' = 0; 'status' = ''}
                        }
                        $stat = $vaultStats[$vName]
                        if($stat.latest -eq 0){
                            $stat.latest = $startTime
                            $stat.status = resolveArchiveStatus $_ $_.expiryTimeUsecs $nowUsecs
                        }
                        $stat.oldest = $startTime
                        if($stat.expiry -eq 0){
                            $stat.expiry = $_.expiryTimeUsecs
                        }
                        $stat.count += 1
                    }
                }
            }
            $runDate = (usecsToDate $latestVersion).ToString("yyyy-MM-dd hh:mm")
            $oldestRunDate = (usecsToDate $oldestVersion).ToString("yyyy-MM-dd hh:mm")

            $rows = @()
            if($vaultStats.Count -eq 0){
                $rows += @{'vault' = ''; 'latest' = ''; 'oldest' = ''; 'count' = 0; 'expiry' = ''; 'status' = ''}
            }else{
                $vaultStats.Keys | Sort-Object | ForEach-Object {
                    $vName = $_
                    $stat = $vaultStats[$vName]
                    $expiry = if($stat.expiry -eq 0){''}else{(usecsToDate $stat.expiry).ToString("yyyy-MM-dd hh:mm")}
                    $rows += @{
                        'vault'  = $vName
                        'latest' = (usecsToDate $stat.latest).ToString("yyyy-MM-dd hh:mm")
                        'oldest' = (usecsToDate $stat.oldest).ToString("yyyy-MM-dd hh:mm")
                        'count'  = $stat.count
                        'expiry' = $expiry
                        'status' = $stat.status
                    }
                }
            }
            foreach($row in $rows){
                write-host ("{0}, {1}, {2}, {3}, {4}, {5}, {6}, {7}, {8}, {9}, {10}" -f $cluster, $jobName, $objType, $objName, $runDate, $oldestRunDate, $row.latest, $row.oldest, $row.count, $row.vault, $row.status)
                $results += [PSCustomObject]@{
                    'Cluster Name'         = $cluster
                    'Job Name'             = $jobName
                    'Job Type'             = $objType
                    'Protected Object'     = $objName
                    'Latest Backup Date'   = $runDate
                    'Oldest Backup Date'   = $oldestRunDate
                    'Latest Archive Date'  = $row.latest
                    'Oldest Archive Date'  = $row.oldest
                    'Archive Count'        = $row.count
                    'Archive Target'       = $row.vault
                    'Status'               = $row.status
                    'ArchiveExpiry'        = $row.expiry
                }
            }
        }
    }
}

$savedFiles = @()
foreach($fmt in ($format | Sort-Object -Unique)){
    $outfileName = Join-Path -Path $outputPath -ChildPath "ArchivedObjects-$dateString.$fmt"
    switch($fmt){
        'csv' {
            $results | Export-Csv -Path $outfileName -NoTypeInformation
            $savedFiles += $outfileName
        }
        'html' {
            toHtmlReport $results 'Archived Objects Report' | Out-File -FilePath $outfileName -Encoding utf8
            $savedFiles += $outfileName
        }
        'pdf' {
            $browser = findPdfBrowser
            if(! $browser){
                Write-Host "No Edge or Chrome browser found to render PDF - saving report as HTML instead" -ForegroundColor Yellow
                $outfileName = [System.IO.Path]::ChangeExtension($outfileName, 'html')
                toHtmlReport $results 'Archived Objects Report' | Out-File -FilePath $outfileName -Encoding utf8
                $savedFiles += $outfileName
            }else{
                # render to a private temp html file (not the user-facing .html output) so a
                # concurrently requested -format html isn't clobbered by the print-mode markup
                $htmlPath = Join-Path -Path ([System.IO.Path]::GetTempPath()) -ChildPath "archivedObjects-pdf-$([guid]::NewGuid()).html"
                toHtmlReport $results 'Archived Objects Report' -forPrint | Out-File -FilePath $htmlPath -Encoding utf8
                $htmlUri = ([uri]([System.IO.Path]::GetFullPath($htmlPath))).AbsoluteUri
                $pdfFullPath = [System.IO.Path]::GetFullPath($outfileName)
                # use a throwaway profile dir - otherwise, if the browser is already running, Chromium
                # just hands the command line to that running instance and ignores --headless/--print-to-pdf
                $pdfProfileDir = Join-Path -Path ([System.IO.Path]::GetTempPath()) -ChildPath "archivedObjects-pdf-$([guid]::NewGuid())"
                # each value is individually quoted - Start-Process joins -ArgumentList elements with plain
                # spaces (it does not quote them), so an unquoted path containing a space (e.g. this script's
                # own OneDrive folder) gets split into separate arguments and Chromium fails with
                # "Multiple targets are not supported in headless mode"
                $browserArgs = @('--headless', '--disable-gpu', "--user-data-dir=`"$pdfProfileDir`"", "--print-to-pdf=`"$pdfFullPath`"", '--no-margins', "`"$htmlUri`"")
                Start-Process -FilePath $browser -ArgumentList $browserArgs -Wait -NoNewWindow
                Remove-Item -Path $pdfProfileDir -Recurse -Force -ErrorAction SilentlyContinue
                if(Test-Path -Path $outfileName -PathType Leaf){
                    Remove-Item -Path $htmlPath -Force
                    $savedFiles += $outfileName
                }else{
                    $fallbackPath = [System.IO.Path]::ChangeExtension($outfileName, 'pdf-failed.html')
                    Move-Item -Path $htmlPath -Destination $fallbackPath -Force
                    Write-Host "PDF conversion failed - html report retained at $fallbackPath" -ForegroundColor Yellow
                    $savedFiles += $fallbackPath
                }
            }
        }
    }
}

write-host "`nReport(s) Saved to $($savedFiles -join ', ')`n" -ForegroundColor Blue
