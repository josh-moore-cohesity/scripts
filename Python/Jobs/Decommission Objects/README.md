# Decommission Objects (VMware, GCP, Azure, AWS VMs and Physical Servers)

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`decomission_object.py` removes decommissioned servers from Cohesity protection. For each object name supplied, it uses the Helios global search API (`data-protect/search/objects`) to find the cluster and protection group(s) the object is protected in, connects to that cluster through Helios, and then removes the object from its protection group(s). Physical servers are also unregistered from the cluster.

Existing snapshots are never deleted.

Supported object types:

| Type | Helios environment | Protection group handling |
|---|---|---|
| VMware VM | `kVMware` | removed from the PG, or excluded if protected through a parent (folder/tag/auto-protect) |
| GCP VM | `kGCP` | removed from the PG, or excluded if protected through a parent (tag/project/auto-protect) |
| Azure VM | `kAzure` | removed from the PG, or excluded if protected through a parent (tag/auto-protect) |
| AWS VM | `kAWS` | removed from the PG, or excluded if protected through a parent (tag/auto-protect) |
| Physical server | `kPhysical` | removed from the file/volume PG object list, then the physical source is unregistered |

The vCenter, GCP, Azure and AWS sources are never unregistered when decommissioning a VM.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `decomission_object.py`
* A Helios connection (always run with `-mcm`)

## Components

* `decomission_object.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module (download separately, see below)

## Usage

### Decommission one or more objects

```
python decomission_object.py -mcm -o myvm01 -o physhost01
```

### Decommission a list of objects

Provide a text file with one object name per line:

```
python decomission_object.py -mcm -ol decom_list.txt
```

### Dry run

Preview what would be changed without making any changes (no confirmation prompts are shown):

```
python decomission_object.py -mcm -ol decom_list.txt -dr
```

### Skip the confirmation prompt

By default the script asks for confirmation for each object/cluster before changing anything:

```
python decomission_object.py -mcm -ol decom_list.txt -y
```

### Restrict to specific clusters

If an object name exists on more than one cluster, restrict the work to the cluster(s) you want:

```
python decomission_object.py -mcm -o myvm01 -c cluster1 -c cluster2
python decomission_object.py -mcm -o myvm01 -cl clusterlist.txt
```

### Delete protection groups that would be left empty

```
python decomission_object.py -mcm -o myvm01 -deleteemptypg
```

## Authentication Parameters

| Flag | Description |
|---|---|
| `-v, --vip` | (optional) DNS or IP of the Helios endpoint (default is `helios.cohesity.com`) |
| `-u, --username` | (optional) username (default is `helios`) |
| `-d, --domain` | (optional) domain of the user (default is `local`) |
| `-mcm, --mcm` | (required) connect through Helios |
| `-i, --useApiKey` | (optional) use an API key for authentication |
| `-pwd, --password` | (optional) password or API key |
| `-np, --noprompt` | (optional) do not prompt for password |
| `-m, --mfacode` | (optional) MFA code for authentication |
| `-e, --emailmfacode` | (optional) send MFA code via email |

## Object Parameters

| Flag | Description |
|---|---|
| `-o, --objectname` | (optional) name of an object to decommission; repeat the flag for multiple objects |
| `-ol, --objectlist` | (optional) text file of object names to decommission (one per line) |
| `-c, --clustername` | (optional) restrict to this cluster; repeat for multiple clusters (default is all clusters) |
| `-cl, --clusters` | (optional) text file of cluster names to restrict to (one per line) |

At least one of `-o` or `-ol` is required. Object names are matched exactly (case-insensitive).

## Behavior Parameters

| Flag | Description |
|---|---|
| `-dr, --dryrun` | (optional) show what would be done, make no changes |
| `-y, --yes` | (optional) do not prompt for confirmation before each object |
| `-deleteemptypg, --deleteemptypg` | (optional) delete a protection group if the object is its last object (snapshots are kept) |
| `-outputpath, --outputpath` | (optional) folder for the CSV report (default is `./Decommission`) |

## Output

A CSV report is written to the output path, named `decommission-<date>.csv`, or `<objectlist filename>-<date>.csv` when `-ol` is used. Each row records the object, cluster, environment, protection group, action and result.

## Notes

* A protection group is left unmodified if the object is its last object, unless `-deleteemptypg` is specified. In that case the protection group is deleted with `deleteSnapshots=false`.
* If an object is protected through a parent (folder, tag, project or auto-protect rule) rather than being listed explicitly in the PG, it is added to the PG's `excludeObjectIds` instead of being removed.
* Physical servers are only unregistered once every protection group removal has succeeded.
* Clusters that are disconnected from Helios are skipped and logged in the report.
* Only protection group types with an explicit object list are supported. Unsupported PG types are skipped and reported as `Unsupported PG type`.
* The GCP, Azure and AWS protection group parameter layouts are handled generically (objects directly under `gcpParams`/`azureParams`/`awsParams`, or under a nested `...ProtectionTypeParams` section). Run with `-dr` first to confirm the behavior in your environment.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Jobs/Decommission%20Objects/decomission_object.py
curl -O https://raw.githubusercontent.com/bseltz-cohesity/scripts/refs/heads/master/python/pyhesity.py
```
