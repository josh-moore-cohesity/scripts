# Cohesity Access Firewall Audit

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`cohesity-access-firewall.py` audits the **Access Firewall (Client's IPSET)** configuration on the `Management` and `SSH` profiles for one or more Cohesity clusters, and reports any entries that don't match an approved allow-list. Results are printed to the console and saved to a CSV.

## What it checks

For each cluster, the script pulls the cluster's Access Firewall configuration (`/nexus/firewall/list`) and compares the `Management` and `SSH` profile's Client's IPSET against an approved list of IPs:

* **`BASE_APPROVED`** - IPs approved on every cluster.
* **`ATL_EXTRA`** - additional IPs required only on clusters whose name contains `atl-lz1` (case/separator-insensitive, so `ATL LZ1-CL1` matches too).
* **`LAS_EXTRA`** - additional IPs required only on clusters whose name contains `las-lz1`.

A cluster/profile is flagged when:

| Discrepancy | Meaning |
|---|---|
| `Client IPSET is "All" (unrestricted)` | The profile has no subnet restriction at all. |
| `Unexpected (not in approved list)` | An IP is present on the cluster but isn't in the approved list. |
| `Missing (approved but not present)` | An approved IP is missing from the cluster's configuration. |

`/32` host suffixes are normalized before comparing, so `10.0.0.1/32` and `10.0.0.1` are treated as equal.

To change the approved IPs or add another site-specific override, edit the `BASE_APPROVED`, `ATL_EXTRA`, and `LAS_EXTRA` lists (and `approved_for_cluster()` if you add a new site) near the top of the script.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `cohesity-access-firewall.py`
* Network access to Helios (`helios.cohesity.com`) or the target cluster
* A valid Cohesity/Helios API key or credentials

## Usage

Check all Helios-connected clusters using an API key:

```
python cohesity-access-firewall.py -v helios.cohesity.com -u myuser -i
```

Check specific clusters:

```
python cohesity-access-firewall.py -c cluster1 cluster2 -i
```

Check clusters listed in a file (one cluster name per line):

```
python cohesity-access-firewall.py -cl clusters.txt -i
```

Custom output directory:

```
python cohesity-access-firewall.py -i -outputpath ./reports
```

If neither `-c` nor `-cl` is provided, the script automatically gathers **all clusters connected to Helios** and checks each.

## Parameters

| Flag | Description |
|---|---|
| `-v, --vip` | (optional) name or IP of Cohesity cluster (defaults to `helios.cohesity.com`) |
| `-u, --username` | (optional) name of user to connect to Cohesity (defaults to `helios`) |
| `-d, --domain` | (optional) your AD domain (defaults to `local`) |
| `-c, --clustername` | (optional) one or more cluster names to check (defaults to all Helios-connected clusters) |
| `-cl, --clusters` | (optional) path to a file listing cluster names (one per line) |
| `-mcm, --mcm` | (optional) connect through MCM |
| `-i, --useApiKey` | (optional) use an API key for authentication |
| `-pwd, --password` | (optional) will use cached password/key or will be prompted |
| `-np, --noprompt` | (optional) do not prompt for password |
| `-m, --mfacode` | (optional) TOTP MFA code |
| `-e, --emailmfacode` | (optional) send MFA code via email |
| `-outputpath, --outputpath` | (optional) directory to write the CSV report (defaults to `./Firewall`) |

## Output

* **Console:** per-cluster, per-profile status (`OK`, `UNEXPECTED entry <ip>`, `MISSING entry <ip>`, or unrestricted warning).
* **CSV:** `firewall-ipset-discrepancies-<YYYY-MM-DD>.csv` written to `--outputpath` (default `./Firewall`), containing only the discrepancies found.

Example CSV:

```
Cluster,Application,Discrepancy,Entry
"cluster1","Management","Unexpected (not in approved list)","10.1.2.3"
"cluster1","SSH","Missing (approved but not present)","10.52.22.83"
"cluster2","Management","Client IPSET is \"All\" (unrestricted)","ALL"
```

## Notes

* Only the `Management` and `SSH` firewall profiles are checked (see `PROFILES_TO_CHECK`).
* If a profile has no attachment at all, it's reported as "no attachment found" and skipped (not treated as a discrepancy).
* Clusters that fail to authenticate/connect through Helios are skipped with an error message rather than aborting the whole run.
