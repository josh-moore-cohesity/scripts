# Report on Cohesity Archive Runs

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`archiveRunsReport.ps1` reports on archive (external target) copy runs across a Cohesity cluster: which ones are queued, running, or completed, what they've transferred, when they expire, and how much write bandwidth each external target is currently pushing. It can also cancel queued or outdated archive tasks. It produces both a TSV log and an HTML dashboard with summary tiles.

## Requirements

* PowerShell
* `cohesity-api.ps1` in the same directory, version `2025.01.10` or later (the script uses its `Get-Runs` helper) - get the latest from the [community-automation-samples](https://github.com/cohesity/community-automation-samples/tree/main/powershell/cohesity-api) repo if needed

## Components

* `archiveRunsReport.ps1` - the main script
* `cohesity-api.ps1` - the Cohesity REST API helper module

## Operating Modes

The script always reports. Passing one or more cancel flags additionally cancels matching archive tasks as it reports on them.

### Report Mode (default)

Report on all active archive tasks across every protection job on the cluster:

```powershell
./archiveRunsReport.ps1 -clusterName mycluster
```

Connect through Helios/MCM (requires `-clusterName`):

```powershell
./archiveRunsReport.ps1 -vip helios.cohesity.com -clusterName mycluster -mcm -useApiKey
```

Report on a single job:

```powershell
./archiveRunsReport.ps1 -clusterName mycluster -jobName "VMs-Azure-PS-Sub"
```

Report on a list of jobs from a text file (one job name per line):

```powershell
./archiveRunsReport.ps1 -clusterName mycluster -jobList jobs.txt
```

Also include completed archive runs that haven't expired yet:

```powershell
./archiveRunsReport.ps1 -clusterName mycluster -showFinished
```

Stop scanning a job's history early once a completed run (or a run with no archive copy tasks) is hit, instead of walking the full history:

```powershell
./archiveRunsReport.ps1 -clusterName mycluster -quickScan
```

On an NGCE (cloud-native) cluster, exclude the storage-domain-backed pseudo target so only true external archives are reported (see [Notes](#notes)):

```powershell
./archiveRunsReport.ps1 -clusterName mycluster -excludeVaults DefaultExternalTarget
```

Report using GiB instead of the default MiB, and skip auto-opening the HTML report in a browser:

```powershell
./archiveRunsReport.ps1 -clusterName mycluster -unit GiB -noBrowser
```

### Cancel Mode

Cancel archive tasks that are already past their intended retention:

```powershell
./archiveRunsReport.ps1 -clusterName mycluster -cancelOutdated
```

Cancel archive tasks that haven't transferred any data yet:

```powershell
./archiveRunsReport.ps1 -clusterName mycluster -cancelQueued
```

Cancel every active archive task found:

```powershell
./archiveRunsReport.ps1 -clusterName mycluster -cancelAll
```

Cancel flags can be combined with the filter parameters (`-jobName`, `-jobList`) to scope cancellation to specific jobs.

## Authentication Parameters

| Flag | Description |
|---|---|
| `-vip` | (optional) name or IP of the Cohesity cluster (defaults to `helios.cohesity.com`) |
| `-username` | (optional) name of user to connect to Cohesity (defaults to `helios`) |
| `-domain` | (optional) your AD domain (defaults to `local`) |
| `-useApiKey` | (optional) use an API key for authentication |
| `-password` | (optional) will use cached password/key or will be prompted |
| `-noPrompt` | (optional) do not prompt for a password |
| `-tenant` | (optional) organization to impersonate |
| `-mcm` | (optional) connect through Helios/MCM |
| `-mfaCode` | (optional) TOTP MFA code |
| `-emailMfaCode` | (optional) send MFA code via email |
| `-clusterName` | (required when connecting through Helios/MCM) cluster to connect to |

## Filter Parameters

| Flag | Description |
|---|---|
| `-jobName` | (optional) only report on/cancel archive tasks for this protection job |
| `-jobList` | (optional) text file of job names to filter on (one per line) |
| `-excludeVaults` | (optional) vault name(s) to exclude from every count and the report - e.g. an NGCE cluster's `DefaultExternalTarget` (see [Notes](#notes)); no default, so nothing is excluded unless specified |
| `-quickScan` | (optional) stop scanning a job's run history once a completed run or a run with no archive copy tasks is found, instead of walking the full history |
| `-showFinished` | (optional) also list completed archive runs that haven't expired yet, in the TSV |
| `-numRuns` | (optional) number of runs to pull per page when walking a job's run history (default `1000`) |

## Cancel Parameters

| Flag | Description |
|---|---|
| `-cancelOutdated` | (optional) cancel archive tasks that are already past their intended retention |
| `-cancelQueued` | (optional) cancel archive tasks that haven't transferred any data yet |
| `-cancelAll` | (optional) cancel every active (queued/running) archive task found |

Only `kAccepted` (queued) and `kRunning` copy runs are ever eligible for cancellation - see [Notes](#notes).

## Report Parameters

| Flag | Description |
|---|---|
| `-unit` | (optional) unit (`MiB`/`GiB`/`TiB`) used for the Transferred column and TSV (default `MiB`) |
| `-statsDays` | (optional) days of write-bandwidth history to pull per external target for the HTML report (default `7`) |
| `-reportPath` | (optional) where to save the HTML report (defaults to `<cluster>-<timestamp>-archiveRunsReport.html` next to the script) |
| `-noBrowser` | (optional) save the HTML report but don't open it |

## Outputs

* **`ArchiveQueue-<cluster>-<date>.tsv`** - one row per active (and, with `-showFinished`, unexpired completed) archive copy run: job, run date, logical/physical bytes transferred, total logical size, status, target, start/end/expiry times.
* **`<cluster>-<timestamp>-archiveRunsReport.html`** - a dashboard with:
  * **Archive Migration Queue** tile - cluster-wide count of queued (`kAccepted`) vs. running (`kRunning`) archive tasks.
  * **External Target Throughput** tile, one per external target actually in use - current/peak/average write bandwidth and total bytes written over `-statsDays`, pulled from `statistics/timeSeriesStats` (`schemaName=kIceboxVaultStats`, `metricName=kNumBytesWritten`) - the same data behind the cluster UI's Advanced Diagnostics -> External Target Stats -> Write Bandwidth view.
  * A detail table of every active archive run: job, run date, status, vault, transferred, total to transfer, retention (expiry date), and whether it was flagged/cancelled.
* **Exit code**: `0` if no active archive tasks were found, `1` otherwise - usable as a simple monitoring check.

## Notes

* **Cancel safety**: only `kAccepted`/`kRunning` copy runs are ever eligible for cancellation. Completed runs (`kSuccess`/`kWarning`) show up in the report but `-cancelOutdated`/`-cancelQueued`/`-cancelAll` will never act on them.
* **NGCE clusters**: on NGCE (cloud-native) clusters, storage domains are backed by object-storage containers, so the primary backup run itself surfaces as a `kArchival` copy run against a vault (typically named `DefaultExternalTarget`). That's the backup, not a true archive - pass `-excludeVaults DefaultExternalTarget` (or any other vault name you want ignored) to keep it out of the queue counts, throughput tiles, and detail table. There's no default exclusion, so on-prem clusters (which only use local disk for backups) are unaffected either way.
* **In-progress first runs**: for a job whose most recent run is still actively running (e.g. its very first backup), the underlying `Get-Runs -includeRunning` helper in `cohesity-api.ps1` issues one extra pagination call that the cluster rejects (`Invalid value for param: endTimeUsecs`). This script silences API error reporting for the duration of that one call per job so the noise doesn't show up in the console; it doesn't affect what gets reported.
