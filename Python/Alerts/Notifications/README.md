# Update Alert Notification Rules

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`update-alert-notification-rules.py` adds and/or removes email delivery targets, renames a rule, and/or expands a rule to cover every alert type, on one or more alert notification rules, across one or more clusters (or all clusters reachable through Helios/MCM). Rules can be updated by name (`-rulename`, repeatable) or, if omitted, every rule on the cluster is updated.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `update-alert-notification-rules.py`

## Components

* `update-alert-notification-rules.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## How It Works

1. Authenticates once (directly to a cluster, or to Helios/MCM with `-mcm`).
2. For each cluster in the list, switches context with `heliosCluster()` and fetches the rule list via `GET /irisservices/api/v1/public/alertNotificationRules`.
3. When connected through Helios, also sets a `clusterid` header (the numeric cluster ID) and `x-cohesity-service-context: Mcm` - matching what the Helios UI itself sends - so the write in step 4 is routed to the right cluster. (These headers are separate from `heliosCluster()`'s own `accessClusterId` header, which is enough to scope the GET but not the PUT.)
4. For each rule (optionally filtered to the names given by `-rulename`), renames the rule if `-updatename` is given, and adds any `-add` email addresses not already present and/or removes any `-remove` email addresses found.
5. Any rule that changed is saved individually via `PUT /irisservices/api/v1/public/alertNotificationRules` with a single rule object as the body (including its `ruleId`) - the endpoint does not accept a bulk array of all rules, which is what caused the original `InvalidInput` error.

## Examples

Add an email address to every alert notification rule on a cluster:

```
python update-alert-notification-rules.py -c cluster1 -add user1@company.com
```

Add an email address to one specific rule:

```
python update-alert-notification-rules.py -c cluster1 -rulename "Critical Alerts" -add user1@company.com
```

Add an email address to several specific rules:

```
python update-alert-notification-rules.py -c cluster1 -rulename "Critical Alerts" -rulename "Warning Alerts" -add user1@company.com
```

Remove an email address from every rule:

```
python update-alert-notification-rules.py -c cluster1 -remove user1@company.com
```

Add and remove email addresses in the same run:

```
python update-alert-notification-rules.py -c cluster1 -add user2@company.com -remove user1@company.com
```

Run against multiple clusters via Helios/MCM, reading cluster names from a file:

```
python update-alert-notification-rules.py -mcm -cl clusters.txt -add user1@company.com
```

Rename a rule (e.g. to remove a space that the UI rejects on save):

```
python update-alert-notification-rules.py -c cluster1 -rulename "Critical Alerts" -updatename "CriticalAlerts"
```

Expand a rule to cover every alert type (not just its current severities/categories filter):

```
python update-alert-notification-rules.py -c cluster1 -rulename "Critical Alerts" -updatetypes
```

## Authentication Parameters

| Flag | Description |
|---|---|
| `-v, --vip` | (optional) cluster or Helios/MCM address (defaults to `helios.cohesity.com`) |
| `-u, --username` | (optional) name of user to connect with (defaults to `helios`) |
| `-d, --domain` | (optional) your AD domain (defaults to `local`) |
| `-i, --useApiKey` | (optional) use an API key for authentication |
| `-pwd, --password` | (optional) will use cached password/key or will be prompted |
| `-np, --noprompt` | (optional) do not prompt for password |
| `-mcm, --mcm` | (optional) connect through Helios/MCM |
| `-m, --mfacode` | (optional) TOTP MFA code |
| `-e, --emailmfacode` | (optional) send MFA code via email |

## Cluster Selection Parameters

| Flag | Description |
|---|---|
| `-c, --clustername` | (required, or use `-cl`) space separated list of cluster names |
| `-cl, --clusters` | (required, or use `-c`) text file of cluster names, one per line |

## Rule Update Parameters

| Flag | Description |
|---|---|
| `-add` | (optional, repeatable) email address to add as a delivery target |
| `-remove` | (optional, repeatable) email address to remove as a delivery target |
| `-rulename` | (optional, repeatable) name of a specific alert notification rule to update; if omitted, all rules are updated |
| `-updatename` | (optional) new name to give the rule; requires exactly one `-rulename` to be specified |
| `-updatetypes` | (optional) set the rule's `alertTypeList`/`alertNames` to the full catalog of alert types, so it fires on every alert type rather than whatever subset it's currently scoped to |
| `-debug` | (optional) log full request/response payloads to `cohesity-har-file.txt` for troubleshooting API errors |

## Notes

* If a rule fails to save, the script prints the API error and that rule's payload to aid troubleshooting.
* `-c` and `-cl` can be combined; the two lists are merged.
* Each changed rule is saved with its own `PUT` call (single rule object as the body), not a single bulk `PUT` with the full rule array.
* `-updatetypes` uses a hardcoded snapshot of alert type ids/names captured from a live cluster - it will not include alert types added in a later cluster version.
