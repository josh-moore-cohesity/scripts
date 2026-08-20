# Clone SQL Databases Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`cloneSQLDBs.py` clones one or more SQL databases from a Cohesity protection job to a target SQL server/instance, optionally applying transaction log replay to a specific point in time or to the latest available point, against a Cohesity cluster (directly, or via Helios/MCM).

This is a Python port of [cloneSQLDBs.ps1](https://raw.githubusercontent.com/bseltz-cohesity/scripts/refs/heads/master/sql/powershell/cloneSQLDBs/cloneSQLDBs.ps1), built on the [pyhesity](https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity/pyhesity.py) REST API wrapper instead of `cohesity-api.ps1`.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `cloneSQLDBs.py`

## Components

* `cloneSQLDBs.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Usage

Clone a single database, keeping the same name on the target:

```
python cloneSQLDBs.py -v mycluster -u myuser -d mydomain.net \
    -ss sqlserver1 -sd mydb -ts sqlserver2
```

Clone several databases in one run, adding a suffix to each cloned name:

```
python cloneSQLDBs.py -v mycluster -u myuser -d mydomain.net \
    -ss sqlserver1 -sd db1 db2 db3 -ts sqlserver2 -sx -clone
```

Clone databases listed in a text file (one name per line), replaying logs up to a specific point in time:

```
python cloneSQLDBs.py -v mycluster -u myuser -d mydomain.net \
    -ss sqlserver1 -sl dblist.txt -ts sqlserver2 \
    -lt "2019-09-29 17:51:01"
```

Clone with logs replayed to the latest available point:

```
python cloneSQLDBs.py -v mycluster -u myuser -d mydomain.net \
    -ss sqlserver1 -sd mydb -ts sqlserver2 -latest
```

Connect through Helios/MCM (requires `-c`/`--clustername`):

```
python cloneSQLDBs.py -v helios.cohesity.com -u myuser -mcm -c mycluster \
    -ss sqlserver1 -sd mydb -ts sqlserver2
```

Preview the clone task JSON without executing it:

```
python cloneSQLDBs.py -v mycluster -ss sqlserver1 -sd mydb -ts sqlserver2 -dbg
```

## Parameters

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
| `-ss, --sourceserver` | (required) server where the database(s) were backed up |
| `-sd, --sourcedb` | (optional) one or more source database names to clone (space-separated, repeatable); supports `instance/dbname` |
| `-sl, --sourcedblist` | (optional) text file of source database names to clone (one per line); combined with `-sd` if both are given |
| `-ts, --targetserver` | (optional) server to attach the clone(s) to (defaults to the same as `-ss`) |
| `-ti, --targetinstance` | (optional) SQL instance name on the target server (defaults to `MSSQLSERVER`) |
| `-p, --prefix` | (optional) prefix added to each cloned database name |
| `-sx, --suffix` | (optional) suffix added to each cloned database name |
| `-lt, --logtime` | (optional) point-in-time log replay, e.g. `'2019-09-29 17:51:01'` |
| `-latest, --latest` | (optional) replay logs to the latest available point instead of a fixed `-lt` time |
| `-nl, --nologs` | (optional) skip log replay even if a valid point in time was found |
| `-dbg, --debug` | (optional) print the raw clone task JSON for the current database and exit (no clone is executed) |

At least one of `-sd`/`-sl` must resolve to one or more database names, or the script exits.

## Notes

* Each database in the list is processed independently: if one database or server can't be found, the script prints a message and moves on to the next one (except when the target server itself can't be found, which is treated as fatal since it affects every database in the run).
* When `-lt`/`--logtime` or `-latest` is used but no valid recovery point can be found within range, the script reports the valid time range and exits (or, for a single database in a multi-database list, skips just that database).
* The cloned database name is always `<prefix><sourcedb><suffix>` — there's no separate "target database name" flag, unlike `cloneSQL.py`.
* After submitting each clone task, the script polls the restore task every 3 seconds until it reaches a finished state (`kSuccess`, `kFailure`, or `kCanceled`) and prints the result.
