# Export Quorum-Governed API Operations Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`quorum_apis.py` exports the complete list of API operations that can be governed by a Cohesity Helios quorum group - the same list shown under **Quorum Group > Operations** in the Helios UI. For each operation it records the template, category, function name, criticality, API version, HTTP method and API path, so the list can be reviewed, filtered or compared outside the UI.

The script reads the operation catalog from the Helios endpoint `GET /v2/mcm/quorum/operations/templates`, using the [pyhesity](https://raw.githubusercontent.com/bseltz-cohesity/scripts/refs/heads/master/python/pyhesity.py) REST API wrapper. The response groups operations by template (for example Access Management) and then by operation category. The script flattens that hierarchy into one row per operation, removes duplicates, and writes the result to a CSV or JSON file. A count of operations per template is shown onscreen.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `quorum_apis.py`
* A Helios user or API key with permission to view quorum groups (`QUORUM_GROUP_VIEW`)

## Components

* `quorum_apis.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## Usage

### Export to CSV (default)

```
python quorum_apis.py -i
```

### Export to JSON

```
python quorum_apis.py -i -output json
```

### Scheduled Export to a Specific Folder

Run unattended and write the file to a chosen folder:

```
python quorum_apis.py -i -np -outputpath /reports/quorum
```

## Output

A file is written to `-outputpath` on every run:

| Format | File name |
| --- | --- |
| CSV | `quorum-operations-<yyyy-mm-dd>.csv` |
| JSON | `quorum-operations-<yyyy-mm-dd>.json` |

The CSV starts with these columns: `templateName`, `category`, `functionId`, `criticality`, `version`, `httpAction`, `apiPath`, `summary`, `id`. Any other fields returned by the API (for example `description`, `isHeliosApi`, `isOnpremApi`, `isDpaasApi`, `updatedQuorumCategory`) follow. The JSON file contains the same flattened list of operations.

The script also prints a summary of operations per template:

```
Operations by template:
  Access Management            79
  Cluster Management           52
  Data Protection              18
  Networking Management        23
  Organization Management      24
  Storage Management           20
  Total                        216

Output written to ./Results/quorum-operations-2026-10-26.csv
```

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

### Output

| Flag | Description |
| --- | --- |
| -o, -output, --output | Output file format: `csv` or `json` (default `csv`) |
| -outputpath, --outputpath | Folder for the output file (default `./Results`) |

## Notes

* The operation catalog API is not publicly documented. The script looks for any item in the response that has a path-like field (such as `apiPath`) and treats it as an operation. If the response format changes and no operations are recognized, the script reports that and exits with code 1.
* The same operation can appear under more than one template or category. Exact duplicates are removed, so each row is unique.
* Each operation has an `id` made of the function name and API version (for example `CreateGroup:v1`). The same function can appear once per API version.
* Criticality is as reported by Helios (`High` or `Medium` at the time of writing).

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/main/Python/Security/Quorum/Quorum%20APIs/quorum_apis.py
```
