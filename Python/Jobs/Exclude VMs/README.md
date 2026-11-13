# Exclude VMs from VM Protection Groups Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

This folder contains scripts that add (or remove) VM exclusions on VM auto-protect protection groups. VMs are located using the Helios/cluster object search, and the exclusion is written to the protection group that currently protects the VM.

All scripts in this folder use the v2 protection group API (`data-protect/protection-groups`) and only modify VMware (or, for `excludeVMs_All_Clusters.py`, VMware and Physical) protection groups. Replicated protection groups (`isActive=false`) are skipped. Every script supports `-dr` (dry run) to preview changes without modifying anything.

## Requirements

* Python 3
* [`pyhesity.py`](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) in the same folder as the scripts (or on your Python path)

## Components

* `excludeVMs_All_Clusters.py` - excludes VMware VMs and physical servers by exact name or wildcard pattern, across all clusters connected to Helios. Finds each object's protection group automatically and updates it through the v2 protection group API.
* `excludeVMs.py` - excludes VMs from one specified VMware protection group (`-j`) on the specified cluster(s). Names are partial (any-match) substrings.
* `excludeVMsAllJobs.py` - excludes VMs from all VMware protection groups on the specified cluster(s). Names are partial (any-match) substrings.
* `remove_vm_exclude_all_clusters.py` - removes VM exclusions from VMware protection groups across all clusters.

## Excluding VMs Across All Clusters

`excludeVMs_All_Clusters.py` connects to Helios (`-mcm`), searches for each name or pattern, connects to the cluster that protects each match, and updates the protection group(s) that protect it using the v2 protection group API. Results are written to a CSV in the output folder (default `./ExcludeVMs`).

### What gets modified

Only VMware VMs (`kVMware`) and physical servers (`kPhysical`) are processed. Anything else a name or wildcard pattern matches (Cassandra, SQL, Oracle, NAS and so on) is ignored, and the console reports how many matches were ignored. Each protection group is also checked after it is retrieved, and any group that is not a VMware or Physical protection group is skipped and logged. Replicated protection groups (`isActive=false`) are skipped.

| Object and protection group | Change made |
|---|---|
| VMware VM protected through a folder, tag or auto-protect parent | VM is added to the protection group's `vmwareParams.excludeObjectIds` |
| VMware VM listed explicitly in the protection group | VM is removed from the protection group's object list |
| Physical server | Server is removed from the protection group's object list (physical file and volume protection groups have no exclusion list) |
| Last remaining object in a protection group | Protection group is not modified and the result is logged |

Existing snapshots are never deleted and protection groups are never deleted.

### Preview (dry run)

Use `-dr` to see what would change without modifying anything. This is recommended before running with wildcard patterns.

```bash
python excludeVMs_All_Clusters.py -v helios.cohesity.com -i -mcm -x '*sql*' -dr
```

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
| `-dr`, `--dryrun` | (Optional) Show what would change without modifying any protection group |
| `-xt`, `--excludeTemplates` | Accepted for compatibility; not used by this script |
| `-outputpath`, `--outputpath` | Folder for the output CSV (default `./ExcludeVMs`) |

At least one of `-x` or `-vl` is required. This script requires a Helios connection (`-mcm`).

The output CSV has the columns `Object,Cluster,Environment,Protection Group,Result` and is written as the script runs.

## Excluding VMs From One Protection Group or All Protection Groups

`excludeVMs.py` and `excludeVMsAllJobs.py` match on partial names (any VM whose name contains the text). They look inside the folders, hosts and other objects that a VMware protection group protects, and add matching VMs to the protection group's `vmwareParams.excludeObjectIds`. Only virtual machines are added (never folders or hosts), and a protection group is only updated when there is something new to exclude.

```bash
python excludeVMs.py -v helios.cohesity.com -i -c cluster1 -j job1 -xt -x ora -x sql
python excludeVMsAllJobs.py -v helios.cohesity.com -i -c cluster1 -xt -x ora -x sql
```

Preview first with `-dr`:

