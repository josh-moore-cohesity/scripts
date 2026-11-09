# Exclude VMs from VM Protection Groups Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

This folder contains scripts that add (or remove) VM exclusions on VM auto-protect protection groups. VMs are located using the Helios/cluster object search, and the exclusion is written to the protection group that currently protects the VM (`excludeSourceIds`).

## Requirements

* Python 3
* [`pyhesity.py`](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) in the same folder as the scripts (or on your Python path)

## Components

* `excludeVMs_All_Clusters.py` - excludes VMs by exact name or wildcard pattern, across all clusters connected to Helios. Finds each VM's protection group automatically.
* `excludeVMs.py` - excludes VMs from one specified protection group (`-j`) on the specified cluster(s). Names are partial (any-match) substrings.
* `excludeVMsAllJobs.py` - excludes VMs from all protection groups on the specified cluster(s). Names are partial (any-match) substrings.
* `remove_vm_exclude_all_clusters.py` - removes manually added VM exclusions across all clusters.

## Excluding VMs Across All Clusters

`excludeVMs_All_Clusters.py` connects to Helios (`-mcm`), searches for each VM name or pattern, connects to the cluster that protects each match, and adds the VM to the exclusion list of its protection group. Results are written to a CSV in the output folder (default `./ExcludeVMs`).

### Exact names

A name with no wildcard characters must match the VM name exactly (case-insensitive).

```bash
python excludeVMs_All_Clusters.py -v helios.cohesity.com -i -mcm -x server1 -x server2
```

### Wildcard patterns

Names can include wildcards. Quote patterns so your shell does not expand them.

| Pattern | Matches |
|---|---|
| `server1*` | any VM whose name starts with `server1` |
| `*server1*` | any VM with `server1` anywhere in the name |
| `*-prod` | any VM whose name ends with `-prod` |
| `web0?` | `web01`, `web02`, ... (`?` is any single character) |
| `db[12]*` | names starting with `db1` or `db2` (`[seq]` is any one character in the set) |

```bash
python excludeVMs_All_Clusters.py -v helios.cohesity.com -i -mcm -x 'server1*' -x '*sql*'
```

### Names from a file

Put one name or pattern per line in a text file and pass it with `-vl`. It can be combined with `-x`.

```bash
python excludeVMs_All_Clusters.py -v helios.cohesity.com -i -mcm -vl ./vmlist.txt
```

### Parameters

| Flag | Description |
|---|---|
| `-v`, `--vip` | Helios or cluster DNS name or IP (default `helios.cohesity.com`) |
| `-u`, `--username` | User name (default `helios`) |
| `-d`, `--domain` | User domain (default `local`) |
| `-i`, `--useApiKey` | Use an API key for authentication |
| `-p`, `--password` | Password or API key (will prompt if omitted) |
| `-np`, `--noprompt` | Do not prompt for a password |
| `-mcm`, `--mcm` | Connect through Helios/MCM |
| `-m`, `--mfacode` | MFA code |
| `-e`, `--emailmfacode` | Send the MFA code by email |
| `-x`, `--exclude` | (Optional) VM name or wildcard pattern to exclude; can be repeated |
| `-vl`, `--excludelist` | (Optional) Text file of VM names or patterns, one per line |
| `-xt`, `--excludeTemplates` | Exclude templates |
| `-outputpath`, `--outputpath` | Folder for the output CSV (default `./ExcludeVMs`) |

At least one of `-x` or `-vl` is required.

## Excluding VMs From One Protection Group or All Protection Groups

`excludeVMs.py` and `excludeVMsAllJobs.py` match on partial names (any VM containing the text).

```bash
python excludeVMs.py -i -xt -x ora -x sql -c cluster1 -j job1
python excludeVMsAllJobs.py -i -xt -x ora -x sql -c cluster1
```

## Removing Exclusions

```bash
python remove_vm_exclude_all_clusters.py -v helios.cohesity.com -i -mcm -n server1 -n server2
python remove_vm_exclude_all_clusters.py -v helios.cohesity.com -i -mcm -vl ./vmlist.txt
```

| Flag | Description |
|---|---|
| `-n`, `--vmname` | VM name to remove from exclusions; can be repeated |
| `-vl`, `--vmlist` | Text file of VM names, one per line |
| `-vc`, `--vcentername` | (Optional) limit to a specific vCenter |
| `-outputpath`, `--outputpath` | Folder for the output CSV (default `./RemoveExcludes`) |

## Notes

* In `excludeVMs_All_Clusters.py`, plain names are exact matches. Earlier versions excluded every VM returned by the substring search, so `-x sql` also excluded `mysql-01`. Use `-x '*sql*'` for that behavior.
* The Helios search is a substring search, so for a wildcard pattern the script searches on the longest non-wildcard piece of the pattern and then filters the results against the full pattern. A pattern with no literal text (such as `*`) is skipped.
* A VM that is already in a protection group's exclusion list is reported as `Already Excluded` and is not added twice.
* Clusters that are disconnected from Helios are skipped and noted in the output CSV.

## Download

```bash
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/excludeVMs_All_Clusters.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/excludeVMs.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/excludeVMsAllJobs.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/remove_vm_exclude_all_clusters.py
curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py
```
