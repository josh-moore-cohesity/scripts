# Datalock Status Report

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`datalock_status.py` reports Cohesity data protection policies **without datalock configured**. It connects through Helios (or directly to a cluster), inspects each in-use policy, and flags any where datalock is not enabled on the regular backup retention. Results are printed to the console and saved to a CSV.

## What it reports

For every policy that is actively in use (has at least one protection group or protected object), the script checks whether datalock is configured on the regular backup retention (`backupPolicy.regular.retention.dataLockConfig`). Only policies **without** datalock (`Datalock = No`) are included in the output.

Output columns:

| Column   | Description                               |
| -------- | ----------------------------------------- |
| Cluster  | Name of the cluster the policy belongs to |
| Policy   | Name of the protection policy             |
| Datalock | Whether datalock is configured            |

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `datalock_status.py`
* Network access to Helios (`helios.cohesity.com`) or the target cluster
* A valid Cohesity/Helios API key or credentials

## Usage

Report all Helios-connected clusters using an API key:

```
python datalock_status.py -v helios.cohesity.com -u myuser -i
```

Report specific clusters:

```
python datalock_status.py -c cluster1 cluster2 -i
```

Report clusters listed in a file (one cluster name per line):

```
python datalock_status.py -cl clusters.txt -i
```

Custom output directory:

```
python datalock_status.py -i -outputpath ./reports
```

If neither `-c` nor `-cl` is provided, the script automatically gathers **all clusters connected to Helios** and reports on each.

## Parameters

| Flag | Description |
|---|---|
| `-v, --vip` | (optional) name or IP of Cohesity cluster (defaults to `helios.cohesity.com`) |
| `-u, --username` | (optional) name of user to connect to Cohesity (defaults to `helios`) |
| `-d, --domain` | (optional) your AD domain (defaults to `local`) |
| `-c, --clustername` | (optional) one or more cluster names to report on (defaults to all Helios-connected clusters) |
| `-cl, --clusters` | (optional) path to a file listing cluster names (one per line) |
| `-mcm, --mcm` | (optional) connect through MCM |
| `-i, --useApiKey` | (optional) use an API key for authentication |
| `-pwd, --password` | (optional) will use cached password/key or will be prompted |
| `-np, --noprompt` | (optional) do not prompt for password |
| `-m, --mfacode` | (optional) TOTP MFA code |
| `-e, --emailmfacode` | (optional) send MFA code via email |
| `-outputpath, --outputpath` | (optional) directory to write the CSV report (defaults to `./DatalockStatus`) |

## Output

* **Console:** a formatted table of clusters/policies without datalock.
* **CSV:** `datalock-status-<YYYY-MM-DD>.csv` written to `--outputpath` (default `./DatalockStatus`).

Example CSV:

```
Cluster,Policy,Datalock
"cluster1","VM-ADHOC","No"
"cluster2","SQL-Daily","No"
```

## Notes

* Datalock detection currently checks only the **regular backup retention**. Datalock configured solely on extended retention or full-backup retention is not evaluated.
* The script uses safe field lookups, so policies missing expected fields are treated as having no datalock rather than causing errors.
