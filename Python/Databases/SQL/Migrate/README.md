# Migrate a SQL Database Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`migrateSQLDB.py` initiates, syncs, finalizes, cancels or lists SQL database migrations against a Cohesity cluster (directly, or via Helios/MCM).

This is a Python port of [migrateSQLDB.ps1](https://raw.githubusercontent.com/bseltz-cohesity/scripts/refs/heads/master/sql/powershell/migrateSQLDB/migrateSQLDB.ps1), built on the [pyhesity](https://raw.githubusercontent.com/bseltz-cohesity/scripts/refs/heads/master/python/pyhesity.py) REST API wrapper instead of `cohesity-api.ps1`.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `migrateSQLDB.py`

## Components

* `migrateSQLDB.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Operating Modes

The script will list, initialize, sync, finalize or cancel migrations, depending on which flags you pass. With no mode flag, it lists migrations (in-progress by default).

### List Mode

List existing migrations in progress (On Hold or Running):

```
python migrateSQLDB.py -v mycluster -u myuser -d mydomain.net
```

List existing migrations, including completed/canceled/failed, going back 7 days:

```
python migrateSQLDB.py -v mycluster -u myuser -d mydomain.net -sa -db 7
```

List existing migrations for a specific source database:

```
python migrateSQLDB.py -v mycluster -u myuser -d mydomain.net -ss sqlserver1 -sd MSSQLSERVER/mydb -sa -db 7
```

### Init Mode

Initiate a new migration:

```
python migrateSQLDB.py -v mycluster -u myuser -d mydomain.net \
    -ss sqlserver1 -sd MSSQLSERVER/mydb \
    -ts sqlserver2 -td mydb2 \
    -mf C:\sqldata
```

Preview the source database's data/log file paths (useful for building `-mf`/`-lf`/`-nf` values) without starting anything:

```
python migrateSQLDB.py -v mycluster -ss sqlserver1 -sd MSSQLSERVER/mydb -sp
```

### Sync Mode

Sync all in-progress migration(s):

```
python migrateSQLDB.py -v mycluster -u myuser -d mydomain.net -sync
```

Or filter on name, id or a name-matching pattern first:

```
python migrateSQLDB.py -v mycluster -u myuser -d mydomain.net -sync -id "428418101664119:1631181117066:180265"
```

### Finalize Mode

Finalize existing migration(s):

```
python migrateSQLDB.py -v mycluster -u myuser -d mydomain.net -fin -id "428418101664119:1631181117066:180265"
```

### Cancel Mode

Cancel existing migration(s):

```
python migrateSQLDB.py -v mycluster -u myuser -d mydomain.net -x -id "428418101664119:1631181117066:180265"
```

## Authentication Parameters

| Flag | Description |
|---|---|
| `-v, --vip` | (optional) name or IP of Cohesity cluster (defaults to `helios.cohesity.com`) |
| `-u, --username` | (optional) name of user to connect to Cohesity (defaults to `helios`) |
| `-d, --domain` | (optional) your AD domain (defaults to `local`) |
| `-i, --useApiKey` | (optional) use an API key for authentication |
| `-pwd, --password` | (optional) will use cached password/key or will be prompted |
| `-np, --noprompt` | (optional) do not prompt for password |
| `-t, --tenant` | (optional) organization to impersonate |
| `-mcm, --mcm` | (optional) connect through MCM |
| `-m, --mfacode` | (optional) TOTP MFA code |
| `-e, --emailmfacode` | (optional) send MFA code via email |
| `-c, --clustername` | (required when connecting through Helios/MCM) cluster to connect to |

## Mode Parameters

If none of these are used, the script lists migrations.

| Flag | Description |
|---|---|
| `-init, --init` | initialize a new migration |
| `-sync, --sync` | perform manual sync now |
| `-fin, --finalize` | finalize migration(s) |
| `-x, --cancel` | cancel migration(s) |

## Filter Parameters (sync/finalize/cancel/list modes)

| Flag | Description |
|---|---|
| `-sa, --showall` | (optional) also show completed/canceled/failed tasks (only in-progress by default) |
| `-db, --daysback` | (optional) days back to look (default 30) |
| `-n, --name` | (optional) only show/sync/finalize/cancel the migration task with this exact name |
| `-f, --filter` | (optional) only show/sync/finalize/cancel migration tasks whose name matches this pattern |
| `-id, --id` | (optional) only show/sync/finalize/cancel the migration task matching this id |
| `-rt, --returntaskids` | (optional) print the matching task IDs (one per line) and exit |
| `-ss, --sourceserver` | (optional) filter on source server (and source DB) |
| `-si, --sourceinstance` | (optional) filter on source SQL instance |
| `-sd, --sourcedb` | (optional) one or more source DBs to filter on (repeat the flag for multiple) |
| `-sl, --sourcedblist` | (optional) text file of source DBs to filter on (one per line) |
| `-ts, --targetserver` | (optional) filter on target server |
| `-td, --targetdb` | (optional) filter on target DB |
| `-dbg, --debug` | (optional) dump the raw JSON of matched migrations and exit (useful for troubleshooting) |

## Init Mode Parameters

| Flag | Description |
|---|---|
| `-ss, --sourceserver` | (required) server (or AAG name) where the database was backed up |
| `-sd, --sourcedb` | (required) original database name, optionally `instance/dbname` |
| `-si, --sourceinstance` | (optional) source SQL instance name (defaults to `MSSQLSERVER`) |
| `-sl, --sourcedblist` | (optional) text file of source DBs to migrate (one per line) |
| `-ts, --targetserver` | (required) server to migrate to |
| `-ti, --targetinstance` | (optional) instance name to restore to (defaults to `MSSQLSERVER`) |
| `-td, --targetdb` | (optional) new database name (defaults to the same as the source DB; not supported with multiple source DBs) |
| `-mf, --mdffolder` | (required unless `-usp`) location to place the primary data file (e.g. `C:\SQLData`) |
| `-lf, --ldffolder` | (optional) location to place the log file (defaults to the same as `-mf`) |
| `-nf, --ndffolders` | (optional) location(s) for secondary/ndf data files; repeatable, format `'.*pattern.ndf=D:\path'` |
| `-sp, --showpaths` | (optional) show source data/log file paths and example restore parameters, then exit |
| `-usp, --usesourcepaths` | (optional) use the same file paths on the target server as the source server |
| `-kc, --keepcdc` | (optional) keep Change Data Capture during restore (default is off) |
| `-nr, --norecovery` | (optional) restore the DB with the `NORECOVERY` option (default is to recover) |
| `-ms, --manualsync` | (optional) use manual sync mode (auto-sync is used by default) |
| `-ow, --overwrite` | (reserved, currently unused - kept for parity with the original PowerShell script) |

## Multiple Folders for Secondary NDF Files

Repeat `-nf` once per pattern:

```
-nf '.*DataFile1.ndf=E:\SQLData' -nf '.*DataFile2.ndf=F:\SQLData'
```

## See Also

`migrateSQLDB_dashboard.py` (Streamlit) provides a browser-based dashboard on top of this same logic for managing migrations across multiple clusters at once - see `sqlmigrationlib.py` for the shared backend.
