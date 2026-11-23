# Storage Growth Report Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`storageGrowth.py` reports daily storage consumption and total capacity for a Cohesity cluster over time, using the cluster's `kBridgeClusterStats` time series statistics (`kMorphedUsageBytes` and `kCapacityBytes`, rolled up daily). For each run it writes a CSV and a self-contained HTML report with charts of consumed storage versus capacity.

With `-c all` (Helios/MCM), the script loops through every cluster connected to Helios and writes a single combined CSV and HTML report covering all of them.

It is built on the [pyhesity](https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity/pyhesity.py) REST API wrapper.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `storageGrowth.py`
* A web browser to view the HTML report (the report is a single file with no external libraries or network calls, so it also works offline)

## Components

* `storageGrowth.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Output

Files are written to the folder given by `-of` (the current directory by default), named with the cluster name and run date:

| Run type | CSV | HTML |
|---|---|---|
| Single cluster | `storageReport-<cluster>-<date>.csv` | `storageReport-<cluster>-<date>.html` |
| Multiple clusters / `-c all` | `storageReport-all-clusters-<date>.csv` (adds a `Cluster` column) | `storageReport-all-clusters-<date>.html` |

### HTML report

* **Summary tiles** per cluster: latest consumed and capacity, % full (highlighted at 80% or more), change over the period, average daily change, and estimated days until full (only shown when usage is growing and the cluster is not already over capacity)
* **Chart** per cluster: consumed (solid line, shaded) versus capacity (dashed line), with a hover tooltip showing the date, consumed, capacity and % full
* **Multi-cluster reports** add:
  * a sortable summary table (click any column header; defaults to % full, highest first), collapsed to the top 5 with a **Show all** button
  * a **Show chart** drop-down (default "All clusters") to filter to a single cluster's chart; clicking a cluster name in the summary table does the same
  * cluster charts ordered by % full, highest first
* Follows the viewer's light/dark mode setting

## Usage

### Single cluster

Connected directly to a cluster:

```
python storageGrowth.py -v mycluster -u myuser -d mydomain.net
```

Connected through Helios (the cluster name is required):

```
python storageGrowth.py -c mycluster
```

Limit the report to the last 90 days and report in TiB:

```
python storageGrowth.py -c mycluster -y 90 -x TiB
```

### Multiple clusters

Report on specific clusters (repeat `-c` and/or separate names with commas):

```
python storageGrowth.py -c cluster1 -c cluster2
python storageGrowth.py -c cluster1,cluster2
```

Report on every cluster connected to Helios:

```
python storageGrowth.py -c all -y 90 -x TiB -of C:\reports
```

`all` can be combined with explicit names; duplicates are removed. Clusters that cannot be reached, or that return no storage statistics, are skipped with a message and the rest of the report is still produced.

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

## Report Parameters

| Flag | Description |
|---|---|
| `-c, --clustername` | (required when connecting through Helios/MCM) cluster(s) to report on; repeat the flag and/or comma separate names, or use `all` for every cluster connected to Helios |
| `-of, --outfolder` | (optional) folder to write the CSV and HTML files to (defaults to the current directory) |
| `-y, --days` | (optional) number of days back to report on (defaults to the full life of the cluster) |
| `-x, --units` | (optional) `GiB` or `TiB` (defaults to `GiB`) |

## Notes

* `-c all` is only supported when connecting through Helios or MCM. Connecting directly to a cluster always reports on that one cluster.
* Statistics are daily rollups (latest value per day). Days where the cluster returned no capacity value are skipped in the CSV and the chart.
* The estimated days until full is a simple straight-line projection of the average daily change over the reported period, so it is only as good as the period you choose; use `-y` to base it on recent growth.
* On very large runs (around 100 clusters) the HTML report can be several hundred KB and takes a few seconds to render in the browser.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Reports/Storage/storageGrowth.py
curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity/pyhesity.py
```
