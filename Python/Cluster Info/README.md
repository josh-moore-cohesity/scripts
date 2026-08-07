# **cluster_info.py**

Collect cluster configuration info for all clusters connected to Helios (or a single cluster) and export the results to CSV. Optionally generate a Cohesity-branded PDF report per cluster.<br />
[pyhesity.py](https://github.com/cohesity/community-automation-samples/blob/main/python/pyhesity.py) is required.

## **Requirements**

    pip install reportlab

## **Download**

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Cluster%20Info/cluster_info.py
    curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py

## **Parameters**

* -v, --vip (Cohesity cluster or Helios endpoint, default: helios.cohesity.com)
* -u, --username (default: helios)
* -i, --useApiKey (use an API key for authentication)
* -mcm, --mcm (connect via Helios/MCM)
* -np, --noprompt (do not prompt for credentials, e.g. when using a stored password)
* -m, --mfacode (MFA code)
* -e, --emailmfacode (send MFA code via email)
* -pdf, --pdf (also generate a branded PDF report per cluster)
* -outputpath, --outputpath (folder to write PDF reports to, default: ./ClusterInfoPDFs)

## **What it collects**

For every cluster connected to Helios, the script gathers:

* Cluster info — ID, type, node count, install date, timezone, software version, encryption, redundancy/erasure coding settings, DNS, SMTP, NTP, SSO, audit log retention, apps network, critical alert email, custom roles/users count, and login banner
* Custom GFlags per service
* Marketplace apps and running instance counts
* Node details — hostname, type, ID, node IP, and IPMI IP (physical clusters)

Clusters not currently connected to Helios are skipped.

## **Output**

CSV files are written to the current directory, one run per day:

* `cluster_info-<date>.csv`
* `cluster_info_gflags-<date>.csv`
* `cluster_info_apps-<date>.csv`
* `cluster_info_nodes-<date>.csv`

When `-pdf` is used, a per-cluster PDF (`cluster_info_<cluster>_<date>.pdf`) is also written to `--outputpath`.

## **Examples**

### Query all clusters connected to Helios using an API key

    python cluster_info.py -i

### Same, and also generate PDF reports

    python cluster_info.py -i -pdf

### Generate CSV and PDF reports to a custom folder

    python cluster_info.py -i -pdf -outputpath ./Reports