```bash
python excludeVMsAllJobs.py -v helios.cohesity.com -i -c cluster1 -x sql -dr
```

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
| `-c`, `--clustername` | Cluster to connect to; can be repeated (required when connecting through Helios) |
| `-cl`, `--clusters` | Text file of cluster names, one per line |
| `-j`, `--jobname` | (`excludeVMs.py` only, required) Name of the VMware protection group |
| `-x`, `--exclude` | VM name substring to exclude; can be repeated |
| `-xt`, `--excludeTemplates` | Also exclude VM templates |
| `-dr`, `--dryrun` | Show what would change without modifying any protection group |

## Removing Exclusions

`remove_vm_exclude_all_clusters.py` connects to Helios (`-mcm`), searches for each VMware VM name or pattern, and removes the VM from the `vmwareParams.excludeObjectIds` of every active VMware protection group (on the cluster that protects it) that excludes it. Results are written to a CSV in the output folder (default `./RemoveExcludes`).

```bash
python remove_vm_exclude_all_clusters.py -v helios.cohesity.com -i -mcm -n server1 -n server2
python remove_vm_exclude_all_clusters.py -v helios.cohesity.com -i -mcm -vl ./vmlist.txt
python remove_vm_exclude_all_clusters.py -v helios.cohesity.com -i -mcm -n 'web0*' -dr
```

| Flag | Description |
|---|---|
| `-n`, `--vmname` | VM name or wildcard pattern to remove from exclusions; can be repeated |
| `-vl`, `--vmlist` | Text file of VM names or patterns, one per line |
| `-vc`, `--vcentername` | (Optional) only change protection groups that use this vCenter source |
| `-dr`, `--dryrun` | Show what would change without modifying any protection group |
| `-outputpath`, `--outputpath` | Folder for the output CSV (default `./RemoveExcludes`) |

Connection flags (`-v`, `-u`, `-d`, `-i`, `-pwd`, `-np`, `-mcm`, `-m`, `-e`) are the same as above (the password flag is `-pwd`). At least one of `-n` or `-vl` is required.

The output CSV has the columns `Object,Cluster,Protection Group,Result`.

## Notes

* In `excludeVMs_All_Clusters.py`, plain names are exact matches. Earlier versions excluded every VM returned by the substring search, so `-x sql` also excluded `mysql-01`. Use `-x '*sql*'` for that behavior.
* The Helios search is a substring search, so for a wildcard pattern the script searches on the longest non-wildcard piece of the pattern and then filters the results against the full pattern. A pattern with no literal text (such as `*`) is skipped.
* A VM that is already in a protection group's exclusion list is reported as `Already excluded` and is not added twice.
* Clusters that are disconnected from Helios are skipped and noted in the output CSV.
* Earlier versions of `excludeVMs_All_Clusters.py` used the v1 `protectionJobs` API, took the first protection group returned by the search, and rewrote the whole job without checking its type. A wildcard that also matched objects in other environments (for example Cassandra nodes) could therefore modify those protection groups. The current version filters by environment and protection group type and uses the v2 API.
* Only VMware VMs and physical servers are supported. AWS, Azure, GCP, Hyper-V and AHV VMs are ignored.
* `excludeVMs.py` and `excludeVMsAllJobs.py` previously used the v1 `protectionJobs` API (`excludeSourceIds`), rewrote the job on every run, and could exclude non-VM objects (folders, hosts) whose names matched. They now use the v2 API, only modify VMware protection groups, only exclude virtual machines, and only update a protection group when something new is excluded. They still match on partial names, so `-x sql` also excludes `mysql-01`.
* `remove_vm_exclude_all_clusters.py` previously used a substring search with no name filter and the v1 API. Plain names are now exact matches (use `-n '*sql*'` for the old behavior), only VMware VMs are considered, and `-vc` is now honored. It finds exclusions through the VM's search result, so a VM that the search does not associate with a vCenter source on a cluster is not changed.

## Download

```bash
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/excludeVMs_All_Clusters.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/excludeVMs.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/excludeVMsAllJobs.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Exclude%20VMs/remove_vm_exclude_all_clusters.py
curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py
```
