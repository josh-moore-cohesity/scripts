# Cohesity Quorum Group Report Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`quorum_report.py` reports on Cohesity Helios quorum group configuration. It can audit one or all cluster-scoped quorum groups against every Helios-connected cluster and show which clusters are missing from which groups, or list every quorum group a specific cluster belongs to.

The script reads quorum groups from the Helios endpoint `GET /v2/mcm/quorum/groups?fetchConflictDetails=true` and the cluster list from `cluster-mgmt/info`, using the [pyhesity](https://raw.githubusercontent.com/bseltz-cohesity/scripts/refs/heads/master/python/pyhesity.py) REST API wrapper. Results are shown onscreen and written to a timestamped CSV or HTML file, so the audit can be run on a schedule.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `quorum_report.py`
* A Helios user or API key with permission to view quorum groups (`QUORUM_GROUP_VIEW`)

## Components

* `quorum_report.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Operating Modes

### Audit All Quorum Groups

Audit every cluster-scoped quorum group against all Helios-connected clusters. For each group, the script lists the clusters that are included and the clusters that are missing:

```
python quorum_report.py -i
```

### Audit a Single Quorum Group

Limit the audit to one group by name (the match is case-insensitive):

```
python quorum_report.py -i -g 'US: Firewall | Cluster Level'
```

### Quorum Groups for a Specific Cluster

List every quorum group a cluster is a member of, followed by the groups it is not a member of (one per line):

```
python quorum_report.py -i -c mycluster
```

### Scheduled Weekly Audit

Run unattended, write an HTML report, and silence the screen output. The script exits with code 1 when any cluster is missing from a group, so the scheduler can alert on it:

```
python quorum_report.py -i -np -q -outtype html -outputpath /reports/quorum
```

## Output

Onscreen output is always shown unless `-q` is used. A file is written to `-outputpath` on every run unless `-nofile` is used.

| Report | File name |
| --- | --- |
| Audit | `quorum-audit-<yyyy-mm-dd_hhmm>.csv` / `.html` |
| Cluster lookup | `quorum-cluster-<yyyy-mm-dd_hhmm>.csv` / `.html` |

The files mirror the onscreen output, grouped by quorum group with the included clusters followed by the missing clusters.

### Audit File

The CSV contains one row per cluster per group, ordered by group (included clusters first, then missing clusters):

| Column | Description |
| --- | --- |
| quorumGroup | Quorum group name |
| groupStatus | `OK` or `MISSING <n>` |
| groupMemberCount | Number of clusters in the group |
| missingCount | Number of Helios-connected clusters missing from the group |
| cluster | Cluster name |
| membership | `included`, `missing`, or `included-not-in-helios-list` |

To list only the gaps, filter the CSV on `membership = missing`.

The HTML file has one section per quorum group, with the group status and the included and missing clusters side by side (included in green, missing in red), followed by the summary lines.

### Cluster Lookup File

The CSV contains one row per quorum group (`cluster, quorumGroup, groupClusterCount, membership`), where `membership` is `member` or `not-member`. The HTML file shows a "Member of" list and a "Not a member of" list for the cluster.

## Parameters

### Authentication

| Flag | Description |
| --- | --- |
| -v, --vip | Helios endpoint (default `helios.cohesity.com`) |
| -u, --username | Username (default `helios`) |
| -d, --domain | Domain (default `local`) |
| -i, --useApiKey | Use an API key for authentication |
| -pwd, --password | Password or API key (will be prompted for, or read from the stored password, if omitted) |
| -np, --noprompt | Do not prompt for a password (use for scheduled runs) |
| -m, --mfacode | MFA code |
| -e, --emailmfacode | Send the MFA code by email |

### Report

| Flag | Description |
| --- | --- |
| -a, --audit | Audit groups against all clusters (default mode) |
| -g, --groupname | Limit the audit to one quorum group (optional) |
| -c, --clustername | List the quorum groups this cluster is in (optional) |

### Output

| Flag | Description |
| --- | --- |
| -outtype, --outtype | Output file type: `csv` or `html` (default `csv`) |
| -outputpath, --outputpath | Folder for the output file (default `./Results`) |
| -nofile, --nofile | Onscreen output only, do not write a file |
| -q, --quiet | No onscreen output |

### Troubleshooting

| Flag | Description |
| --- | --- |
| -dump, --dump | Print the raw quorum group API response and exit |
| -endpoint, --endpoint | Override the quorum group API path |

## Notes

* Only Helios-connected clusters are included in the audit.
* Helios-level groups (for example `Accounts | Helios Local` or `IDP | Helios Level`) have no cluster scope, so they are skipped. The audit prints a count of the groups skipped.
* Group members that cannot be matched to a Helios-connected cluster are shown as `?` lines with their cluster ID onscreen, are marked `included-not-in-helios-list` in the files, and are not counted as missing.
* The quorum group API response is not publicly documented. If the field parsing needs adjusting for your environment, run with `-dump` to see the raw response.
* If a cluster you expect to see in the audit is absent, confirm it is connected to Helios.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Security/Quorum/quorum_report.py
```
