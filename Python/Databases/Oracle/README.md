# Oracle Protection Group Run Duration Trends and CSV Report

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`oracle_pg_durations.py` graphs the run duration and data read (GB) of Oracle protection groups over time, and exports every run to a CSV file. It connects through Helios, selects each cluster in turn, finds the active Oracle protection groups, and reads their run history using the `protectionRuns` REST API.

Two outputs are produced:

* **HTML trend graphs** - one `<clustername>-job_duration_trends.html` per cluster, with one chart per protection group (duration in minutes and GB read, by run start time). These use incremental (`kRegular`) runs only, so frequent log backups do not skew the trends.
* **CSV report** - one `oracle_pg_durations-YYYY-MM-DD.csv` covering all clusters, with one row per completed run of any type (full, incremental or log).

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/), [`pandas`](https://pypi.org/project/pandas/) and [`plotly`](https://pypi.org/project/plotly/) (`pip install requests pandas plotly`)
* [`pyhesity.py`](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) in the same directory as `oracle_pg_durations.py`

## Components

* `oracle_pg_durations.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Usage

Output files are written to the current directory.

### Graph Oracle PGs on one cluster (default last 30 days)

```
python oracle_pg_durations.py -c cluster1
```

### Graph Oracle PGs on multiple clusters using a cluster list file, last 60 days

```
python oracle_pg_durations.py -cl clusters.txt -daysback 60
```

## CSV Columns

| Column | Description |
| --- | --- |
| Cluster Name | Cluster the protection group belongs to |
| Protection Group | Protection group (job) name |
| Run ID | Job run ID (`backupRun.jobRunId`) |
| Run Type | `Full`, `Incremental` or `Log` |
| Run Start | Run start time |
| Run End | Run end time |
| Duration (Minutes) | Run duration, rounded to 2 decimals |
| GB Read | Data read from source in GB, rounded to 2 decimals |
| Databases | Database names included in the run, separated by `; ` |

Runs still in progress are excluded.

## Parameters

### Authentication

| Flag | Description |
| --- | --- |
| -v, --vip | DNS or IP of the Cohesity endpoint (optional, default is helios.cohesity.com) |
| -u, --username | Username (optional, default is helios) |
| -d, --domain | Domain of the user (optional, default is local) |
| -mcm, --mcm | Connect through Helios (MCM) |
| -i, --useApiKey | Use an API key for authentication |
| -pwd, --password | Password or API key (optional, will prompt if omitted) |
| -np, --noprompt | Do not prompt for a password |
| -m, --mfacode | MFA code for authentication |
| -e, --emailmfacode | Send an MFA code via email |

### Selection

| Flag | Description |
| --- | --- |
| -c, --clustername | One or more cluster names to report on (required unless -cl is used) |
| -cl, --clusters | Text file of cluster names to report on, one per line (required unless -c is used) |
| -daysback, --daysback | Number of days of run history to include (optional, default is 30) |

## Notes

* **Database names are unverified.** The `Databases` column is read from `sourceBackupStatus[].appsBackupStatus[]` in the run data. If a run has no per-database information, the column falls back to the source (host) name. If the column shows host names or is empty, inspect `run['backupRun']['sourceBackupStatus']` for a run and adjust `getDbNames()`.
* **Log backups and paging.** The CSV query requests `kRegular`, `kFull` and `kLog` runs and pages backward in time in batches of 1000, since log runs can exceed the API limit over 30 days. Duplicate run IDs are skipped.
* **Graphs exclude full and log runs.** The HTML graphs still use the `kRegular`-only query, as in earlier versions.
* The `-j` and `-jl` job filter parameters are accepted by the script but not currently applied; all active Oracle protection groups are processed.
* Clusters that fail to connect are skipped and have no rows in the CSV.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Databases/Oracle/oracle_pg_durations.py
```
