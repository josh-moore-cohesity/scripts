# Protection Group Alert Emails

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`pg_alert_emails.py` inventories the email alert settings configured on every protection group across one or more clusters (or all clusters reachable through Helios/MCM), and writes the results to a CSV report. Optionally, `-add`/`-remove` can be used to add or remove alert email recipients on every protection group covered by the run before the report is generated, and `-pglist` can be used to restrict which protection groups those updates are applied to. `-find` can be used instead to search every protection group covered by the run for a given email address and report which ones are using it, without modifying anything.

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
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Alerts/Notifications/PG%20Notifications/pg_alert_emails.py
curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity/pyhesity.py
```

### PowerShell

```
Invoke-WebRequest -Uri https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Alerts/Notifications/PG%20Notifications/pg_alert_emails.py -OutFile pg_alert_emails.py
Invoke-WebRequest -Uri https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity/pyhesity.py -OutFile pyhesity.py
```

## How It Works

1. Authenticates once (directly to a cluster, or to Helios/MCM with `-mcm`).
2. Builds the list of clusters to check: from `-c`/`-cl` if given, otherwise every cluster connected to Helios.
3. For each cluster, switches context with `heliosCluster()` and fetches every non-deleted protection group via `GET /data-protect/protection-groups`.
4. For each protection group, reads its `alertPolicy` and records the alert conditions (`backupRunStatus`) and every configured email recipient (`alertTargets`).
5. If `-add` and/or `-remove` were given, updates each protection group's `alertTargets` accordingly via `PUT /data-protect/protection-groups/{id}` before recording it - restricted to the cluster/protection-group pairs listed in `-pglist` when it's provided.
6. If `-find` was given instead, checks each protection group's `alertTargets` for a matching email address (case-insensitive) and prints it as a match if found - nothing is modified.
7. Writes one row per protection group to the output CSV, regardless of whether alerting is configured.
8. Console output during the run differs depending on mode: with no `-add`/`-remove`/`-find`, every protection group is printed as it's inventoried; with `-add`/`-remove`, only protection groups that were actually modified are printed; with `-find`, only matching protection groups are printed as they're found, followed by a summary at the end (the CSV report always includes every protection group regardless of mode).

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

Add an email recipient to every protection group's alert settings:

```
python pg_alert_emails.py -mcm -add user1@domain.com
```

Remove an email recipient from every protection group's alert settings:

```
python pg_alert_emails.py -mcm -remove user1@domain.com
```

`-add` and `-remove` can each be repeated to add/remove multiple addresses, and can be combined in the same run:

```
python pg_alert_emails.py -c cluster1 -add user1@domain.com -add user2@domain.com -remove olduser@domain.com
```

Only update the protection groups listed in a CSV file (`cluster,pgname` per line, e.g. `cluster1,VM-PG-01`), instead of every protection group on the selected cluster(s):

```
python pg_alert_emails.py -mcm -pglist pgs_to_update.csv -add user1@domain.com
```

If `-c`/`-cl` aren't also given, the clusters to connect to are inferred from the cluster names found in `-pglist`.

Check whether an email address is configured as an alert recipient on any protection group:

```
python pg_alert_emails.py -mcm -find user1@domain.com
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

## Alert Recipient Update Parameters

| Flag | Description |
|---|---|
| `-add, --add` | (optional, repeatable) email address to add as an alert recipient on every protection group covered by the run |
| `-remove, --remove` | (optional, repeatable) email address to remove as an alert recipient from every protection group covered by the run |
| `-pglist, --pglist` | (optional) path to a CSV file of `clustername,pgname` pairs (no header) restricting which protection groups `-add`/`-remove` are applied to |

## Alert Recipient Search Parameters

| Flag | Description |
|---|---|
| `-find, --find` | (optional) email address to search for among the alert recipients of every protection group covered by the run; matching protection groups are printed to the console (case-insensitive, read-only - does not modify anything) |

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
* `-add`/`-remove` apply to every protection group returned for the selected cluster(s) unless `-pglist` is given, in which case only the exact `clustername,pgname` pairs listed are updated.
* Matching against `-pglist` is case-insensitive.
* `-remove` is applied before `-add`, so passing the same address to both effectively re-adds it (a no-op).
* When `-add`/`-remove` is used, the console only prints protection groups that were actually changed (plus an `updating <name>` line for each); unaffected protection groups are silent on screen but are still written to the CSV report.
* `-find` is a read-only search; it ignores `-add`/`-remove`/`-pglist` and never modifies alert settings.
