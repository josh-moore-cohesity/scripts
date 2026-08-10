# **cluster_utilization_summary.py**

Generate a storage utilization report (replication vs. backup vs. total, per cluster) for every Cohesity cluster connected to Helios, or for a specific list of clusters. Writes an HTML report and a CSV, and can optionally email the HTML report.<br />
[pyhesity.py](https://github.com/cohesity/community-automation-samples/blob/main/python/pyhesity.py) is required.

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

## **Requirements**

* Python 3
* `pyhesity.py` in the same directory as `cluster_utilization_summary.py`
* Network access to an SMTP server if using `-email` (no authentication/TLS is configured by default - see [Notes](#notes))

## **Download**

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Cluster%20Utilization%20Summary/cluster_utilization_summary.py
    curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py

## **Parameters**

* -v, --vip (Cohesity cluster or Helios endpoint, default: helios.cohesity.com)
* -u, --username (default: helios)
* -i, --useApiKey (use an API key for authentication)
* -mcm, --mcm (connect via Helios/MCM)
* -np, --noprompt (do not prompt for credentials, e.g. when using a stored password)
* -m, --mfacode (MFA code)
* -e, --emailmfacode (send MFA code via email)
* -c, --clustername (space separated list of cluster names to target; if omitted, all clusters connected to Helios are used)
* -cl, --clusters (text file of cluster names, one per line; can be combined with `-c`)
* -email, --email (email the HTML report after it's written; if omitted, no email is sent)

## **How It Works**

1. Authenticates once (directly to a cluster, or to Helios/MCM with `-mcm`).
2. Fetches `cluster-mgmt/info` once, to auto-discover cluster names (if none were given via `-c`/`-cl`) and to build a `clusterName -> type` lookup used in step 4. Auto-discovery is limited to clusters with `isConnectedToHelios == true`.
3. For each cluster, switches context with `heliosCluster()` and calls `stats/consumers?consumerType=kReplicationRuns`, summing the response's `storageConsumedBytes`, for the replication figure.
4. For the backup figure, branches by cluster type:
   * Non-GCP clusters: calls `stats/consumers?consumerType=kProtectionRuns` and sums `storageConsumedBytes`, same as the replication figure.
   * GCP (`kGoogleCloud`) clusters: backup data lives in a GCP bucket external target rather than local/logical storage, so `stats/consumers` doesn't reflect it. Instead the script looks up the cluster's storage domain, finds the external target tied to that domain, and reads the vault's latest `kIceboxVaultStats`/`kMorphedUsageBytes` value over the trailing 24 hours.
5. Converts each sum from bytes to TB (divide by 1024^4, rounded to 2 decimals) and rolls up grand totals across all clusters.
6. Sorts the per-cluster results alphabetically by cluster name.
7. Writes an HTML report with summary cards (total/backup/replication utilization) and a per-cluster table, and a CSV with the same per-cluster rows plus a `Total` row.
8. If `-email` is set, emails the HTML report via SMTP; otherwise the script exits after writing the files.

## **Output**

Both files are written to the current directory, one run per day:

* `cluster_utilization_<date>.html` - branded HTML report with summary cards and a per-cluster table
* `cluster_utilization_<date>.csv` - `Cluster Name, Replication_Sum_TB, Backup_Sum_TB, Total_Sum_TB`, one row per cluster plus a final `Total` row

## **Examples**

### Generate HTML + CSV reports for every cluster connected to Helios using an API key (no email)

    python cluster_utilization_summary.py -mcm -i

### Same, and also email the HTML report

    python cluster_utilization_summary.py -mcm -i -email

### Report on specific clusters by name

    python cluster_utilization_summary.py -mcm -i -c cluster1 cluster2

### Report on clusters listed in a text file

    python cluster_utilization_summary.py -mcm -i -cl clusters.txt

## **Notes**

* `-c` and `-cl` can be combined; the two lists are merged.
* Clusters not currently connected to Helios are skipped when no explicit cluster list is given.
* Utilization figures are TiB (bytes / 1024^4), not TB (bytes / 1000^4), despite the `_TB` column/label naming.
* GCP clusters need `cluster-mgmt/info` to report `type == kGoogleCloud` for the vault-based backup lookup to kick in; if a GCP cluster is missing from that response (or its type field is empty), it silently falls back to the `stats/consumers` logic and will likely report 0 for backup usage.
* The GCP backup figure reads only the first storage domain and its first matching external target for the cluster - if a GCP cluster has multiple storage domains or external targets, only one is reported.
* SMTP settings (`smtp_server`, `smtp_port`, `from_email`, `to_list`) are hardcoded near the top of the email block - edit them directly in the script before using `-email`. The default config assumes an open relay on port 25 with no auth/TLS; uncomment `server.starttls()` / `server.login()` if your SMTP server requires them.
