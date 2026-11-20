# Helios User Audit Using Python

Warning: this code is provided on a best effort basis and is not in any way officially supported or sanctioned by Cohesity. The code is intentionally kept simple to retain value as example code. The code in this repository is provided as-is and the author accepts no liability for damages resulting from its use.

This folder contains scripts that report on users: `Audit_User_Login.py` reports last login/logout and cluster access for Helios users, `get_users_cluster_access.py` reports which clusters a Helios user can access (or which users and roles have access to a cluster), and `local_users.py` reports local cluster users and their roles. All are built on the [pyhesity](https://github.com/bseltz-cohesity/scripts/tree/master/python/pyhesity) REST API wrapper.

## Requirements

* Python 3
* [`requests`](https://pypi.org/project/requests/) (`pip install requests`)
* `pyhesity.py` in the same directory as the scripts

## Components

* `Audit_User_Login.py` - reports last login, last logout, role and accessible clusters for all Helios users (or a single user)
* `get_users_cluster_access.py` - prints the clusters a given user has access to, or the users and roles with access to given clusters (also written to CSV)
* `local_users.py` - reports all local cluster users and their current role
* `pyhesity.py` - the Cohesity REST API helper module

## Audit_User_Login.py

Queries all Helios users and the Helios audit log (login/logout events, up to 365 days back) and writes `user_audit-<date>.csv` (and optionally an HTML report) with one row per user: username, domain, last login, last logout, role, total clusters, accessible clusters, and the list of accessible cluster names.

### All Users

```
python Audit_User_Login.py -i -y 7
```

### Specific Users

Use `-user` and/or `-userlist` to limit the report to specific users and print the list of clusters each user has access to. The name is matched case-insensitively against `username` or `username@domain`. The CSV then contains only those users' rows. A name that matches no user is reported and skipped; the script exits with an error only if none match.

```
python Audit_User_Login.py -mcm -user jsmith
python Audit_User_Login.py -mcm -user jsmith@mydomain.net
python Audit_User_Login.py -mcm -user jsmith,jdoe
python Audit_User_Login.py -mcm -user jsmith -user jdoe
python Audit_User_Login.py -mcm -userlist users.txt
```

`-user` may be comma separated or repeated, and can be combined with `-userlist`, a text file with one user per line (blank lines and lines starting with `#` are ignored).

When specific users are requested, the accessible clusters are printed on screen sorted alphabetically.

### Clusters Only

Use `-clustersonly` together with `-user` and/or `-userlist` to print only the accessible clusters for the specified users. The audit log is not queried and no CSV or HTML file is written; output goes to the screen only.

```
python Audit_User_Login.py -mcm -user jsmith -clustersonly
python Audit_User_Login.py -mcm -userlist users.txt -clustersonly
```

Example output:

```
User jsmith (mydomain.net) has access to 40/100 clusters

  cluster-a
  cluster-b
```

`-clustersonly` requires `-user` or `-userlist`, and `-html` is ignored when it is used.

### HTML Report

Use `-html` (without `-user`) to also write `user_audit-<date>.html`, a self-contained page covering all users. It has a dropdown of every user; selecting one shows their role, last login/logout and the clusters they can access. The page needs no web server or internet access. If `-user` or `-userlist` is also specified, `-html` is ignored.

```
python Audit_User_Login.py -mcm -html
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
| -user, --user | (optional) report on only this user and list their accessible clusters (sorted); comma separated or repeated for multiple users |
| -userlist, --userlist | (optional) text file of users to report on, one per line |
| -html, --html | (optional) also write an HTML report with a user dropdown showing accessible clusters (all users only; ignored when -user or -userlist is used) |
| -clustersonly, --clustersonly | (optional) print only the accessible clusters for the users given with -user or -userlist; skips the audit log and writes no files |

## get_users_cluster_access.py

Reports on Helios cluster access in either direction: which clusters a user can access, or which users (and roles) have access to a cluster. At least one of `-user`, `-cluster` or `-clusterlist` is required; if both a user and clusters are given, both reports are produced.

### Clusters a User Can Access

```
python get_users_cluster_access.py -mcm -user jsmith@mydomain.net
```

Example output:

```
User jsmith (mydomain.net) has access to 40/100 clusters

  cluster-a
  cluster-b
```

The name is matched case-insensitively against `username` or `username@domain`. If the same username exists in more than one domain, a section is printed for each match. This report is screen output only.

### Users With Access to a Cluster

```
python get_users_cluster_access.py -mcm -cluster coh-p-atl-az1-cl4
python get_users_cluster_access.py -mcm -cluster cluster1,cluster2
python get_users_cluster_access.py -mcm -clusterlist clusters.txt
python get_users_cluster_access.py -mcm -c all
```

Example output:

```
Cluster coh-p-atl-az1-cl4 has 12/85 users with access

  jsmith (mydomain.net)  Admin
  jdoe (mydomain.net)    Operations, View
```

Cluster names are matched case-insensitively; a name that matches no cluster is reported and skipped.

### All Connected Clusters

Use `-c all` to report on every cluster in `cluster-mgmt/info` that is currently connected to Helios (`isConnectedToHelios` is true). Disconnected clusters are skipped, and the number skipped is printed. `all` can be combined with explicitly named clusters (duplicates are removed), and all clusters are written to a single CSV.

```
python get_users_cluster_access.py -mcm -c all
```

### CSV Output

The results are also written to `cluster_users-<date>.csv` (or `cluster_users-<clustername>-<date>.csv` when only one cluster is given) with one line per cluster and user:

| Column | Description |
| --- | --- |
| Cluster | cluster name |
| User | username |
| Domain | user's domain |
| Role | user's role(s); multiple roles are joined with `; ` |

### Parameters

It accepts the same authentication parameters listed above, plus:

| Flag | Description |
| --- | --- |
| -user, --user | (optional) username or username@domain of the user whose accessible clusters to report |
| -c, -cluster, --cluster | (optional) cluster name to report users for; comma separated or repeated for multiple clusters. Use `all` for every cluster connected to Helios |
| -clusterlist, --clusterlist | (optional) text file of cluster names, one per line (blank lines and lines starting with `#` are ignored) |

## local_users.py

Reports all local cluster users and their current role.

```
python local_users.py -i
```

It accepts the same authentication parameters listed above.

## Notes

* `-u/--username` is the account used to log in to Helios; `-user/--user` is the user being audited. They are unrelated.
* Users with access to all clusters (`clusterId` of -1) are listed with every cluster. A user with no cluster entries is reported as having 0 accessible clusters.
* The total cluster count is every cluster registered to Helios, whether or not it is currently connected. `-c all` is limited to connected clusters, while `-user` reports still count all registered clusters.
* Login/logout times only reflect Helios-sourced audit records within the search window; users with none show `NA`.

## Download

```
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/User%20Management/User%20Audit/Audit_User_Login.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/User%20Management/User%20Audit/get_users_cluster_access.py
curl -O https://raw.githubusercontent.com/josh-moore-cohesity/scripts/refs/heads/main/Python/User%20Management/User%20Audit/local_users.py
curl -O https://raw.githubusercontent.com/cohesity/community-automation-samples/main/python/pyhesity.py
```
