# Update Alert Notification Rules

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

`update-alert-notification-rules.py` adds and/or removes email delivery targets, and/or renames a rule, on one or more alert notification rules, across one or more clusters (or all clusters reachable through Helios/MCM). Rules can be updated by name (`-rulename`, repeatable) or, if omitted, every rule on the cluster is updated.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as `update-alert-notification-rules.py`

## Components

* `update-alert-notification-rules.py` - the main script
* `pyhesity.py` - the Cohesity REST API helper module

## How It Works

1. Authenticates once (directly to a cluster, or to Helios/MCM with `-mcm`).
2. For each cluster in the list, switches context with `heliosCluster()` and fetches the rule list via the v1 `alertNotificationRules` endpoint.
3. For each rule (optionally filtered to the names given by `-rulename`), renames the rule if `-updatename` is given, and adds any `-add` email addresses not already present and/or removes any `-remove` email addresses found.
4. Any rule that changed is saved individually via `PUT /v2/alerts/config/notification-rules/{ruleId}` ([API reference](https://developers.cohesity.com/v1-cluster-7.4/reference/updatealertnotificationrule)) - the bulk v1 PUT does not accept a full rule array and returns `InvalidInput`, so each modified rule is sent one at a time to its own v2 endpoint.

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
| `-debug` | (optional) log full request/response payloads to `cohesity-har-file.txt` for troubleshooting API errors |

## Notes

* If a rule fails to save, the script prints the API error and that rule's payload to aid troubleshooting.
* `-c` and `-cl` can be combined; the two lists are merged.
* Updates are saved per-rule via `PUT /v2/alerts/config/notification-rules/{ruleId}`, not the bulk v1 `alertNotificationRules` PUT.
