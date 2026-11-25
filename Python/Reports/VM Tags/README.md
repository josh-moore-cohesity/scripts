# VMware VM Tag Report Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`get_vm_tags.py` reports the vCenter name, VM name and VMware tag(s) for every VM in your VMware protection sources.

Run with no cluster or vCenter specified, it connects to Helios, uses the Helios reporting `resources` API (`POST /heliosreporting/api/v1/public/resources`, `resourceType: RegisteredSources`) to list every registered VMware source, works out which cluster each one is registered on, and pulls the tags from the cluster's protection source tree. A vCenter that is registered on more than one cluster is only queried once.

You can also name specific VMs with `-o` / `-ol`. Each VM is located with Helios global search (`GET /v2/data-protect/search/objects`) to find the cluster and vCenter it belongs to, and then the tags are read from that vCenter's source tree.

The vCenter's source tree is requested on its own (not the whole cluster's VMware tree) and is split into smaller requests if the response would exceed the Helios proxy's 8 MB message limit.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `get_vm_tags.py`
* A Helios account with access to the clusters that hold the vCenter registrations (an API key is recommended)

## Components

* `get_vm_tags.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Usage

### All vCenters (auto-discovery)

Find every registered vCenter across all Helios clusters and write one combined CSV (`vm_tags_<date>.csv`):

```
python get_vm_tags.py
```

Limit the scan to specific clusters:

```
python get_vm_tags.py -c cluster1 cluster2
```

### One vCenter, shown on screen

Print `vCenter`, `VM Name` and `VMware Tags` for one vCenter on screen:

```
python get_vm_tags.py -s vcenter1.mydomain.net
```

### Filter by tag

Only show VMs that have a given tag (or any of several tags):

```
python get_vm_tags.py -s vcenter1.mydomain.net -t SNAP
python get_vm_tags.py -t SNAP GOLD
```

### Specific VMs

Report tags for one or more named VMs. Helios global search finds each VM's cluster and vCenter, then only that vCenter is read. Results are shown on screen:

```
python get_vm_tags.py -o vm01 vm02
```

Or give a text file with one VM name per line:

```
python get_vm_tags.py -ol vms.txt
```

VM names must match exactly (case-insensitive). Add `-of` to also write a CSV (`vm_tags_objects_<date>.csv`).

### Write a CSV

`-of` on its own writes an auto-named CSV (`vm_tags_<date>.csv`, or `vm_tags_<vcenter>_<date>.csv` when `-s` is used):

```
python get_vm_tags.py -s vcenter1.mydomain.net -of
```

Or give it a file name:

```
python get_vm_tags.py -of mytags.csv
```

### Explicit cluster and vCenter (no discovery)

If both `-c` and `-s` are given, discovery is skipped and the named vCenter is read directly from the named cluster(s):

```
python get_vm_tags.py -c cluster1 -s vcenter1.mydomain.net
```

## Parameters

### Authentication

| Flag | Description |
| --- | --- |
| -v, --vip | Helios endpoint (optional, default is helios.cohesity.com) |
| -u, --username | Username (optional, default is helios) |
| -d, --domain | Domain (optional, default is local) |
| -i, --useApiKey | Use API key for authentication |
| -pwd, --password | Password or API key (optional, will prompt if omitted) |
| -np, --noprompt | Do not prompt for a password |
| -m, --mfacode | MFA code (optional) |
| -e, --emailmfacode | Email an MFA code (optional) |
| -mcm, --mcm | Connect through Helios (forced on automatically when discovering vCenters) |

### Selection

| Flag | Description |
| --- | --- |
| -c, --clustername | One or more cluster names to limit the scan to (optional) |
| -cl, --clusters | Text file of cluster names, one per line (optional) |
| -s, --vcenter | vCenter name to report on (optional). Shows the result on screen |
| -o, --object | One or more VM names to report on (optional). Each VM is located via Helios global search; shows the result on screen |
| -ol, --objectlist | Text file of VM names, one per line (optional) |
| -t, --tag | One or more VMware tag names; only VMs with at least one of them are reported (optional, case-insensitive, exact name) |

### Output

| Flag | Description |
| --- | --- |
| -of, --output | Write a CSV (optional). No file name is needed; a name may be given |
| --pgs | Also look up protection groups and add a `Protection Groups` column (optional, extra API calls) |
| --debug | Print raw API responses for troubleshooting (optional) |

## Output

The CSV (and the on-screen table) has these columns:

| Column | Description |
| --- | --- |
| vCenter | vCenter source name |
| VM Name | Name of the VM |
| VMware Tags | The VM's tags, separated by commas |
| Protection Groups | Only with `--pgs`. `Unprotected` if the VM is not in any group |

## Notes

* The `resources` API does not say which cluster a source is registered on, so the script asks each connected cluster for its registered VMware sources until every vCenter has been located. This adds one call per cluster on the first part of a run; `-c` narrows it down.
* A vCenter registered on several clusters is only read from the first cluster it is found on, so `--pgs` only reflects protection groups on that cluster. A VM protected only from another cluster will show as `Unprotected`.
* If a single folder holds so many VMs that its tree is still too large for one request, the script prints a warning and the VMs under it are missing from the report.
* Without `-s`, `-o` or `-ol`, results are always written to a CSV. With any of them, results are shown on screen and a CSV is only written if `-of` is given.
* Place `-of` after the other options or before another flag, because it can take an optional file name.
* With `-o` / `-ol`, a vCenter registered on several clusters is only read from the first cluster the search reports it on. `-c` and `-s` also narrow which search matches are used.
* The vCenter name is taken from the global search result (`sourceName`). If a VM reports `could not determine vCenter`, run with `--debug` to inspect the search result.
* The tag column shows VMware tag names exactly as they appear in vCenter, so numeric tag names (for example a cost center ID) are real tags.
* `-o` was previously the CSV output flag; it is now `-of`.

## Download

```bash
# download commands
curl -O 'https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Reports/VM%20Tags/get_vm_tags.py'
curl -O https://raw.githubusercontent.com/bseltz-cohesity/scripts/refs/heads/master/python/pyhesity.py
chmod +x get_vm_tags.py
# end download commands
```
