# **gcp_cluster_performance.py**

Generate an HTML performance report (target storage usage, daily ingest, and network throughput trend) for GCP Cloud Edition clusters connected to Helios, or for a specific list of clusters.<br />
[pyhesity.py](https://github.com/cohesity/community-automation-samples/blob/main/python/pyhesity.py) is required.

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

## **Requirements**

* Python 3
* `pyhesity.py` in the same directory as `gcp_cluster_performance.py`

## **Download**

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Reports/GCP%20Performance/gcp_cluster_performance.py
    curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py

## **Parameters**

* -v, --vip (Cohesity cluster or Helios endpoint, default: helios.cohesity.com)
* -u, --username (default: helios)
* -d, --domain (default: local)
* -i, --useApiKey (use an API key for authentication)
* -mcm, --mcm (connect via Helios/MCM)
* -pwd, --password (optional; will use cached password/key or will be prompted)
* -np, --noprompt (do not prompt for credentials, e.g. when using a stored password)
* -m, --mfacode (MFA code)
* -e, --emailmfacode (send MFA code via email)
* -c, --clustername (space separated list of GCP cluster names to target; if omitted, GCP clusters are auto-discovered)
* -cl, --clusters (text file of cluster names, one per line; can be combined with `-c`)
* -outputpath, --outputpath (folder to write the HTML report to, default: `./Results`; created if it doesn't exist)

## **How It Works**

1. Authenticates once (directly to a cluster, or to Helios/MCM with `-mcm`).
2. If no clusters were given via `-c`/`-cl`, auto-discovers GCP clusters by calling `cluster-mgmt/info` and filtering for `isConnectedToHelios == true` and `type == kGoogleCloud`.
3. Classifies each cluster name into `nonprod`, `lab`, `prod`, or `other` by a case-insensitive substring match on the cluster name (checking `nonprod` before `prod`, since `nonprod` contains `prod` as a substring). This is name-convention based, not derived from any Cohesity metadata.
4. For each cluster, switches context with `heliosCluster()` and:
   * **Target usage (TB):** backup data on GCP Cloud Edition clusters lives entirely in the GCP bucket configured as the cluster's external target, not on local disks or the cluster's logical storage layer. The script finds the cluster's first storage domain, finds the external target tied to that domain, and reads the vault's latest `kIceboxVaultStats`/`kMorphedUsageBytes` value over the trailing 24 hours.
   * **Ingest, last 24h (GB):** sums `kBridgeClusterLogicalStats`/`kNumBytesWritten` (rate rollup, 5-minute buckets) over the trailing 24 hours.
   * **Throughput, last 7d (avg/peak Mbps + trend):** same metric, 1-hour buckets over the trailing 7 days; computes the average and peak, and keeps the per-bucket series for a sparkline.
5. Rolls up grand totals (total target usage, total ingest) and counts of nonprod/lab/prod clusters across all rows.
6. Sorts the per-cluster results alphabetically by cluster name.
7. Renders a small inline SVG sparkline per cluster for the 7-day throughput trend, labeling the peak point(s) with their value.
8. Writes a single self-contained HTML report with summary cards and a per-cluster table.

## **Output**

Written to `outputpath` (default `./Results`), one run per day:

* `gcp_cluster_performance_<date>.html` - HTML report with summary cards (total target usage, total ingest, nonprod/lab/prod cluster counts) and a per-cluster table (target usage, ingest, avg/peak throughput, 7-day throughput sparkline)

## **Examples**

### Auto-discover and report on all GCP clusters connected to Helios, using an API key

    python gcp_cluster_performance.py -mcm -i

### Report on specific clusters by name

    python gcp_cluster_performance.py -mcm -i -c cluster1 cluster2

### Report on clusters listed in a text file

    python gcp_cluster_performance.py -mcm -i -cl clusters_gcp.txt

### Write the report to a custom folder

    python gcp_cluster_performance.py -mcm -i -outputpath C:\Reports

## **Notes**

* Auto-discovery is limited to clusters with `isConnectedToHelios == true` and `type == kGoogleCloud` in `cluster-mgmt/info`; a GCP cluster missing or misreporting that `type` field won't be auto-discovered (though it can still be targeted explicitly with `-c`/`-cl`).
* The target usage figure reads only the first storage domain and its first matching external target for the cluster - if a cluster has multiple storage domains or external targets, only one is reported.
* Environment counts (nonprod/lab/prod) in the summary cards are based purely on substring matching in the cluster name; clusters that don't match any pattern are classified `other` and aren't shown as their own summary card.
* No CSV or email output - this script only writes the HTML report (unlike `cluster_utilization_summary.py`, which also writes a CSV and can email the report).
