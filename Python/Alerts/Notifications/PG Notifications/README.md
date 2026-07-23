# Protection Group Alert Emails

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`pg_alert_emails.py` inventories the email alert settings configured on every protection group across one or more clusters (or all clusters reachable through Helios/MCM), and writes the results to a CSV report.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `pg_alert_emails.py`

## Components

* `pg_alert_emails.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Download

### curl

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Alerts/pg_alert_emails.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/pyhesity.py
```

### PowerShell

```
Invoke-WebRequest -Uri https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Alerts/pg_alert_emails.py -OutFile pg_alert_emails.py
Invoke-WebRequest -Uri https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/pyhesity.py -OutFile pyhesity.py
```

## How It Works

1. Authenticates once (directly to a cluster, or to Helios/MCM with `-mcm`).
2. Builds the list of clusters to check: from `-c`/`-cl` if given, otherwise every cluster connected to Helios.
3. For each cluster, switches context with `heliosCluster()` and fetches every non-deleted protection group via `GET /data-protect/protection-groups`.
4. For each protection group, reads its `alertPolicy` and records the alert conditions (`backupRunStatus`) and every configured email recipient (`alertTargets`).
5. Writes one row per protection group to the output CSV, regardless of whether alerting is configured.

## Examples

Report on every protection group across all clusters connected to Helios:

```
python pg_alert_emails.py -mcm
```

Report on a single cluster:

```
python pg_alert_emails.py -c cluster1
```

Report on multiple clusters, reading cluster names from a file:

```
python pg_alert_emails.py -mcm -cl clusters.txt
```

Write the report to a specific folder:

```
python pg_alert_emails.py -mcm -outputpath ./Reports
```

## Authentication Parameters

| Flag | Description |
|---|---|
| `-v, --vip` | (optional) cluster or Helios/MCM address (defaults to `helios.cohesity.com`) |
| `-u, --username` | (optional) name of user to connect with (defaults to `helios`) |
| `-d, --domain` | (optional) your AD domain (defaults to `local`) |
| `-i, --useApiKey` | (optional) use an API key for authentication |
| `-pwd, --password` | (optional) will use cached password/key or will be prompted |
| `-np, --noprompt` | (optional) do not prompt for password |
| `-mcm, --mcm` | (optional) connect through Helios/MCM |
| `-m, --mfacode` | (optional) TOTP MFA code |
| `-e, --emailmfacode` | (optional) send MFA code via email |

## Cluster Selection Parameters

| Flag | Description |
|---|---|
| `-c, --clustername` | (optional) space separated list of cluster names |
| `-cl, --clusters` | (optional) text file of cluster names, one per line |

If neither `-c` nor `-cl` is given, every cluster connected to Helios/MCM is used.

## Output Parameters

| Flag | Description |
|---|---|
| `-outputpath, --outputpath` | (optional) folder to write the CSV report to (defaults to `./Results`) |

## Output

`pg_alert_emails-<date>.csv` is written to the output path, with one row per protection group:

| Column | Description |
|---|---|
| Cluster | name of the cluster the protection group belongs to |
| Protection Group | protection group name |
| Environment | protection group environment (e.g. `kVMware`, `kSQL`) |
| PG ID | protection group ID |
| Alert On | comma separated list of backup run statuses that trigger alerts (e.g. `kFailure,kWarning`) |
| Alert Recipients | comma separated list of email addresses configured to receive alerts |

## Notes

* `-c` and `-cl` can be combined; the two lists are merged.
* Every protection group is reported, including those with no alert recipients configured (an empty `Alert Recipients` column).
