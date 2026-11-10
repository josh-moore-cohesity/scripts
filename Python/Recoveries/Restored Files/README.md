# List the Files Restored by a Cohesity Recovery Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`get_restored_file_list.py` produces a file list for a completed Cohesity recovery, along with the settings the restore ran with (restore target, overwrite, preserve attributes, continue on error) and any errors or warnings the restore task recorded.

Cohesity does not keep a per-file manifest of what a restore wrote. For a NAS volume restore the entire snapshot is restored, so the script finds the snapshot the recovery used (the `snapshotId` in the recovery is a base64 encoded run reference) and lists its contents with the same snapshot browse call (`/vm/directoryList`) that the UI uses. For a file / folder restore it lists only the paths that were selected for the restore. Restore events (errors, warnings) come from the recovery's progress task via `/progressMonitors`.

The recovery is read through the [Data Protect recoveries API](https://developer.cohesity.com/apidocs-production.html#/rest/Recoveries) (`/v2/data-protect/recoveries`).

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `get_restored_file_list.py`

## Components

* `get_restored_file_list.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Usage

Find a recovery by name and list the files it restored:

```
python get_restored_file_list.py -c mycluster -n "Recover_Storage_Volumes_Nov_9_2026_9_12_PM"
```

Find a recovery by id:

```
python get_restored_file_list.py -c mycluster -r "1736762937940464:1751380818142:313525"
```

List only part of the snapshot (a folder under the restored volume):

```
python get_restored_file_list.py -c mycluster -n "Recover_Storage_Volumes_Nov_9_2026_9_12_PM" -p /vdbench
```

Search every Helios-connected cluster for the recovery (omit `-c`):

```
python get_restored_file_list.py -n "Recover_Storage_Volumes_Nov_9_2026_9_12_PM"
```

## Output

Files are written to `./Results` (or `-outputpath`), prefixed with the cluster and recovery name:

* `...-restored-files.csv` - object, file path, type, size (bytes), last modified and snapshot date for every file in the restored snapshot
* `...-recovery-settings.csv` - recovery name, id, action, status, requester, start / end time, bytes transferred, restore target (original / alternate location) and the restore options (`overwriteExistingFile`, `preserveFileAttributes`, `continueOnError`, `encryptionEnabled`)
* `...-requested-paths.csv` - (file / folder restores only) the paths selected for the restore, with destination directory
* `...-events.csv` - (only if present) error / warning events from the restore task

## Authentication Parameters

| Flag | Description |
|---|---|
| `-v, --vip` | (optional) name or IP of Cohesity cluster (defaults to `helios.cohesity.com`) |
| `-u, --username` | (optional) name of user to connect to Cohesity (defaults to `helios`) |
| `-d, --domain` | (optional) your AD domain (defaults to `local`) |
| `-i, --useApiKey` | (optional) use an API key for authentication |
| `-pwd, --password` | (optional) will use cached password/key or will be prompted |
| `-np, --noprompt` | (optional) do not prompt for password |
| `-mcm, --mcm` | (optional) connect through MCM |
| `-m, --mfacode` | (optional) TOTP MFA code |
| `-e, --emailmfacode` | (optional) send MFA code via email |
| `-c, --clustername` | (optional) one or more clusters to search for the recovery (defaults to all Helios-connected clusters) |
| `-cl, --clusters` | (optional) text file of cluster names to search (one per line) |

## Recovery Parameters

| Flag | Description |
|---|---|
| `-r, --recoveryid` | (required unless `-n` is used) id of the recovery |
| `-n, --recoveryname` | (required unless `-r` is used) name of the recovery (case insensitive) |
| `-p, --path` | (optional) list only this path within the snapshot (defaults to `/`, or to the selected paths for a file / folder restore) |
| `-a, --attemptnum` | (optional) backup run attempt number to browse (defaults to 0) |
| `-outputpath, --outputpath` | (optional) folder to write output files to (defaults to `./Results`) |
| `-showraw, --showraw` | (optional) print the first raw snapshot browse response, for troubleshooting |

## Notes

* **The list comes from the snapshot, not from the restore destination.** Cohesity does not record each file written, so the list is "everything in the snapshot at the restored path". Pair it with the status and events output: if the recovery succeeded with no error or warning events, every file in the list was restored.
* **`continueOnError`:** when this is `True` in the recovery settings, an individual file failure does not fail the restore, so a status of `Succeeded` on its own does not prove that every file landed. Check `...-events.csv` (the script reports when there are no error or warning events).
* **`overwriteExistingFile`:** when `True` and the restore target is the original location, any file at the same path was replaced with the snapshot version, so changes made after the snapshot date were overwritten. The recovery options do not include a setting to delete files that are not in the snapshot.
* The snapshot is browsed one folder at a time, so large volumes take a while (progress is printed every 5,000 files). Transient errors from the cluster are retried; a folder that still fails is reported and skipped, and a warning states that the list is incomplete.
* The output is written to a `.partial` file and renamed only when the listing completes, so a failed run does not overwrite an earlier complete list.
* Tested against an Isilon NAS volume restore (`RecoverNasVolume`). File / folder restores and other environments use the same code path, but the snapshot browse call and field names have not been verified against them. Use `-showraw` to inspect the raw response if a column comes back blank.

## Download

    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Recoveries/Restored%20Files/get_restored_file_list.py
