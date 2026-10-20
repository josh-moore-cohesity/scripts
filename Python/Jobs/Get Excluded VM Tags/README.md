# Report VMs Excluded by Tag from Protection Groups Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`vm-tag-exclusions.py` finds VMware and GCP protection groups that use tag exclusions (`excludeVmTagIds`) and reports, for each excluded tag, the VMs that carry that tag. It runs against one or more clusters through Helios, or against every Helios-connected cluster if none are specified.

For each tag-excluding protection group, the script reads the group's registered source (or selected objects) from the protection source tree, then lists the VMs under that source that carry each excluded tag. Tags are matched by tag ID, so two tags with the same name but different IDs are treated as different tags.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `vm-tag-exclusions.py`

## Components

* `vm-tag-exclusions.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Usage

### All Connected Clusters

```
python vm-tag-exclusions.py -mcm -i
```

### Specific Clusters

```
python vm-tag-exclusions.py -c mycluster1 mycluster2
python vm-tag-exclusions.py -cl clusters.txt
```

### Single Protection Group

Use `-pg` to report on only one protection group (exact name, case-insensitive). Combine with `-c` to limit to a single cluster.

```
python vm-tag-exclusions.py -c mycluster -pg MyProtectionGroup
```

### Output

The script prints a header and, for each group and excluded tag, the VM count followed by one VM per line:

```
  PG Name | Tag | VM Count

  MyProtectionGroup | NO-BACKUP | 2 VMs
    vm001
    vm002
```

It also writes `vm-tag-exclusions-<date>.csv` to the output folder (`./Results` by default) with one row per excluded VM:

| Column | Description |
| --- | --- |
| Cluster | cluster name |
| Protection Group | protection group name |
| Environment | `kVMware` or `kGCP` |
| Excluded Tag | name of the excluded tag |
| Excluded VM Count | number of VMs excluded by that tag in that group |
| Excluded VM | one excluded VM per row (empty if the tag matched no VMs) |

## Parameters

### Authentication

| Flag | Description |
| --- | --- |
| -v, --vip | (optional) Helios endpoint (default is helios.cohesity.com) |
| -u, --username | (optional) username used to authenticate (default is helios) |
| -d, --domain | (optional) domain of the authenticating user (default is local) |
| -i, --useApiKey | (optional) use API key for authentication |
| -pwd, --password | (optional) password or API key |
| -np, --noprompt | (optional) do not prompt for password |
| -mcm, --mcm | (optional) connect through Helios |
| -m, --mfacode | (optional) MFA code for authentication |
| -e, --emailmfacode | (optional) send MFA code via email |

### Selection and Output

| Flag | Description |
| --- | --- |
| -c, --clustername | (optional) one or more cluster names (default is all Helios-connected clusters) |
| -cl, --clusters | (optional) text file of cluster names, one per line |
| -pg, --protectiongroup | (optional) report on only this protection group |
| -outputpath, --outputpath | (optional) folder for the CSV (default is ./Results) |
| -debug, --debug | (optional) print raw protection group parameters and sample source nodes for troubleshooting |

## Notes

* Only protection groups that have at least one excluded tag are reported. Clusters with none print `no tag exclusions found`.
* The VM list is every VM under the group's source that carries the excluded tag, matching what is shown when editing the protection group; it is not limited to VMs the group would otherwise include.
* VMs excluded by name or object rather than by tag are not reported.
* Tag names are resolved from the VMs in the source tree. An excluded tag that no VM carries is reported by tag ID with a count of 0.
* Both VMware and GCP groups are read from the `data-protect/protection-groups` API; use `-debug` if a group's exclusions are not detected.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/Jobs/Get%20Excluded%20VM%20Tags/vm-tag-exclusions.py
curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py
```
