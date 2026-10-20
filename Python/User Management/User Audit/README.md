# Helios User Audit Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

This folder contains scripts that report on users: `Audit_User_Login.py` reports last login/logout and cluster access for Helios users, and `local_users.py` reports local cluster users and their roles. Both are built on the [pyhesity](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) REST API wrapper.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as the scripts

## Components

* `Audit_User_Login.py` - reports last login, last logout, role and accessible clusters for all Helios users (or a single user)
* `local_users.py` - reports all local cluster users and their current role
* `pyhesity.py` - the Cohesity REST API helper module

## Audit_User_Login.py

Queries all Helios users and the Helios audit log (login/logout events, up to 365 days back) and writes `user_audit-<date>.csv` with one row per user: username, domain, last login, last logout, role, total clusters, accessible clusters, and the list of accessible cluster names.

### All Users

```
python Audit_User_Login.py -i -y 7
```

### Single User

Use `-user` to limit the report to one user and print the list of clusters that user has access to. The name is matched case-insensitively against `username` or `username@domain`. The CSV then contains only that user's row.

```
python Audit_User_Login.py -mcm -user jsmith
python Audit_User_Login.py -mcm -user jsmith@mydomain.net
```

### Parameters

#### Authentication

| Flag | Description |
| --- | --- |
| -v, --vip | (optional) Helios endpoint (default is helios.cohesity.com) |
| -u, --username | (optional) username used to authenticate (default is helios) |
| -d, --domain | (optional) domain of the authenticating user (default is local) |
| -i, --useApiKey | (optional) use API key for authentication |
| -p, --password | (optional) password or API key |
| -np, --noprompt | (optional) do not prompt for password |
| -mcm, --mcm | (optional) connect through Helios |
| -m, --mfacode | (optional) MFA code for authentication |
| -e, --emailmfacode | (optional) send MFA code via email |

#### Report

| Flag | Description |
| --- | --- |
| -y, --days | (optional) days of audit log to search for logins/logouts (max 365; default is 365) |
| -user, --user | (optional) report on only this user and list their accessible clusters |

## local_users.py

Reports all local cluster users and their current role.

```
python local_users.py -i
```

It accepts the same authentication parameters listed above.

## Notes

* `-u/--username` is the account used to log in to Helios; `-user/--user` is the user being audited. They are unrelated.
* Users with access to all clusters (`clusterId` of -1) are listed with every cluster.
* Login/logout times only reflect Helios-sourced audit records within the search window; users with none show `NA`.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/User%20Management/User%20Audit/Audit_User_Login.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/User%20Management/User%20Audit/local_users.py
curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py
```
