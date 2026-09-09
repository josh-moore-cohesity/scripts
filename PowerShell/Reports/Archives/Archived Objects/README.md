# Report Archived Objects

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`archivedObjects.ps1` reports every protected object that has an archive copy, across one or more Cohesity clusters: latest/oldest backup dates, latest/oldest archive dates per target, archive count, archive target, expiry, and a per-copy Active/Expired status. It reads from the `/searchvms` recoverable-objects endpoint rather than walking job run history, so it reflects what's currently recoverable/archived regardless of retention on the original backup. Output can be saved as CSV, a sortable/filterable HTML report, or a PDF snapshot (rendered from the HTML via headless Edge/Chrome) - any combination of the three in one run.

## Requirements

* Windows PowerShell 5.1+ or PowerShell 7+ (`pwsh`)
* [`cohesity-api.ps1`](https://github.com/bseltz-cohesity/scripts/tree/master/powershell/cohesity-api) in the same directory as `archivedObjects.ps1`
* Microsoft Edge or Google Chrome installed, only if using `-format pdf` (the script renders the PDF by launching the browser headless with `--print-to-pdf`; if neither is found it falls back to saving HTML instead)

## Components

* `archivedObjects.ps1` - the main script
* `cohesity-api.ps1` - the Cohesity REST API helper module

## Usage

Report on a specific cluster:

```powershell
./archivedObjects.ps1 -clusterName mycluster
```

Connect through Helios/MCM and report across every Helios-connected cluster (default when `-clusterName`/`-clusterList` are omitted):

```powershell
./archivedObjects.ps1 -vip helios.cohesity.com -useApiKey
```

Report on a list of clusters from a text file (one cluster name per line):

```powershell
./archivedObjects.ps1 -clusterList clusters.txt
```

### Output formats

Save as CSV (default):

```powershell
./archivedObjects.ps1 -clusterName mycluster -format csv
```

Save as a sortable, filterable HTML report (click a column header to sort; filter by job, status, vault, or a retention date range):

```powershell
./archivedObjects.ps1 -clusterName mycluster -format html
```

Save as PDF (filters/sort controls are omitted from the PDF render since they aren't interactive on paper):

```powershell
./archivedObjects.ps1 -clusterName mycluster -format pdf
```

Save multiple formats in one run:

```powershell
./archivedObjects.ps1 -clusterName mycluster -format pdf,html,csv
```

## Parameters

### Authentication

| Flag | Description |
|---|---|
| `-vip` | (optional) name or IP of Cohesity cluster (defaults to `helios.cohesity.com`) |
| `-username` | (optional) name of user to connect to Cohesity (defaults to `helios`) |
| `-domain` | (optional) your AD domain (defaults to `local`) |
| `-tenant` | (optional) organization to impersonate |
| `-useApiKey` | (optional) use an API key for authentication |
| `-password` | (optional) will use cached password/key or will be prompted |
| `-noPrompt` | (optional) do not prompt for a password |
| `-mcm` | (optional) connect through Helios/MCM |
| `-mfaCode` | (optional) TOTP MFA code |
| `-emailMfaCode` | (optional) send MFA code via email |

### Cluster and Output

| Flag | Description |
|---|---|
| `-clusterName` | (optional) one or more cluster names to report on; repeat the flag for multiple. Defaults to every Helios-connected cluster |
| `-clusterList` | (optional) text file of cluster names (one per line) |
| `-outputPath` | (optional) folder for the output file(s) (defaults to `./Results`) |
| `-format` | (optional) one or more of `csv`, `html`, `pdf`; repeat or comma-separate for multiple, e.g. `-format pdf,html` (default `csv`) |

## Output

One row per protected object per archive target it has a copy on, written to `<outputPath>/ArchivedObjects-<date>.<format>` for each requested format and printed to the console:

| Column | Description |
|---|---|
| `Cluster Name` | cluster the object was found on |
| `Job Name` | protection group name |
| `Job Type` | source environment (e.g. `VMware`, `Physical`, `Azure`) |
| `Protected Object` | object name (with its alias/hostname appended for non-VMware physical/agent-based sources) |
| `Latest Backup Date` / `Oldest Backup Date` | newest/oldest backup run found for the object |
| `Latest Archive Date` / `Oldest Archive Date` | newest/oldest archive copy on this target |
| `Archive Count` | number of archive copies found on this target |
| `Archive Target` | vault/external target name |
| `Status` | `Active` or `Expired`, derived from the copy's expiry time (or the API's own status field when present) |
| `ArchiveExpiry` | expiration date/time of the most recent archive copy on this target |

If PDF rendering fails (e.g. the browser closed unexpectedly mid-render), the HTML it was rendered from is kept as `ArchivedObjects-<date>.pdf-failed.html` instead of being silently lost.

## Notes

* **PDF rendering reliability**: headless Edge/Chrome print-to-pdf occasionally fails to produce the PDF file even though the browser process exits with code 0 (observed intermittently, not reproducible on demand) - a retry of the same command usually succeeds. The script always uses a fresh, throwaway browser profile directory per PDF render so an already-running Edge/Chrome instance won't hijack the headless flags.
* **Multiple formats, one HTML render per PDF**: when `-format pdf` and `-format html` are both requested in the same run, the PDF's internal HTML render is written to a private temp file (not the user-facing `.html` output), so it can't collide with or overwrite the interactive HTML report.
* **Object alias**: for VMware objects, the alias column is always suppressed (VMware's own object name is already the display name); for other environments, the object's `.vmx`-style alias is shown only when it differs from the object name (e.g. a physical/agent-based source registered under a different hostname).

## Download
    curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/PowerShell/Reports/Archives/Archived%20Objects/archivedObjects.ps1
