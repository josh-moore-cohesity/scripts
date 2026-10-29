# Oracle Protection Group Run Duration Trends and CSV Reports

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`oracle_pg_durations.py` graphs the run duration and data read (GB) of Oracle protection groups over time, and exports every run to CSV files. It connects through Helios, selects each cluster in turn, finds the active Oracle protection groups, and reads their run history using the `data-protect/protection-groups` and `data-protect/protection-groups/<id>/runs` (v2) REST APIs.

Three outputs are produced:

* **HTML trend graphs** - one `<clustername>-job_duration_trends.html` per cluster, with one chart per protection group (duration in minutes and GB read, by run start time). The chart title shows the source name and the database names in the protection group. These use incremental (`kRegular`) runs only, so frequent log backups do not skew the trends.
* **Run CSV** - one `oracle_pg_durations-YYYY-MM-DD.csv` covering all clusters, with one row per completed run of any type (full, incremental or log).
* **Database CSV** - one `oracle_db_durations-YYYY-MM-DD.csv` covering all clusters, with one row per database per completed run.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/), [`pandas`](https://pypi.org/project/pandas/) and [`plotly`](https://pypi.org/project/plotly/) (`pip install requests pandas plotly`)
* [`pyhesity.py`](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) in the same directory as `oracle_pg_durations.py` (a version that includes `getRuns()`)

## Components

* `oracle_pg_durations.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Usage

Output files are written to the current directory.

### Graph and report Oracle PGs on one cluster (default last 30 days)

```
python oracle_pg_durations.py -c cluster1
```

### Multiple clusters using a cluster list file, last 60 days

```
python oracle_pg_durations.py -cl clusters.txt -daysback 60
```

### Troubleshooting: dump the structure of one run

```
python oracle_pg_durations.py -c cluster1 -debug
```

Prints the first completed run's info and its objects (and the first non-cluster object in full) for the first protection group, then exits without writing any files.

## CSV Columns

### Run CSV (`oracle_pg_durations-YYYY-MM-DD.csv`)

| Column | Description |
| --- | --- |
| Cluster Name | Cluster the protection group belongs to |
| Protection Group | Protection group (job) name |
| Run ID | Job run ID (`protectionGroupInstanceId`) |
| Run Type | `Full`, `Incremental` or `Log` |
| Run Start | Run start time |
| Run End | Run end time |
| Duration (Minutes) | Run duration, rounded to 2 decimals |
| GB Read | Data read in GB, rounded to 2 decimals |
| Databases | Database names included in the run, separated by `; ` |

### Database CSV (`oracle_db_durations-YYYY-MM-DD.csv`)

| Column | Description |
| --- | --- |
| Cluster Name | Cluster the protection group belongs to |
| Source Name | Source (Oracle host or RAC cluster) the database belongs to |
| Database | Database name |
| Run ID | Job run ID (`protectionGroupInstanceId`) |
| Run Type | `Full`, `Incremental` or `Log` (the type of the run the database was part of) |
| Start Time | Database backup start time |
| End Time | Database backup end time |
| Duration (Minutes) | Database backup duration, rounded to 2 decimals |
| Data Read (MiB) | Data read for the database, in MiB, rounded to 2 decimals |

Runs still in progress are excluded from both CSV files.

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
| -debug, --debug | Dump the structure of one run for troubleshooting and exit (optional) |

## Notes

* **Where the data comes from.** The CSV files use the v2 runs API, which includes per-database objects (`objectType` of `kDatabase`) in each run. The source (host) for each database is found in the same run's objects by matching `sourceId`; no separate source lookup is needed. If a source cannot be matched, the numeric source ID is shown instead.
* **Direct-to-archive protection groups.** Runs with no local backup information (for example, groups that back up directly to a cloud archive target) use the first archive target result for start time, end time, run type and data read, so durations reflect the archive target times.
* **Log backups and paging.** The v2 runs are fetched with `getRuns()` from `pyhesity.py`, which pages backward in time, so large numbers of log runs over the period are handled.
* **Graphs exclude full and log runs.** The HTML graphs are built from the same v2 run data as the CSV files, using incremental (`kRegular`) runs only. Protection groups with no incremental runs in the period are skipped in the graphs.
* The `-j` and `-jl` job filter parameters are accepted by the script but not currently applied; all active Oracle protection groups are processed.
* Clusters that fail to connect are skipped and have no rows in the CSV files.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Databases/Oracle/oracle_pg_durations.py
```
